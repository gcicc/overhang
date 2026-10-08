# OVERHANG data-source recon

Tested 2026-10-08 from a local Windows machine with python requests (UA `overhang-recon/0.1`). No keys used or saved.
Rate limits marked "documented" (arXiv, Manifold, HN, ClinicalTrials) are from the providers' docs as I know them and were not exercised here; only HF, Altmetric and GitHub returned limit headers.
GREEN = works and usable. AMBER = works with caveats. RED = unusable as specified.

| # | Source | Status | URL | Auth | Rate limit | Licence | Fields |
|---|--------|--------|-----|------|-----------|---------|--------|
| 1 | METR time horizon | AMBER | `https://metr.org/assets/benchmark_results_1_1.yaml` (also `_1_0.yaml`) | none | static file | none stated (repo "See LICENSE", GitHub reports no licence; cite METR) | model key, `release_date`, `p50_horizon_length.estimate/ci_low/ci_high` (minutes), `p80_...`, `doubling_time_in_days` |
| 2a | Epoch Notable AI Models | GREEN | `https://epoch.ai/data/notable_ai_models.csv` | none | none observed | CC BY 4.0 | Model, Organization, Publication date, Training compute (FLOP), Organization categorization, Country |
| 2b | Epoch Frontier models | GREEN | `https://epoch.ai/data/frontier_ai_models.csv` (also `large_scale_ai_models.csv`) | none | none observed | CC BY 4.0 | Model, Publication date, Organization, Training compute (FLOP) |
| 2c | Epoch Benchmarking hub | GREEN | `https://epoch.ai/data/benchmark_data.zip` | none | none observed | CC BY 4.0 | per-benchmark CSVs: Model version, mean_score, Release date, Organization, Country |
| 2d | Epoch Frontier data centers | GREEN | `https://epoch.ai/data/data_centers/data_centers.zip` | none | none observed | CC BY 4.0 | Name, Current H100 equivalents, Current power (MW), Owner, Country; timelines CSV |
| 3 | ARC Prize leaderboard | AMBER | `https://arcprize.org/media/data/leaderboard/{v1,v2,v3}.json`, `.../models.json` | none | none observed | not stated | evaluations[]: modelDisplayName, modelReleaseDate, score, costPerTask, datasetDisplayName |
| 4 | Manifold Markets | GREEN | `https://api.manifold.markets/v0/search-markets`, `/v0/bets`, `/v0/market/{id}` | none (read) | documented 500 req/min/IP; no headers returned | API docs permit use; no explicit derived-data terms (attribute + link) | question, probability, volume, closeTime, url; history from bets `probAfter`/`createdTime` |
| 5 | Metaculus | RED | `https://www.metaculus.com/api/posts/{id}/` | token required (403 unauthenticated) | n/a | ToS governs API use; not checked | n/a without token |
| 6 | arXiv API | GREEN | `https://export.arxiv.org/api/query` | none | 1 request / 3 s, single connection (documented) | metadata CC0; abstracts per arXiv terms | id, title, updated, summary, categories, totalResults |
| 7 | HF Daily Papers | GREEN | `https://huggingface.co/api/daily_papers` | none | 500 req / 300 s (RateLimit header) | metadata; no explicit licence, link back | paper.id, title, upvotes, githubRepo, githubStars, numComments, publishedAt |
| 8 | HN Algolia | GREEN | `https://hn.algolia.com/api/v1/search` | none | ~10k req/hr/IP (documented, not in headers) | HN data; no explicit licence, link back | title, url, points, num_comments, created_at, objectID |
| 9 | Semantic Scholar Graph | AMBER | `https://api.semanticscholar.org/graph/v1/paper/arXiv:{id}?fields=citationCount` | none works but shared pool; free key available | unauth: 429 on first call, 200 on retry after 5 s; shared 1000 rps pool across all unauth users | S2 API licence requires attribution; derived counts OK with attribution | citationCount, influentialCitationCount |
| 10 | Altmetric | RED | `https://api.altmetric.com/v1/arxiv/{id}` | API key required since 2025-11-10 (403) | 720/hr, 1200/day headers shown | n/a | n/a |
| 11 | Reddit JSON | RED | `https://www.reddit.com/r/MachineLearning/top.json` | 403 blocked unauthenticated; old.reddit redirects to login | n/a | Reddit API terms restrict | n/a |
| 12 | ClinicalTrials.gov v2 | AMBER | `https://clinicaltrials.gov/api/v2/studies` | none | ~50 req/min/IP (documented) | public domain (NLM terms: attribute, no endorsement) | nctId, phases, leadSponsor, interventions |

## Counts

GREEN 5 (Epoch as one source, Manifold, arXiv, HF, HN), AMBER 4 (METR, ARC, Semantic Scholar, ClinicalTrials), RED 3 (Metaculus, Altmetric, Reddit).

## Per-source notes

### 1. METR (AMBER)

