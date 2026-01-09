"""
Unpaywall API integration for open access PDF discovery.

This module provides functions to query the Unpaywall database for open access
locations of scholarly articles. Unpaywall is a free service that harvests
open access content from over 50,000 publishers and repositories.

API Documentation: https://unpaywall.org/products/api
Data Format: https://unpaywall.org/data-format
"""

import os
import requests
from typing import Optional, Dict, Any
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_URL = "https://api.unpaywall.org/v2"
UNPAYWALL_EMAIL = os.getenv('UNPAYWALL_EMAIL', os.getenv('OPENALEX_EMAIL'))

# Rate limit: 100,000 calls per day


def get_article_by_doi(doi: str, email: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Retrieve article metadata and OA locations from Unpaywall by DOI.

    Args:
        doi: Article DOI (e.g., "10.1371/journal.pone.0128238")
        email: Your email for polite API access (uses UNPAYWALL_EMAIL env var if not provided)

    Returns:
        Dictionary with article metadata including OA locations, or None if not found

    Example:
        >>> article = get_article_by_doi("10.1371/journal.pone.0128238")
        >>> if article and article['is_oa']:
        ...     print(article['best_oa_location']['url_for_pdf'])
    """
    # Use provided email or fall back to environment variable
    email_param = email or UNPAYWALL_EMAIL

    if not email_param:
        raise ValueError(
            "Email required for Unpaywall API. Set UNPAYWALL_EMAIL environment variable "
            "or pass email parameter."
        )

    # Clean DOI
    doi = doi.replace("https://doi.org/", "").replace("http://doi.org/", "").replace("doi:", "")

    # Build request URL
    endpoint = f"{BASE_URL}/{doi}"
    params = {'email': email_param}

    try:
        response = requests.get(endpoint, params=params, timeout=10)

        if response.status_code == 404:
            logger.debug(f"DOI not found in Unpaywall: {doi}")
            return None

        response.raise_for_status()
        return response.json()

    except requests.exceptions.RequestException as e:
        logger.warning(f"Error querying Unpaywall for DOI {doi}: {e}")
        return None


def extract_pdf_url(article: Dict[str, Any]) -> Optional[str]:
    """
    Extract best available PDF URL from Unpaywall article record.

    Args:
        article: Unpaywall article dictionary

    Returns:
        PDF URL or None if not available

    Example:
        >>> article = get_article_by_doi("10.1371/journal.pone.0128238")
        >>> pdf_url = extract_pdf_url(article)
    """
    if not article:
        return None

    # Check if article is OA
    if not article.get('is_oa', False):
        return None

    # Get best OA location
    best_oa_location = article.get('best_oa_location')
    if not best_oa_location:
        return None

    # Prefer url_for_pdf, fall back to url
    pdf_url = best_oa_location.get('url_for_pdf')
    if pdf_url:
        return pdf_url

    # If no direct PDF URL, try landing page URL
    return best_oa_location.get('url')


def get_all_pdf_urls(article: Dict[str, Any]) -> list:
    """
    Extract all available PDF URLs from Unpaywall article record.

    Args:
        article: Unpaywall article dictionary

    Returns:
        List of PDF URLs (may be empty)

    Example:
        >>> article = get_article_by_doi("10.1371/journal.pone.0128238")
        >>> urls = get_all_pdf_urls(article)
        >>> print(f"Found {len(urls)} PDF URLs")
    """
    if not article or not article.get('is_oa', False):
        return []

    pdf_urls = []

    # Get all OA locations
    oa_locations = article.get('oa_locations', [])

    for location in oa_locations:
        # Try url_for_pdf first
        pdf_url = location.get('url_for_pdf')
        if pdf_url and pdf_url not in pdf_urls:
            pdf_urls.append(pdf_url)

        # Also collect landing page URLs as fallback
        url = location.get('url')
        if url and url not in pdf_urls and url.endswith('.pdf'):
            pdf_urls.append(url)

    return pdf_urls


def get_oa_status(article: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract OA status information from Unpaywall article record.

    Args:
        article: Unpaywall article dictionary

    Returns:
        Dictionary with OA status details

    Example:
        >>> article = get_article_by_doi("10.1371/journal.pone.0128238")
        >>> status = get_oa_status(article)
        >>> print(status['is_oa'])
        >>> print(status['oa_status'])
    """
    if not article:
        return {
            'is_oa': False,
            'oa_status': None,
            'has_repository_copy': False
        }

    return {
        'is_oa': article.get('is_oa', False),
        'oa_status': article.get('oa_status'),
        'has_repository_copy': article.get('has_repository_copy', False),
        'journal_is_oa': article.get('journal_is_oa', False),
        'journal_is_in_doaj': article.get('journal_is_in_doaj', False)
    }


if __name__ == "__main__":
    # Load environment variables
    try:
        from dotenv import load_dotenv
        load_dotenv()
        # Reload the module-level email variable after loading .env
        import os
        UNPAYWALL_EMAIL = os.getenv('UNPAYWALL_EMAIL', os.getenv('OPENALEX_EMAIL'))
    except ImportError:
        print("Note: python-dotenv not installed, using environment variables as-is")

    # Example usage
    print("Testing Unpaywall API integration...")

    # Test 1: Get article by DOI
    print("\n1. Retrieving article metadata from Unpaywall...")
    doi = "10.1371/journal.pone.0128238"

    article = get_article_by_doi(doi)

    if article:
        print(f"  Title: {article.get('title', 'N/A')}")
        print(f"  Open Access: {article.get('is_oa', False)}")
        print(f"  OA Status: {article.get('oa_status', 'N/A')}")

        # Test 2: Extract PDF URL
        print("\n2. Extracting PDF URL...")
        pdf_url = extract_pdf_url(article)
        if pdf_url:
            print(f"  PDF URL: {pdf_url}")
        else:
            print("  No PDF URL available")

        # Test 3: Get all PDF URLs
        print("\n3. Getting all available PDF URLs...")
        all_urls = get_all_pdf_urls(article)
        print(f"  Found {len(all_urls)} PDF URLs")
        for i, url in enumerate(all_urls, 1):
            print(f"    {i}. {url}")

        # Test 4: Get OA status
        print("\n4. OA Status details...")
        status = get_oa_status(article)
        for key, value in status.items():
            print(f"  {key}: {value}")

    else:
        print("  Failed to retrieve article from Unpaywall")

    # Test 5: Try a paywalled article
    print("\n5. Testing with a potentially paywalled article...")
    paywalled_doi = "10.1038/nature12345"  # Example Nature DOI (may not exist)
    paywalled_article = get_article_by_doi(paywalled_doi)

    if paywalled_article:
        print(f"  Open Access: {paywalled_article.get('is_oa', False)}")
    else:
        print(f"  Article not found or error")

    print("\n✅ Unpaywall API integration test complete!")
