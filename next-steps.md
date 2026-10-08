---
name: overhang
type: maintain
category: building
tier: 02-Maintain
updated: 2026-10-08
note: started directly in 02-Maintain per Greg 2026-10-08
url: https://gcicc.github.io/overhang/
---

# OVERHANG — next steps

## Where this stands

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

Slice 2: SPEC Sections 3 to 5 (frontier news and arXiv ranked by buzz; AI in the sciences;
history), on the same pipeline.

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
