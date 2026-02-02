"""
Download all article PDFs for the Fuster analysis.

Reads DOI mapping from data/dataset_article_mapping.csv, fetches OpenAlex
metadata, and downloads PDFs using the multi-strategy fallback chain.
Skips Zenodo-hosted DOIs (10.5281/zenodo.*).

Usage:
    uv run --env-file .env python scripts/download_all_fuster_pdfs.py
"""

import argparse
import logging
import time
from pathlib import Path

import pandas as pd

from llm_metadata.openalex import get_work_by_doi, extract_pdf_url
from llm_metadata.pdf_download import download_pdf_with_fallback

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("download_fuster_pdfs")

MAPPING_PATH = Path("data/dataset_article_mapping.csv")
OUTPUT_DIR = Path("data/pdfs/fuster")
MANIFEST_PATH = OUTPUT_DIR / "manifest.csv"

# Delay between OpenAlex API requests (polite crawling)
API_DELAY = 1.0
# Delay between download attempts
DOWNLOAD_DELAY = 0.5


def load_article_dois(mapping_path: Path) -> pd.DataFrame:
    """Load dataset-article mapping and return rows with valid article DOIs."""
    df = pd.read_csv(mapping_path, dtype=str)
    df.columns = [c.strip() for c in df.columns]
    df["article_doi"] = df["article_doi"].fillna("").str.strip()

    # Keep only rows with an article DOI
    df = df[df["article_doi"] != ""].copy()

    # Skip Zenodo-hosted DOIs (not journal articles)
    zenodo_mask = df["article_doi"].str.startswith("10.5281/zenodo")
    skipped = zenodo_mask.sum()
    if skipped:
        logger.info(f"Skipping {skipped} Zenodo-hosted DOI(s)")
    df = df[~zenodo_mask].copy()

    # Skip rows with multiple DOIs (semicolon-separated, can't resolve)
    multi_mask = df["article_doi"].str.contains(";")
    skipped_multi = multi_mask.sum()
    if skipped_multi:
        logger.info(f"Skipping {skipped_multi} row(s) with multiple DOIs")
    df = df[~multi_mask].copy()

    df.reset_index(drop=True, inplace=True)
    return df


def fetch_openalex_works(dois: list[str]) -> dict:
    """Fetch OpenAlex metadata for each DOI. Returns {doi: work_dict_or_None}."""
    cache = {}
    for doi in dois:
        logger.info(f"Fetching OpenAlex work for {doi}")
        try:
            work = get_work_by_doi(doi)
            cache[doi] = work
            if work:
                oa = work.get("open_access", {})
                logger.info(
                    f"  Found: OA={oa.get('oa_status', 'unknown')}"
                )
            else:
                logger.warning(f"  Not found in OpenAlex")
        except Exception as e:
            logger.error(f"  Error: {e}")
            cache[doi] = None
        time.sleep(API_DELAY)
    return cache


def download_all(
    df: pd.DataFrame,
    works_cache: dict,
    output_dir: Path,
    ezproxy_cookies: dict | None = None,
) -> pd.DataFrame:
    """Download PDFs for all rows. Returns results DataFrame."""
    results = []

    for _, row in df.iterrows():
        doi = row["article_doi"]
        dataset_doi = row.get("dataset_doi", "")
        source = row.get("source", "")
        title = row.get("title", "")

        work = works_cache.get(doi)

        record = {
            "article_doi": doi,
            "dataset_doi": dataset_doi,
            "source": source,
            "title": title,
            "openalex_id": work.get("id") if work else None,
            "oa_status": work.get("open_access", {}).get("oa_status")
            if work
            else None,
            "is_oa": work.get("open_access", {}).get("is_oa") if work else False,
            "openalex_pdf_url": None,
            "downloaded_pdf_path": None,
            "status": "pending",
            "error": None,
        }

        if not work:
            record["status"] = "no_openalex_work"
            record["error"] = "OpenAlex work not found"
            results.append(record)
            continue

        openalex_pdf_url = extract_pdf_url(work)
        record["openalex_pdf_url"] = openalex_pdf_url

        logger.info(f"Downloading PDF for {doi}")
        try:
            pdf_path = download_pdf_with_fallback(
                doi=doi,
                openalex_pdf_url=openalex_pdf_url,
                output_dir=output_dir,
                use_unpaywall=True,
                ezproxy_cookies=ezproxy_cookies,
            )
            if pdf_path:
                record["status"] = "downloaded"
                record["downloaded_pdf_path"] = str(pdf_path)
                logger.info(f"  Downloaded: {pdf_path.name}")
            else:
                record["status"] = "failed"
                record["error"] = "All download strategies failed"
                logger.warning(f"  Failed: all strategies exhausted")
        except Exception as e:
            record["status"] = "error"
            record["error"] = str(e)
            logger.error(f"  Error: {e}")

        results.append(record)
        time.sleep(DOWNLOAD_DELAY)

    return pd.DataFrame(results)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--use-ezproxy",
        action="store_true",
        help="Try to extract EZproxy cookies from Firefox for paywalled content",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=OUTPUT_DIR,
        help=f"Output directory for PDFs (default: {OUTPUT_DIR})",
    )
    args = parser.parse_args()

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load DOIs
    assert MAPPING_PATH.exists(), f"Mapping file not found: {MAPPING_PATH}"
    df = load_article_dois(MAPPING_PATH)
    logger.info(f"Loaded {len(df)} article DOIs to download")

    # Optional EZproxy cookies
    ezproxy_cookies = None
    if args.use_ezproxy:
        try:
            from llm_metadata.ezproxy import extract_cookies_from_browser

            ezproxy_cookies = extract_cookies_from_browser(browser="firefox")
            logger.info("EZproxy cookies extracted")
        except Exception as e:
            logger.warning(f"Could not extract EZproxy cookies: {e}")

    # Fetch OpenAlex metadata
    unique_dois = df["article_doi"].unique().tolist()
    works_cache = fetch_openalex_works(unique_dois)

    found = sum(1 for w in works_cache.values() if w is not None)
    logger.info(f"OpenAlex: {found}/{len(works_cache)} works found")

    # Download PDFs
    results_df = download_all(df, works_cache, output_dir, ezproxy_cookies)

    # Save manifest
    manifest_path = output_dir / "manifest.csv"
    results_df.to_csv(manifest_path, index=False)
    logger.info(f"Manifest saved: {manifest_path}")

    # Summary
    status_counts = results_df["status"].value_counts()
    print("\n" + "=" * 60)
    print("DOWNLOAD SUMMARY")
    print("=" * 60)
    for status, count in status_counts.items():
        print(f"  {status:25s}: {count}")
    print(f"\n  Total: {len(results_df)}")
    print(f"  Manifest: {manifest_path}")


if __name__ == "__main__":
    main()
