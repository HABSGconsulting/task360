#!/usr/bin/env python3
"""
01_build_base_db.py
-------------------
Step 1 of the Task360 pipeline.

Reads  : data/FUST_cleaned.csv
Writes : data/base_db.csv

What it does
------------
1. Load raw CSV
2. Normalise / clean every field
3. Parse Funding Amount → numeric USD (funding_amount_usd)
4. Parse Employee Size → numeric midpoint (employee_size_num)
5. Map Industry Bucket → canonical Category (from industry_taxonomy.json)
6. Derive source_tier (Manual-Main | Kaggle | LeadMagic | Other)
7. Add pipeline bookkeeping columns
8. Deduplicate on company name (keep first occurrence)
9. Save to data/base_db.csv
"""

import re
import json
import pathlib
import pandas as pd
import numpy as np

# ── paths ──────────────────────────────────────────────────────────────────
BASE_DIR   = pathlib.Path(__file__).parent.parent.resolve()
DATA_DIR   = BASE_DIR / "data"
CSV_IN     = DATA_DIR / "FUST_cleaned.csv"
JSON_TAX   = BASE_DIR / "industry_taxonomy.json"
CSV_OUT    = DATA_DIR / "base_db.csv"

DATA_DIR.mkdir(parents=True, exist_ok=True)


# ── 1. load ────────────────────────────────────────────────────────────────
df = pd.read_csv(CSV_IN, dtype=str).fillna("")

# normalise column names
df.columns = (
    df.columns
    .str.strip()
    .str.lower()
    .str.replace(r"[\s/]+", "_", regex=True)
    .str.replace(r"[^a-z0-9_]", "", regex=True)
)

# rename to stable internal names
RENAME = {
    "startup_name":    "company_name",
    "sector":          "sector_raw",
    "city":            "city",
    "website":         "website",
    "founder_name":    "founder_name",
    "email":           "email",
    "funding_year":    "funding_year_raw",
    "funding_amount":  "funding_amount_raw",
    "funding_stage":   "funding_stage_raw",
    "investor":        "investor_raw",
    "employee_size":   "employee_size_raw",
    "revenue_stage":   "revenue_stage_raw",
    "contact_status":  "contact_status",
    "source":          "source_raw",
    "industry_bucket": "industry_bucket_raw",
    "company_linkedin":"company_linkedin",
    "founder_linkedin":"founder_linkedin",
}
df.rename(columns=RENAME, inplace=True)

# ensure all expected cols exist
for col in RENAME.values():
    if col not in df.columns:
        df[col] = ""


# ── 2. basic string cleaning ───────────────────────────────────────────────
STR_COLS = ["company_name", "city", "website", "founder_name", "email",
            "funding_stage_raw", "investor_raw", "contact_status",
            "source_raw", "industry_bucket_raw",
            "company_linkedin", "founder_linkedin"]

for c in STR_COLS:
    df[c] = df[c].str.strip()

# strip BOM / invisible chars from company_name
df["company_name"] = df["company_name"].str.replace(r"^[\ufeff\u200b]+", "", regex=True)


# ── 3. funding_amount_usd ─────────────────────────────────────────────────
INR_TO_USD = 85.0      # approximate fixed rate


def _extract_usd_first(s: str):
    """
    If the string contains an explicit USD amount (preceded by $ or followed
    by 'million'/'mn'/'billion'), extract and return it as USD float.
    Returns None if no clear USD figure is found.

    Handles patterns like:
        "$5 million (Rs 43 Cr)"  → 5_000_000
        "Rs 65 crore ($7.7 million)" → 7_700_000
        "$30 Mn"                 → 30_000_000
        "$7.8 million"           → 7_800_000
        "$1.2 Mn"                → 1_200_000
        "$200K"                  → 200_000
    """
    # Pattern: $ followed by number and optional M/K/B/million/mn/billion/bn
    m = re.search(
        r"\$([\d,.]+)\s*(?:(billion|bn|million|mn|mn\b|m\b|k\b|b\b))",
        s, re.I
    )
    if m:
        num = float(m.group(1).replace(",", ""))
        unit = m.group(2).lower()
        mult = (
            1e9 if unit in ("billion", "bn")
            else 1e6 if unit in ("million", "mn", "m")
            else 1e3 if unit == "k"
            else 1
        )
        return round(num * mult, 2)

    # Pattern: number followed by 'million' or 'mn' preceded by $
    # already covered above; also handle plain $NNN,NNN
    m2 = re.search(r"\$([\d,]+(?:\.\d+)?)\s*([MKBmkb])?", s)
    if m2:
        num = float(m2.group(1).replace(",", ""))
        unit = (m2.group(2) or "").upper()
        mult = {"M": 1e6, "K": 1e3, "B": 1e9}.get(unit, 1)
        return round(num * mult, 2)

    return None


