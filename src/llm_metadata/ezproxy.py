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


def extract_cookies_from_browser(browser: Optional[str] = None, include_cas: bool = True) -> Optional[dict]:
    """
    Extract EZproxy and CAS session cookies from browser.

    Note: Requires browser_cookie3 package and prior authentication in browser.

    Args:
        browser: Browser to extract from ('firefox', 'chrome', 'edge', 'safari').
                 If None, uses BROWSER_FOR_COOKIES env var (default: 'firefox')
        include_cas: Whether to also extract CAS (Central Authentication Service)
                     cookies from cas.usherbrooke.ca (default: True)

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

        cookies_dict = {}

        # Extract EZproxy cookies
        print(f"Extracting cookies from {browser.capitalize()}...")
        ezproxy_jar = get_cookies(domain_name='ezproxy.usherbrooke.ca')
        for cookie in ezproxy_jar:
            cookies_dict[cookie.name] = cookie.value

        ezproxy_count = len(cookies_dict)
        if ezproxy_count > 0:
            print(f"  ✓ Found {ezproxy_count} EZproxy cookie(s)")

        # Extract CAS cookies (for SSO authentication)
        if include_cas:
            try:
                cas_jar = get_cookies(domain_name='cas.usherbrooke.ca')
                cas_count = 0
                for cookie in cas_jar:
                    cookies_dict[f"cas_{cookie.name}"] = cookie.value
                    cas_count += 1
                if cas_count > 0:
                    print(f"  ✓ Found {cas_count} CAS cookie(s)")
            except Exception as e:
                print(f"  ⚠ Could not extract CAS cookies: {e}")

        if cookies_dict:
            print(f"✓ Total: {len(cookies_dict)} cookie(s)")
            return cookies_dict
        else:
            print("✗ No authentication cookies found in browser")
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


def verify_session_active(cookies: dict, timeout: int = 10) -> bool:
    """
    Verify if the EZproxy/CAS session is still active by making a test request.

    Args:
        cookies: Dictionary of cookies from extract_cookies_from_browser()
        timeout: Request timeout in seconds

    Returns:
        True if session is valid, False if expired or invalid

    Example:
        >>> cookies = extract_cookies_from_browser()
        >>> if verify_session_active(cookies):
        ...     print("Session is active - proceed with downloads")
        ... else:
        ...     print("Session expired - re-authenticate in browser")
    """
    import requests
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    # Test URL - EZproxy login with a DOI
    test_url = "http://ezproxy.usherbrooke.ca/login?url=https://doi.org/10.1111/ddi.12496"

    session = requests.Session()

    # Set up cookies
    if cookies:
        for name, value in cookies.items():
            if name.startswith('cas_'):
                session.cookies.set(name[4:], value, domain='cas.usherbrooke.ca')
            else:
                session.cookies.set(name, value, domain='.ezproxy.usherbrooke.ca')

    try:
        response = session.get(
            test_url,
            timeout=timeout,
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'},
            allow_redirects=True,
            verify=False
        )

        # Check if we ended up at CAS login (session expired)
        if 'cas.usherbrooke.ca/login' in response.url:
            return False

        # Check for HTTP 403 (access denied)
        if response.status_code == 403:
            return False

        # If we got redirected to the actual resource, session is valid
        return True

    except Exception:
        return False


def print_authentication_instructions():
    """Print instructions for authenticating with EZproxy."""
    print("\n" + "=" * 70)
    print("EZPROXY AUTHENTICATION REQUIRED")
    print("=" * 70)
    print("\nYour EZproxy session has expired. To re-authenticate:\n")
    print("1. Open Firefox")
    print("2. Visit this URL:")
    print("   http://ezproxy.usherbrooke.ca/login?url=https://doi.org/10.1111/ddi.12496")
    print("3. Complete UdeS Microsoft SSO login + 2FA")
    print("4. Wait until you see the article page (confirming authentication)")
    print("5. IMPORTANT: Keep Firefox open OR close it BEFORE running your script")
    print("   (Firefox locks cookies while running on Windows)")
    print("6. Run your script IMMEDIATELY (sessions expire quickly)")
    print("\n" + "=" * 70)


def create_proxied_publisher_url(publisher_url: str) -> str:
    """
    Convert a publisher URL to EZproxy-proxied format.

    This creates URLs like:
    - https://onlinelibrary-wiley-com.ezproxy.usherbrooke.ca/...
    - https://www-nature-com.ezproxy.usherbrooke.ca/...

    These URLs may work without the full CAS authentication flow if you
    have a valid EZproxy session cookie.

    Args:
        publisher_url: Original publisher URL

    Returns:
        EZproxy-proxied URL with rewritten hostname

    Example:
        >>> create_proxied_publisher_url("https://onlinelibrary.wiley.com/doi/10.1111/ddi.12496")
        'https://onlinelibrary-wiley-com.ezproxy.usherbrooke.ca/doi/10.1111/ddi.12496'
    """
    from urllib.parse import urlparse, urlunparse

    parsed = urlparse(publisher_url)

    # Convert hostname: onlinelibrary.wiley.com → onlinelibrary-wiley-com.ezproxy.usherbrooke.ca
    proxied_host = parsed.netloc.replace('.', '-') + '.ezproxy.usherbrooke.ca'

    # Reconstruct URL with proxied hostname
    proxied = parsed._replace(netloc=proxied_host)

    return urlunparse(proxied)


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
