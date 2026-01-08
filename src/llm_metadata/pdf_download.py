"""
PDF download module for scientific papers.

This module provides functions to download PDFs from URLs with error handling,
retry logic, and storage management. Designed for batch downloading of open
access scientific papers from OpenAlex and similar sources.
"""

import requests
import time
import logging
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Default storage directory
PDF_STORAGE_DIR = Path("data/pdfs")

# Download configuration
DEFAULT_TIMEOUT = 30  # seconds
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds (exponential backoff)


def sanitize_doi(doi: str) -> str:
    """
    Sanitize DOI for use as filename.

    Replaces characters that are problematic in filenames.

    Args:
        doi: DOI string (e.g., "10.1371/journal.pone.0128238")

    Returns:
        Sanitized string safe for filename (e.g., "10.1371_journal.pone.0128238")

    Example:
        >>> sanitize_doi("10.1371/journal.pone.0128238")
        '10.1371_journal.pone.0128238'
    """
    # Remove common prefixes
    doi = doi.replace("https://doi.org/", "")
    doi = doi.replace("http://doi.org/", "")
    doi = doi.replace("doi:", "")

    # Replace problematic characters
    sanitized = doi.replace("/", "_").replace("\\", "_")
    sanitized = sanitized.replace(":", "_").replace(" ", "_")

    return sanitized


def download_pdf(
    pdf_url: str,
    doi: str,
    output_dir: Optional[Path] = None,
    timeout: int = DEFAULT_TIMEOUT,
    max_retries: int = MAX_RETRIES,
    year: Optional[int] = None
) -> Optional[Path]:
    """
    Download PDF from URL with error handling and retry logic.

    Args:
        pdf_url: Direct PDF link
        doi: Work DOI (for filename generation)
        output_dir: Storage directory (default: data/pdfs/)
        timeout: Request timeout in seconds (default: 30)
        max_retries: Number of retry attempts (default: 3)
        year: Publication year for subdirectory organization (optional)

    Returns:
        Path to downloaded file or None on failure

    Example:
        >>> pdf_path = download_pdf(
        ...     "https://example.com/paper.pdf",
        ...     "10.1371/journal.pone.0128238",
        ...     year=2025
        ... )
        >>> print(pdf_path)
        data/pdfs/2025/10.1371_journal.pone.0128238.pdf
    """
    # Set default output directory
    if output_dir is None:
        output_dir = PDF_STORAGE_DIR

    # Create year subdirectory if specified
    if year:
        output_dir = output_dir / str(year)

    # Create output directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate filename
    sanitized_doi = sanitize_doi(doi)
    filename = f"{sanitized_doi}.pdf"
    output_path = output_dir / filename

    # Check if file already exists
    if output_path.exists():
        logger.info(f"PDF already exists: {output_path}")
        return output_path

    # Download with retries
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"Downloading PDF (attempt {attempt}/{max_retries}): {doi}")

            # Make request
            response = requests.get(
                pdf_url,
                timeout=timeout,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                },
                stream=True  # Stream for large files
            )

            # Check for rate limiting
            if response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', RETRY_DELAY))
                logger.warning(f"Rate limited. Waiting {retry_after} seconds...")
                time.sleep(retry_after)
                continue

            # Raise for other errors
            response.raise_for_status()

            # Verify content type
            content_type = response.headers.get('Content-Type', '').lower()
            if 'pdf' not in content_type and 'application/octet-stream' not in content_type:
                logger.warning(f"Unexpected content type: {content_type}")
                # Continue anyway - some servers don't set correct content-type

            # Write to file
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

            # Verify file size
            file_size = output_path.stat().st_size
            if file_size < 1000:  # Less than 1KB is suspicious
                logger.warning(f"Downloaded file is very small ({file_size} bytes)")
                output_path.unlink()  # Delete suspicious file
                raise ValueError(f"Downloaded file too small: {file_size} bytes")

            logger.info(f"Successfully downloaded: {output_path} ({file_size / 1024:.1f} KB)")
            return output_path

        except requests.exceptions.Timeout:
            logger.warning(f"Timeout on attempt {attempt}/{max_retries}")
            if attempt < max_retries:
                time.sleep(RETRY_DELAY * attempt)  # Exponential backoff

        except requests.exceptions.RequestException as e:
            logger.warning(f"Request error on attempt {attempt}/{max_retries}: {e}")
            if attempt < max_retries:
                time.sleep(RETRY_DELAY * attempt)

        except Exception as e:
            logger.error(f"Unexpected error downloading {doi}: {e}")
            break

    # All retries failed
    logger.error(f"Failed to download PDF after {max_retries} attempts: {doi}")

    # Log failed download
    _log_failed_download(pdf_url, doi, output_dir.parent)

    return None


