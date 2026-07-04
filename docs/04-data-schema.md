# 04 — Data Schema

---

## Full Record Structure

Every record in `task360_base.json` and `task360_intelligence.json` follows this schema.

```json
{
  "startup_id": "T360-001",

  "core": {
    "startup_name": "Easebuzz",
    "founder_name": "Rohit Prasad",
    "city": "Pune",
    "website": "https://easebuzz.in/",
    "company_linkedin": "https://in.linkedin.com/company/easebuzz",
    "funding_stage": "Series A",
    "funding_year": 2025,
    "funding_amount_usd": 30000000,
    "investor": "Bessemer",
    "employee_size": "",
    "taxonomy_category": "FinTech / InsurTech / LendingTech",
    "taxonomy_subsector": "Financial Infrastructure",
    "raw_sector_original": "B2B Fintech"
  },

  "task360_services": {
    "primary": ["Virtual CFO", "Secretarial Compliances", "ESOP Design"],
    "growth": ["FDI Compliances under FEMA", "Valuation Advisory"]
  },

  "intelligence": {
    "strategic_theme": "B2B payments infrastructure enabling SME collections and disbursements",
    "macro_tags": ["digital payments regulation", "RBI policy", "GST compliance", "SME digitisation"],
    "risk_signals": ["regulation-sensitive", "RBI licensing dependent", "high-growth hiring pressure"],
    "partnership_score": 8,
    "partnership_score_rationale": "Series A FinTech with active compliance needs — FDI, GST, secretarial, and valuation are all immediately relevant to their stage.",
    "funding_amount_bracket": "₹10–25L",
    "potential_work_areas": [
      "FDI Compliances under FEMA",
      "GST Services and Reconciliation",
      "Secretarial Compliances + ESOP design"
    ],
    "collab_potential_tags": ["FinTech regulatory roundtable", "Fundraising readiness workshop", "Case study"]
  },

  "outreach": {
    "hook_line": "Easebuzz is navigating Series A growth with cross-border investor capital — exactly where FEMA, GST reconciliation, and ESOP structuring become high-stakes.",
    "one_page_proposal": "[150-word AI-generated proposal]",
    "engagement_strategy": "[300-word AI-generated engagement strategy]"
  },

  "meta": {
    "intelligence_generated": false,
    "model_used": null,
    "generated_on": null
  }
}
```

---

## Field Reference

### `core` block — sourced from FUST_cleaned.csv

| Field | Type | Source | Notes |
|---|---|---|---|
| `startup_id` | string | Generated | Format: `T360-001` to `T360-546`, stable across runs |
| `startup_name` | string | CSV: `Startup Name` | |
| `founder_name` | string | CSV: `Founder Name` | Public name only — no contact info |
| `city` | string | CSV: `City` | |
| `website` | string | CSV: `Website` | Used as context for AI generation |
| `company_linkedin` | string | CSV: `Company LinkedIn` | Company page only — not personal |
| `funding_stage` | string | CSV: `Funding Stage` | Normalised: Seed, Pre-Series A, Series A, etc. |
| `funding_year` | integer | CSV: `Funding Year` | |
| `funding_amount_usd` | integer or null | CSV: `Funding Amount` | Parsed to USD integer; null if unparseable |
| `investor` | string | CSV: `Investor` | Raw string, may contain multiple investors |
| `employee_size` | string | CSV: `Employee Size` | Often blank |
| `taxonomy_category` | string | Mapped | From `bucket_to_taxonomy_map.json` |
| `taxonomy_subsector` | string | Mapped/AI | Best-effort; `UNMAPPED` if not resolved |
| `raw_sector_original` | string | CSV: `Sector` | Preserved for reference |

### `task360_services` block — rule-based

| Field | Type | Source | Notes |
|---|---|---|---|
| `primary` | array of strings | Rule-based | From `stage_to_services_map.json`: most urgent services |
| `growth` | array of strings | Rule-based | From `stage_to_services_map.json`: next-stage services |

### `intelligence` block — AI-generated

| Field | Type | Notes |
|---|---|---|
| `strategic_theme` | string | 1-line: what they're building and why |
| `macro_tags` | array of strings | Macro/policy factors most relevant to this startup |
| `risk_signals` | array of strings | Flags: regulation-sensitive, macro-sensitive, pre-revenue, etc. |
| `partnership_score` | integer (1–10) | 10 = strongest fit for Task360 engagement right now |
| `partnership_score_rationale` | string | 1–2 sentences explaining the score — makes it auditable |
| `funding_amount_bracket` | string | Estimated Task360 work order size: ₹2–5L / ₹5–15L / ₹15–50L / ₹50L+ |
| `potential_work_areas` | array of 3 strings | Top 3 Task360 services, ranked by fit |
| `collab_potential_tags` | array of strings | Event/engagement formats: roundtable, workshop, case study, etc. |

### `outreach` block — AI-generated

| Field | Type | Notes |
|---|---|---|
| `hook_line` | string | 1 personalised sentence to open a conversation — specific to this startup's stage and context |
| `one_page_proposal` | string | 150-word proposal from Task360's perspective: what they offer, why it fits, what the founder gets |
| `engagement_strategy` | string | 300-word strategy: how to approach, what to lead with, sequencing, what to avoid |

### `meta` block

| Field | Type | Notes |
|---|---|---|
| `intelligence_generated` | boolean | `false` in base DB; set to `true` after AI generation |
| `model_used` | string or null | `gemini-3.1-flash-lite` once generated |
| `generated_on` | ISO timestamp or null | UTC timestamp of generation |

---

## Fields Deliberately Excluded

The following fields from `FUST_cleaned.csv` are **not** carried into this database:

| Excluded Field | Reason |
|---|---|
| `Email` | Personal contact data — not appropriate for this DB |
| `Founder LinkedIn` | Personal profile — not appropriate for this DB |
| `Contact Status` | Outreach pipeline field — not relevant here |
| `Source` | Internal data provenance tag — not relevant here |
| `Revenue Stage` | Mostly blank, low signal value |
