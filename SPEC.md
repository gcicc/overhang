# SPEC — OVERHANG

Status: **approved by Greg 2026-10-08** · written 2026-10-08 · kickoff decisions recorded below

## Goal

A self-refreshing website that tracks AI's progress toward superintelligence. Its organising question
is **what has been claimed about AI vs. what has been measured**. It also covers current events at
frontier labs and on arXiv, notable ("Nature-calibre") applications across the sciences, and the
history of milestones in academia and industry.

## Kickoff decisions (Greg, 2026-10-08)

| # | Decision | Greg's words / answer |
|---|---|---|
| K1 | Accountability first: claims vs. measured is the spine; discovery feeds support it | "Accountability first" |
| K2 | Sciences section = notable applications; "Nature" is a quality bar, not a journal filter; preprints and lab announcements qualify | "the neat applications that might make it into nature journal"; "Quality bar" |
| K3 | Feeds ranked by interest/buzz | "can you rank by interest or buzz factor?" |
| K4 | Design is not bound to prior projects (HANGAR, GRUDGE); reuse code only where it fits | "I don't want to limit your planning by what we've done before" |

## Sections

1. **The Ledger: claims vs. measured.** A claims register (dated statements, who, when, source,
   and the measured quantity each resolves against). Measured trend lines (METR time horizon, Epoch
   frontier compute, ARC-AGI, FrontierMath) with doubling times and "if this continues"
   extrapolations. Crowd (Metaculus/Manifold) vs. CEO horizons. A prediction graveyard.
2. **Superhuman Ledger.** The first date AI matched or exceeded the best humans in each domain, with
   a source, a confidence grade, and the criterion used.
3. **Frontier now.** Lab announcements, a model-release register, buzz-ranked arXiv cs.AI/LG/CL in
   topic lanes, capex and funding, and policy actions.
4. **AI in the sciences.** Lanes for math, physics, bio/chem, medicine/pharma, and other fields.
   Each has a buzz-ranked feed and a sourced milestone strip; pharma also gets AI-origin molecules
   by trial phase.
5. **History.** Academia and industry lanes from 1943, with the AI winters shaded. Backbone: Epoch
   *Notable AI Models* (compute on a log axis). Plus researcher lineage.

## Done criteria (testable)

- [ ] D1. One command refreshes all sources and renders the site. A scheduled job runs it unattended.
- [ ] D2. Every claim, milestone and superhuman-ledger row carries a source URL. The build fails on a
      row without one.
- [ ] D3. No claim row is authored from recollection. Curated rows are separated from auto-detected
      rows, and the separation is visible on the page.
- [ ] D4. Each measured series shows its value, `fetched_at`, and a fitted doubling time with the
      fit window stated.
- [ ] D5. A claim whose deadline has passed renders as "deadline passed: outcome unverified" unless
      a measured metric resolves it. It is never shown as "missed" without evidence.
- [ ] D6. The buzz score is deterministic: the same inputs give the same ranking. Weights are read
      from config and printed on the page.
- [ ] D7. Each science item is tagged `published` or `preprint/announced`, and shows staying power
      (citations at 30/90 days) once those dates are reached.
- [ ] D8. A failed source keeps its last good payload and is visibly flagged stale. An empty panel
      is never silently shown as "no news".
- [ ] D9. Tests pass and ruff is clean. The rendered site is opened in a browser and checked before
      any "done" claim.
- [ ] D10. Closeout is verified against this list by an independent reviewer agent.

## Out of scope (for v1)

- LLM-written selection or summaries (K3 is met deterministically). This can be revisited.
- X/Twitter as a buzz signal (needs a real browser; same open question as HANGAR).
- Paywalled sources, and full-text paper ingestion.
- User accounts, comments, or any write path from the browser.

## Constraints

- Python 3.11+, ruff. Minimal dependencies, and any new one is asked about first.
- Free data sources only. Respect rate limits (arXiv: 1 request per 3 s).
- The browser makes no API calls: the scheduled job writes static data and the page reads it.
- Sensitive-material rules from `Dropbox/CLAUDE.md` apply. No secrets in the repo.

## Assumptions (labelled — not confirmed by Greg)

- A1. The audience is Greg alone, though the site is public on GitHub Pages.
- A2. The project lives in `02-Maintain/overhang/` from the start (Greg, 2026-10-08).
- A3. Refreshing a few times a day is enough. Nothing needs real-time updates.

## Open questions (one at a time, during the build)

1. What would make it wrong: hype amplification, a missed key result, or stale data?
2. Single page or multi-page site? Is a weekly digest (email/RSS) wanted as well?
3. Does a pharma-specific lane deserve extra weight, given Greg's domain?

## ADR-level decisions (to be briefed in 4 lines each when reached)

Hosting and repo · single page vs. site · stack (static generator vs. Quarto vs. hand-rolled) ·
buzz-score weights · whether to copy HANGAR's ingest layer or extract a shared package.
