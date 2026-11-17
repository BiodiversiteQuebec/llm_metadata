# Completing the PDF corpus from a desktop on the UdeS network

**Status:** Ready to execute
**Branch:** `feat/anthropic-extraction` (or a new branch from it)
**Follows:** [`plans/anthropic-article-results.md`](anthropic-article-results.md) (corpus work, second PDF pass)

## Why this plan exists

The server pass got 47 of the 98 open-access articles. The other 51 (14 dev, 37 held-out) are open access, but publishers answer scripts with HTTP 403 or a Cloudflare "Just a moment" page. Headless Chromium on the server never gets past it, and the server has no display.

Long-text results therefore rest on 16 dev and 31 held-out records, and on 19 labelled held-out records for relevance. Those records are a biased sample: the ones that have an open PDF are easier. Filling the gap is the cheapest way to strengthen Tables 1 to 3.

A desktop on the Université de Sherbrooke network has what the server lacks:
- a real Chrome with a display;
- a person who can watch, debug, and click through a challenge;
- the university IP.

## Missing PDFs (from `data/manifests/oa_corpus_pdfs.csv`, 2026-11-17)

| Publisher (DOI prefix) | Dev | Held-out | Server failure |
|---|---|---|---|
| Wiley (10.1111, 10.1002) | 3 | 13 | 403 on `onlinelibrary.wiley.com` (`/doi/pdfdirect/`, `/doi/pdf/`) |
| Canadian Science Publishing / CIF-IFC (10.5558, 10.1139) | 1 | 5 | 403 |
| MDPI (10.3390) | 1 | 3 | 403 on `/pdf` |
| BioOne (10.1603, 10.1890, 10.2307, 10.3732, 10.1600) | 4 | 5 | 403 or HTML page |
| Royal Society (10.1098) | 2 | 2 | 403; PMC copies are author manuscripts outside the open bucket |
| Oxford Academic (10.1093) | 2 | 1 | 403 |
| Zenodo / figshare deposits listed as the article (10.5281) | 0 | 2 | no PDF location at all |
| Others (Hindawi, IWA, CONICET, university repositories, …) | 1 | 6 | 403, dead repositories, HTML pages |

## Rules

- **Open-access copies only.** These articles are open access; the browser fetches the publisher's own open PDF. No Sci-Hub, no EZproxy, no subscriber-only content.
- **No evasion of bot protection.** No stealth plugins, spoofed fingerprints or CAPTCHA solvers. A person may click through a challenge in the visible browser, as any reader would.
- **Polite:** one article at a time, at least 3 s between pages on the same host.
- **Held-out discipline:** for the 37 held-out records, handle metadata only: DOI, URL, the `%PDF` header, SHA-256 and page count. Never open, read or summarise their text. The script must not print or log PDF text.
- **No PDF in git:** PDFs stay git-ignored. The manifest, the script and the recipes make the corpus reproducible.

## Work units

### D1: Desktop setup `haiku`

