# 06 — API and Rate Limits

---

## SDK

| Parameter | Value |
|---|---|
| Package | `google-genai` |
| Install | `pip install google-genai` |
| Import | `from google import genai` |
| Old package (deprecated) | `google-generativeai` — support ended 30 Nov 2025. Do not use. |

---

## Model

| Parameter | Value |
|---|---|
| Model name | `gemini-3.1-flash-lite` |
| Status | GA — stable as of May 7, 2026 |
| Retirement | Not before May 7, 2027 |
| Predecessor (retired) | `gemini-2.0-flash-lite` — retired June 1, 2026. Do not use. |

---

## Rate Limits (Free Tier)

| Limit | Value |
|---|---|
| Requests per minute | 15 |
| Requests per day | 500 |
| Safe delay between calls | 5 seconds (= 12 req/min, safe headroom under 15/min cap) |

---

## Connection Pattern

```python
import os, sys, time, json
from google import genai
from dotenv import load_dotenv

load_dotenv()  # reads GEMINI_API_KEY from .env file
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

response = client.models.generate_content(
    model="gemini-3.1-flash-lite",
    contents=prompt
)
result_text = response.text
```

---

## Error Handling Reference

```python
MAX_RETRIES = 3

for attempt in range(MAX_RETRIES):
    try:
        response = client.models.generate_content(
            model="gemini-3.1-flash-lite",
            contents=prompt
        )
        # Strip markdown fences if Gemini wraps response in ```json ... ```
        text = response.text.strip().removeprefix("```json").removesuffix("```").strip()
        data = json.loads(text)
        break  # success — exit retry loop

    except Exception as e:
        err = str(e)

        if "429" in err or "RESOURCE_EXHAUSTED" in err:
            print("❌ Daily quota exhausted. Exiting cleanly.")
            print_run_summary()
            sys.exit(1)

        elif "503" in err or "unavailable" in err.lower():
            print(f"⏳ Model unavailable. Waiting 60s (attempt {attempt+1}/3)...")
            time.sleep(60)
            continue

        else:
            print(f"⚠️  Unknown error for {startup_id}: {err}. Skipping.")
            log_skipped(startup_id, err)
            break
else:
    print(f"❌ Max retries exceeded for {startup_id}. Skipping.")
    log_skipped(startup_id, "max_retries_exceeded")
```

---

## API Key Management

- Store the key in a `.env` file at repo root: `GEMINI_API_KEY=AIza...`
- `.env` is in `.gitignore` — never commit API keys to the repo
- When one key's 500/day quota exhausts, update `.env` with the next key and re-run — no code changes needed
- Multiple keys can be rotated this way across sessions

---

## Estimated Timeline

| Scenario | Daily rows | Days to complete 546 rows |
|---|---|---|
| Single key, 500/day quota | 500 | 2 days |
| Rotating keys (no effective daily cap) | 546 | 1 session (~45 min) |
| Conservative (safety testing) | 50 | 11 days |
