# EZproxy Guide for UdeS Library Access

## Overview

This guide explains how to use Université de Sherbrooke's EZproxy service to access paywalled journal articles programmatically.

**EZproxy URL Format:**
```
http://ezproxy.usherbrooke.ca/login?url=<original_url>
```

**Documentation:**
https://www.usherbrooke.ca/biblio/services/soutien-a-enseignement/creer-ou-obtenir-le-lien-permanent-un-document-electronique

## How EZproxy Works

```
┌──────────────┐
│ Your Request │
└──────┬───────┘
       │
       ↓
┌─────────────────────────────┐
│ UdeS EZproxy Server         │
│ ezproxy.usherbrooke.ca      │
│ - Checks authentication     │
│ - Adds UdeS credentials     │
└──────┬──────────────────────┘
       │
       ↓
┌─────────────────────────────┐
│ Publisher (Wiley, Elsevier) │
│ - Sees UdeS IP/credentials  │
│ - Grants institutional access│
└──────┬──────────────────────┘
       │
       ↓
┌──────────────┐
│  PDF Returned│
└──────────────┘
```

## Setup Instructions

### Step 1: Install browser-cookie3 (Optional, but Recommended)

```bash
pip install browser-cookie3
```

This allows Python to extract cookies from your browser after authentication.

### Step 2: Authenticate in Browser

1. Open your browser (Chrome recommended)
2. Visit an EZproxy URL:
   ```
   http://ezproxy.usherbrooke.ca/login?url=https://doi.org/10.1111/ddi.12496
   ```
3. You'll be redirected to Microsoft login
4. Authenticate with:
   - UdeS email (e.g., vincent.beauregard@usherbrooke.ca)
   - Password
   - 2FA (Authenticator app)
5. Browser will save session cookies automatically
6. You should see the article page

**Important:** Keep this browser window open while running Python scripts.

### Step 3: Extract Cookies in Python

```python
from llm_metadata.ezproxy import extract_cookies_from_browser

# Extract cookies from your authenticated browser session
cookies = extract_cookies_from_browser()

if cookies:
    print("✓ Successfully extracted cookies")
else:
    print("✗ No cookies found - authenticate in browser first")
```

### Step 4: Download PDFs with EZproxy

```python
from llm_metadata.pdf_download import download_pdf_with_fallback
from llm_metadata.ezproxy import extract_cookies_from_browser

# Get cookies
cookies = extract_cookies_from_browser()

# Download paywalled article
pdf_path = download_pdf_with_fallback(
    doi="10.1111/ddi.12496",  # Paywalled Wiley article
    ezproxy_cookies=cookies,   # Use EZproxy authentication
    year=2024
)

if pdf_path:
    print(f"✓ Downloaded: {pdf_path}")
else:
    print("✗ Download failed")
```

## Complete Example: Batch Download with EZproxy

```python
from pathlib import Path
from llm_metadata.ezproxy import extract_cookies_from_browser
from llm_metadata.pdf_download import download_pdf_with_fallback

def download_paywalled_articles(dois, output_dir="data/pdfs/ezproxy"):
    """
    Download articles using EZproxy authentication.

    Args:
        dois: List of DOIs to download
        output_dir: Output directory for PDFs

    Returns:
        Dict with 'successful' and 'failed' lists
    """
    # Step 1: Extract cookies
    print("Extracting EZproxy cookies from browser...")
    cookies = extract_cookies_from_browser()

    if not cookies:
        print("✗ Failed to extract cookies")
        print("  1. Visit an EZproxy link in your browser")
        print("  2. Log in with UdeS credentials")
        print("  3. Keep browser window open")
        print("  4. Try again")
        return {'successful': [], 'failed': dois}

    print(f"✓ Found {len(cookies)} cookies")

    # Step 2: Download articles
    results = {'successful': [], 'failed': []}

    for i, doi in enumerate(dois, 1):
        print(f"\n[{i}/{len(dois)}] Downloading {doi}...")

        pdf_path = download_pdf_with_fallback(
            doi=doi,
            ezproxy_cookies=cookies,
            output_dir=Path(output_dir),
            use_unpaywall=True  # Still try Unpaywall first (faster)
        )

        if pdf_path:
            print(f"  ✓ Success: {pdf_path.name}")
            results['successful'].append(doi)
        else:
            print(f"  ✗ Failed")
            results['failed'].append(doi)

    # Step 3: Summary
    print("\n" + "="*70)
    print(f"Downloaded: {len(results['successful'])}/{len(dois)}")
    print(f"Failed: {len(results['failed'])}")

    return results


# Example usage
test_dois = [
    "10.1111/ddi.12496",          # Wiley - needs subscription
    "10.1098/rspb.2014.1779",     # Royal Society - needs subscription
    "10.1371/journal.pone.0128238"  # PLOS - open access (baseline)
]

results = download_paywalled_articles(test_dois)
```