- The GitHub repo `METR/eval-analysis-public` has the code and `runs.jsonl` (about 1 MB per report) but the computed fits are DVC-tracked and not in git. Use the site YAML instead, which is the published headline output.
- `benchmark_results_1_1.yaml` (Time Horizon v1.1): 26 models. Latest entry `claude_mythos_preview_early_inspect`, released 2026-04-07. Repo's last commit is 2026-03-06 ("Sync public pipeline"), so updates are irregular and the series lags the newest models by months. Do not promise freshness.
- Units: minutes. Sample:
  - `gpt_5_4`, 2026-03-05, p50 = 341.7 min
  - `claude_mythos_preview_early_inspect`, 2026-04-07, p50 = 1044.8 min (ci_low 508.9; CI is wide)
  - `doubling_time_in_days`: all_time_stitched 187.8, from_2023_on 128.7 (CI 104.4 to 158.0)
- The v1.0 and v1.1 task suites differ; do not splice them. Parse with PyYAML (not stdlib) or a small hand parser; this adds a dependency to check with Greg.
- Licence unclear: attribute METR and link to the page.

### 2. Epoch AI (GREEN)

- All four are plain CSV/ZIP, no auth, no key. Licence CC BY 4.0 (stated in the zip READMEs and on `epoch.ai/data`): credit Epoch AI and link.
- Notable models: 1078 rows. Frontier models: 138 rows. Rows for the newest models often have an empty `Training compute (FLOP)` (for example GPT-6.1 Sol, 2026-09-29 in Notable). Compute-trend charts must tolerate blanks.
- Frontier CSV has no `Organization categorization` column populated (None); the Notable CSV does (`Industry`, etc.). Use Notable for organization type.
- Benchmark zip: about 30 CSVs including `frontiermath.csv`, `frontiermath_tier_4.csv`, `gpqa_diamond.csv`, `swe_bench_verified.csv`. Several `Logs` and `Log viewer` columns hold private S3 URLs; ignore them.
- Data centers zip: `data_centers.csv` (404 rows) plus timelines, chip quantities, chillers, cooling towers, chip types.
- Samples:
  - Notable: `GPT-6.1 Sol, OpenAI, 2026-09-29, Industry`
  - Frontier: `GPT-6 Astra, OpenAI, 2026-09-03, 1.0001e+27 FLOP`
  - Benchmark `frontiermath.csv`: `claude-opus-4-8_max, 0.4724, 2026-05-28, Anthropic, United States of America`
  - `data_centers.csv`: `Colossus 2, 1111672 H100e, 946 MW, 35.8 B USD (2025)`
- Update cadence: observed data to 2026-09-30, so at least weekly. ETag/Last-Modified not checked; cache by hash.
- Column names contain spaces and parentheses; pin them in a schema check so a rename fails loudly.

### 3. ARC Prize (AMBER)

- No documented API. The leaderboard page is a Next.js app that fetches static JSON; these URLs work today: `/media/data/leaderboard/v1.json` (ARC-AGI-1, 270 evaluations), `v2.json` (ARC-AGI-2, 273), `v3.json` (ARC-AGI-3, fewer), and `/media/data/models.json` (331 models with `modelReleaseDate`, `providerId`). `generatedAt` was 2026-10-05.
- Undocumented, so the paths can move without notice; the build should fail loudly and keep the last good copy. No licence stated; attribute ARC Prize and link.
- Sample (v2): `GPT-6 Astra (Max)`, 2026-09-02, score 0.95, cost per task 1.12 USD. (v1): `Claude Fable 5 (Max)`, 2026-06-09, score 0.985. Some v3 rows lack `costPerTask`.
- Scores are on the semi-private set. The human panel row has no release date (`modelReleaseDate` null); filter it.
- Plot by `modelReleaseDate` (model date), not eval date; there is no eval date field.

### 4. Manifold (GREEN)

