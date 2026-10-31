---
name: overhang
type: maintain
category: building
tier: 02-Maintain
updated: 2026-10-31
note: started directly in 02-Maintain per Greg 2026-10-08
url: https://gcicc.github.io/overhang/
---

# OVERHANG — next steps

## Where this stands

**2026-10-31: split into two pages (Greg).** `index.html` now opens with a countdown to the
next dated AI milestone and Recent news, then Measured, Race, Compute & Silicon, Superhuman,
History. `claims.html` holds the Ledger, What counts as AGI?, Crowd vs. CEOs and All claims.
Cross-page `#` links are rewritten at render (`render._cross_links`).
- Countdown reads `data/curated/upcoming.csv` (5 rows, all quote-verified: Nvidia Q3 FY27 call
  2026-11-17 22:00 UTC, re:Invent and GTC DC 11-30, NeurIPS 12-08, GTC 2027 03-15). The clock
  never shows units finer than the row's `precision`. No lab has published a fixed model-release
  date, so model launches enter only when one does.
- News: `overhang/news.py`, stdlib XML, 6 feeds (OpenAI, DeepMind, Hugging Face, 3 Google News
  queries), 7-day window, newest first, deduped, `max_age` 5 h. First cut of SPEC Section 3.
44 tests pass.

**Slice 1b shipped 2026-10-29 (SPEC "Race, Compute & Silicon").** Two new sections and a
glossary; History added the same day. 39 tests pass, ruff clean, checked in a browser at 1280 and 390 px.

| Panel | State (2026-10-29) |
|---|---|
| The Race | 5 metrics since 2023. Leaders now: compute OpenAI, GPQA Google, SWE-bench Anthropic, FrontierMath OpenAI, METR Anthropic. GPQA median spell 84 d overall, 27 d over the last 5 |
| Country share | Frontier models since 2018: 43 US, 3 China, 8 other (n=54, disclosed compute only) |
| Accelerators | Fastest AMD MI455X 5.0 PFLOP/s (16-bit); frontier 1.6×/yr (n=15 since 2017) |
| Data centers | 15.2M H100e tracked across 96 sites; Google largest owner |
| Filings | Latest quarter: Nvidia $96.2B, Broadcom $29.6B, AMD $11.5B. Hyperscaler capex TTM $573B combined |
| Glossary | 29 terms with hover definitions and a Glossary section |
| History | One timeline from 1940: 541 Epoch notable models with compute (547 without, counted not plotted), 23 sourced milestones + 2 AI winters in `history.csv`, and the 31 superhuman firsts. All 75 checkable quotes verbatim |
| What counts as AGI? | 8 sourced definitions (2 measurable, 3 partly, 3 not); all quotes verbatim. Jensen Huang's 2026-09-06 "AGI has arrived" added as claim cu24 |

Earlier state (slice 1, 2026-10-08):

Slice 1 is built and verified locally (2026-10-08): Sections 1 and 2 of `SPEC.md`, plus the
measured and crowd panels. `python run.py` builds `docs/index.html` from four live sources (METR,
Epoch, ARC Prize, Manifold) and three curated ledgers. 23 tests pass, ruff is clean, and the page
was checked in a browser at 1280 px and 390 px with no horizontal overflow.

| Panel | State |
|---|---|
| The Ledger | 39 claims shown (3 held: quote not confirmed). Statuses: 1 achieved, 4 window open, 16 open, 9 deadline passed and unverified, 9 undated |
| Quote check | 41 of 41 checkable quotes found verbatim in the raw source; 1 fetch failure is on a held row |
| METR | Own fit: 129-day doubling (n=14, 2023-03 to 2026-02), which matches METR's published 128.7 days. METR's file lags, with the latest model dated 2026-04-07 |
| Epoch compute | 4.6×/yr since 2018 (n=16, R² 0.98); 11 of 138 rows have no compute and are not imputed |
| Bounded | FrontierMath T1–3 52%, ARC-AGI-1 98%, ARC-AGI-2 95% (best to date) |
| Crowd | Manifold P(AGI before 2027/28/30/32) = 4/24/50/56% |
| Superhuman Ledger | 31 events; 24 industry, 4 academia, 3 collaboration |

ADR 0001: a Python pipeline renders one self-contained HTML page, the same approach as HANGAR.

## Next task

Seed vendor roadmap claims (SPEC R6), e.g. Nvidia architecture ship dates, as quote-verified
`claims.csv` rows. They need sourced quotes, never recollection. Optional: add the
`SEC_CONTACT` repo secret (`gh secret set SEC_CONTACT -R gcicc/overhang`); without it SEC gets a
placeholder address. Then Slice 2 as below.


Slice 2: SPEC Sections 3 and 4 (frontier news and arXiv ranked by buzz; AI in the sciences),
on the same pipeline. History (Section 5) has a first cut; researcher lineage is open.

Published 2026-10-08 at https://gcicc.github.io/overhang/ (repo `gcicc/overhang`, Pages from
`/docs` on `main`, branch build). Greg approved going straight to Tier 2, skipping the
Tier 1 hold-up period in PUBLISHING-PROTOCOL.md. The refresh workflow was verified green on a
manual dispatch, and the site is in the liveness check (60 of 60 live).

## Blockers

- Held claims need a primary source: Hassabis 2026 (cu16), Kurzweil 2005 (gr15), and
  Hinton's 2023 tweet (cu22).
- Six graveyard quotes (gr04 to gr07, gr09, gr10) rest on Wikipedia. The originals were not
  fetchable (INFORMS 403, Internet Archive lending-restricted).

## What keeps this current

`.github/workflows/refresh.yml` runs at `17 */6 * * *` and commits `docs/` and `data/`. Each
source's `max_age` lives in `overhang/cache.py`: Manifold 6 h; METR, Epoch and ARC 1 day; the
quote check 7 days. Failed fetches keep the last good copy and show as STALE in the footer.
Curated ledgers change only by hand, and the build fails on any row without a source.