## Fallback Strategy with EZproxy

The improved download system tries strategies in this order:

1. **OpenAlex PDF URL** - Try direct download
2. **Unpaywall API** - Check for repository copies
3. **EZproxy** ⭐ - Use UdeS library access (if cookies provided)
4. **HTTP Proxy Retry** - Final attempt with network proxy

```python
# EZproxy is automatically included in the fallback chain
pdf_path = download_pdf_with_fallback(
    doi="10.1111/paywalled-article",
    ezproxy_cookies=cookies  # Just add this parameter!
)
```

## Troubleshooting

### Issue 1: "No cookies found"

**Cause:** Browser cookies not accessible or session expired

**Solutions:**
1. Open Chrome/Firefox and visit an EZproxy link
2. Complete full authentication (Microsoft SSO + 2FA)
3. Keep browser window open
4. Try again immediately

### Issue 2: "Received HTML instead of PDF"

**Cause:** EZproxy session expired or authentication failed

**Solutions:**
1. Re-authenticate in browser (visit an EZproxy link)
2. Check if you can access the article manually in browser
3. Extract fresh cookies:
   ```python
   cookies = extract_cookies_from_browser()
   ```

### Issue 3: browser_cookie3 Import Error

**Cause:** Package not installed

**Solution:**
```bash
pip install browser-cookie3
```

### Issue 4: Still Getting 403 Forbidden

**Possible causes:**
- Article not in UdeS subscription
- Publisher requires additional authentication
- EZproxy session not properly established

**Solutions:**
1. Verify article is accessible manually:
   - Visit: `http://ezproxy.usherbrooke.ca/login?url=https://doi.org/<DOI>`
   - Can you download it in browser?
2. If yes: Cookie extraction issue (re-authenticate)
3. If no: Article not in UdeS subscription (try Unpaywall or interlibrary loan)

## Manual Cookie Extraction (Alternative Method)

If `browser_cookie3` doesn't work, manually extract cookies:

### Chrome:
1. Visit an EZproxy link and authenticate
2. Press F12 (Developer Tools)
3. Go to "Application" tab
4. Click "Cookies" → "http://ezproxy.usherbrooke.ca"
5. Copy cookie names and values

```python
# Use manually extracted cookies
cookies = {
    'ezproxy': 'your_session_value_here',
    # ... other cookies
}

pdf_path = download_pdf_with_fallback(
    doi="10.1111/ddi.12496",
    ezproxy_cookies=cookies
)
```

## Best Practices

1. **Authenticate Once Per Session**
   - Extract cookies at start of script
   - Reuse for all downloads

2. **Check Cookie Validity**
   ```python
   from llm_metadata.ezproxy import is_authenticated

   if is_authenticated(cookies):
       print("✓ Session valid")
   else:
       print("✗ Re-authenticate needed")
   ```

3. **Rate Limiting**
   - Don't hammer publishers (1-2 seconds between requests)
   - Be a good citizen

4. **Error Handling**
   - Some articles won't be accessible (not in subscription)
   - Always have fallback strategies (Unpaywall, interlibrary loan)

## Security Notes

- **Never commit cookies to Git** (.gitignore cookies)
- **Cookies expire** (typically 1-8 hours)
- **Re-authenticate regularly** for long-running scripts
- **Respect publisher terms** (personal use only)

## Jupyter Notebook Integration

```python
# At top of notebook
from llm_metadata.ezproxy import extract_cookies_from_browser
from llm_metadata.pdf_download import download_pdf_with_fallback

# Extract cookies once
cookies = extract_cookies_from_browser()

# Use throughout notebook
for doi in my_dois:
    pdf_path = download_pdf_with_fallback(
        doi=doi,
        ezproxy_cookies=cookies
    )
```

## Expected Success Rates with EZproxy

| Scenario | Expected Success |
|----------|-----------------|
| **Gold OA** (PLOS, BMC) | ~95-100% (no EZproxy needed) |
| **Green OA** (Unpaywall) | ~60-80% (repository copies) |
| **Paywalled + EZproxy** | ~70-90% (if in UdeS subscription) |
| **Paywalled, no EZproxy** | ~5-20% (very low) |

## Support Resources

- **Library Help**: biblio@usherbrooke.ca
- **EZproxy Issues**: IT Services (services-informatiques@usherbrooke.ca)
- **Subscription Questions**: Check library A-Z database list

## Legal & Ethical Use

✓ **Allowed:**
- Downloading for research/study
- Personal academic use
- Building research databases

✗ **Not Allowed:**
- Bulk downloading entire journals
- Sharing subscription content publicly
- Commercial use
- Bypassing paywalls for distribution

Use responsibly according to UdeS library policies.
