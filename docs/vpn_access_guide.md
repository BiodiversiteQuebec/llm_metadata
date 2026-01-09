# University VPN Access Guide for Paywalled Articles

## Overview

This guide explains how to access paywalled journal articles using Université de Sherbrooke's VPN connection.

## How University VPN Access Works

When you connect to UdeS VPN:
1. Your computer creates a secure tunnel to the university network
2. Your IP address appears to be from Université de Sherbrooke
3. Publishers (Wiley, Elsevier, Springer, etc.) recognize the UdeS IP
4. You automatically get access to subscribed content
5. **No special proxy configuration needed in Python**

## Step-by-Step Workflow

### Method 1: Connect VPN Before Running Scripts (Recommended)

```bash
# Step 1: Connect to UdeS VPN
# - Use your VPN client (GlobalProtect, Cisco AnyConnect, etc.)
# - Authenticate with Microsoft account + 2FA
# - Wait for "Connected" status

# Step 2: Verify connection (optional)
curl https://api.ipify.org
# Should show UdeS IP address range

# Step 3: Run your Python script
cd /path/to/llm_metadata
python notebooks/download_dryad_pdfs_fuster_improved.ipynb
```

**The script will automatically:**
- Try OpenAlex PDF URL (works better with VPN)
- Fall back to Unpaywall if needed
- Publishers will see UdeS IP and grant access

### Method 2: Check VPN Status Programmatically (Optional)

```python
import requests

def check_vpn_status():
    """Check if connected to UdeS VPN by checking public IP."""
    try:
        response = requests.get('https://api.ipify.org', timeout=5)
        ip = response.text
        print(f"Your public IP: {ip}")

        # UdeS IP ranges (approximate - check with IT)
        # 132.210.x.x is a common UdeS range
        if ip.startswith('132.210'):
            print("✓ Likely connected to UdeS network/VPN")
            return True
        else:
            print("✗ Not on UdeS network (connect VPN for paywalled access)")
            return False
    except Exception as e:
        print(f"Error checking IP: {e}")
        return False

# Use before downloading
if check_vpn_status():
    # Proceed with downloads
    download_pdfs()
```

## Common Issues and Solutions

### Issue 1: 403 Forbidden Errors Despite VPN

**Possible causes:**
- VPN not fully connected
- Publisher doesn't have UdeS subscription
- Publisher uses different authentication (e.g., Shibboleth)

**Solutions:**
1. Verify VPN connection: Check IP address shows UdeS range
2. Try accessing article in browser first
3. Use Unpaywall fallback (green OA versions)

### Issue 2: VPN Disconnects During Downloads

**Solution:**
```python
# Enable auto-reconnect check in script
def download_with_vpn_check(dois):
    results = []
    for doi in dois:
        # Check VPN before each download
        if not check_vpn_status():
            print("⚠ VPN disconnected! Reconnect and press Enter...")
            input()

        pdf_path = download_pdf_with_fallback(doi)
        results.append(pdf_path)
    return results
```

### Issue 3: Some Articles Still Blocked

**Explanation:** UdeS doesn't subscribe to all publishers

**Alternative strategies:**
1. **Unpaywall**: Finds repository copies (green OA)
2. **OpenAlex**: Sometimes has author manuscripts
3. **Interlibrary Loan**: Request through library
4. **Author Contact**: Email corresponding author for PDF

## Fallback Strategy Summary

The improved download script tries multiple strategies automatically:

```
┌─────────────────────────────┐
│  Connected to UdeS VPN?     │
└──────────┬──────────────────┘
           │
           ├─ YES ──┐
           │        ↓
           │  ┌─────────────────────────────┐
           │  │ Strategy 1: OpenAlex URL    │ ← Better success with VPN
           │  │ (Publisher recognizes UdeS) │
           │  └──────────┬──────────────────┘
           │             │ If fails
           │             ↓
           │  ┌─────────────────────────────┐
           │  │ Strategy 2: Unpaywall API   │
           │  │ (Alternative OA locations)  │
           │  └──────────┬──────────────────┘
           │             │ If fails
           │             ↓
           │  ┌─────────────────────────────┐
           │  │ Strategy 3: Retry w/ delay  │
           │  └─────────────────────────────┘
           │
           └─ NO ───┐
                    ↓
              ┌─────────────────────────────┐
              │ Strategy 1: OpenAlex URL    │ ← May fail (403)
              │ (Publisher blocks non-UdeS) │
              └──────────┬──────────────────┘
                         │
                         ↓
              ┌─────────────────────────────┐
              │ Strategy 2: Unpaywall API   │ ← Best chance without VPN
              │ (Green OA repositories)     │
              └─────────────────────────────┘
```

## Testing Your Setup

Run this test script to verify VPN + download pipeline:

```python
from pathlib import Path
from llm_metadata.pdf_download import download_pdf_with_fallback

# Test DOIs: mix of open access and potentially paywalled
test_dois = [
    ("10.1371/journal.pone.0128238", "PLOS ONE (Gold OA, should always work)"),
    ("10.1111/ddi.12496", "Wiley (Hybrid, needs UdeS subscription)"),
    ("10.1098/rspb.2014.1779", "Royal Society (Needs subscription)")
]

print("Testing PDF Download with VPN\n" + "="*60)

results = []
for doi, description in test_dois:
    print(f"\n{description}")
    print(f"DOI: {doi}")

    pdf_path = download_pdf_with_fallback(
        doi=doi,
        output_dir=Path("data/pdfs/vpn_test"),
        use_unpaywall=True
    )

    status = "✓ Success" if pdf_path else "✗ Failed"
    results.append((doi, status, pdf_path))
    print(f"Result: {status}")

print("\n" + "="*60)
print("SUMMARY")
print("="*60)
for doi, status, path in results:
    print(f"{status}: {doi}")

success_rate = sum(1 for _, s, _ in results if s == "✓ Success") / len(results) * 100
print(f"\nSuccess rate: {success_rate:.0f}%")

if success_rate < 100:
    print("\n💡 Tips to improve success rate:")
    print("1. Verify VPN is connected (check IP address)")
    print("2. Some publishers may not be in UdeS subscription")
    print("3. Unpaywall fallback helps find repository copies")
```

## Expected Success Rates

| Scenario | Expected Success |
|----------|-----------------|
| **Gold OA** (PLOS, BMC, etc.) | ~95-100% (no VPN needed) |
| **Green OA** (with Unpaywall) | ~60-80% (repository copies) |
| **Paywalled + VPN connected** | ~70-90% (depends on UdeS subscriptions) |
| **Paywalled, no VPN** | ~5-20% (very low) |

## University Library Resources

For articles that can't be downloaded:
- **Bibliothèque UdeS**: https://www.usherbrooke.ca/biblio/
- **Interlibrary Loan**: Request articles not in collection
- **Document Delivery**: 24-48 hour turnaround for most requests

## Support

- **IT Support (VPN issues)**: https://www.usherbrooke.ca/services-informatiques/
- **Library Support (Access issues)**: biblio@usherbrooke.ca
- **This Project**: Check `README.md` or open an issue
