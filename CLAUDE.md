# OVERHANG — project rules

Large project. `SPEC.md` holds the goal and done criteria (D1–D10). ADRs are in `decisions/`;
they are never edited, only superseded.

## Architecture

`run.py` → `overhang/cache.py` (per-source `max_age`) → `overhang/sources.py` (METR, Epoch,
ARC, Manifold) + `overhang/quotecheck.py` → `overhang/curated.py` (validation) →
`overhang/resolve.py` (claim status) + `overhang/trend.py` (fits) → `overhang/charts.py`
(server-side SVG) → `overhang/render.py` + `templates/` → `docs/index.html`.

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
