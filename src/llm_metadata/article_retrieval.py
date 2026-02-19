"""
Article DOI retrieval from Dryad/Zenodo datasets.

This module implements the recommended workflow for retrieving article DOIs:
1. Check cited_articles column in Excel (fast, primary method)
2. Query repository API if cited_articles is empty (fallback method)
3. Use Semantic Scholar API to retrieve citing papers for any dataset (SS-3.2)
"""

import logging
import pandas as pd
from typing import Optional, Dict, Any, List
from llm_metadata.dryad import get_dataset
from llm_metadata.zenodo import get_record_by_doi
from llm_metadata.openalex import get_work_by_doi
from llm_metadata.semantic_scholar import (
    get_open_access_pdf_url,
    get_paper_by_doi,
    get_paper_by_title,
    get_paper_citations,
)

logger = logging.getLogger(__name__)


def extract_doi_from_url(url: str) -> str:
    """Extract DOI from URL (handles both https://doi.org/ and bare DOIs)"""
    if pd.isna(url):
        return None
    url = str(url).strip()
    if url.startswith('https://doi.org/'):
        return url.replace('https://doi.org/', '')
    elif url.startswith('http://doi.org/'):
        return url.replace('http://doi.org/', '')
    return url


def get_article_doi_from_excel(row: pd.Series) -> Optional[str]:
    """
    Extract article DOI from Excel cited_articles column.

    Returns:
        Article DOI string or None if not found
    """
    cited_articles = row.get('cited_articles')
    if pd.notna(cited_articles):
        # Clean and extract DOI
        article_doi = extract_doi_from_url(cited_articles)
        return article_doi
    return None


def get_article_doi_from_dryad_api(dataset_url: str) -> Optional[str]:
    """
    Query Dryad API for article DOI via relatedWorks field.

    Args:
        dataset_url: Dryad dataset URL (https://doi.org/...)

    Returns:
        Article DOI string or None if not found
    """
    try:
        doi = extract_doi_from_url(dataset_url)
        if not doi:
            return None

        # Add 'doi:' prefix if not present
        if not doi.startswith('doi:'):
            doi = f'doi:{doi}'

        dataset = get_dataset(doi)

        if dataset and 'relatedWorks' in dataset:
            for work in dataset['relatedWorks']:
                # Look for primary article
                if work.get('relationship') == 'primary_article':
                    article_identifier = work.get('identifier', '')
                    return extract_doi_from_url(article_identifier)

        return None
    except Exception as e:
        print(f"Error querying Dryad API for {dataset_url}: {e}")
        return None


def get_article_doi_from_zenodo_api(dataset_url: str) -> Optional[str]:
    """
    Query Zenodo API for article DOI via related_identifiers field.

    Args:
        dataset_url: Zenodo dataset URL (https://doi.org/...)

    Returns:
        Article DOI string or None if not found
    """
    try:
        doi = extract_doi_from_url(dataset_url)
        if not doi:
            return None

        record = get_record_by_doi(doi)

        if record and 'metadata' in record:
            metadata = record['metadata']

            # Check related_identifiers
            if 'related_identifiers' in metadata:
                for rel_id in metadata['related_identifiers']:
                    # Look for 'isCitedBy' or 'isSupplementTo' relationships
                    relation = rel_id.get('relation', '')
                    if relation in ['isCitedBy', 'isSupplementTo', 'isReferencedBy']:
                        return rel_id.get('identifier')

        return None
    except Exception as e:
        print(f"Error querying Zenodo API for {dataset_url}: {e}")
        return None


def retrieve_article_doi(row: pd.Series) -> Dict[str, str]:
    """
    Retrieve article DOI using recommended workflow:
    1. Check Excel cited_articles column
    2. Fall back to API query based on source

    Args:
        row: DataFrame row with columns: url, source, cited_articles

    Returns:
        Dict with keys: article_doi, retrieval_method
    """
    result = {
        'article_doi': None,
        'retrieval_method': None
    }

    # Step 1: Check Excel
    article_doi = get_article_doi_from_excel(row)
    if article_doi:
        result['article_doi'] = article_doi
        result['retrieval_method'] = 'excel'
        return result

    # Step 2: Fall back to API
    source = row.get('source', '').lower()
    dataset_url = row.get('url')

    if source == 'dryad':
        article_doi = get_article_doi_from_dryad_api(dataset_url)
        if article_doi:
            result['article_doi'] = article_doi
            result['retrieval_method'] = 'dryad_api'

    elif source == 'zenodo':
        article_doi = get_article_doi_from_zenodo_api(dataset_url)
        if article_doi:
            result['article_doi'] = article_doi
            result['retrieval_method'] = 'zenodo_api'

    return result


