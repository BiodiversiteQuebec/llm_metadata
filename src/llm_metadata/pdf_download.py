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

from llm_metadata import doi_utils

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Default storage directory
PDF_STORAGE_DIR = Path("data/pdfs")

# Download configuration
DEFAULT_TIMEOUT = 30  # seconds
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds (exponential backoff)

# PDF validation
MIN_PDF_SIZE = 100_000  # 100 KB - valid scientific PDFs are larger than this
PDF_MAGIC_BYTES = b"%PDF"


class InvalidPDFError(Exception):
    """Raised when a downloaded file is not a valid PDF."""
    pass


def validate_pdf(path: Path, min_size: int = MIN_PDF_SIZE) -> None:
    """
    Validate that a file is a real PDF.

    Checks:
    1. File exists
    2. Starts with %PDF magic bytes (not HTML or other content)
    3. File size >= min_size (default 100 KB)

    Args:
        path: Path to the PDF file
        min_size: Minimum acceptable file size in bytes

    Raises:
        InvalidPDFError: If the file fails validation
    """
    if not path.exists():
        raise InvalidPDFError(f"File does not exist: {path}")

    # Check magic bytes
    with open(path, "rb") as f:
        header = f.read(4)
    if header != PDF_MAGIC_BYTES:
        raise InvalidPDFError(
            f"File is not a PDF (starts with {header!r}, expected {PDF_MAGIC_BYTES!r}): {path}"
        )

    # Check file size
    file_size = path.stat().st_size
    if file_size < min_size:
        raise InvalidPDFError(
            f"PDF too small ({file_size} bytes, minimum {min_size}): {path}"
        )

def sanitize_doi(doi: str) -> str:
    """
    Sanitize DOI for use as filename.

    Delegates to ``doi_utils.doi_filename_stem`` for prefix stripping and
    slash replacement, then additionally replaces backslashes, colons, and
    spaces which may appear in malformed DOI strings.

    Args:
        doi: DOI string (e.g., "10.1371/journal.pone.0128238")

    Returns:
        Sanitized string safe for filename (e.g., "10.1371_journal.pone.0128238")

    Example:
        >>> sanitize_doi("10.1371/journal.pone.0128238")
        '10.1371_journal.pone.0128238'
    """
    stem = doi_utils.doi_filename_stem(doi)
    # doi_filename_stem handles prefix stripping and "/" → "_"; apply
    # additional replacements for edge-case characters in malformed DOIs.
    sanitized = stem.replace("\\", "_").replace(":", "_").replace(" ", "_")
    return sanitized


def guess_publisher_pdf_url(doi: str) -> Optional[str]:
    """
    Construct a likely direct PDF URL from a DOI based on known publisher patterns.

    Useful for closed-access papers where OpenAlex/Unpaywall don't provide
    a PDF URL, but we can guess the publisher's PDF endpoint from the DOI prefix.

    Args:
        doi: Article DOI (e.g. "10.1111/mec.14361")

    Returns:
        Guessed PDF URL or None if the publisher pattern is unknown
    """
    doi = doi.strip()

    # Wiley: 10.1111/*, 10.1002/*, 10.1890/*
    if doi.startswith(("10.1111/", "10.1002/", "10.1890/")):
        return f"https://onlinelibrary.wiley.com/doi/pdfdirect/{doi}"

    # Springer: 10.1007/*
    if doi.startswith("10.1007/"):
        return f"https://link.springer.com/content/pdf/{doi}.pdf"

    # Nature: 10.1038/*  (e.g. 10.1038/s41477-020-0647-x)
    if doi.startswith("10.1038/"):
        suffix = doi.split("/", 1)[1]
        return f"https://www.nature.com/articles/{suffix}.pdf"

    # Oxford Academic (OUP): 10.1093/*
    # OUP doesn't have a simple pattern; skip (EZproxy login may still work)

    # Cambridge University Press: 10.1017/*
    if doi.startswith("10.1017/"):
        return f"https://www.cambridge.org/core/services/aop-cambridge-core/content/view/{doi}"

    # Pensoft (BDJ): 10.3897/*
    if doi.startswith("10.3897/"):
        return f"https://doi.org/{doi}"

    return None


