#!/usr/bin/env python
"""
Troubleshooting script for EZproxy cookie extraction.

This script helps diagnose why cookies aren't being extracted from Firefox.

Usage:
    python scripts/test_ezproxy_cookies.py
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

def check_browser_cookie3():
    """Check if browser_cookie3 is installed."""
    print("="*70)
    print("1. Checking browser_cookie3 installation...")
    print("="*70)

    try:
        import browser_cookie3
        print("✓ browser_cookie3 is installed")
        return True
    except ImportError:
        print("✗ browser_cookie3 is NOT installed")
        print("  Install with: pip install browser-cookie3")
        return False


def check_firefox_cookies():
    """Check if Firefox cookies can be read at all."""
    print("\n" + "="*70)
    print("2. Checking Firefox cookie access...")
    print("="*70)

    try:
        import browser_cookie3

        # Try to read ANY Firefox cookies (not just EZproxy)
        print("Attempting to read Firefox cookies...")
        cookies_jar = browser_cookie3.firefox()

        # Count cookies
        cookie_list = list(cookies_jar)
        print(f"✓ Successfully read {len(cookie_list)} cookie(s) from Firefox")

        if len(cookie_list) == 0:
            print("\n⚠ Warning: Firefox has no cookies")
            print("  This could mean:")
            print("  1. Firefox hasn't been used recently")
            print("  2. Cookies were cleared")
            print("  3. Firefox profile path is incorrect")

        return True

    except PermissionError:
        print("✗ Permission denied reading Firefox cookies")
        print("\n  SOLUTION: Close Firefox completely and try again")
        print("  Firefox locks its cookie database when running")
        return False

    except FileNotFoundError as e:
        print("✗ Firefox cookie database not found")
        print(f"  Error: {e}")
        print("\n  Possible causes:")
        print("  1. Firefox is not installed")
        print("  2. Firefox hasn't been opened yet")
        print("  3. Using a non-standard Firefox profile")
        return False

    except Exception as e:
        print(f"✗ Error reading Firefox cookies: {e}")
        return False


def check_ezproxy_cookies():
    """Check specifically for EZproxy cookies."""
    print("\n" + "="*70)
    print("3. Checking for EZproxy cookies specifically...")
    print("="*70)

    try:
        import browser_cookie3

        print("Searching for cookies from ezproxy.usherbrooke.ca...")
        cookies_jar = browser_cookie3.firefox(domain_name='ezproxy.usherbrooke.ca')

        # Convert to list to check
        cookie_list = list(cookies_jar)

        if len(cookie_list) == 0:
            print("✗ No EZproxy cookies found")
            print("\n  This means you haven't authenticated with EZproxy yet")
            print("\n  TO FIX:")
            print("  1. Open Firefox")
            print("  2. Visit: http://ezproxy.usherbrooke.ca/login?url=https://doi.org/10.1111/ddi.12496")
            print("  3. Log in with UdeS credentials (Microsoft SSO + 2FA)")
            print("  4. Complete authentication until you see the article page")
            print("  5. Keep Firefox open (or close it AFTER running this script again)")
            return False
        else:
            print(f"✓ Found {len(cookie_list)} EZproxy cookie(s)")
            print("\nCookie details:")
            for cookie in cookie_list:
                print(f"  - {cookie.name}")
            return True

    except PermissionError:
        print("✗ Permission denied")
        print("  Close Firefox and try again")
        return False

    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def test_extraction_function():
    """Test the actual extraction function from the module."""
    print("\n" + "="*70)
    print("4. Testing llm_metadata.ezproxy.extract_cookies_from_browser()...")
    print("="*70)

    try:
        from llm_metadata.ezproxy import extract_cookies_from_browser

        cookies = extract_cookies_from_browser()

        if cookies:
            print(f"\n✓ SUCCESS! Extracted {len(cookies)} cookie(s)")
            print("\nYou're ready to download PDFs with EZproxy!")
            return True
        else:
            print("\n✗ Function returned no cookies")
            return False

    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def provide_summary(results):
    """Provide a summary and next steps."""
    print("\n" + "="*70)
    print("SUMMARY & NEXT STEPS")
    print("="*70)

    all_passed = all(results.values())

    if all_passed:
        print("\n✓ All checks passed! You're ready to use EZproxy.")
        print("\nNext steps:")
        print("1. Run: python scripts/test_vpn_access.py")
        print("2. Or use in your own code:")
        print("   from llm_metadata.ezproxy import extract_cookies_from_browser")
        print("   cookies = extract_cookies_from_browser()")

    else:
        print("\n✗ Some checks failed. Follow these steps:\n")

        if not results.get('browser_cookie3'):
            print("→ Install browser_cookie3:")
            print("  pip install browser-cookie3\n")

        if not results.get('firefox_access'):
            print("→ Close Firefox completely, then try again\n")

        if not results.get('ezproxy_cookies'):
            print("→ Authenticate with EZproxy in Firefox:")
            print("  1. Open Firefox")
            print("  2. Visit: http://ezproxy.usherbrooke.ca/login?url=https://doi.org/10.1111/ddi.12496")
            print("  3. Log in with UdeS credentials")
            print("  4. Complete 2FA")
            print("  5. Verify you can see the article")
            print("  6. Close Firefox")
            print("  7. Run this script again\n")

    # Browser alternatives
    print("\nTroubleshooting tips:")
    print("- Make sure Firefox is COMPLETELY closed before extracting cookies")
    print("- Try a different browser by setting: BROWSER_FOR_COOKIES=chrome in .env")
    print("- Check Firefox profile if using a non-default profile")
    print("- Verify EZproxy works manually in browser first")


def main():
    """Run all diagnostic checks."""
    print("\n" + "="*70)
    print("EZPROXY COOKIE EXTRACTION DIAGNOSTICS")
    print("="*70)
    print("This script will help diagnose cookie extraction issues\n")

    results = {}

    # Run checks
    results['browser_cookie3'] = check_browser_cookie3()

    if results['browser_cookie3']:
        results['firefox_access'] = check_firefox_cookies()

        if results['firefox_access']:
            results['ezproxy_cookies'] = check_ezproxy_cookies()

            if results['ezproxy_cookies']:
                results['extraction_function'] = test_extraction_function()
            else:
                results['extraction_function'] = False
        else:
            results['ezproxy_cookies'] = False
            results['extraction_function'] = False
    else:
        results['firefox_access'] = False
        results['ezproxy_cookies'] = False
        results['extraction_function'] = False

    # Summary
    provide_summary(results)

    print("\n" + "="*70)
    print("DIAGNOSTICS COMPLETE")
    print("="*70)


if __name__ == "__main__":
    # Load environment variables
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    main()