def enrich_article_metadata(article_doi: str) -> Dict[str, Any]:
    """Query OpenAlex (+ Semantic Scholar fallback) for journal_url, pdf_url, is_oa.

    Args:
        article_doi: Article DOI (with or without https://doi.org/ prefix)

    Returns:
        Dict with keys: journal_url, pdf_url, is_oa (all Optional)
    """
    result: Dict[str, Any] = {'journal_url': None, 'pdf_url': None, 'is_oa': None}

    work = get_work_by_doi(article_doi)
    if work:
        oa = work.get('open_access') or {}
        result['is_oa'] = oa.get('is_oa')

        best_oa = work.get('best_oa_location') or {}
        result['journal_url'] = best_oa.get('landing_page_url')
        result['pdf_url'] = best_oa.get('pdf_url')

    # Semantic Scholar fallback for pdf_url
    if not result['pdf_url']:
        result['pdf_url'] = get_open_access_pdf_url(article_doi)

    return result


def get_cited_articles_for_dataset(
    dataset_title: str,
    dataset_doi: Optional[str] = None,
    citation_limit: int = 100,
) -> List[Dict[str, Any]]:
    """Retrieve articles that cite a dataset using the Semantic Scholar API.

    Searches for the dataset in Semantic Scholar by DOI (preferred) or title,
    then retrieves the list of papers that cite it.  Each returned entry
    includes the citing paper's Semantic Scholar ID, title, abstract, year,
    DOI (if available), and the method used to locate the dataset.

    Args:
        dataset_title: Title of the dataset (used as fallback when DOI lookup fails)
        dataset_doi: Dataset DOI (with or without https://doi.org/ prefix)
        citation_limit: Maximum number of citing papers to retrieve

    Returns:
        List of dicts, each with keys:
            - citing_paper_id: Semantic Scholar paper ID
            - citing_paper_doi: DOI of citing paper (may be None)
            - citing_paper_title: Title of citing paper
            - citing_paper_abstract: Abstract of citing paper (may be None)
            - citing_paper_year: Publication year (may be None)
            - retrieval_method: "by_doi" | "by_title" | "not_found"

    Example:
        >>> articles = get_cited_articles_for_dataset(
        ...     "Camera trap dataset for mammal biodiversity",
        ...     dataset_doi="10.5061/dryad.abc123"
        ... )
        >>> print(f"Found {len(articles)} citing articles")
    """
    ss_paper = None
    retrieval_method = "not_found"

    # Step 1: lookup by DOI (most reliable)
    if dataset_doi:
        try:
            ss_paper = get_paper_by_doi(dataset_doi)
            if ss_paper:
                retrieval_method = "by_doi"
                logger.debug("Found dataset in SS by DOI: %s", dataset_doi)
        except Exception as exc:
            logger.warning("SS DOI lookup failed for %s: %s", dataset_doi, exc)

    # Step 2: fallback to title search
    if ss_paper is None and dataset_title:
        try:
            ss_paper = get_paper_by_title(dataset_title)
            if ss_paper:
                retrieval_method = "by_title"
                logger.debug("Found dataset in SS by title: %s", dataset_title[:60])
        except Exception as exc:
            logger.warning("SS title search failed for '%s': %s", dataset_title[:60], exc)

    if ss_paper is None:
        logger.debug("Dataset not found in Semantic Scholar: %s", dataset_title[:60])
        return []

    # Step 3: retrieve citing papers
    paper_id = ss_paper.get("paperId")
    if not paper_id:
        return []

    try:
        citing_papers = get_paper_citations(paper_id, limit=citation_limit)
    except Exception as exc:
        logger.warning("SS citation lookup failed for paper %s: %s", paper_id, exc)
        return []

    results: List[Dict[str, Any]] = []
    for paper in citing_papers:
        external_ids = paper.get("externalIds") or {}
        doi = external_ids.get("DOI")
        results.append(
            {
                "citing_paper_id": paper.get("paperId"),
                "citing_paper_doi": doi,
                "citing_paper_title": paper.get("title"),
                "citing_paper_abstract": paper.get("abstract"),
                "citing_paper_year": paper.get("year"),
                "retrieval_method": retrieval_method,
            }
        )

    return results


