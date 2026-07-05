#!/usr/bin/env python3
"""
enrich_startups.py

Reads data/FUST_cleaned.csv, calls Gemini 3.1 Flash Lite for each startup,
writes enriched intelligence to data/task360_intelligence.json.

Resume logic  : skips rows whose startup_name already exists in output JSON.
Rate limiting : 5s sleep after every successful call (stays under 15 req/min).
503 errors    : wait 60s, retry up to 3 times.
429 errors    : log progress summary and sys.exit(1) — daily quota exhausted.
JSON failures : log raw response, write to data/skipped_rows.json, move on.
Other errors  : log, write to data/skipped_rows.json, move on.

Usage:
    python scripts/enrich_startups.py \
        --input  data/FUST_cleaned.csv \
        --output data/task360_intelligence.json \
        --batch  20
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from google import genai

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MODEL = "gemini-3.1-flash-lite"
NORMAL_DELAY = 5          # seconds between successful calls
RETRY_DELAY  = 60         # seconds to wait on 503
MAX_RETRIES  = 3          # max retries per row on 503
SKIPPED_PATH = Path("data/skipped_rows.json")


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------
PROMPT_TEMPLATE = """
You are an expert startup intelligence analyst. Given the following Indian startup profile,
return ONLY a valid JSON object — no markdown, no code fences, no extra text.

Startup profile:
  Name           : {startup_name}
  Sector         : {sector}
  City           : {city}
  Website        : {website}
  Founder(s)     : {founder_name}
  Funding Stage  : {funding_stage}
  Funding Amount : {funding_amount}
  Investor(s)    : {investor}
  Industry Bucket: {industry_bucket}

Return this exact JSON schema (all fields required, use null if unknown):
{{
  "startup_name": "<string>",
  "founder_thesis": "<1-2 sentence summary of what the founder is building and why>",
  "strategic_theme": "<one of: Financial Inclusion | SME Digitisation | Climate Mitigation | Healthcare Access | AI Infrastructure | AgriTech Innovation | Consumer Brands | Deep Tech | Other>",
  "macro_tags": ["<tag1>", "<tag2>"],
  "collab_potential": "<one of: High | Medium | Emerging>",
  "collab_reasoning": "<1 sentence explaining the collab_potential rating>",
  "relationship_hooks": ["<hook1>", "<hook2>"],
  "risk_signals": ["<signal1>", "<signal2>"],
  "task360_services": ["<most relevant Task360 service 1>", "<most relevant Task360 service 2>"],
  "enriched_at": "{enriched_at}"
}}

