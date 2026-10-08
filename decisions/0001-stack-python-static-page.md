# 0001 — Stack: Python pipeline rendering one self-contained HTML page

Date: 2026-10-08 · Status: accepted · Decided by: Greg ("can we do same approach as hangar")

## Context

OVERHANG needs scheduled data refreshes (METR, Epoch, ARC, Manifold, curated ledgers) and a
published page with charts. Three options were briefed: (a) a Python build writing one
self-contained HTML file, as in `02-Maintain/hangar`; (b) a Quarto website with Observable JS,
rendered in CI; (c) a JavaScript static-site generator.

## Decision

(a). A Python pipeline fetches on a GitHub Actions cron, caches per source with `max_age`, and
renders `docs/index.html`. GitHub Pages serves `/docs` on `main`, which is never a Pages build
workflow (`03-Tools/project-management/docs/PUBLISHING-PROTOCOL.md`).

Implementation choices that follow:
- Charts are SVG generated server-side in Python (`overhang/charts.py`). They are deterministic,
  testable, need no JS chart library, and the page works from `file://`.
- Dependencies are `requests` and `jinja2` only, the same as HANGAR. METR's YAML is read by a small
  indentation parser, not PyYAML.

## Consequences

- No Quarto in CI. The page is not a `.qmd`, which is an accepted exception to the
  ".qmd deliverables" default for a scheduled, self-refreshing site.
- One page holds five sections. If it outgrows one page, revisit with a superseding ADR.
- Charts are hand-built SVG: cheap for static views, but costly for rich interaction.