def generate_cited_articles_csv(
    validated_xlsx: str,
    output_csv: str = "data/semantic_scholar_cited_articles.csv",
    citation_limit: int = 100,
) -> pd.DataFrame:
    """Use Semantic Scholar API to retrieve citing articles for all valid datasets.

    For each valid record in the validated Excel file, searches Semantic Scholar
    by dataset DOI (if available) or title, then retrieves citing papers.  The
    results are stored as a flat CSV with one row per citing-paper/dataset pair,
    following the same conventions as ``dataset_article_mapping.csv``.

    Only processes records that do **not** already have a ``cited_article_doi``
    set, so this supplements (rather than replaces) the Excel-based retrieval.

    Args:
        validated_xlsx: Path to the validated Excel file (dataset_092624_validated.xlsx)
        output_csv: Destination path for the output CSV
        citation_limit: Maximum citing papers to retrieve per dataset

    Returns:
        DataFrame written to ``output_csv``
    """
    df = pd.read_excel(validated_xlsx)
    valid_df = df[df["valid_yn"] == "yes"].copy()

    logger.info("Processing %d valid records for SS citation retrieval", len(valid_df))

    rows: List[Dict[str, Any]] = []
    not_found = 0
    found = 0

    for _, row in valid_df.iterrows():
        dataset_doi = row.get("source_url") or row.get("url")
        if pd.notna(dataset_doi):
            dataset_doi = str(dataset_doi).strip()
            # Only treat it as a DOI if it looks like one (contains doi.org or starts with 10.)
            if "doi.org/" in dataset_doi:
                dataset_doi = dataset_doi.split("doi.org/")[-1]
            elif dataset_doi.startswith("10."):
                pass  # already clean
            else:
                dataset_doi = None  # not a resolvable DOI
        else:
            dataset_doi = None

        title = row.get("title") or ""
        citing_articles = get_cited_articles_for_dataset(
            dataset_title=str(title),
            dataset_doi=dataset_doi,
            citation_limit=citation_limit,
        )

        if citing_articles:
            found += 1
            for article in citing_articles:
                rows.append(
                    {
                        "dataset_id": row.get("id"),
                        "dataset_doi": dataset_doi,
                        "dataset_title": title,
                        "dataset_source": row.get("source"),
                        **article,
                    }
                )
        else:
            not_found += 1

    logger.info(
        "SS citation retrieval complete: %d datasets with results, %d not found",
        found,
        not_found,
    )

    result_df = pd.DataFrame(rows)
    result_df.to_csv(output_csv, index=False)
    logger.info("Saved %d citing-article rows to %s", len(result_df), output_csv)
    return result_df


def process_dataset(excel_path: str, output_csv: str = 'data/dataset_article_mapping.csv'):
    """
    Process all valid datasets and create CSV mapping dataset DOIs to article DOIs.

    Args:
        excel_path: Path to input Excel file
        output_csv: Path to output CSV file
    """
    print(f"Loading dataset from: {excel_path}")
    df = pd.read_excel(excel_path)

    # Filter for valid datasets only
    valid_df = df[df['valid_yn'] == 'yes'].copy()
    print(f"\nTotal datasets: {len(df)}")
    print(f"Valid datasets: {len(valid_df)}")

    # Initialize results columns
    valid_df['article_doi'] = None
    valid_df['retrieval_method'] = None

    # Process each valid dataset
    print("\nRetrieving article DOIs...")
    for idx, row in valid_df.iterrows():
        result = retrieve_article_doi(row)
        valid_df.at[idx, 'article_doi'] = result['article_doi']
        valid_df.at[idx, 'retrieval_method'] = result['retrieval_method']

        # Progress indicator
        if (idx + 1) % 20 == 0:
            print(f"Processed {idx + 1}/{len(valid_df)} datasets...")

    # Calculate coverage statistics
    total_valid = len(valid_df)
    with_article_doi = valid_df['article_doi'].notna().sum()
    from_excel = (valid_df['retrieval_method'] == 'excel').sum()
    from_api = valid_df['retrieval_method'].notna().sum() - from_excel

    print(f"\n{'='*80}")
    print("ARTICLE DOI COVERAGE STATISTICS")
    print(f"{'='*80}")
    print(f"Total valid datasets: {total_valid}")
    print(f"With article DOIs: {with_article_doi} ({with_article_doi/total_valid*100:.1f}%)")
    print(f"\nRetrieval methods:")
    print(f"  - Excel cited_articles: {from_excel} ({from_excel/total_valid*100:.1f}%)")
    print(f"  - API queries: {from_api} ({from_api/total_valid*100:.1f}%)")

    # Breakdown by source
    print(f"\n{'='*80}")
    print("COVERAGE BY SOURCE")
    print(f"{'='*80}")
    for source in valid_df['source'].unique():
        source_df = valid_df[valid_df['source'] == source]
        total_source = len(source_df)
        with_doi_source = source_df['article_doi'].notna().sum()
        print(f"{source:20s}: {with_doi_source:3d}/{total_source:3d} ({with_doi_source/total_source*100:5.1f}%)")

    # Create output CSV
    output_df = valid_df[['id', 'url', 'source', 'title', 'article_doi', 'retrieval_method']]
    output_df = output_df.rename(columns={'url': 'dataset_url'})

    # Extract dataset DOI for cleaner output
    output_df['dataset_doi'] = output_df['dataset_url'].apply(extract_doi_from_url)
    output_df = output_df[['id', 'dataset_doi', 'article_doi', 'source', 'retrieval_method', 'title']]

    # Save to CSV
    output_df.to_csv(output_csv, index=False)
    print(f"\n✅ Results saved to: {output_csv}")

    return output_df


if __name__ == "__main__":
    import os
    from pathlib import Path
    from dotenv import load_dotenv

    # Load environment variables
    dotenv_path = Path('.env')
    load_dotenv(dotenv_path)

    # Process dataset
    excel_path = 'data/dataset_092624.xlsx'
    output_csv = 'data/dataset_article_mapping.csv'

    result_df = process_dataset(excel_path, output_csv)

    print("\nFirst 10 results:")
    print(result_df.head(10).to_string())