Macro tag options (pick 2-3 most relevant):
interest rates | credit availability | digital infrastructure | GST compliance |
global demand | regulation-sensitive | FDI policy | climate policy |
consumer spending | supply chain | INR exchange rate | government schemes
"""


def build_prompt(row: dict) -> str:
    return PROMPT_TEMPLATE.format(
        startup_name   = row.get("Startup Name", ""),
        sector         = row.get("Sector", ""),
        city           = row.get("City", ""),
        website        = row.get("Website", ""),
        founder_name   = row.get("Founder Name", ""),
        funding_stage  = row.get("Funding Stage", ""),
        funding_amount = row.get("Funding Amount", ""),
        investor       = row.get("Investor", ""),
        industry_bucket= row.get("Industry Bucket", ""),
        enriched_at    = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def load_existing(output_path: Path) -> dict:
    """Returns dict keyed by startup_name from existing output JSON."""
    if output_path.exists():
        try:
            data = json.loads(output_path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return {item["startup_name"]: item for item in data if "startup_name" in item}
        except Exception as e:
            log.warning("Could not parse existing output: %s", e)
    return {}


def save_output(output_path: Path, records: dict) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(list(records.values()), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def log_skipped(startup_name: str, reason: str, raw: str = "") -> None:
    SKIPPED_PATH.parent.mkdir(parents=True, exist_ok=True)
    skipped = []
    if SKIPPED_PATH.exists():
        try:
            skipped = json.loads(SKIPPED_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    skipped.append({
        "startup_name": startup_name,
        "reason": reason,
        "raw_response": raw[:500] if raw else "",
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    })
    SKIPPED_PATH.write_text(json.dumps(skipped, indent=2, ensure_ascii=False), encoding="utf-8")


def print_summary(processed_this_run: int, total_done: int, total_rows: int) -> None:
    remaining = total_rows - total_done
    log.info("=" * 55)
    log.info("Processed this run : %d", processed_this_run)
    log.info("Total done         : %d / %d", total_done, total_rows)
    log.info("Remaining          : %d", remaining)
    log.info("=" * 55)


# ---------------------------------------------------------------------------
# Core enrichment call
# ---------------------------------------------------------------------------
def call_gemini(client: genai.Client, prompt: str, startup_name: str) -> dict | None:
    """
    Calls Gemini with retry logic.
    Returns parsed dict on success, None if row should be skipped.
    Calls sys.exit(1) on 429.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.models.generate_content(
                model=MODEL,
                contents=prompt,
            )
            raw = response.text.strip()

            # Strip markdown fences if Gemini wraps response anyway
            if raw.startswith("```"):
                lines = raw.splitlines()
                raw = "\n".join(
                    line for line in lines
                    if not line.startswith("```")
                ).strip()

            parsed = json.loads(raw)
            return parsed

        except Exception as e:
            err_str = str(e)

            # 429 — daily quota gone, hard stop
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                log.error("429 RESOURCE_EXHAUSTED — daily quota hit. Stopping cleanly.")
                return "QUOTA_HIT"

            # 503 — temporary unavailability, retry with backoff
            if "503" in err_str or "unavailable" in err_str.lower():
                if attempt < MAX_RETRIES:
                    log.warning(
                        "503 on '%s' (attempt %d/%d) — waiting %ds before retry.",
                        startup_name, attempt, MAX_RETRIES, RETRY_DELAY,
                    )
                    time.sleep(RETRY_DELAY)
                    continue
                else:
                    log.error("503 persisted after %d retries for '%s' — skipping.", MAX_RETRIES, startup_name)
                    log_skipped(startup_name, "503 after max retries", err_str)
                    return None

            # JSON parse failure
            raw_text = ""
            try:
                raw_text = response.text  # type: ignore
            except Exception:
                pass
            if isinstance(e, json.JSONDecodeError):
                log.error("JSON parse failure for '%s' — skipping. Raw: %.200s", startup_name, raw_text)
                log_skipped(startup_name, "JSON parse failure", raw_text)
                return None

            # Any other error
            log.error("Unexpected error for '%s': %s — skipping.", startup_name, err_str)
            log_skipped(startup_name, f"unexpected error: {err_str}", "")
            return None

    return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="Enrich FUST_cleaned.csv with Gemini 3.1 Flash Lite")
    parser.add_argument("--input",  default="data/FUST_cleaned.csv",           help="Path to input CSV")
    parser.add_argument("--output", default="data/task360_intelligence.json",  help="Path to output JSON")
    parser.add_argument("--batch",  type=int, default=20,                       help="Max rows to process this run")
    args = parser.parse_args()

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        log.error("GEMINI_API_KEY environment variable not set.")
        sys.exit(1)

    client = genai.Client(api_key=api_key)

    input_path  = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        log.error("Input file not found: %s", input_path)
        sys.exit(1)

    df = pd.read_csv(input_path, dtype=str).fillna("")
    total_rows = len(df)
    log.info("Loaded %d rows from %s", total_rows, input_path)

    existing = load_existing(output_path)
    log.info("Already enriched: %d rows — will skip these.", len(existing))

    processed_this_run = 0

    for _, row in df.iterrows():
        startup_name = row.get("Startup Name", "").strip()
        if not startup_name:
            continue

        # Resume logic — skip if already done
        if startup_name in existing:
            continue

        # Batch limit
        if processed_this_run >= args.batch:
            log.info("Batch limit of %d reached — stopping.", args.batch)
            break

        log.info("Enriching [%d/%d]: %s", processed_this_run + 1, args.batch, startup_name)
        prompt = build_prompt(row.to_dict())
        result = call_gemini(client, prompt, startup_name)

        # Hard stop on quota
        if result == "QUOTA_HIT":
            print_summary(processed_this_run, len(existing), total_rows)
            sys.exit(1)

        if result is not None:
            existing[startup_name] = result
            save_output(output_path, existing)  # save after every row — never lose progress
            processed_this_run += 1
            log.info("  Done. Sleeping %ds.", NORMAL_DELAY)
            time.sleep(NORMAL_DELAY)
        else:
            log.warning("  Skipped '%s' — see data/skipped_rows.json.", startup_name)

    print_summary(processed_this_run, len(existing), total_rows)


if __name__ == "__main__":
    main()
