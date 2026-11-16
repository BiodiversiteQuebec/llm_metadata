# Open-access corpus: coverage report

Built on 2026-11-15 by `scripts/rebuild_oa_corpus.py`. Only open sources were used: OpenAlex (all locations), Unpaywall (all locations), the PMC Open Access bucket, Europe PMC, Semantic Scholar, CORE, repository copies, publisher open-access URLs and the PDF link stored in the annotation file. No Sci-Hub, no EZproxy.

## Short version

- The corpus is 98 valid open-access records: 30 dev, 68 held-out (the frozen list, digest checked by the script).
- Every record has a linked article DOI.
- Second pass (publisher recipes and new sources): **47 of 98 PDFs** (16 of 30 dev, 31 of 68 held-out), up from 31 (9 dev, 22 held-out). 51 stay unreachable. No record could be saved as JATS XML (`text_only`): the records with a PMC number that are missing a PDF are not in the PMC open-access subset, and Europe PMC has no full text for them.
- What the second pass added: 13 PDFs from the PMC Open Access bucket on AWS, 1 from Semantic Scholar's `openAccessPdf`, the rest from repository copies already on the first list. Every OpenAlex location and every Unpaywall `oa_location` is now tried, plus CORE (works without a key).
- The remaining failures are bot protection (HTTP 403) on the publisher sites. We did not try to get past it: no spoofed browser, no stealth, no proxy. Headless Chromium gets the same Cloudflare page, so it adds nothing.
- Abstract-only and feature-field runs are unaffected: all 98 records have abstracts.

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
| Semantic Scholar | 3 / 10 | 16 / 36 | 19 / 46 |
| Zenodo | 7 / 10 | 8 / 17 | 15 / 27 |
| Dryad | 6 / 10 | 7 / 15 | 13 / 25 |
| Total | 16 / 30 | 31 / 68 | 47 / 98 |

Where the 47 PDFs came from. Dev: 7 already on disk, 7 PMC bucket, 2 repository copies. Held-out: 12 OpenAlex links (open publishers such as PLOS, Nature, Frontiers), 10 repository copies, 6 PMC bucket, 2 the link stored in the annotation file, 1 Semantic Scholar.

New columns in `oa_corpus_pdfs.csv`: `text_source` (`pdf`, `jats_xml` or `none`) and `preprint` (`true` when the copy is on a preprint server or the location is flagged as a submitted version). Three records are flagged: 54 and 117 (held-out) and 253 (dev). The text of a preprint can differ from the published article.

## PDF coverage by licence

The licence is the one OpenAlex or Unpaywall report for the best open location. It is empty when neither reports one.

| Licence | PDF held | Unreachable |
|---|---|---|
| cc-by | 39 | 11 |
| cc-by-nc | 0 | 5 |
| cc-by-nc-nd | 0 | 4 |
| cc-by-nc-sa | 1 | 0 |
| public-domain | 1 | 1 |
| other-oa | 2 | 1 |
| not reported | 4 | 29 |

The 11 unreachable cc-by papers are blocked only by the publisher's bot filter, so the licence would allow the copy.

## Result by publisher (DOI prefix, all 98 records)

| Publisher | With PDF | Why the rest fail |
|---|---|---|
| Wiley / Hindawi | 17 / 35 | 403 on onlinelibrary.wiley.com. The 17 come from the PMC bucket or repositories |
| BioOne (Entomological Society, ASPT, AJB) | 0 / 7 | 403 or HTML wall, no repository copy with a file |
| Canadian Science Publishing and CIF-IFC | 0 / 6 | 403 on cdnsciencepub.com and pubs.cif-ifc.org; UQAC copies are listed but carry no file |
| MDPI | 3 / 7 | 403 on mdpi.com `/pdf` |
| Oxford Academic | 1 / 4 | 403 (Cloudflare) |
| Royal Society | 0 / 4 | 403; the PMC copies are author manuscripts, not in the open-access bucket |
| Springer / BioMed Central | 3 / 3 | works |
| PLOS | 10 / 10 | works (open links from OpenAlex) |
| Frontiers | 2 / 2 | works |
| Others (repositories, Zenodo, IWA, SAGE, etc.) | 11 / 20 | IWA 403; dead repositories (see below) |

