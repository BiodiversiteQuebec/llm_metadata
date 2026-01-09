#!/usr/bin/env python
"""
Test script to verify VPN connection and PDF download capabilities.

Usage:
    python scripts/test_vpn_access.py

This script:
1. Checks if you're connected to UdeS network
2. Tests PDF download with multiple fallback strategies
3. Provides recommendations for improving success rates
"""

import sys
from pathlib import Path
import requests

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from llm_metadata.pdf_download import download_pdf_with_fallback


def check_vpn_status():
    """Check if connected to UdeS VPN by checking public IP."""
    print("="*70)
    print("VPN CONNECTION CHECK")
    print("="*70)

    try:
        response = requests.get('https://api.ipify.org', timeout=5)
        ip = response.text
        print(f"Your public IP: {ip}")

        # UdeS IP ranges (132.210.x.x is common)
        if ip.startswith('132.210'):
            print("✓ You appear to be connected to UdeS network/VPN")
            print("  Publishers should recognize your institutional access")
            return True
        else:
            print("✗ You're NOT on UdeS network")
            print("  Connect VPN for better access to paywalled content")
            print(f"  Current IP: {ip}")
            return False
    except Exception as e:
        print(f"⚠ Error checking IP: {e}")
        print("  Cannot determine VPN status")
        return None


def test_pdf_downloads(output_dir: Path):
    """Test PDF downloads with various article types."""
    print("\n" + "="*70)
    print("PDF DOWNLOAD TEST")
    print("="*70)

    test_cases = [
        {
            'doi': '10.1371/journal.pone.0128238',
            'description': 'PLOS ONE (Gold OA)',
            'expected': 'Should always work (no subscription needed)'
        },
        {
            'doi': '10.1111/ddi.12496',
            'description': 'Wiley (Hybrid OA)',
            'expected': 'May need UdeS subscription or repository copy'
        },
        {
            'doi': '10.1098/rspb.2014.1779',
            'description': 'Royal Society (Subscription)',
            'expected': 'Needs UdeS subscription or VPN access'
        }
    ]

    results = []

    for i, test in enumerate(test_cases, 1):
        print(f"\n[Test {i}/3] {test['description']}")
        print(f"DOI: {test['doi']}")
        print(f"Expected: {test['expected']}")
        print("-" * 70)

        try:
            pdf_path = download_pdf_with_fallback(
                doi=test['doi'],
                output_dir=output_dir,
                use_unpaywall=True,
                use_proxy=False  # VPN works at network level, not HTTP proxy
            )

            if pdf_path:
                file_size = pdf_path.stat().st_size / 1024
                result = {
                    'doi': test['doi'],
                    'status': 'Success',
                    'path': pdf_path,
                    'size_kb': file_size
                }
                print(f"✓ SUCCESS: Downloaded {file_size:.1f} KB")
            else:
                result = {
                    'doi': test['doi'],
                    'status': 'Failed',
                    'path': None,
                    'size_kb': 0
                }
                print(f"✗ FAILED: Could not download")

        except Exception as e:
            result = {
                'doi': test['doi'],
                'status': 'Error',
                'path': None,
                'size_kb': 0,
                'error': str(e)
            }
            print(f"✗ ERROR: {e}")

        results.append(result)

    return results


def print_summary(vpn_connected, results):
    """Print test summary and recommendations."""
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)

    # VPN Status
    if vpn_connected is True:
        print("VPN Status: ✓ Connected to UdeS network")
    elif vpn_connected is False:
        print("VPN Status: ✗ NOT connected to UdeS network")
    else:
        print("VPN Status: ⚠ Unknown (check manually)")

    # Download Results
    print("\nDownload Results:")
    success_count = sum(1 for r in results if r['status'] == 'Success')
    total_count = len(results)

    for r in results:
        status_icon = "✓" if r['status'] == 'Success' else "✗"
        print(f"  {status_icon} {r['doi']}: {r['status']}")
        if r['status'] == 'Success':
            print(f"     → {r['size_kb']:.1f} KB")

    success_rate = (success_count / total_count * 100) if total_count > 0 else 0
    print(f"\nSuccess Rate: {success_count}/{total_count} ({success_rate:.0f}%)")

    # Recommendations
    print("\n" + "="*70)
    print("RECOMMENDATIONS")
    print("="*70)

    if success_rate == 100:
        print("✓ Excellent! All downloads succeeded.")
        if vpn_connected:
            print("  Your VPN setup is working perfectly.")
        else:
            print("  All test articles were open access.")
    elif success_rate >= 66:
        print("⚠ Good, but some downloads failed.")
        if not vpn_connected:
            print("  → Connect to UdeS VPN to improve access to paywalled content")
        print("  → Failed articles may not be in UdeS subscriptions")
        print("  → Check Unpaywall for repository copies")
    else:
        print("✗ Many downloads failed. Try these steps:")
        if not vpn_connected:
            print("  1. Connect to UdeS VPN before running downloads")
        print("  2. Verify your VPN client is fully connected")
        print("  3. Check if OPENALEX_EMAIL is set in .env")
        print("  4. For persistent failures, request via interlibrary loan")

    # Next Steps
    print("\n" + "="*70)
    print("NEXT STEPS")
    print("="*70)
    print("1. Review the VPN Access Guide: docs/vpn_access_guide.md")
    print("2. Use the improved notebook: notebooks/download_dryad_pdfs_fuster_improved.ipynb")
    print("3. For questions, check: https://www.usherbrooke.ca/biblio/")


def main():
    """Run all tests."""
    print("\n" + "="*70)
    print("UdeS VPN & PDF DOWNLOAD TEST")
    print("="*70)
    print("This script tests your setup for downloading scientific papers")
    print("with Université de Sherbrooke institutional access.")
    print()

    # Create test output directory
    output_dir = Path("data/pdfs/vpn_test")
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Test PDFs will be saved to: {output_dir}")

    # Run tests
    vpn_connected = check_vpn_status()
    results = test_pdf_downloads(output_dir)

    # Print summary
    print_summary(vpn_connected, results)

    print("\n" + "="*70)
    print("TEST COMPLETE")
    print("="*70)


if __name__ == "__main__":
    # Load environment variables
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        print("Note: python-dotenv not installed")

    main()
