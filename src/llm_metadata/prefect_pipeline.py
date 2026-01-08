from prefect import task, flow
from prefect.task_runners import ThreadPoolTaskRunner

from pydantic import BaseModel
from typing import Optional, List
from pathlib import Path
import pandas as pd

from llm_metadata.zenodo import get_record_by_doi, get_record_by_doi_list
from llm_metadata.gpt_classify import classify_abstract
from llm_metadata.schemas import DatasetFeatureExtraction
from llm_metadata.openalex import get_works_by_filters_all
from llm_metadata.schemas.openalex_work import OpenAlexWork, work_dict_to_model, works_to_dict_list
from llm_metadata.pdf_download import download_pdf

@task
def fetch_abstract(doi: str) -> str:
    record = get_record_by_doi(doi)
    if record and 'metadata' in record and 'description' in record['metadata']:
        return record['metadata']['description']
    else:
        raise ValueError(f"No abstract found for DOI: {doi}")

@task
def fetch_abstracts(dois: List[str]) -> List[str]:
    abstracts = []
    for i in range(0, len(dois), 20):
        batch = dois[i:i+20]
        records = get_record_by_doi_list(batch)
        for record in records:
            if 'metadata' in record and 'description' in record['metadata']:
                abstracts.append(record['metadata']['description'])
            else:
                abstracts.append(None)
    return abstracts

@task
def classify_abstract_task(abstract: str, response_format:BaseModel = DatasetFeatureExtraction) -> dict:
    classification = classify_abstract(abstract, response_format=response_format)
    return classification

@flow(task_runner=ThreadPoolTaskRunner(max_workers=10))
def doi_classification_pipeline(dois: List[str]) -> List:
    abstracts = fetch_abstracts(dois)
    futures = classify_abstract_task.map(abstracts, )
    return futures.result()

# ============================================================================
# OpenAlex Quebec Ecology Papers Pipeline
# ============================================================================

@task
def fetch_quebec_ecology_papers(
    ror_id: str = "https://ror.org/00kybxq39",
    year: int = 2025,
    keywords: str = "ecology",
    max_results: Optional[int] = None
) -> List[OpenAlexWork]:
    """
    Fetch ecology papers from Quebec institution.

    Args:
        ror_id: Institution ROR ID (default: Université de Sherbrooke)
        year: Publication year (default: 2025)
        keywords: Search keywords (default: "ecology")
        max_results: Limit results for testing (None = all)

    Returns:
        List of OpenAlexWork models
    """
    works = get_works_by_filters_all(
        ror_id=ror_id,
        publication_year=year,
        keywords=keywords,
        is_oa=True,
        max_results=max_results
    )
    return [work_dict_to_model(w) for w in works]


@task
def download_pdf_task(work: OpenAlexWork) -> Optional[Path]:
    """
    Download PDF for a single work.

    Args:
        work: OpenAlexWork model

    Returns:
        Path to downloaded PDF or None on failure
    """
    if not work.pdf_url or not work.doi:
        return None

    return download_pdf(
        pdf_url=work.pdf_url,
        doi=work.doi,
        year=work.publication_year
    )


@task
def save_works_to_csv(works: List[OpenAlexWork], output_path: Path):
    """
    Save works metadata to CSV.

    Args:
        works: List of OpenAlexWork models
        output_path: Path to output CSV file
    """
    df = pd.DataFrame(works_to_dict_list(works))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    print(f"Saved {len(works)} works to {output_path}")


@flow(task_runner=ThreadPoolTaskRunner(max_workers=5))
def quebec_papers_pipeline(
    ror_id: str = "https://ror.org/00kybxq39",
    year: int = 2025,
    keywords: str = "ecology",
    download_pdfs: bool = True,
    max_results: Optional[int] = None,
    output_dir: Path = Path("data")
) -> List[OpenAlexWork]:
    """
    End-to-end pipeline for Quebec ecology papers.

    Steps:
    1. Fetch works from OpenAlex
    2. Download PDFs (optional, parallel)
    3. Store metadata to CSV

    Args:
        ror_id: Institution ROR ID
        year: Publication year
        keywords: Search keywords
        download_pdfs: Whether to download PDFs
        max_results: Limit results for testing
        output_dir: Output directory for CSV and PDFs

    Returns:
        List of work models with PDF paths populated
    """
    # Fetch works
    print(f"Fetching papers for {ror_id}, year={year}, keywords='{keywords}'...")
    works = fetch_quebec_ecology_papers(
        ror_id=ror_id,
        year=year,
        keywords=keywords,
        max_results=max_results
    )
    print(f"Fetched {len(works)} works")

    # Download PDFs in parallel
    if download_pdfs:
        print(f"Downloading PDFs (parallel, max_workers=5)...")
        pdf_paths = download_pdf_task.map(works)

        # Update work models with local PDF paths
        for work, pdf_path_future in zip(works, pdf_paths):
            pdf_path = pdf_path_future.result()
            if pdf_path:
                work.local_pdf_path = pdf_path

        successful_downloads = sum(1 for w in works if w.local_pdf_path)
        print(f"Successfully downloaded {successful_downloads}/{len(works)} PDFs")

    # Save metadata to CSV
    csv_path = output_dir / f"quebec_papers_{year}.csv"
    save_works_to_csv(works, csv_path)

    return works


if __name__ == "__main__":
    # Example 1: Original Zenodo pipeline
    # results = doi_classification_pipeline(dois=["10.5061/dryad.2n5h6"])
    # print(results)

    # Example 2: Quebec ecology papers pipeline (test mode)
    print("Testing Quebec ecology papers pipeline...")
    works = quebec_papers_pipeline(
        ror_id="https://ror.org/00kybxq39",
        year=2024,  # Use 2024 for testing (2025 may have few results)
        keywords="ecology",
        download_pdfs=True,
        max_results=5  # Small test
    )
    print(f"\n✅ Pipeline complete! Retrieved {len(works)} works")