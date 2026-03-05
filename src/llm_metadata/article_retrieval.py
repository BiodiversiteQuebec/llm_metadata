"""
Article DOI retrieval from Dryad/Zenodo datasets.

This module implements the recommended workflow for retrieving article DOIs:
1. Check cited_articles column in Excel (fast, primary method)
2. Query repository API if cited_articles is empty (fallback method)
"""

import pandas as pd
from typing import Optional, Dict, Any
from llm_metadata.dryad import get_dataset
from llm_metadata.zenodo import get_record_by_doi
from llm_metadata.openalex import get_work_by_doi
from llm_metadata.semantic_scholar import get_open_access_pdf_url
from llm_metadata import doi_utils


def get_article_doi_from_excel(row: pd.Series) -> Optional[str]:
    """
    Extract article DOI from Excel cited_articles column.

    Returns:
        Article DOI string or None if not found
    """
    cited_articles = row.get('cited_articles')
    if pd.notna(cited_articles):
        # Clean and extract DOI
        article_doi = doi_utils.strip_doi_prefix(str(cited_articles))
        return article_doi or None
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
        doi = doi_utils.strip_doi_prefix(str(dataset_url)) if dataset_url else None
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
                    return doi_utils.strip_doi_prefix(article_identifier) or None

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
        doi = doi_utils.strip_doi_prefix(str(dataset_url)) if dataset_url else None
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
    output_df['dataset_doi'] = output_df['dataset_url'].apply(
        lambda u: doi_utils.strip_doi_prefix(str(u)) if pd.notna(u) else None
    )
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