- `search-markets?term=AGI&sort=liquidity&filter=open&limit=N` returns market objects. Sample:
  - `Will we get AGI before 2028?`, p = 0.259, volume 172k, close 2027-ish (`closeTime` ms epoch)
  - `When will a weakly general AI become publicly known?` is `PSEUDO_NUMERIC`, value 0.484 (needs the market's min/max to convert; read `/v0/market/{id}`)
  - `Will a weakly general AI become publicly known before 2030?`, p = 0.776
- Probability history: no dedicated endpoint used here; page `/v0/bets?contractId={id}&limit=1000&before=...` and take `probAfter` with `createdTime` (ms). Verified: returns `probBefore`, `probAfter`, `createdTime`. High-volume markets mean many pages; fetch incrementally and store a cursor.
- Many AGI markets are joke or niche ("before Frozen 3"). Curate a fixed list of market IDs rather than searching at runtime.
- No auth for reads. No rate-limit headers returned; stay well under 500/min.

### 5. Metaculus (RED)

- Both `/api/posts/` and `/api/posts/{id}/` return 403 "The API is only available to authenticated users". A token requires a free account and use is subject to Metaculus ToS. Tokens in a public repo's Actions secrets are possible but not "easy, no keys". Recommend dropping it, or hard-coding the published community-forecast numbers by hand with a source link and date (a curated, manually refreshed entry).

### 6. arXiv (GREEN)

- Query `search_query=cat:cs.AI+OR+cat:cs.LG+OR+cat:cs.CL&sortBy=submittedDate&max_results=N` returns Atom XML (stdlib `xml.etree` works). `opensearch:totalResults` 474,560 for the OR query.
- Sample entry: `2610.10538v1`, "Never Look Back: Understanding Persistence in 3D Object Memory from Egocentric Videos", updated 2026-10-07.
- Respect the 1 request per 3 s rule and set a contact UA. For daily counts use date range filters `submittedDate:[YYYYMMDD0000 TO YYYYMMDD2359]` with `max_results=1` and read totalResults.
- Note the arXiv IDs now run `2610.` (October 2026); no problem for parsing.

### 7. Hugging Face Daily Papers (GREEN)

- `GET /api/daily_papers?limit=N` (also accepts `date=YYYY-MM-DD`; not tested). Returns JSON with `paper.id`, `paper.title`, `paper.upvotes`, `paper.githubRepo`, `paper.githubStars`, `numComments`, `publishedAt`.
- Sample: `2610.09457`, "DSReg: Provably Recovering Individual World Latents without Reconstruction", upvotes 1, 1 comment, 2026-10-06. Early-day papers have low counts; snapshot after the day settles.
- Limit header: `RateLimit-Policy: "api";q=500;w=300` unauthenticated.

### 8. Hacker News Algolia (GREEN)

- `search?query=<url or title>&restrictSearchableAttributes=url&tags=story`. Sample (arXiv URL match): `The paper that made ChatGPT possible`, url `https://arxiv.org/abs/1706.03762`, 173 points, 55 comments, 2023-02-03.
- A URL query can return several posts; take the max by points and sum comments deliberately. Titles with `<em>` markup appear in `_highlightResult`; ignore that block.

### 9. Semantic Scholar (AMBER)

- `/graph/v1/paper/arXiv:1706.03762?fields=title,citationCount` returned 429 on the first call and 200 on retry 5 s later (`citationCount` 196,005). The `/paper/batch` POST also returned 429 on this run. Unauthenticated traffic shares a global pool, so a CI runner will hit 429 often. Build with retry/backoff (5 s, 15 s, 45 s) and treat failure as "no data this run", or request a free API key (form on semanticscholar.org/product/api, stored as a GitHub secret). Citation counts for new papers are near zero, so the use is limited to older papers.

### 10. Altmetric (RED)

- Since 2025-11-10 every request needs `key=`: HTTP 403 "You must supply an API key" on both `/v1/arxiv/` and `/v1/doi/`. Keys are by registration for researchers, not an easy free tier. Replace with HN points plus HF upvotes as attention proxies.

### 11. Reddit (RED)

- `www.reddit.com/r/MachineLearning/top.json` returns 403 (HTML block page) from a script; `old.reddit.com/.../top/.rss` redirects to a login page. Authenticated OAuth is now subject to Reddit's approval process. Drop it.

### 12. ClinicalTrials.gov v2 (AMBER)

- API works with no auth (`apiVersion 2.0.5`, data timestamp 2026-10-08). `fields=NCTId,Phase,LeadSponsorName,InterventionName` and `countTotal=true` work; phases come back as `PHASE1`, `PHASE2`, `PHASE3`, `NA`.
- There is no structured "AI-discovered" flag. A free-text intervention query for "AI-discovered OR AI-designed OR machine learning-designed" returned 323 studies, but the top hits are AI software and diagnostic trials (for example CLAiR eye software), not molecules. Counting AI-discovered drugs by phase therefore needs a curated list of molecules or sponsors.
- Sponsor queries work: Insilico Medicine 11 studies (for example rentosertib INS018_055, Phase 3, NCT07687459; ISM8969, Phase 1), Recursion 10 (REC-3964 Phase 2; Exscientia GTAEXS617 Phase 1/2).
- Recommended design: a hand-curated `ai_molecules.csv` (molecule, sponsor, discovery-method source) joined to NCT IDs by intervention name, with the highest phase per molecule. The curation and its sourcing is the real work; the API is the easy part.
- Public domain data; NLM asks for attribution and the retrieval date.

## Notes for the build

- Dependencies: stdlib plus requests is enough for everything GREEN except METR (YAML). A tiny hand parser can read the flat `p50_horizon_length.estimate` and `release_date` fields, or add PyYAML (needs approval).
- Set a contact User-Agent on every call; arXiv and Wikimedia-style APIs ask for it.
- Every run should snapshot raw responses under `data/staging/` with a retrieval timestamp and keep the last good copy when a source fails.
- Python in this environment has `requests` only in the user site-packages; GitHub Actions needs an explicit `pip install requests`.
