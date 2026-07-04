# 05 — Pipeline Scripts

---

## Script Overview

| Script | Purpose | API Calls | When to Run |
|---|---|---|---|
| `01_build_base_db.py` | Build clean base JSON from FUST CSV | None | Once, or when source CSV updates |
| `02_validate_base.py` | QA check before AI generation | None | After Script 01, before Script 03 |
| `03_generate_intelligence.py` | Gemini AI loop — generates all intelligence fields | Yes (Gemini) | Daily until all 546 rows done |
| `04_export_final.py` | Merge + sort + export final outputs | None | Once, when all rows are generated |

---

## Script 01 — `01_build_base_db.py`

**Dependencies:** `pandas`, `json`, `bucket_to_taxonomy_map.json`, `stage_to_services_map.json`

**Logic:**
1. Read `FUST_cleaned.csv`
2. Drop: `Email`, `Founder LinkedIn`, `Contact Status`, `Source`, `Revenue Stage`
3. Rename columns to schema field names
4. Assign `startup_id` sequentially (`T360-001` … `T360-546`)
5. Map `Industry Bucket` → `taxonomy_category` via `bucket_to_taxonomy_map.json`
6. Attempt `Sector` → `taxonomy_subsector` via keyword rules; set `UNMAPPED` if not resolved
7. Parse `Funding Amount` → `funding_amount_usd` (handles `$Mn`, `Rs crore`, raw numbers)
8. Map `funding_stage` × `taxonomy_category` → `task360_services` via `stage_to_services_map.json`
9. Initialise all intelligence/outreach/meta fields as `null` / `false` / `[]`
10. Write `data/task360_base.json` (array of objects) and `data/task360_base.csv`

---

## Script 02 — `02_validate_base.py`

**Dependencies:** `json`

**Checks performed:**
- Rows where `funding_stage` is blank or null
- Rows where `website` is blank or null
- Rows where `taxonomy_subsector` = `UNMAPPED`
- Rows where `funding_amount_usd` is null
- Rows where `taxonomy_category` is blank

**Output format (`validation_report.txt`):**
```
TASK360 BASE DB — VALIDATION REPORT
Generated: 2026-07-05 10:00:00

Total records: 546

[WARN] Blank funding_stage: 74 rows
  - T360-012: Startup Name here
  - T360-019: ...

[WARN] Blank website: 88 rows
[WARN] UNMAPPED taxonomy_subsector: 41 rows
[INFO] Null funding_amount_usd: 23 rows

STATUS: PROCEED WITH CAUTION — review WARN items before running Script 03
```

---

## Script 03 — `03_generate_intelligence.py`

**Dependencies:** `google-genai` (`pip install google-genai`), `json`, `time`, `os`, `python-dotenv`

**Environment variables (`.env` file):**
```
GEMINI_API_KEY=AIza...
```

**SDK usage:**
```python
from google import genai
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
response = client.models.generate_content(
    model="gemini-3.1-flash-lite",
    contents=prompt
)
```

**Rate limit handling:**

| Situation | Behaviour |
|---|---|
| Successful call | `time.sleep(5)` — 12 req/min, safe under 15/min cap |
| `429 / RESOURCE_EXHAUSTED` | Print summary, `sys.exit(1)` — quota done for day |
| `503 / model unavailable` | `time.sleep(60)`, retry up to 3 times |
| JSON parse failure | Log raw response to `skipped_rows.json`, skip row, continue |
| Any other exception | Log to `skipped_rows.json`, skip row, continue |

**Resume logic:**
```python
done_ids = {r["startup_id"] for r in already_processed}
for record in all_records:
    if record["startup_id"] in done_ids:
        continue
    # process...
```

**File write discipline:** Save `task360_intelligence.json` after **every single record** — not in batches. A crash or 429 loses at most 1 row.

**Exit summary (always printed):**
```
✅ Processed this run:    47
⏭️  Already done (skipped): 103
❌ Errors/skipped:         2
📊 Total done so far:     150 / 546
⏳ Remaining:             396
```

---

## Script 04 — `04_export_final.py`

**Dependencies:** `json`, `pandas`

**When to run:** Only when `task360_intelligence.json` contains 546 records with `intelligence_generated = true`.

**What it produces:**

| Output file | Description |
|---|---|
| `data/task360_master.json` | All 546 records, full schema, merged |
| `data/task360_master.csv` | Flat CSV version of master JSON |
| `data/task360_priority.csv` | Master CSV sorted by `partnership_score` DESC |
| `data/by_category/fintech.csv` | Records where `taxonomy_category` = FinTech |
| `data/by_category/saas.csv` | SaaS records |
| `data/by_category/d2c.csv` | D2C / E-commerce records |
| `data/by_category/healthtech.csv` | HealthTech records |
| `data/by_category/agritech.csv` | AgriTech records |
| `data/by_category/cleantech.csv` | CleanTech records |
| `data/by_category/manufacturing.csv` | Manufacturing / DeepTech records |
| `data/by_category/aiml.csv` | AI / Data / DeepTech records |
| `data/by_category/others.csv` | Others / uncategorised records |
