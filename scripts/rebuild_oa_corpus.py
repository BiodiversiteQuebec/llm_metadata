"""Rebuild the open-access corpus (98 valid, open-access Fuster records).

Steps
1. Build the manifests through ``DataPaperManifest`` (corpus, held-out, dev).
2. Download each article PDF from OPEN sources only (manifest URL, OpenAlex,
   Unpaywall, Europe PMC, repository copies, then Chromium via Playwright if it
   is installed). No Sci-Hub, no EZproxy.
3. Write ``data/manifests/oa_corpus_pdfs.csv`` (URL, licence, SHA-256, pages).

Held-out discipline: for held-out records this script only checks the ``%PDF``
header, the page count and the SHA-256. It never extracts or prints text.

Run:  uv run python scripts/rebuild_oa_corpus.py
Options: --no-download (manifests and PDF table only, from files on disk),
         --chromium (try Chromium for records still missing).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import time
from pathlib import Path
from urllib.parse import quote, unquote, urlparse

import fitz  # PyMuPDF
import pandas as pd
import requests

from llm_metadata.doi_utils import doi_filename_stem
from llm_metadata.schemas.data_paper import DataPaperManifest

ROOT = Path(__file__).resolve().parents[1]
GT_PATH = "data/dataset_092624_validated.xlsx"
MANIFEST_DIR = ROOT / "data" / "manifests"
PDF_DIR_REL = "data/pdfs/fuster"
CACHE_DIR = ROOT / "artifacts" / "oa_corpus_cache"
EMAIL = "vincent.beauregard@usherbrooke.ca"
API_UA = f"llm_metadata-corpus-rebuild (mailto:{EMAIL})"
BROWSER_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)
MIN_DELAY = 1.1  # seconds between requests to the same host
TIMEOUT = 40

PDF_COLUMNS = [
    "gt_record_id", "split", "source", "article_doi", "pdf_url_used", "pdf_source",
    "licence", "sha256", "pages", "status", "failure_reason",
]

_last_hit: dict[str, float] = {}
_session = requests.Session()


def throttle(url: str) -> None:
    host = urlparse(url).netloc
    wait = MIN_DELAY - (time.time() - _last_hit.get(host, 0.0))
    if wait > 0:
        time.sleep(wait)
    _last_hit[host] = time.time()


def get(url: str, *, api: bool = False, **kw) -> requests.Response:
    throttle(url)
    headers = {"User-Agent": API_UA if api else BROWSER_UA}
    if not api:
        headers["Accept"] = "application/pdf,text/html;q=0.8,*/*;q=0.5"
    return _session.get(url, headers=headers, timeout=TIMEOUT, allow_redirects=True, **kw)


def cached_json(name: str, url: str) -> dict | None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / name
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    try:
        resp = get(url, api=True)
        data = resp.json() if resp.status_code == 200 else {"_status": resp.status_code}
    except Exception as exc:  # network or JSON error: remember it, do not retry forever
        data = {"_error": str(exc)[:200]}
    path.write_text(json.dumps(data), encoding="utf-8")
    return data


# --- candidate URLs from open sources --------------------------------------

def candidates_for(doi: str, manifest_pdf_url: str | None) -> tuple[list[tuple[str, str]], str | None, dict]:
    """Return ([(source, url)], licence, notes). Order = order of attempts."""
    stem = doi_filename_stem(doi)
    cands: list[tuple[str, str]] = []
    licence: str | None = None
    notes: dict = {}

    oa = cached_json(f"{stem}_openalex.json", f"https://api.openalex.org/works/doi:{quote(doi, safe='/')}?mailto={EMAIL}")
    if oa and "id" in oa:
        best = oa.get("best_oa_location") or {}
        licence = best.get("license") or licence
        for loc in [best] + (oa.get("locations") or []):
            if loc and loc.get("pdf_url"):
                kind = "repository" if (loc.get("source") or {}).get("type") == "repository" else "openalex"
                cands.append((kind, loc["pdf_url"]))
            if loc and not licence and loc.get("license"):
                licence = loc["license"]
    else:
        notes["openalex"] = "no record"

    up = cached_json(f"{stem}_unpaywall.json", f"https://api.unpaywall.org/v2/{quote(doi, safe='/')}?email={EMAIL}")
    if up and "doi" in up:
        best = up.get("best_oa_location") or {}
        if best.get("license"):
            licence = licence or best["license"]
        for loc in [best] + (up.get("oa_locations") or []):
            if loc and loc.get("url_for_pdf"):
                kind = "repository" if loc.get("host_type") == "repository" else "unpaywall"
                cands.append((kind, loc["url_for_pdf"]))
            if loc and not licence and loc.get("license"):
                licence = loc["license"]
    else:
        notes["unpaywall"] = "no record"

    epmc = cached_json(
        f"{stem}_europepmc.json",
        "https://www.ebi.ac.uk/europepmc/webservices/rest/search?"
        f"query=DOI:%22{quote(doi, safe='/')}%22&format=json&resultType=core",
    )
    try:
        hit = (epmc or {}).get("resultList", {}).get("result", [None])[0]
    except (IndexError, AttributeError):
        hit = None
    if hit and hit.get("pmcid"):
        pmc = hit["pmcid"]
        cands.append(("europepmc", f"https://europepmc.org/backend/ptpmcrender.fcgi?accid={pmc}&blobtype=pdf"))
        cands.append(("europepmc", f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmc}/pdf/"))
        if not licence and hit.get("license"):
            licence = hit["license"]

    # The URL carried by the annotation file goes after the API ones: it is usually the publisher.
    if manifest_pdf_url:
        cands.append(("manifest", manifest_pdf_url))

    seen, ordered = set(), []
    for src, url in cands:
        if url not in seen and url.startswith("http"):
            seen.add(url)
            ordered.append((src, url))
    return ordered, licence, notes


# --- download and validation ------------------------------------------------

def inspect_pdf(path: Path) -> tuple[str, int] | None:
    """Return (sha256, pages) if path is a readable PDF, else None. Never reads text."""
    try:
        with path.open("rb") as fh:
            if not fh.read(5).startswith(b"%PDF"):
                return None
        with fitz.open(path) as doc:
            pages = doc.page_count
        if pages < 1:
            return None
        return hashlib.sha256(path.read_bytes()).hexdigest(), pages
    except Exception:
        return None


def try_url(url: str, dest: Path) -> str | None:
    """Download url to dest. Return None on success, else a short failure reason."""
    tmp = dest.with_suffix(".part")
    try:
        resp = get(url)
        if resp.status_code in (403, 406):  # some hosts block browser-like agents but accept an honest one
            resp = get(url, api=True)
        if resp.status_code != 200:
            return f"HTTP {resp.status_code} {urlparse(url).netloc}"
        body = resp.content
        if not body.startswith(b"%PDF"):
            # Landing page: follow the open citation_pdf_url meta tag once.
            m = re.search(rb'name=["\']citation_pdf_url["\']\s+content=["\']([^"\']+)', body[:200000]) or re.search(
                rb'content=["\']([^"\']+)["\']\s+name=["\']citation_pdf_url["\']', body[:200000]
            )
            if m:
                nxt = m.group(1).decode("utf-8", "ignore").replace("&amp;", "&")
                if nxt != url:
                    resp2 = get(nxt)
                    if resp2.status_code == 200 and resp2.content.startswith(b"%PDF"):
                        body = resp2.content
                    else:
                        return f"HTML page, linked PDF HTTP {resp2.status_code} {urlparse(nxt).netloc}"
            if not body.startswith(b"%PDF"):
                return f"HTML page, not a PDF ({urlparse(url).netloc})"
        tmp.write_bytes(body)
        if inspect_pdf(tmp) is None:
            tmp.unlink(missing_ok=True)
            return f"corrupt PDF ({urlparse(url).netloc})"
        tmp.replace(dest)
        return None
    except Exception as exc:
        tmp.unlink(missing_ok=True)
        return f"{type(exc).__name__} {urlparse(url).netloc}"


def try_chromium(doi: str, urls: list[str], dest: Path) -> str | None:
    """Last resort: real browser. Open sources only (DOI page and OA URLs)."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return "playwright not installed"
    targets = list(urls) + [f"https://doi.org/{doi}"]
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            ctx = browser.new_context(user_agent=BROWSER_UA, accept_downloads=True)
            for url in targets:
                page = ctx.new_page()
                try:
                    throttle(url)
                    resp = page.request.get(url, timeout=60000)
                    body = resp.body() if resp.ok else b""
                    if not body.startswith(b"%PDF"):
                        page.goto(url, wait_until="domcontentloaded", timeout=60000)
                        meta = page.locator('meta[name="citation_pdf_url"]').first
                        link = meta.get_attribute("content", timeout=3000) if meta.count() else None
                        if link:
                            throttle(link)
                            r2 = page.request.get(link, timeout=60000)
                            body = r2.body() if r2.ok else b""
                    if body.startswith(b"%PDF"):
                        tmp = dest.with_suffix(".part")
                        tmp.write_bytes(body)
                        if inspect_pdf(tmp):
                            tmp.replace(dest)
                            browser.close()
                            return None
                        tmp.unlink(missing_ok=True)
                except Exception:
                    pass
                finally:
                    page.close()
            browser.close()
    except Exception as exc:
        return f"chromium unavailable: {str(exc)[:80]}"
    return "chromium: no PDF served"