## What stays unreachable, and why

Counts are records. The per-record reason is in `data/manifests/oa_corpus_pdfs.csv`, column `failure_reason`.

| Cause | Records (approx.) | Notes |
|---|---|---|
| Wiley answers 403 | 18 | No PMC copy in the open-access bucket |
| BioOne, CSP, CIF-IFC, MDPI, Oxford, Royal Society, IWA, Hindawi answer 403 | about 22 | Same for `/pdf`, `pdfdirect` and Crossref link URLs |
| PMC number known but not in the open-access subset | 6 | Royal Society author manuscripts (39, 74, 78, 123), 162, 227. Europe PMC full text answers 500 |
| Link leads to an HTML page, not a PDF | 6 | UQAC Constellation (189, 193, 235: the page lists no file), BioOne (121), York University journals (256, challenge page), CONICET (201) |
| No open PDF location in OpenAlex, Unpaywall, Europe PMC, Semantic Scholar or CORE | 2 | Records 4 and 155 (Zenodo or figshare deposits listed as the article) |
| Repository link dead or blocked | 4 | doc.rero.ch (410), espace.inrs.ca (404), USF digital commons (403), TELUQ (timeout) |

Dev records still without a PDF (14): 5, 19, 27, 39, 71, 89, 123, 175, 201, 258, 271, 315, 343, 351.

## Publisher recipes

Code: `src/llm_metadata/publisher_pdf.py` (recipes only build URLs; the script downloads, 1.1 s between requests to one host, honest User-Agent "llm_metadata research client", the contact email only goes to OpenAlex and Unpaywall). Checked on 2026-11-15 from the Universite de Sherbrooke network. The university IP does not change any answer.

| Route | Verdict | Detail |
|---|---|---|
| PMC Open Access bucket on AWS (`pmc-oa-opendata.s3.amazonaws.com`) | works | DOI to PMCID with the NCBI ID converter (`pmc.ncbi.nlm.nih.gov/tools/idconv/api/v1/articles/`), then list `PMC<id>.` and take `PMC<id>.<version>.pdf` (or `.xml`). Only articles with an open licence. 13 PDFs |
| Old PMC web service `ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi` | gone | Answers 404 |
| Europe PMC `ptpmcrender` and `?pdf=render`, PMC `/pdf/` | blocked | Cloudflare 403 |
| Europe PMC REST `fullTextXML` | works for open articles | Used as the `text_only` fallback; no record needed it |
| Springer `link.springer.com/content/pdf/{doi}.pdf` | works | |
| Semantic Scholar `openAccessPdf`, CORE v3 search | work | CORE needs no key at this volume; they added 1 PDF |
| Wiley `pdfdirect` and `pdf`, Oxford `article-pdf`, MDPI `/pdf`, Royal Society, CSP, IWA | blocked | HTTP 403 to scripts |
| Frontiers, PLOS, PeerJ, Elsevier `pdfft` | written, mostly untested | Frontiers and PLOS PDFs came through OpenAlex links; no PeerJ or Elsevier record in the corpus |

Headless Chromium (Playwright) gets the Cloudflare "Just a moment" page on Wiley, Europe PMC and Oxford, also after a wait. The `--chromium` option is still in the script but is not worth running here.

## How to rebuild

```
cd ~/code/llm_metadata
uv run python scripts/rebuild_oa_corpus.py            # manifests + PDF download (about 6 min)
uv run python scripts/rebuild_oa_corpus.py --chromium # optional, blocked by Cloudflare here
uv run python scripts/rebuild_oa_corpus.py --no-download # manifests and PDF table from files on disk
```

Outputs: `data/manifests/oa_corpus_data_paper.csv` (98), `heldout_data_paper.csv` (68), `dev_subset_data_paper.csv` (30, POSIX paths), `oa_corpus_pdfs.csv` (one row per record: URL used, source, licence, SHA-256, pages, status). PDFs are in `data/pdfs/fuster/` and are git-ignored (the script reads and writes them in the main checkout, `DATA_ROOT`). API answers are cached in `artifacts/oa_corpus_cache/`; JATS XML would go to `artifacts/fulltext/<id>.xml`.

Held-out records: the script only checks the `%PDF` header, page count and SHA-256. No held-out PDF text was read.
