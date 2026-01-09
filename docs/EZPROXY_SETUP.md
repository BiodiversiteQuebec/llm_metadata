# Quick Start: EZproxy Setup for Paywalled Articles

## TL;DR - Complete Setup in 5 Minutes

### 1. Install Required Package
```bash
pip install browser-cookie3
```

### 2. Authenticate in Browser
1. Click this link: [http://ezproxy.usherbrooke.ca/login?url=https://doi.org/10.1111/ddi.12496](http://ezproxy.usherbrooke.ca/login?url=https://doi.org/10.1111/ddi.12496)
2. Log in with UdeS credentials (Microsoft SSO + 2FA)
3. Keep browser window open

### 3. Download PDFs in Python

```python
# Import modules
from llm_metadata.ezproxy import extract_cookies_from_browser
from llm_metadata.pdf_download import download_pdf_with_fallback

# Extract cookies from browser
cookies = extract_cookies_from_browser()

# Download paywalled article
pdf_path = download_pdf_with_fallback(
    doi="10.1111/ddi.12496",  # Any DOI
    ezproxy_cookies=cookies
)

print(f"Downloaded: {pdf_path}")
```

**That's it!** The system will automatically:
1. Try OpenAlex (direct download)
2. Try Unpaywall (repository copies)
3. **Try EZproxy** (UdeS library access) ⭐
4. Fall back to HTTP proxy if configured

## Test Your Setup

Run the test script:
```bash
python scripts/test_vpn_access.py
```

Or use this quick test:
```python
from llm_metadata.ezproxy import create_ezproxy_doi_url

# Generate EZproxy URL
url = create_ezproxy_doi_url("10.1111/ddi.12496")
print(url)
# Output: http://ezproxy.usherbrooke.ca/login?url=https://doi.org/10.1111/ddi.12496

# Open in browser to test
import webbrowser
webbrowser.open(url)
```

## Use in Notebooks

See `notebooks/download_dryad_pdfs_fuster_improved.ipynb` for a complete example.

## Troubleshooting

| Problem | Solution |
|---------|----------|
| No cookies found | Authenticate in browser first, keep window open |
| HTML instead of PDF | Session expired, re-authenticate |
| Still 403 errors | Article not in UdeS subscription, try Unpaywall |
| browser_cookie3 error | `pip install browser-cookie3` |

## Full Documentation

- **Detailed Guide**: `docs/ezproxy_guide.md`
- **VPN Access**: `docs/vpn_access_guide.md`
- **API Documentation**: Check module docstrings

## Success Rates

With EZproxy, expect:
- **70-90%** success for paywalled articles in UdeS subscription
- **95-100%** success for open access articles (via Unpaywall)
- **Overall: ~80-85%** success rate for ecology journals

## Questions?

- Technical: Open GitHub issue
- Library: biblio@usherbrooke.ca
- VPN: services-informatiques@usherbrooke.ca
