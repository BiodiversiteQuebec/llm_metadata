"""
PDF download module for scientific papers with proxy and fallback support.

This module provides functions to download PDFs from URLs with error handling,
retry logic, proxy support (for university VPN), and Unpaywall fallback.
Designed for batch downloading of open access scientific papers.
"""

import os
import requests
import time
import logging
from pathlib import Path
from typing import Optional, Dict, List
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

# Proxy configuration from environment variables
# Set these in your .env if you have university VPN/proxy access
HTTP_PROXY = os.getenv('HTTP_PROXY')
HTTPS_PROXY = os.getenv('HTTPS_PROXY')


def get_proxies() -> Optional[Dict[str, str]]:
    """
    Get proxy configuration from environment variables.

    Returns:
        Dictionary with proxy settings or None if not configured

    Example:
        Set in .env:
        HTTP_PROXY=http://proxy.university.edu:8080
        HTTPS_PROXY=http://proxy.university.edu:8080
    """
    if HTTP_PROXY or HTTPS_PROXY:
        proxies = {}
        if HTTP_PROXY:
            proxies['http'] = HTTP_PROXY
        if HTTPS_PROXY:
            proxies['https'] = HTTPS_PROXY
        logger.debug(f"Using proxy configuration: {proxies}")
        return proxies
    return None


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


def download_pdf_from_url(
    pdf_url: str,
    output_path: Path,
    timeout: int = DEFAULT_TIMEOUT,
    max_retries: int = MAX_RETRIES,
    use_proxy: bool = True
) -> bool:
    """
    Download PDF from a single URL with retry logic.

    Args:
        pdf_url: Direct PDF link
        output_path: Path to save the PDF
        timeout: Request timeout in seconds
        max_retries: Number of retry attempts
        use_proxy: Whether to use proxy (if configured)

    Returns:
        True if download succeeded, False otherwise
    """
    proxies = get_proxies() if use_proxy else None

    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"Downloading from {pdf_url} (attempt {attempt}/{max_retries})")

            # Make request with proxy support
            response = requests.get(
                pdf_url,
                timeout=timeout,
                proxies=proxies,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                },
                stream=True
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
            return True

        except requests.exceptions.Timeout:
            logger.warning(f"Timeout on attempt {attempt}/{max_retries}")
            if attempt < max_retries:
                time.sleep(RETRY_DELAY * attempt)

        except requests.exceptions.RequestException as e:
            logger.warning(f"Request error on attempt {attempt}/{max_retries}: {e}")
            if attempt < max_retries:
                time.sleep(RETRY_DELAY * attempt)

        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            break

    return False


