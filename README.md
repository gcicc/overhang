# OVERHANG

What has been claimed about AI, against what has been measured.

```
python run.py             # refresh what has gone stale, then render
python run.py --force     # refresh everything, ignoring cache age
python run.py --render    # rebuild the page from cache; no network at all
```

Output is `docs/index.html`, one self-contained file (ADR 0001). The page makes no data
requests; a scheduled job fetches, commits JSON to `data/`, and renders.

## Sections

| Section | Data | Kind |
|---|---|---|
| The Ledger | `data/curated/claims.csv`, `resolutions.csv` | curated, sourced, quote-checked weekly |
| Measured | METR time horizons; Epoch frontier compute and FrontierMath; ARC-AGI | live |
| Crowd vs. CEOs | Manifold markets listed in `data/curated/manifold_markets.csv` | live |
| Superhuman Ledger | `data/curated/superhuman.csv` | curated, sourced |

## Rules the build enforces

- **Every curated row has a source URL, a parseable date and in-vocabulary grades,** or
  the build stops (`overhang/curated.py`). Rows are never skipped silently.
- **Only claims with `quote_verified=yes` are shown.** The rest stay in the CSV, and the
  page states how many are held.
- **Every quote is re-checked weekly** against the raw text of its source
  (`overhang/quotecheck.py`). A quote that can no longer be found is flagged on the page.
- **A claim's status is computed, never written.** A passed deadline reads "outcome
  unverified" unless `resolutions.csv` links it to a dated Superhuman Ledger event.
- **Doubling times state their window and n.** Bounded scores get best-to-date, not a
  doubling time.
- **A failed fetch keeps the last good copy** and is marked stale in the footer
  (`overhang/cache.py`, adapted from HANGAR).

## Adding data

- A claim: add a row to `claims.csv` with a verbatim quote and the URL where it appears,
  and set `quote_verified=yes` only after confirming the quote in the page's raw text.
  `public_note` is shown to readers; `notes` is for curation and is not rendered.
- A resolution: add `claim_id,superhuman_id,rationale` to `resolutions.csv`.
- A market: add its id to `manifold_markets.csv`.

## Sources and credit

METR · Epoch AI (CC BY 4.0) · ARC Prize (undocumented JSON endpoint) · Manifold Markets.
Source recon is in `data/staging/SOURCES.md`, and curation fixes in `data/staging/FIXES.md`.
