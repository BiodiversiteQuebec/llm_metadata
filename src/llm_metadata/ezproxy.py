"""
EZproxy integration for Université de Sherbrooke library access.

This module provides utilities for accessing subscription content through
UdeS library's EZproxy service, which authenticates institutional access
to paywalled publishers.

EZproxy URL format: http://ezproxy.usherbrooke.ca/login?url=<resource_url>

Documentation: https://www.usherbrooke.ca/biblio/services/soutien-a-enseignement/creer-ou-obtenir-le-lien-permanent-un-document-electronique
"""

import os
from typing import Optional
from urllib.parse import quote, urlparse

# UdeS EZproxy base URL
EZPROXY_BASE = "http://ezproxy.usherbrooke.ca/login?url="

# Browser selection (firefox, chrome, edge, safari)
# Set via environment variable: BROWSER_FOR_COOKIES=firefox
DEFAULT_BROWSER = os.getenv('BROWSER_FOR_COOKIES', 'firefox').lower()


def create_ezproxy_url(url: str) -> str:
    """
    Convert a regular URL to an EZproxy-authenticated URL.

    Args:
        url: Original URL (DOI, publisher URL, etc.)

    Returns:
        EZproxy-proxied URL for institutional access

    Example:
        >>> create_ezproxy_url("https://doi.org/10.1111/ddi.12496")
        'http://ezproxy.usherbrooke.ca/login?url=https://doi.org/10.1111/ddi.12496'
    """
    # Ensure URL is properly formatted
    if not url.startswith('http'):
        # Assume it's a DOI
        if url.startswith('10.'):
            url = f"https://doi.org/{url}"
        else:
            raise ValueError(f"Invalid URL or DOI: {url}")

    # Create EZproxy URL
    return f"{EZPROXY_BASE}{url}"


def create_ezproxy_doi_url(doi: str) -> str:
    """
    Convert a DOI to an EZproxy-authenticated DOI URL.

    Args:
        doi: Article DOI (with or without https://doi.org/ prefix)

    Returns:
        EZproxy-proxied DOI URL

    Example:
        >>> create_ezproxy_doi_url("10.1111/ddi.12496")
        'http://ezproxy.usherbrooke.ca/login?url=https://doi.org/10.1111/ddi.12496'
    """
    # Clean DOI
    doi = doi.replace("https://doi.org/", "").replace("http://doi.org/", "").replace("doi:", "")

    # Create DOI URL
    doi_url = f"https://doi.org/{doi}"

    return create_ezproxy_url(doi_url)


def extract_cookies_from_browser(browser: Optional[str] = None) -> Optional[dict]:
    """
    Extract EZproxy session cookies from browser.

    Note: Requires browser_cookie3 package and prior authentication in browser.

    Args:
        browser: Browser to extract from ('firefox', 'chrome', 'edge', 'safari').
                 If None, uses BROWSER_FOR_COOKIES env var (default: 'firefox')

    Returns:
        Dictionary of cookies or None if extraction fails

    Example:
        >>> # Use default browser (Firefox)
        >>> cookies = extract_cookies_from_browser()

        >>> # Explicitly use Chrome
        >>> cookies = extract_cookies_from_browser(browser='chrome')

        >>> if cookies:
        ...     # Use cookies for authenticated requests
        ...     requests.get(url, cookies=cookies)
    """
    try:
        import browser_cookie3
    except ImportError:
        raise ImportError(
            "browser_cookie3 package required for cookie extraction. "
            "Install with: pip install browser-cookie3"
        )

    # Use specified browser or default
    if browser is None:
        browser = DEFAULT_BROWSER

    browser = browser.lower()

    # Map browser names to browser_cookie3 functions
    browser_functions = {
        'firefox': browser_cookie3.firefox,
        'chrome': browser_cookie3.chrome,
        'chromium': browser_cookie3.chromium,
        'edge': browser_cookie3.edge,
        'safari': browser_cookie3.safari,
        'opera': browser_cookie3.opera,
        'brave': browser_cookie3.brave
    }

    if browser not in browser_functions:
        print(f"⚠ Unknown browser: {browser}")
        print(f"  Supported: {', '.join(browser_functions.keys())}")
        print(f"  Falling back to Firefox")
        browser = 'firefox'

    try:
        # Get browser function
        get_cookies = browser_functions[browser]

        # Try to get cookies for ezproxy domain
        print(f"Extracting cookies from {browser.capitalize()}...")
        cookies_jar = get_cookies(domain_name='ezproxy.usherbrooke.ca')

        # Convert to dict
        cookies_dict = {}
        for cookie in cookies_jar:
            cookies_dict[cookie.name] = cookie.value

        if cookies_dict:
            print(f"✓ Found {len(cookies_dict)} cookie(s)")
            return cookies_dict
        else:
            print("✗ No EZproxy cookies found in browser")
            return None

    except PermissionError as e:
        print(f"✗ Permission denied accessing {browser.capitalize()} cookies")
        print(f"  Make sure {browser.capitalize()} is closed, then try again")
        return None
    except Exception as e:
        print(f"✗ Error extracting cookies from {browser.capitalize()}: {e}")
        return None