def parse_amount(raw: str):
    """Return numeric USD float, or None if unparseable."""
    s = str(raw).strip()
    if not s or s.lower() in ("undisclosed", "nan", "", "–", "-"):
        return None

    has_usd = bool(re.search(r"\$", s))
    has_inr = bool(re.search(r"(?i)(rs\.?|inr|crore|lakh|₹)", s))

    # ── KEY FIX: when string has BOTH currencies, prefer the USD figure ──
    if has_usd and has_inr:
        usd_val = _extract_usd_first(s)
        if usd_val is not None:
            return usd_val
        # fall through to INR path if USD extraction failed

    is_inr = has_inr and not has_usd

    # strip currency symbols / words for generic parsing
    s2 = re.sub(r"(?i)(rs\.?\s*|inr\s*|\$|₹|usd\s*)", "", s)
    s2 = re.sub(r"(?i)approx.*$", "", s2).strip().rstrip(".")
    # strip parenthetical clarifications like "(~$12 million)"
    s2 = re.sub(r"\([^)]*\)", "", s2).strip()

    # range like "$2-5M" or "2-5M" → midpoint
    rng = re.match(r"([\d.]+)\s*[-–]\s*([\d.]+)\s*([MKBmkb]?)", s2)
    if rng:
        lo, hi = float(rng.group(1)), float(rng.group(2))
        mult = {"M": 1e6, "K": 1e3, "B": 1e9}.get(rng.group(3).upper(), 1)
        val = ((lo + hi) / 2) * mult
        return round(val / INR_TO_USD if is_inr else val, 2)

    # "< $1M" or "> $5M"
    lt = re.match(r"[<>]\s*([\d.]+)\s*([MKBmkb]?)", s2)
    if lt:
        mult = {"M": 1e6, "K": 1e3, "B": 1e9}.get(lt.group(2).upper(), 1)
        val = float(lt.group(1)) * mult
        return round(val / INR_TO_USD if is_inr else val, 2)

    # crore / lakh  (only reached when pure INR, no $ present)
    crore = re.search(r"([\d,.]+)\s*(?:crore)", s2, re.I)
    if crore:
        return round((float(crore.group(1).replace(",", "")) * 1e7) / INR_TO_USD, 2)

    lakh = re.search(r"([\d,.]+)\s*(?:lakh)", s2, re.I)
    if lakh:
        return round((float(lakh.group(1).replace(",", "")) * 1e5) / INR_TO_USD, 2)

    # plain number with optional M/K/B  (million/mn handled inline)
    s2_clean = s2.replace(",", "")
    plain = re.match(r"([\d\.]+)\s*(million|mn|billion|bn|[MKBmkb])?", s2_clean, re.I)
    if plain:
        try:
            num = float(plain.group(1))
        except ValueError:
            return None
        unit = (plain.group(2) or "").lower()
        mult = (
            1e9 if unit in ("billion", "bn")
            else 1e6 if unit in ("million", "mn", "m")
            else 1e3 if unit == "k"
            else 1
        )
        val = num * mult
        return round(val / INR_TO_USD if is_inr else val, 2)

    return None

df["funding_amount_usd"] = df["funding_amount_raw"].apply(parse_amount)


# ── 4. employee_size_num ──────────────────────────────────────────────────
def parse_employees(raw: str):
    s = str(raw).strip()
    if not s or s == "nan":
        return None
    nums = re.findall(r"\d+", s)
    if len(nums) >= 2:
        return (float(nums[0]) + float(nums[1])) / 2
    if len(nums) == 1:
        return float(nums[0])
    return None

df["employee_size_num"] = df["employee_size_raw"].apply(parse_employees)


# ── 5. canonical Category from Industry Bucket ───────────────────────────
BUCKET_MAP = {
    "AI/ML":                  "AI / Data / DeepTech",
    "AgriTech":               "AgriTech / FoodTech",
    "CleanTech":              "CleanTech / Climate / Energy",
    "D2C/E-commerce":         "D2C / E-commerce",
    "FinTech":                "FinTech",
    "HealthTech":             "HealthTech / MedTech",
    "Manufacturing/DeepTech": "Manufacturing / Hardware / Industrial",
    "SaaS":                   "SaaS / Software",
    "Others":                 "Services / Consulting / Others",
}