def _log_failed_download(pdf_url: str, doi: str, log_dir: Path):
    """
    Log failed download attempts.

    Args:
        pdf_url: PDF URL that failed
        doi: Work DOI
        log_dir: Directory for log file
    """
    log_file = log_dir / "failed_downloads.log"

    try:
        with open(log_file, 'a', encoding='utf-8') as f:
            timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
            f.write(f"{timestamp}\t{doi}\t{pdf_url}\n")
    except Exception as e:
        logger.error(f"Failed to write to log file: {e}")


def batch_download_pdfs(
    works: list,
    output_dir: Optional[Path] = None,
    timeout: int = DEFAULT_TIMEOUT
) -> dict:
    """
    Download PDFs for a batch of works.

    Args:
        works: List of OpenAlexWork models or dicts with pdf_url, doi, publication_year
        output_dir: Storage directory (default: data/pdfs/)
        timeout: Request timeout in seconds

    Returns:
        Dict with keys: 'successful' (list of paths), 'failed' (list of DOIs)

    Example:
        >>> results = batch_download_pdfs(works)
        >>> print(f"Downloaded: {len(results['successful'])}")
        >>> print(f"Failed: {len(results['failed'])}")
    """
    successful = []
    failed = []

    for work in works:
        # Handle both Pydantic models and dicts
        if hasattr(work, 'pdf_url'):
            pdf_url = work.pdf_url
            doi = work.doi
            year = work.publication_year
        else:
            pdf_url = work.get('pdf_url')
            doi = work.get('doi')
            year = work.get('publication_year')

        # Skip if no PDF URL
        if not pdf_url or not doi:
            logger.warning(f"Skipping work without PDF URL or DOI")
            if doi:
                failed.append(doi)
            continue

        # Download
        pdf_path = download_pdf(
            pdf_url=pdf_url,
            doi=doi,
            output_dir=output_dir,
            timeout=timeout,
            year=year
        )

        if pdf_path:
            successful.append(pdf_path)
        else:
            failed.append(doi)

    logger.info(f"Batch download complete: {len(successful)} successful, {len(failed)} failed")

    return {
        'successful': successful,
        'failed': failed
    }


if __name__ == "__main__":
    # Example usage
    print("Testing PDF download module...")

    # Test 1: Sanitize DOI
    print("\n1. Testing DOI sanitization...")
    test_doi = "10.1371/journal.pone.0128238"
    sanitized = sanitize_doi(test_doi)
    print(f"  Original: {test_doi}")
    print(f"  Sanitized: {sanitized}")

    # Test 2: Download a known OA PDF
    print("\n2. Testing PDF download...")
    test_pdf_url = "https://journals.plos.org/plosone/article/file?id=10.1371/journal.pone.0128238&type=printable"
    test_doi = "10.1371/journal.pone.0128238"
    test_output = Path("data/pdfs/test")

    pdf_path = download_pdf(
        pdf_url=test_pdf_url,
        doi=test_doi,
        output_dir=test_output,
        year=2025
    )

    if pdf_path:
        print(f"  ✅ Downloaded to: {pdf_path}")
        print(f"  File size: {pdf_path.stat().st_size / 1024:.1f} KB")
    else:
        print("  ❌ Download failed")

    print("\n✅ PDF download module test complete!")
