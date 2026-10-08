# Staging fixes (2026-10-08)

All evidence below was fetched as raw text (curl, pdftotext) and grepped.

## superhuman.csv
| Row | Field | Old -> New | Evidence |
|---|---|---|---|
| math-imo-openai-2025 | (new row) | added; date 2025-07-19, level exceeded_expert_median, confidence medium, source_type official | https://x.com/alexwei_/status/1946477742855532918 (OpenAI researcher post, "7:50 AM, Jul 19, 2025": 5 of 6 problems, three former IMO medalists graded, 35/42); https://github.com/aw31/openai-imo-2025-proofs (README "our experimental reasoning LLM"; commit 2025-07-18 via GitHub API). No IMO-organiser statement was fetchable (imo2025.au pages empty, openai.com page blocked), so certification status recorded as "not stated in fetched sources". Confidence medium (not high) because grading was by former medalists, whereas DeepMind page says IMO coordinators graded and certified. |
| math-imo-gemini-2025 | date | 2025-07-21 -> unchanged (confirmed) | DeepMind page raw text shows "July 21, 2025". |
| math-imo-gemini-2025 | notes | "per search summary only; fetched page has no date" -> "confirmed in raw text of the fetched page" | same |
| law-gpt4-bar-2023 | level | exceeded_expert_median -> contested | Martinez, AI and Law 33:581-604, published 30 Mar 2024, https://link.springer.com/article/10.1007/s10506-024-09396-9 (abstract: ~69th pct or below, ~62nd vs first-time takers, ~48th vs passers). Author and venue confirmed. |
| law-gpt4-bar-2023 | notes | appended reanalysis finding and URL | same |
| coding-ioi-nvidia-2026 | notes | rewritten | https://arxiv.org/abs/2609.02849 and PDF: claim 535.4/600, 498.27, 361.12 and v1 date 2 Sep 2026 confirmed. Affiliation NOT stated on either page; NVIDIA inferred (Nemotron models, NVIDIA-NeMo/Skills, 760 NVIDIA GB300 GPUs). Confidence left medium; row kept. |

Flag for lead: the Gemini row's note "IMO confirmed answers correct but did not validate the system" was not checked here; the DeepMind page itself says results were "officially graded and certified by IMO coordinators". Reconcile if the earlier source is not on file.

## claims.csv
| Row | Field | Old -> New | Evidence |
|---|---|---|---|
| cu13 | date_said / date_precision | 2024 / year -> 2024-06 / month | "Leopold Aschenbrenner, June 2024" on https://situational-awareness.ai/ (landing page; chapter page has no date). Quote "strikingly plausible" re-confirmed on chapter page. |
| cu13 | notes | removed "from general knowledge" caveat; date source added | same |
| cu23 | date_said / date_precision | 2024 / year -> 2024-03-07 / day | https://lexfridman.com/yann-lecun-3-transcript/ : "posted in transcripts on March 7, 2024". This is the transcript post date, not necessarily the recording date. |
| cu23 | notes | date source added | same |

## Not done
- gr04-gr07 (item 6): unchanged. INFORMS (403) and the Internet Archive scan of The Shape of Automation (401, lending-restricted) are not fetchable; no raw text containing the quotes was obtained.