def download_pdf(
    pdf_url: str,
    doi: str,
    output_dir: Optional[Path] = None,
    timeout: int = DEFAULT_TIMEOUT,
    max_retries: int = MAX_RETRIES,
    year: Optional[int] = None,
    use_proxy: bool = True
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
        use_proxy: Whether to use proxy if configured (default: True)

    Returns:
        Path to downloaded file or None on failure

    Example:
        >>> pdf_path = download_pdf(
        ...     "https://example.com/paper.pdf",
        ...     "10.1371/journal.pone.0128238",
        ...     year=2025
        ... )
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

    # Attempt download
    success = download_pdf_from_url(
        pdf_url=pdf_url,
        output_path=output_path,
        timeout=timeout,
        max_retries=max_retries,
        use_proxy=use_proxy
    )

    if success:
        return output_path

    # Log failed download
    _log_failed_download(pdf_url, doi, output_dir.parent)

    return None


def download_pdf_with_ezproxy(
    doi: str,
    ezproxy_cookies: Optional[Dict[str, str]] = None,
    output_dir: Optional[Path] = None,
    timeout: int = DEFAULT_TIMEOUT,
    year: Optional[int] = None
) -> Optional[Path]:
    """
    Download PDF using UdeS EZproxy authentication.

    Requires EZproxy session cookies from browser authentication.

    Args:
        doi: Article DOI
        ezproxy_cookies: Session cookies from authenticated browser
        output_dir: Storage directory (default: data/pdfs/)
        timeout: Request timeout in seconds
        year: Publication year for subdirectory organization

    Returns:
        Path to downloaded file or None if failed

    Example:
        >>> from llm_metadata.ezproxy import extract_cookies_from_browser
        >>> cookies = extract_cookies_from_browser()
        >>> pdf_path = download_pdf_with_ezproxy(
        ...     doi="10.1111/ddi.12496",
        ...     ezproxy_cookies=cookies
        ... )
    """
    try:
        from llm_metadata.ezproxy import create_ezproxy_doi_url
    except ImportError:
        logger.error("EZproxy module not available")
        return None

    # Set default output directory
    if output_dir is None:
        output_dir = PDF_STORAGE_DIR

    if year:
        output_dir = output_dir / str(year)

    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate output path
    sanitized_doi = sanitize_doi(doi)
    filename = f"{sanitized_doi}.pdf"
    output_path = output_dir / filename

    # Check if file already exists
    if output_path.exists():
        logger.info(f"PDF already exists: {output_path}")
        return output_path

    # Create EZproxy URL
    ezproxy_url = create_ezproxy_doi_url(doi)
    logger.info(f"Trying EZproxy for {doi}")
    logger.debug(f"EZproxy URL: {ezproxy_url}")

    try:
        # Make request with cookies
        response = requests.get(
            ezproxy_url,
            timeout=timeout,
            cookies=ezproxy_cookies,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            },
            allow_redirects=True,
            stream=True
        )

        # EZproxy may redirect to the actual PDF
        # Check final URL for PDF
        final_url = response.url
        logger.debug(f"Final URL after redirects: {final_url}")

        # Check if we got HTML (login page) instead of PDF
        content_type = response.headers.get('Content-Type', '').lower()

        if 'text/html' in content_type:
            logger.warning("Received HTML instead of PDF - authentication may have failed")
            logger.warning("You may need to re-authenticate in browser")
            return None

        response.raise_for_status()

        # Write PDF
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        # Verify file
        file_size = output_path.stat().st_size
        if file_size < 1000:
            logger.warning(f"Downloaded file is very small ({file_size} bytes)")
            output_path.unlink()
            return None

        logger.info(f"Successfully downloaded via EZproxy: {output_path} ({file_size / 1024:.1f} KB)")
        return output_path

    except Exception as e:
        logger.error(f"EZproxy download failed: {e}")
        return None