**files:** none (setup notes go in D5's report)

- Clone the repo on the Windows desktop (MSYS2 / Git Bash), check out the branch, `uv sync`.
- `uv pip install playwright`. Use the installed Google Chrome (`channel="chrome"`), not a downloaded Chromium.
- Use a dedicated, persistent Chrome profile for this work (e.g. `%LOCALAPPDATA%\llm_metadata\chrome-profile`), so cookies from a challenge solved once are kept, and the personal profile stays untouched.
- Debug mode: start Chrome with `--remote-debugging-port=9222 --user-data-dir=<profile>`. The script then attaches with `chromium.connect_over_cdp("http://localhost:9222")`, so a person can watch, open DevTools, and take over by hand.

### D2: Browser download script `sonnet`

**deps:** D1 | **files:** `scripts/fetch_pdfs_browser.py`, `src/llm_metadata/publisher_pdf.py`, `tests/test_publisher_pdf.py`

- **Input:** the rows of `oa_corpus_pdfs.csv` whose status is not `ok`, optionally filtered with `--split dev|heldout` and `--publisher`.
- **For each record:**
  1. Open the DOI landing page in the headed browser.
  2. Try the publisher recipe from `publisher_pdf.py` (the PDF link read from the page, or a URL pattern).
  3. Catch the PDF through the `download` event, or by reading the response body when the PDF opens inline.
- **Fallback:** when no recipe works, pause and let the person find the PDF by hand (`--manual`). The script records the final URL the person reached; that URL becomes the candidate recipe.
- **Validate each file:** `%PDF` header, PyMuPDF page count, SHA-256. Save it as `data/pdfs/fuster/<doi_stem>.pdf`.
- **Update the table:** `pdf_url_used`, `pdf_source = browser` or `browser_manual`, licence (kept from OpenAlex/Unpaywall), `sha256`, `pages`, `status`, and a new `fetched_on` column.
- **Resumable:** skip records already `ok`; write the CSV after each record.
- **Logging:** a log of each step (URL, HTTP status, page title, outcome), with no PDF content in it.

### D3: Recipes per publisher `sonnet` (with a person at the desktop)

**deps:** D2 | **files:** `src/llm_metadata/publisher_pdf.py`, `docs/results/corpus_report.md`

- Work through the publishers one at a time, Wiley first (16 records).
- For each publisher, find in DevTools how the open PDF is reached:
  - which link on the landing page;
  - whether an `epdf` viewer stands in front of a `pdfdirect` URL;
  - whether the download needs a cookie set by the landing page;
  - whether a challenge comes back.
- Write each working recipe as a small documented function with its date of verification, plus a test with mocked HTML.
- Record what never works, and why (for example: the PDF exists only behind a challenge; a manuscript held only in PMC as an author version).
- The two Zenodo or figshare deposits (held-out) have no article PDF. Record them as `no_article_pdf` and leave them as they are.

### D4: Transfer and registration on the server `haiku`

**deps:** D3 | **files:** `data/manifests/oa_corpus_pdfs.csv`, `data/manifests/*_data_paper.csv`, `data/manifests/*_with_pdf.csv`

- Copy the new PDFs to the server: `scp` or `rsync` into `~/code/llm_metadata/data/pdfs/fuster/`. Never through git or OneDrive.
- On the server, check every SHA-256 against the CSV.
- Rerun `scripts/rebuild_oa_corpus.py` so that the manifests (`dev_subset_with_pdf.csv`, `heldout_with_pdf.csv`) pick up the new files.
- Commit the updated CSVs and the recipes, never the PDFs.

### D5: Report and decision on the long-text results `opus`

**deps:** D4 | **files:** `docs/results/corpus_report.md`, `notebooks/README.md`, `plans/anthropic-article-results.md`

- Update the coverage report: by split, publisher and licence, which recipe worked, and what stays unreachable.
- **Decision for Vincent before any API spending:** the held-out pass was run once, with a frozen configuration. Running the same frozen long-text conditions on the newly covered held-out records extends the sample; it does not tune anything. The options:
  - **(a)** Run the eight frozen conditions only on the new records (estimated 0.15 to 0.30 USD for about 35 PDFs), then report the full long-text sample. The runner's "already run" guard needs a `--records` option for this.
  - **(b)** Keep the current results and report the coverage gap as a limit.
- New dev PDFs (up to 14) may be used for further dev work only; they do not change the frozen configuration.

## Execution rounds

```
Round 1: D1, then D2 (script tested on dev records first, with a person watching)
Round 2: D3, one publisher at a time, Wiley first
Round 3: D4, then D5 (decision on option a or b)
```

## Done

- [ ] Desktop setup documented (Chrome profile, debug port, how to attach)
- [ ] `scripts/fetch_pdfs_browser.py` committed, resumable, no PDF text in logs
- [ ] One recipe per publisher that works, with tests and a verification date; non-working cases explained
- [ ] New PDFs on the server, SHA-256 checked, manifests rebuilt and committed (no PDF in git)
- [ ] Coverage report updated; decision on the long-text held-out extension recorded in `notebooks/README.md`
