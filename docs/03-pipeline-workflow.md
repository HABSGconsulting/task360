# 03 — Pipeline Workflow

---

## Overview

The pipeline runs in four sequential script steps, preceded by two static reference files that are written once by hand. Each step produces output files that the next step consumes. No step modifies the output of a previous step.

---

## Step 0 — Reference Files (Human-Written, One-Time)

These are not scripts. They are JSON configuration files that encode domain knowledge. Write them once; all scripts reference them.

### `bucket_to_taxonomy_map.json`
Maps the 8 raw `Industry Bucket` labels in `FUST_cleaned.csv` to the 9 canonical categories in `industry_taxonomy.json`.

Example:
```json
{
  "AI/ML": "AI / Data / DeepTech",
  "D2C/E-commerce": "D2C / E-commerce / Consumer",
  "FinTech": "FinTech / InsurTech / LendingTech",
  "Others": "REVIEW_REQUIRED"
}
```

### `stage_to_services_map.json`
Maps funding stage × taxonomy category → ranked list of Task360 service clusters. This is the core business logic of the database — it defines which services are most relevant at each stage.

Example entry:
```json
{
  "Pre-Seed": {
    "default": ["Incorporation Services", "GST Registration", "Startup India Recognition"],
    "FinTech / InsurTech / LendingTech": ["Incorporation Services", "RBI/SEBI Compliance", "Co-founders Agreement"]
  },
  "Series A": {
    "default": ["Virtual CFO", "Secretarial Compliances", "ESOP Design", "FDI Compliances under FEMA"],
    "D2C / E-commerce / Consumer": ["GST Services", "Virtual CFO", "Trademark", "FSSAI"]
  }
}
```

---

## Step 1 — Build Base Database
**Script:** `scripts/01_build_base_db.py`  
**Input:** `../internship/data/FUST_cleaned.csv` (or local copy)  
**Output:** `data/task360_base.csv`, `data/task360_base.json`  
**API calls:** None  
**Runtime:** Seconds

What it does:
- Drops 5 fields: `Email`, `Founder LinkedIn`, `Contact Status`, `Source`, `Revenue Stage`
- Keeps and renames 12 fields (see schema in `docs/04-data-schema.md`)
- Assigns `startup_id`: `T360-001` through `T360-546` (zero-padded, stable)
- Maps `Industry Bucket` → `taxonomy_category` using `bucket_to_taxonomy_map.json`
- Attempts `Sector` → `taxonomy_subsector` mapping; flags unknowns as `UNMAPPED`
- Normalises `Funding Amount` → `funding_amount_usd` (integer, best-effort parse)
- Initialises all intelligence fields as `null` / `false`
- Writes both CSV and JSON outputs

---

## Step 2 — Validate Base Database
**Script:** `scripts/02_validate_base.py`  
**Input:** `data/task360_base.json`  
**Output:** `data/validation_report.txt`  
**API calls:** None  
**Runtime:** Seconds

What it does:
- Counts and lists rows with blank `funding_stage` (affects service mapping quality)
- Counts and lists rows with blank `website` (AI has less context)
- Lists all `UNMAPPED` taxonomy subsectors
- Counts rows with `funding_amount_usd = null` (normalisation failed)
- Prints a pass/fail summary

**Himanshi should review `validation_report.txt` before running Step 3.** Rows with blank funding stage will still be processed but will receive lower-quality service mappings.

---

## Step 3 — Generate Intelligence (Main AI Loop)
**Script:** `scripts/03_generate_intelligence.py`  
**Input:** `data/task360_base.json`  
**Output:** `data/task360_intelligence.json`, `data/skipped_rows.json`  
**API calls:** 1 per startup row  
**Runtime:** ~45 minutes per 500-row daily quota

What it does:
- Loads `task360_base.json` (all 546 records)
- Loads `task360_intelligence.json` (already-processed records) — creates empty `[]` if not present
- Builds `done_ids` set from already-processed records
- Loops through all records, skipping any in `done_ids` (resume logic)
- For each unprocessed record:
  - Builds a structured prompt from the record's fields
  - Calls Gemini 3.1 Flash-Lite
  - Parses JSON response
  - Merges intelligence + outreach blocks into record
  - Sets `meta.intelligence_generated = true`, timestamps the record
  - Appends to `task360_intelligence.json` and **saves after every single record**
  - Sleeps 5 seconds
- On `429`: logs and exits cleanly with summary
- On `503` / unavailable: waits 60 seconds, retries up to 3 times
- On JSON parse failure: logs raw response to `skipped_rows.json`, continues
- Prints run summary on exit

**Resume behaviour:** Start the script again at any time. It reads existing output and skips already-processed rows. Swap API keys in `.env` when daily quota exhausts.

---

## Step 4 — Export Final Outputs
**Script:** `scripts/04_export_final.py`  
**Input:** `data/task360_base.json`, `data/task360_intelligence.json`  
**Output:** `data/task360_master.json`, `data/task360_master.csv`, `data/task360_priority.csv`, `data/by_category/*.csv`  
**API calls:** None  
**When to run:** Once all 546 rows in `task360_intelligence.json` have `intelligence_generated = true`

What it does:
- Merges base and intelligence records on `startup_id`
- Exports full master JSON and flat CSV
- Exports `task360_priority.csv` sorted by `partnership_score` descending
- Exports one CSV per taxonomy category into `data/by_category/`

---

## Daily Running Pattern

```
Day 1:   Run scripts 01 and 02. Review validation report.
         Run script 03 → up to 500 rows processed.
Day 2:   Run script 03 again → resumes from where it stopped.
Final:   Run script 04 → all exports ready.
```

With rotating API keys (no effective daily cap):
```
Single session: Run script 03 → all 546 rows done in ~45 minutes.
Then:           Run script 04 → done.
```
