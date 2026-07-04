# 02 — Objective and Context

---

## Who This Is For

**Task360** is a CA and advisory firm providing end-to-end compliance, taxation, legal, and fundraising support to Indian startups and growing businesses. Their service stack covers the full startup lifecycle:

- **Launch** — incorporation, GST registration, Startup India recognition, trademark
- **Operate** — accounting, GST filings, TDS, virtual CFO, secretarial, ESOP design
- **Grow** — valuation, fundraise support, FDI compliance, M&A advisory, SME IPO

Their primary clients are funded Indian startups — exactly the population this database covers.

---

## The Business Problem

Task360 needs a structured way to answer three questions for each funded startup in India:

1. **Is this startup a good fit for Task360 services?** (prioritisation)
2. **Which specific services are most relevant to them right now?** (targeting)
3. **How should Task360 approach this founder?** (engagement)

Manually researching 546 startups to answer these questions is not feasible. This database automates that process using AI.

---

## The Internship Connection

This project is built by **Himanshi Gururani** as part of an internship at HABSGconsulting, under the mentorship of Task360. The academic component of the internship (macro/policy impact study on Indian startups 2023–2026) lives in a separate repo: `HABSGconsulting/internship`.

The two projects share the same startup population (`FUST_cleaned.csv`) but serve different purposes:

| Dimension | Internship Repo | This Repo (task360) |
|---|---|---|
| Purpose | Academic research | Business intelligence |
| Primary output | Research report | Prioritised startup DB |
| AI use | Contact enrichment | Intelligence generation |
| Personal data | Includes emails, LinkedIn | None — company-level only |
| Audience | Faculty / academic | Task360 BD team |

---

## What Success Looks Like

At the end of this project, Task360 should have:

1. A **prioritised list of 546 startups** ranked by partnership score (1–10)
2. For each startup: the **top 3 Task360 service areas** most relevant to their stage and sector
3. A **ready-to-use hook line** for opening a conversation with each founder
4. A **150-word personalised proposal** from Task360's perspective
5. A **300-word engagement strategy** covering how to approach, what to offer, and when
6. Per-category exports so the Task360 team can focus by sector

The database does not replace human judgment — it gives the Task360 team a structured, AI-assisted starting point that would otherwise take weeks to build manually.

---

## Why AI-Derived Fields Have Value

Standard startup databases (Crunchbase, Tracxn, Venture Intelligence) provide factual data: funding, stage, investor, sector. They do not provide:

- Service-specific relevance scores calibrated to a particular advisory firm
- Engagement hooks that connect a specific advisor's offering to a founder's current stage
- Personalised proposals written from the advisor's voice

These fields require combining structured startup data with contextual reasoning — which is exactly what a well-prompted LLM can do at scale. The value is not in the raw data. It is in the **interpretation layer** built on top of it.