def download_pdf_with_fallback(
    doi: str,
    openalex_pdf_url: Optional[str] = None,
    output_dir: Optional[Path] = None,
    timeout: int = DEFAULT_TIMEOUT,
    year: Optional[int] = None,
    use_unpaywall: bool = True,
    ezproxy_cookies: Optional[Dict[str, str]] = None
) -> Optional[Path]:
    """
    Download PDF with fallback strategy: OpenAlex → Unpaywall → EZproxy → Proxy retry.

    This is the recommended function for robust PDF downloading.

    Args:
        doi: Article DOI
        openalex_pdf_url: PDF URL from OpenAlex (optional)
        output_dir: Storage directory (default: data/pdfs/)
        timeout: Request timeout in seconds
        year: Publication year for subdirectory organization
        use_unpaywall: Whether to try Unpaywall fallback (default: True)
        ezproxy_cookies: UdeS EZproxy session cookies (optional)

    Returns:
        Path to downloaded file or None if all attempts failed

    Example:
        >>> # Without EZproxy
        >>> pdf_path = download_pdf_with_fallback(
        ...     doi="10.1371/journal.pone.0128238",
        ...     openalex_pdf_url="https://journals.plos.org/...",
        ...     year=2025
        ... )

        >>> # With EZproxy for paywalled content
        >>> from llm_metadata.ezproxy import extract_cookies_from_browser
        >>> cookies = extract_cookies_from_browser()
        >>> pdf_path = download_pdf_with_fallback(
        ...     doi="10.1111/paywalled",
        ...     ezproxy_cookies=cookies
        ... )
    """
    # Set default output directory
    if output_dir is None:
        output_dir = PDF_STORAGE_DIR

    if year:
        output_dir = output_dir / str(year)

    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate output path
    sanitized_doi = sanitize_doi(doi)
    filename = f"{sanitized_doi}.pdf"
    output_path = output_dir / filename

    # Check if file already exists
    if output_path.exists():
        logger.info(f"PDF already exists: {output_path}")
        return output_path

    # Strategy 1: Try OpenAlex PDF URL
    if openalex_pdf_url:
        logger.info(f"Strategy 1: Trying OpenAlex PDF URL for {doi}")
        success = download_pdf_from_url(
            pdf_url=openalex_pdf_url,
            output_path=output_path,
            timeout=timeout,
            use_proxy=use_proxy
        )
        if success:
            return output_path

    # Strategy 2: Try Unpaywall
    if use_unpaywall:
        try:
            from llm_metadata.unpaywall import get_article_by_doi, get_all_pdf_urls

            logger.info(f"Strategy 2: Trying Unpaywall for {doi}")
            unpaywall_article = get_article_by_doi(doi)

            if unpaywall_article:
                pdf_urls = get_all_pdf_urls(unpaywall_article)

                for i, url in enumerate(pdf_urls, 1):
                    if url == openalex_pdf_url:
                        continue  # Skip already tried URL

                    logger.info(f"  Trying Unpaywall URL {i}/{len(pdf_urls)}")
                    success = download_pdf_from_url(
                        pdf_url=url,
                        output_path=output_path,
                        timeout=timeout,
                        max_retries=2,  # Fewer retries for fallback attempts
                        use_proxy=use_proxy
                    )
                    if success:
                        return output_path

        except ImportError:
            logger.warning("Unpaywall module not available, skipping fallback")
        except Exception as e:
            logger.warning(f"Unpaywall fallback error: {e}")

    # Strategy 3: Try EZproxy (if cookies provided)
    if ezproxy_cookies:
        logger.info(f"Strategy 3: Trying EZproxy for {doi}")
        ezproxy_path = download_pdf_with_ezproxy(
            doi=doi,
            ezproxy_cookies=ezproxy_cookies,
            output_dir=output_dir,
            timeout=timeout,
            year=year
        )
        if ezproxy_path:
            return ezproxy_path

    # All strategies failed
    logger.error(f"All download strategies failed for {doi}")
    _log_failed_download(openalex_pdf_url or doi, doi, output_dir.parent)

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
    timeout: int = DEFAULT_TIMEOUT,
    use_fallback: bool = True
) -> dict:
    """
    Download PDFs for a batch of works with fallback support.

    Args:
        works: List of OpenAlexWork models or dicts with pdf_url, doi, publication_year
        output_dir: Storage directory (default: data/pdfs/)
        timeout: Request timeout in seconds
        use_fallback: Whether to use fallback strategies (default: True)

    Returns:
        Dict with keys: 'successful' (list of paths), 'failed' (list of DOIs)

    Example:
        >>> results = batch_download_pdfs(works, use_fallback=True)
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

        # Skip if no DOI
        if not doi:
            logger.warning(f"Skipping work without DOI")
            continue

        # Download with or without fallback
        if use_fallback:
            pdf_path = download_pdf_with_fallback(
                doi=doi,
                openalex_pdf_url=pdf_url,
                output_dir=output_dir,
                timeout=timeout,
                year=year
            )
        else:
            if not pdf_url:
                logger.warning(f"Skipping {doi} - no PDF URL")
                failed.append(doi)
                continue

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
    # Load environment variables
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        print("Note: python-dotenv not installed, using environment variables as-is")

    # Example usage
    print("Testing PDF download module with fallback support...")

    # Test 1: Sanitize DOI
    print("\n1. Testing DOI sanitization...")
    test_doi = "10.1371/journal.pone.0128238"
    sanitized = sanitize_doi(test_doi)
    print(f"  Original: {test_doi}")
    print(f"  Sanitized: {sanitized}")

    # Test 2: Download with fallback
    print("\n2. Testing PDF download with fallback...")
    test_doi = "10.1371/journal.pone.0128238"
    test_output = Path("data/pdfs/test")

    pdf_path = download_pdf_with_fallback(
        doi=test_doi,
        output_dir=test_output,
        year=2025,
        use_unpaywall=True
    )

    if pdf_path:
        print(f"  ✅ Downloaded to: {pdf_path}")
        print(f"  File size: {pdf_path.stat().st_size / 1024:.1f} KB")
    else:
        print("  ❌ Download failed with all strategies")

    print("\n✅ PDF download module test complete!")
