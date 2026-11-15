# Open-access corpus: coverage report

Built on 2026-11-15 by `scripts/rebuild_oa_corpus.py`. Only open sources were used: OpenAlex, Unpaywall, Europe PMC, repository copies and the PDF link stored in the annotation file. No Sci-Hub, no EZproxy.

## Short version

- The corpus is 98 valid open-access records: 30 dev, 68 held-out (the frozen list, digest checked by the script).
- Every record has a linked article DOI. No record is missing its article.
- We hold **31 of 98 PDFs** (9 dev, 22 held-out). 67 are unreachable from this server.
- The main cause is bot protection, not missing open copies: most failures are HTTP 403 from Wiley, Oxford Academic, MDPI, the Royal Society and Cloudflare-protected Europe PMC. Chromium was not available here (see below), so the browser fallback was not tried.
- Abstract-only and feature-field runs are unaffected: all 98 records have abstracts. PDF-based runs can use 9 of the 30 dev records until more PDFs are fetched.

## Records by source and split

| Source | Dev | Held-out | Total |
|---|---|---|---|
| Semantic Scholar | 10 | 36 | 46 |
| Zenodo | 10 | 17 | 27 |
| Dryad | 10 | 15 | 25 |
| Total | 30 | 68 | 98 |

## PDF coverage by source and split

| Source | Dev with PDF | Held-out with PDF | Total with PDF |
|---|---|---|---|
| Semantic Scholar | 3 / 10 | 12 / 36 | 15 / 46 |
| Zenodo | 5 / 10 | 6 / 17 | 11 / 27 |
| Dryad | 1 / 10 | 4 / 15 | 5 / 25 |
| Total | 9 / 30 | 22 / 68 | 31 / 98 |

Where the 31 PDFs came from: 7 already on disk (dev), 11 OpenAlex links, 11 repository copies, 2 the PDF link stored in the annotation file. Dev: 7 pre-existing + 2 repository.

## PDF coverage by licence

The licence is the one OpenAlex or Unpaywall report for the best open location. It is empty when neither reports one.

| Licence | PDF held | Unreachable |
|---|---|---|
| cc-by | 25 | 25 |
| cc-by-nc | 0 | 5 |
| cc-by-nc-nd | 0 | 4 |
| cc-by-nc-sa | 1 | 0 |
| public-domain | 1 | 1 |
| other-oa | 0 | 3 |
| not reported | 4 | 29 |

Half of the unreachable cc-by papers are blocked only by the publisher's bot filter, so the licence would allow the copy.

## What stays unreachable, and why

Counts are records (one record can fail on several hosts). The per-record reason is in `data/manifests/oa_corpus_pdfs.csv`, column `failure_reason`.

| Cause | Records (approx.) | Notes |
|---|---|---|
| Wiley (onlinelibrary.wiley.com) answers 403 | 29 | Includes the Ecology and Evolution, Evolutionary Applications, Diversity and Distributions papers |
| Oxford Academic (academic.oup.com) answers 403 | 10 | |
| MDPI, Royal Society, CIF-IFC, Hindawi, IWA and similar publishers answer 403 | about 15 | |
| Europe PMC and PMC answer 403 | 21 | Cloudflare "Just a moment" challenge page. A plain script cannot pass it; a browser might |
| Link leads to an HTML page, not a PDF | 8 | HAL, BioOne, CONICET, BioMed Central, York University journals, Springer. Records 30, 54, 121, 201, 207, 256, 268 |
| No open PDF location in OpenAlex, Unpaywall or Europe PMC | 5 | Records 4, 155, 189, 193, 235. Their open status in the annotation file could not be confirmed from a PDF link |
| Repository link dead or blocked | 6 | doc.rero.ch (410), espace.inrs.ca (404), UQAT, UQAC, USF, TELUQ (timeout) |

Dev records still without a PDF (21): 5, 12, 19, 27, 29, 30, 31, 37, 39, 56, 71, 89, 91, 123, 175, 201, 258, 271, 315, 343, 351.

Chromium: the task assumed a preinstalled Chromium. None is on this server (no `/opt/pw-browsers`, no Playwright package). Playwright's installer refuses this Ubuntu version, and I did not force it. `scripts/rebuild_oa_corpus.py --chromium` is ready: install Chromium and Playwright, then rerun with that flag to try the 67 missing records. Already-held PDFs are kept.

## How to rebuild

```
cd ~/code/llm_metadata
uv run python scripts/rebuild_oa_corpus.py            # manifests + PDF download (about 6 min)
uv run python scripts/rebuild_oa_corpus.py --chromium # also try Chromium for missing ones
uv run python scripts/rebuild_oa_corpus.py --no-download # manifests and PDF table from files on disk
```

Outputs: `data/manifests/oa_corpus_data_paper.csv` (98), `heldout_data_paper.csv` (68), `dev_subset_data_paper.csv` (30, POSIX paths), `oa_corpus_pdfs.csv` (one row per record: URL used, source, licence, SHA-256, pages, status). PDFs are in `data/pdfs/fuster/` and are git-ignored. API answers are cached in `artifacts/oa_corpus_cache/`.

Held-out records: the script only checks the `%PDF` header, page count and SHA-256. No held-out PDF text was read.