def is_authenticated(session_cookies: dict) -> bool:
    """
    Check if EZproxy session cookies are valid.

    Args:
        session_cookies: Dictionary of cookies from browser

    Returns:
        True if cookies appear valid, False otherwise
    """
    # Check for common EZproxy session cookie
    required_cookies = ['ezproxy']  # Common EZproxy cookie name

    return any(key in session_cookies for key in required_cookies)


if __name__ == "__main__":
    # Example usage
    print("Testing EZproxy URL creation...")

    # Test 1: Create EZproxy URL from DOI
    print("\n1. Creating EZproxy URL from DOI...")
    doi = "10.1111/ddi.12496"
    ezproxy_url = create_ezproxy_doi_url(doi)
    print(f"  Original DOI: {doi}")
    print(f"  EZproxy URL: {ezproxy_url}")

    # Test 2: Create EZproxy URL from full DOI URL
    print("\n2. Creating EZproxy URL from full DOI URL...")
    doi_url = "https://doi.org/10.1098/rspb.2014.1779"
    ezproxy_url = create_ezproxy_url(doi_url)
    print(f"  Original URL: {doi_url}")
    print(f"  EZproxy URL: {ezproxy_url}")

    # Test 3: Create EZproxy URL from publisher URL
    print("\n3. Creating EZproxy URL from publisher URL...")
    publisher_url = "https://onlinelibrary.wiley.com/doi/10.1111/ddi.12496"
    ezproxy_url = create_ezproxy_url(publisher_url)
    print(f"  Original URL: {publisher_url}")
    print(f"  EZproxy URL: {ezproxy_url}")

    # Test 4: Try to extract cookies (may fail if not authenticated)
    print("\n4. Attempting to extract EZproxy cookies from browser...")
    try:
        cookies = extract_cookies_from_browser()
        if cookies:
            print(f"  ✓ Found {len(cookies)} cookies")
            if is_authenticated(cookies):
                print("  ✓ Session appears authenticated")
            else:
                print("  ⚠ Session may not be authenticated")
        else:
            print("  ✗ No cookies found")
            print("  → Authenticate in browser first: visit an EZproxy link")
    except ImportError as e:
        print(f"  ⚠ {e}")
        print("  → Install: pip install browser-cookie3")
    except Exception as e:
        print(f"  ✗ Error: {e}")

    print("\n" + "="*70)
    print("USAGE INSTRUCTIONS")
    print("="*70)
    print("1. Authenticate in browser:")
    print("   - Visit any EZproxy URL (e.g., the URLs printed above)")
    print("   - Log in with your UdeS Microsoft account + 2FA")
    print("   - Browser will save session cookies")
    print()
    print("2. Use in Python:")
    print("   from llm_metadata.ezproxy import extract_cookies_from_browser")
    print("   cookies = extract_cookies_from_browser()")
    print("   response = requests.get(ezproxy_url, cookies=cookies)")
    print()
    print("3. Or use with pdf_download module:")
    print("   pdf_path = download_pdf_with_ezproxy(doi, cookies=cookies)")

    print("\n✅ EZproxy integration test complete!")
