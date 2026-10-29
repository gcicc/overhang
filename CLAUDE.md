# OVERHANG — project rules

Large project. `SPEC.md` holds the goal and done criteria (D1–D10). ADRs are in `decisions/`;
they are never edited, only superseded.

## Architecture

`run.py` → `overhang/cache.py` (per-source `max_age`) → `overhang/sources.py` (METR, Epoch,
ARC, Manifold, Epoch Notable models) + `overhang/filings.py` (SEC, Yahoo) + `overhang/quotecheck.py` → `overhang/curated.py` (validation) →
`overhang/resolve.py` (claim status) + `overhang/trend.py` (fits) + `overhang/race.py`
(frontier holders) + `overhang/compute.py` (data centers) → `overhang/charts.py`
(server-side SVG) → `overhang/render.py` (+ glossary pass) + `templates/` → `docs/index.html`.

Colour follows the entity: every lab, chip maker and company takes its fixed slot from
`race.SLOTS` (never enumeration order). New jargon on the page gets a `render.GLOSSARY` entry. History colours compute dots by
sector (`charts.SECTOR_SLOT`); milestones stay in ink so they never read as a sector.

## Rules

- No LLM calls in the pipeline. Selection, status and ranking are deterministic.
- Never add a claim or ledger row from memory. Every row needs a source URL, and a quote
  must be confirmed in the raw page text (not a fetch-tool summary) before
  `quote_verified=yes`.
- Never write a claim's status by hand. It is computed in `resolve.py`.
- `notes` is curation-only. Reader-facing caveats go in `public_note`.
- Dependencies are `requests` and `jinja2` only. Ask Greg before adding one.
- Run `python -m pytest -q` and `python -m ruff check overhang tests run.py` before committing.
  Open `docs/index.html` in a browser before saying any change is done.
- The refresh bot commits `docs/` and `data/` every 6 hours. `git pull --rebase` before
  editing. If `docs/index.html` conflicts, it is generated: run `python run.py --render`,
  `git add docs/index.html`, then continue the rebase. Never hand-merge it.