def download_pdf_from_url(
    pdf_url: str,
    output_path: Path,
    timeout: int = DEFAULT_TIMEOUT,
    max_retries: int = MAX_RETRIES
) -> bool:
    """
    Download PDF from a single URL with retry logic.

    Args:
        pdf_url: Direct PDF link
        output_path: Path to save the PDF
        timeout: Request timeout in seconds
        max_retries: Number of retry attempts

    Returns:
        True if download succeeded, False otherwise
    """

    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"Downloading from {pdf_url} (attempt {attempt}/{max_retries})")

            # Make request with proxy support
            response = requests.get(
                pdf_url,
                timeout=timeout,
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

            # Validate the downloaded file is a real PDF
            try:
                validate_pdf(output_path)
            except InvalidPDFError as e:
                logger.warning(f"Invalid PDF: {e}")
                output_path.unlink()
                raise

            file_size = output_path.stat().st_size
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

        except InvalidPDFError:
            # Don't retry if the server returned non-PDF content
            break

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

    # Check if file already exists and is valid
    if output_path.exists():
        try:
            validate_pdf(output_path)
            logger.info(f"PDF already exists and is valid: {output_path}")
            return output_path
        except InvalidPDFError as e:
            logger.warning(f"Existing file invalid, re-downloading: {e}")
            output_path.unlink()

    # Attempt download
    success = download_pdf_from_url(
        pdf_url=pdf_url,
        output_path=output_path,
        timeout=timeout,
        max_retries=max_retries
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
    year: Optional[int] = None,
    verify_ssl: bool = False,
    publisher_pdf_url: Optional[str] = None
) -> Optional[Path]:
    """
    Download PDF using UdeS EZproxy authentication.

    Requires EZproxy session cookies from browser authentication.
    Tries two strategies:
    1. Direct DOI → EZproxy login URL (requires active CAS session)
    2. Proxied publisher URL (may work with just EZproxy cookies)

    Args:
        doi: Article DOI
        ezproxy_cookies: Session cookies from authenticated browser
        output_dir: Storage directory (default: data/pdfs/)
        timeout: Request timeout in seconds
        year: Publication year for subdirectory organization
        verify_ssl: Whether to verify SSL certificates (default: False for EZproxy)
        publisher_pdf_url: Direct publisher PDF URL (optional, enables proxied URL strategy)

    Returns:
        Path to downloaded file or None if failed

    Note:
        SSL verification is disabled by default because university EZproxy
        servers often use certificates that Python's requests library cannot
        verify (enterprise CA chains). This is safe for academic paper downloads.

    Example:
        >>> from llm_metadata.ezproxy import extract_cookies_from_browser
        >>> cookies = extract_cookies_from_browser()
        >>> pdf_path = download_pdf_with_ezproxy(
        ...     doi="10.1111/ddi.12496",
        ...     ezproxy_cookies=cookies
        ... )
    """
    # Suppress SSL warnings if verification is disabled
    if not verify_ssl:
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    try:
        from llm_metadata.ezproxy import create_ezproxy_doi_url, create_proxied_publisher_url
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

    # Check if file already exists and is valid
    if output_path.exists():
        try:
            validate_pdf(output_path)
            logger.info(f"PDF already exists and is valid: {output_path}")
            return output_path
        except InvalidPDFError as e:
            logger.warning(f"Existing file invalid, re-downloading: {e}")
            output_path.unlink()

    # Build URLs to try
    urls_to_try = []

    # Strategy 1: If we have a publisher PDF URL, try the proxied version first
    # This often works with just EZproxy cookies (no CAS redirect needed)
    if publisher_pdf_url:
        proxied_url = create_proxied_publisher_url(publisher_pdf_url)
        urls_to_try.append(('proxied_publisher', proxied_url))

    # Strategy 2: EZproxy login URL (requires active CAS session)
    ezproxy_url = create_ezproxy_doi_url(doi)
    urls_to_try.append(('ezproxy_login', ezproxy_url))

    # Create session with cookies
    session = requests.Session()

    # Pre-populate session with browser cookies
    if ezproxy_cookies:
        for name, value in ezproxy_cookies.items():
            if name.startswith('cas_'):
                session.cookies.set(name[4:], value, domain='cas.usherbrooke.ca')
            else:
                # Set EZproxy cookie for the base domain (works for subdomains too)
                session.cookies.set(name, value, domain='.ezproxy.usherbrooke.ca')

    for strategy_name, url in urls_to_try:
        logger.info(f"Trying EZproxy {strategy_name} for {doi}")
        logger.debug(f"URL: {url}")

        try:
            response = session.get(
                url,
                timeout=timeout,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                },
                allow_redirects=True,
                stream=True,
                verify=verify_ssl
            )

            final_url = response.url
            logger.debug(f"Final URL after redirects: {final_url}")

            # Check if we got redirected to login page
            if 'cas.usherbrooke.ca/login' in final_url:
                logger.debug(f"  {strategy_name}: Redirected to CAS login")
                continue  # Try next strategy

            # Check content type
            content_type = response.headers.get('Content-Type', '').lower()

            if 'text/html' in content_type:
                content_sample = response.text[:1000].lower()
                if 'access denied' in content_sample or 'forbidden' in content_sample:
                    logger.debug(f"  {strategy_name}: Access denied")
                    continue
                elif 'login' in content_sample or 'sign in' in content_sample:
                    logger.debug(f"  {strategy_name}: Login required")
                    continue
                else:
                    logger.debug(f"  {strategy_name}: Received HTML (landing page?)")
                    continue

            # We got something that's not HTML - check if it's a PDF
            if response.status_code == 200:
                # Write PDF
                with open(output_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)

                # Validate the downloaded file is a real PDF
                try:
                    validate_pdf(output_path)
                except InvalidPDFError as e:
                    logger.warning(f"EZproxy {strategy_name}: Invalid PDF: {e}")
                    output_path.unlink()
                    continue

                file_size = output_path.stat().st_size
                logger.info(f"Successfully downloaded via EZproxy ({strategy_name}): {output_path} ({file_size / 1024:.1f} KB)")
                return output_path

        except Exception as e:
            logger.debug(f"  {strategy_name} error: {e}")
            continue

    # All strategies failed
    logger.warning("EZproxy download failed - session may have expired")
    logger.warning("To re-authenticate:")
    logger.warning("  1. Visit in Firefox: http://ezproxy.usherbrooke.ca/login?url=https://doi.org/10.1111/ddi.12496")
    logger.warning("  2. Complete SSO + 2FA login")
    logger.warning("  3. Close Firefox and retry")
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

    # Check if file already exists and is valid
    if output_path.exists():
        try:
            validate_pdf(output_path)
            logger.info(f"PDF already exists and is valid: {output_path}")
            return output_path
        except InvalidPDFError as e:
            logger.warning(f"Existing file invalid, re-downloading: {e}")
            output_path.unlink()

    # Strategy 1: Try OpenAlex PDF URL
    if openalex_pdf_url:
        logger.info(f"Strategy 1: Trying OpenAlex PDF URL for {doi}")
        success = download_pdf_from_url(
            pdf_url=openalex_pdf_url,
            output_path=output_path,
            timeout=timeout
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
                        max_retries=2  # Fewer retries for fallback attempts
                    )
                    if success:
                        return output_path

        except ImportError:
            logger.warning("Unpaywall module not available, skipping fallback")
        except Exception as e:
            logger.warning(f"Unpaywall fallback error: {e}")

    # Strategy 3: Try EZproxy (if cookies provided)
    if ezproxy_cookies:
        # Use known PDF URL, or guess one from the DOI prefix
        pdf_url_for_proxy = openalex_pdf_url or guess_publisher_pdf_url(doi)
        logger.info(f"Strategy 3: Trying EZproxy for {doi}")
        ezproxy_path = download_pdf_with_ezproxy(
            doi=doi,
            ezproxy_cookies=ezproxy_cookies,
            output_dir=output_dir,
            publisher_pdf_url=pdf_url_for_proxy,
            timeout=timeout,
            year=year
        )
        if ezproxy_path:
            return ezproxy_path
        
    # Strategy 4: Sci-Hub
    try:
        from llm_metadata.scihub import SciHub, CaptchaNeedException

        logger.info(f"Strategy 4: Trying Sci-Hub for {doi}")
        sh = SciHub()

        # Fetch returns {'pdf': bytes, 'url': str, 'name': str} or {'err': str}
        result = sh.fetch(doi)

        if result and result.get('pdf'):
            # SciHub returns PDF content as bytes - write directly to file
            pdf_bytes = result['pdf']

            # Verify it's actually a PDF
            if not pdf_bytes.startswith(PDF_MAGIC_BYTES):
                logger.warning(f"Sci-Hub: Response is not a valid PDF for {doi}")
            else:
                # Write the PDF bytes to file
                with open(output_path, 'wb') as f:
                    f.write(pdf_bytes)

                # Validate the downloaded file
                try:
                    validate_pdf(output_path)
                    logger.info(f"Successfully downloaded via Sci-Hub: {output_path}")
                    return output_path
                except InvalidPDFError as e:
                    logger.warning(f"Sci-Hub: Invalid PDF: {e}")
                    output_path.unlink()
        elif result and result.get('err'):
            logger.debug(f"Sci-Hub error: {result['err']}")
        else:
            logger.debug(f"Sci-Hub: No PDF found for {doi}")

    except ImportError:
        logger.warning("scihub module not available, skipping Sci-Hub fallback")
    except CaptchaNeedException:
        logger.warning("Sci-Hub: Captcha required, skipping")
    except Exception as e:
        logger.warning(f"Sci-Hub fallback error: {e}")
    

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
