#!/usr/bin/env python
"""
Live test of Sci-Hub functionality against the failed DOIs.

This script tests Sci-Hub directly to see which papers it can retrieve.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from llm_metadata.scihub import SciHub, CaptchaNeedException

# Unique failed DOIs from the log (most recent failures)
FAILED_DOIS = [
    "10.1639/0007-2745-119.1.008",      # American Bryological Society
    "10.22541/au.161832268.87346989/v1",  # Authorea preprint
    "10.1093/jhered/esx005",             # Oxford Academic
    "10.1600/036364416x692514",          # Systematic Botany
    "10.1093/ee/nvy113",                 # Oxford Academic
    "10.3897/BDJ.8.e49450",              # Pensoft
    "10.1017/9781316711644",             # Cambridge (book)
]


def test_scihub_live():
    """Test Sci-Hub against the failed DOIs."""
    print("=" * 60)
    print("Sci-Hub Live Test")
    print("=" * 60)

    try:
        print("\n1. Initializing Sci-Hub...")
        sh = SciHub()
        print(f"   Available mirrors: {len(sh.available_base_url_list)}")
        print(f"   Using: {sh.base_url}")
    except Exception as e:
        print(f"   FAILED to initialize: {e}")
        return

    print("\n2. Testing DOI fetches...")
    print("-" * 60)

    results = {"success": [], "failed": [], "captcha": []}

    for doi in FAILED_DOIS:
        print(f"\n   DOI: {doi}")
        try:
            result = sh.fetch(doi)

            if result is None:
                print(f"      Result: None (no response)")
                results["failed"].append(doi)
            elif "err" in result:
                print(f"      FAILED: {result['err']}")
                results["failed"].append(doi)
            elif "pdf" in result:
                pdf_bytes = result["pdf"]
                url = result.get("url", "unknown")

                # Check if it's actually a PDF
                if pdf_bytes.startswith(b"%PDF"):
                    print(f"      SUCCESS: {len(pdf_bytes):,} bytes")
                    print(f"      URL: {url}")
                    results["success"].append(doi)
                else:
                    print(f"      INVALID: Not a PDF (starts with {pdf_bytes[:20]!r})")
                    results["failed"].append(doi)
            else:
                print(f"      UNKNOWN response: {result}")
                results["failed"].append(doi)

        except CaptchaNeedException:
            print("      CAPTCHA required")
            results["captcha"].append(doi)
        except Exception as e:
            print(f"      ERROR: {type(e).__name__}: {e}")
            results["failed"].append(doi)

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"   Success:  {len(results['success'])} / {len(FAILED_DOIS)}")
    print(f"   Failed:   {len(results['failed'])} / {len(FAILED_DOIS)}")
    print(f"   Captcha:  {len(results['captcha'])} / {len(FAILED_DOIS)}")

    if results["success"]:
        print("\n   Successful DOIs:")
        for doi in results["success"]:
            print(f"      - {doi}")

    if results["failed"]:
        print("\n   Failed DOIs:")
        for doi in results["failed"]:
            print(f"      - {doi}")

    if results["captcha"]:
        print("\n   Captcha-blocked DOIs:")
        for doi in results["captcha"]:
            print(f"      - {doi}")


if __name__ == "__main__":
    test_scihub_live()