def map_category(bucket: str) -> str:
    return BUCKET_MAP.get(bucket.strip(), "Services / Consulting / Others")

df["category"] = df["industry_bucket_raw"].apply(map_category)


# ── 6. funding_year ────────────────────────────────────────────────────────
def clean_year(raw: str):
    m = re.search(r"(202\d)", str(raw))
    return int(m.group(1)) if m else None

df["funding_year"] = df["funding_year_raw"].apply(clean_year)


# ── 7. funding_stage (normalised) ─────────────────────────────────────────
STAGE_MAP = {
    "pre-seed":     "Pre-Seed",
    "seed":         "Seed",
    "bridge":       "Bridge",
    "pre-series a": "Pre-Series A",
    "series a":     "Series A",
    "series b":     "Series B",
    "series c":     "Series C",
    "series d":     "Series D",
    "series e":     "Series E",
    "series f":     "Series F",
    "growth":       "Growth",
    "debt":         "Debt",
    "pe":           "Private Equity",
    "private equity": "Private Equity",
    "pre-ipo":      "Pre-IPO",
    "angel":        "Angel",
    "grant":        "Grant",
    "pre-series b": "Pre-Series B",
    "pre-series c": "Pre-Series C",
}

def norm_stage(raw: str) -> str:
    return STAGE_MAP.get(str(raw).strip().lower(), str(raw).strip())

df["funding_stage"] = df["funding_stage_raw"].apply(norm_stage)


# ── 8. source_tier ─────────────────────────────────────────────────────────
def source_tier(raw: str) -> str:
    s = str(raw).lower()
    if "manual" in s:
        return "Manual-Main"
    if "leadmagic" in s:
        return "LeadMagic"
    if "kaggle" in s:
        return "Kaggle"
    return "Other"

df["source_tier"] = df["source_raw"].apply(source_tier)


# ── 9. pipeline bookkeeping ───────────────────────────────────────────────
df["enrichment_status"]      = "Pending"
df["ai_classification_done"] = False
df["outreach_drafted"]       = False
df["outreach_sent"]          = False


# ── 10. dedup on company_name ─────────────────────────────────────────────
before = len(df)
df["_name_lower"] = df["company_name"].str.lower().str.strip()
df = df.drop_duplicates(subset=["_name_lower"], keep="first")
df.drop(columns=["_name_lower"], inplace=True)
after = len(df)


# ── 11. column order for output ───────────────────────────────────────────
OUTPUT_COLS = [
    # identity
    "company_name", "city", "category", "sector_raw",
    # founders / contact
    "founder_name", "email", "company_linkedin", "founder_linkedin",
    # funding
    "funding_year", "funding_stage", "funding_amount_raw", "funding_amount_usd",
    # investors
    "investor_raw",
    # size
    "employee_size_raw", "employee_size_num", "revenue_stage_raw",
    # web
    "website",
    # provenance
    "source_raw", "source_tier", "industry_bucket_raw",
    # pipeline
    "contact_status", "enrichment_status",
    "ai_classification_done", "outreach_drafted", "outreach_sent",
]

output_cols = [c for c in OUTPUT_COLS if c in df.columns]
df_out = df[output_cols].copy()


# ── 12. save ───────────────────────────────────────────────────────────────
df_out.to_csv(CSV_OUT, index=False)

print(f"Rows in              : {before}")
print(f"Duplicates removed   : {before - after}")
print(f"Rows out             : {after}")
print(f"Columns              : {len(df_out.columns)}")
print(f"Saved to             : {CSV_OUT}")
print()
print("Category breakdown:")
print(df_out["category"].value_counts().to_string())
print()
print("Source tier breakdown:")
print(df_out["source_tier"].value_counts().to_string())
print()
print("Funding stage breakdown (top 15):")
print(df_out["funding_stage"].value_counts().head(15).to_string())
print()
print(f"funding_amount_usd parsed: {df_out['funding_amount_usd'].notna().sum()} / {len(df_out)}")

# ── 13. spot-check mixed-currency rows ────────────────────────────────────
print()
print("Mixed-currency spot-check (rows with both $ and Rs/INR in raw amount):")
mixed = df_out[
    df_out["funding_amount_raw"].str.contains(r"\$", na=False) &
    df_out["funding_amount_raw"].str.contains(r"(?i)(rs\.?|inr|crore|lakh)", na=False)
][["company_name", "funding_amount_raw", "funding_amount_usd"]]
print(mixed.to_string(index=False))