# --- main ---------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-download", action="store_true")
    ap.add_argument("--chromium", action="store_true", help="try Chromium for records still missing")
    args = ap.parse_args()

    gt = pd.read_excel(ROOT / GT_PATH)
    ids = {int(i) for i in gt[(gt.valid_yn == "yes") & (gt.is_oa == 1)].id}
    assert len(ids) == 98, len(ids)

    heldout_ids = [int(r["gt_record_id"]) for r in csv.DictReader((MANIFEST_DIR / "heldout_ids.csv").open())]
    freeze = json.loads((MANIFEST_DIR / "heldout_freeze.json").read_text())
    digest = hashlib.sha256(",".join(str(i) for i in sorted(heldout_ids)).encode()).hexdigest()
    assert len(heldout_ids) == 68 and digest == freeze["ids_sha256"], "held-out list does not match its frozen digest"
    assert set(heldout_ids) <= ids

    dev_manifest = DataPaperManifest.load_csv(MANIFEST_DIR / "dev_subset_data_paper.csv")
    dev_ids = {r.gt_record_id for r in dev_manifest}
    assert len(dev_ids) == 30 and dev_ids | set(heldout_ids) == ids and not dev_ids & set(heldout_ids)

    corpus = DataPaperManifest.build(pdf_manifest_path=None, subset_ids=ids, deduplicate_gt=True)
    assert len(corpus) == 98

    # File names: keep the dev file names already used, else the DOI stem.
    dev_names = {r.gt_record_id: Path(str(r.pdf_local_path).replace("\\", "/")).name for r in dev_manifest if r.pdf_local_path}
    prev_rows = {}
    pdfs_csv = MANIFEST_DIR / "oa_corpus_pdfs.csv"
    if pdfs_csv.exists():
        prev_rows = {int(r["gt_record_id"]): r for r in csv.DictReader(pdfs_csv.open(encoding="utf-8"))}

    (ROOT / PDF_DIR_REL).mkdir(parents=True, exist_ok=True)
    rows = []
    for rec in sorted(corpus, key=lambda r: r.gt_record_id):
        split = "dev" if rec.gt_record_id in dev_ids else "heldout"
        src = rec.source.value if rec.source else ""
        row = dict.fromkeys(PDF_COLUMNS, "")
        row.update(gt_record_id=rec.gt_record_id, split=split, source=src, article_doi=rec.article_doi or "")
        if not rec.article_doi:
            row.update(status="no_article", failure_reason="dataset has no linked article DOI")
            rows.append(row)
            continue
        api_doi = unquote(rec.article_doi)
        name = dev_names.get(rec.gt_record_id) or f"{doi_filename_stem(rec.article_doi)}.pdf"
        dest = ROOT / PDF_DIR_REL / name
        row["_dest"] = dest
        row["_pdf_rel"] = f"{PDF_DIR_REL}/{name}"

        if args.no_download:
            cands, licence, notes = [], None, {}
        else:
            cands, licence, notes = candidates_for(api_doi, rec.pdf_url)
        row["licence"] = licence or ""

        prev = prev_rows.get(rec.gt_record_id)
        info = inspect_pdf(dest) if dest.exists() else None
        errors: list[str] = []
        if info is not None:
            if prev and prev.get("sha256") == info[0] and prev.get("status") == "ok":
                row.update(pdf_url_used=prev["pdf_url_used"], pdf_source=prev["pdf_source"])
            else:
                row.update(pdf_source="preexisting")
        elif dest.exists():
            dest.unlink()  # not a real PDF: delete
        if info is None and not args.no_download:
            for source_kind, url in cands:
                err = try_url(url, dest)
                if err is None:
                    info = inspect_pdf(dest)
                    row.update(pdf_url_used=url, pdf_source=source_kind)
                    break
                errors.append(f"{source_kind}: {err}")
            if info is None and args.chromium:
                err = try_chromium(api_doi, [u for _, u in cands], dest)
                if err is None:
                    info = inspect_pdf(dest)
                    row.update(pdf_source="chromium", pdf_url_used=f"https://doi.org/{api_doi}")
                else:
                    errors.append(err)
        if info is not None:
            row.update(sha256=info[0], pages=info[1], status="ok")
        else:
            reasons = "; ".join(dict.fromkeys(errors)) or ("no open PDF location found" if not cands else "not attempted")
            if notes and not cands:
                reasons = "no open PDF location found (" + ", ".join(f"{k}: {v}" for k, v in notes.items()) + ")"
            row.update(status="unreachable", failure_reason=reasons[:300])
        rows.append(row)
        print(f"{rec.gt_record_id:>4} {split:8} {src:17} {row['status']:11} {row['pdf_source']:11} {row['failure_reason'][:70]}", flush=True)

    # Manifests through the contract module
    def with_paths(manifest: DataPaperManifest) -> DataPaperManifest:
        for r in rows:
            if r["status"] == "ok" and r["gt_record_id"] in manifest.by_id():
                manifest = manifest.with_pdf_path(r["gt_record_id"], r["_pdf_rel"])
        return manifest

    with_paths(corpus).save_csv(MANIFEST_DIR / "oa_corpus_data_paper.csv")
    held = DataPaperManifest.build(pdf_manifest_path=None, subset_ids=set(heldout_ids), deduplicate_gt=True)
    assert sorted(held.by_id()) == sorted(heldout_ids)
    with_paths(held).save_csv(MANIFEST_DIR / "heldout_data_paper.csv")

    # Dev manifest: same records and columns, POSIX separators, paths filled for new PDFs.
    dev_out = dev_manifest
    ok_paths = {r["gt_record_id"]: r["_pdf_rel"] for r in rows if r["status"] == "ok"}
    for rec in dev_manifest:
        if rec.gt_record_id in ok_paths:
            dev_out = dev_out.with_pdf_path(rec.gt_record_id, ok_paths[rec.gt_record_id])
        elif rec.pdf_local_path:
            dev_out = dev_out.with_pdf_path(rec.gt_record_id, rec.pdf_local_path.replace("\\", "/"))
    dev_out.save_csv(MANIFEST_DIR / "dev_subset_data_paper.csv")

    with pdfs_csv.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=PDF_COLUMNS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"ok: {sum(r['status'] == 'ok' for r in rows)} / {len(rows)}")


if __name__ == "__main__":
    main()
