"""Per-publisher recipes to find the PDF of an OPEN-ACCESS article.

Each recipe is a small pure function: it only builds candidate URLs (no network),
so it is easy to read and to test. The script ``scripts/rebuild_oa_corpus.py``
does the downloading, one request per second per host, with an honest User-Agent.

Rules followed here: open-access copies only; no EZproxy, no Sci-Hub; no attempt
to get past bot protection (a 403 or a "Just a moment" page is a final answer).

"Verified" dates below are the last time the recipe was run from the Universite
de Sherbrooke network (2026-11-15). A recipe marked NO_GO is kept for the record
so nobody tries it again: the publisher answered HTTP 403 to every script.
"""

from __future__ import annotations

import re
from urllib.parse import quote, urlparse

# Which publisher recipes give a PDF from a script (verified 2026-11-15).
WORKING_RECIPES = ("pmc_s3", "springer")
# Which ones answer 403 / Cloudflare to scripts (and to plain headless Chromium).
NO_GO_RECIPES = ("wiley", "oxford", "mdpi", "royal_society", "csp", "europepmc_render")

PMC_S3_BASE = "https://pmc-oa-opendata.s3.amazonaws.com"
IDCONV_URL = "https://pmc.ncbi.nlm.nih.gov/tools/idconv/api/v1/articles/"
EUROPEPMC_XML = "https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid}/fullTextXML"

# DOI prefix -> publisher name (only the prefixes seen in the corpus).
DOI_PREFIX_PUBLISHER = {
    "10.1002": "wiley", "10.1111": "wiley", "10.1155": "wiley",  # Hindawi is now Wiley
    "10.1046": "wiley",
    "10.1093": "oxford",
    "10.3390": "mdpi",
    "10.1098": "royal_society",
    "10.1139": "csp", "10.5558": "csp",
    "10.1007": "springer", "10.1186": "springer",  # BioMed Central is Springer Nature
    "10.1603": "bioone", "10.1600": "bioone", "10.3732": "bioone",
    "10.3389": "frontiers",
    "10.1371": "plos",
    "10.7717": "peerj",
    "10.1016": "elsevier",
}


def clean_doi(doi: str) -> str:
    """Lowercase-safe DOI without URL prefix; percent-escapes such as %2f are decoded."""
    from urllib.parse import unquote

    d = unquote(doi.strip())
    return re.sub(r"^https?://(dx\.)?doi\.org/", "", d)


def publisher_of(doi: str) -> str | None:
    return DOI_PREFIX_PUBLISHER.get(clean_doi(doi).split("/")[0])


# --- PMC (official channels) --------------------------------------------------

def pmcid_from_url(url: str) -> str | None:
    """Pull 'PMC1234567' out of a PMC / Europe PMC URL, else None."""
    m = re.search(r"(PMC\d{4,9})", url or "", flags=re.I)
    return m.group(1).upper() if m else None


def idconv_url(doi: str) -> str:
    """NCBI ID converter query (DOI -> PMCID). JSON answer: records[0].pmcid."""
    return f"{IDCONV_URL}?ids={quote(clean_doi(doi), safe='/')}&format=json&tool=llm_metadata"


def pmc_s3_listing_url(pmcid: str) -> str:
    """List the files of one article in the PMC Open Access bucket (AWS Open Data).

    Verified 2026-11-15. Layout: PMC<id>.<version>/PMC<id>.<version>.{pdf,xml,txt,json}.
    Only articles with an open licence are in the bucket.
    """
    return f"{PMC_S3_BASE}/?list-type=2&prefix={pmcid}.&max-keys=50"


def pmc_s3_keys_from_listing(xml_text: str) -> list[str]:
    return re.findall(r"<Key>([^<]+)</Key>", xml_text)


def pmc_s3_urls(keys: list[str]) -> dict[str, str]:
    """From the bucket listing, return {'pdf': url, 'xml': url} (latest version first)."""
    out: dict[str, str] = {}
    for ext in ("pdf", "xml"):
        hits = sorted(
            (k for k in keys if re.fullmatch(rf"PMC\d+\.\d+/PMC\d+\.\d+\.{ext}", k)),
            key=lambda k: int(k.split("/")[0].split(".")[1]),
            reverse=True,
        )
        if hits:
            out[ext] = f"{PMC_S3_BASE}/{hits[0]}"
    return out


def europepmc_xml_url(pmcid: str) -> str:
    """Europe PMC REST full-text JATS XML (only for open-access articles)."""
    return EUROPEPMC_XML.format(pmcid=pmcid)


# --- publisher recipes -----------------------------------------------------------

def springer(doi: str, landing_url: str | None = None) -> list[str]:
    """Springer Nature (Springer, BioMed Central, Nature OA). WORKS, verified 2026-11-15."""
    d = quote(clean_doi(doi), safe="/()")
    return [f"https://link.springer.com/content/pdf/{d}.pdf"]


def wiley(doi: str, landing_url: str | None = None) -> list[str]:
    """Wiley and Hindawi. NO_GO 2026-11-15: HTTP 403 to scripts, Cloudflare in Chromium."""
    d = clean_doi(doi)
    return [f"https://onlinelibrary.wiley.com/doi/pdfdirect/{d}", f"https://onlinelibrary.wiley.com/doi/pdf/{d}"]


def oxford(doi: str, landing_url: str | None = None) -> list[str]:
    """Oxford Academic. NO_GO 2026-11-15: HTTP 403 (Cloudflare). article-pdf links need the landing page."""
    return [f"https://academic.oup.com/article-pdf/doi/{clean_doi(doi)}"]


def mdpi(doi: str, landing_url: str | None = None) -> list[str]:
    """MDPI: '<article url>/pdf'. NO_GO 2026-11-15: HTTP 403."""
    if landing_url and "mdpi.com" in landing_url:
        return [landing_url.rstrip("/") + "/pdf"]
    return [f"https://www.mdpi.com/{clean_doi(doi)}"]  # resolved by redirect, then add /pdf


def royal_society(doi: str, landing_url: str | None = None) -> list[str]:
    """Royal Society. NO_GO 2026-11-15: HTTP 403."""
    return [f"https://royalsocietypublishing.org/doi/pdf/{clean_doi(doi)}"]


def csp(doi: str, landing_url: str | None = None) -> list[str]:
    """Canadian Science Publishing (cdnsciencepub.com). NO_GO 2026-11-15: HTTP 403."""
    return [f"https://cdnsciencepub.com/doi/pdf/{clean_doi(doi)}"]


def frontiers(doi: str, landing_url: str | None = None) -> list[str]:
    """Frontiers: '/pdf' after the article URL. Not in this corpus, untested."""
    return [f"https://www.frontiersin.org/articles/{clean_doi(doi)}/pdf"]


def plos(doi: str, landing_url: str | None = None) -> list[str]:
    """PLOS: printable PDF. Not in this corpus, untested."""
    return [f"https://journals.plos.org/plosone/article/file?id={clean_doi(doi)}&type=printable"]


def peerj(doi: str, landing_url: str | None = None) -> list[str]:
    """PeerJ: DOI 10.7717/peerj.1234 -> https://peerj.com/articles/1234.pdf. Untested."""
    m = re.search(r"peerj\.(\d+)$", clean_doi(doi))
    return [f"https://peerj.com/articles/{m.group(1)}.pdf"] if m else []


def elsevier(doi: str, landing_url: str | None = None) -> list[str]:
    """Elsevier open access: needs the PII from the landing page. Untested, not in this corpus."""
    m = re.search(r"/pii/([A-Z0-9]+)", landing_url or "")
    return [f"https://www.sciencedirect.com/science/article/pii/{m.group(1)}/pdfft"] if m else []


RECIPES = {
    "springer": springer, "wiley": wiley, "oxford": oxford, "mdpi": mdpi,
    "royal_society": royal_society, "csp": csp, "frontiers": frontiers,
    "plos": plos, "peerj": peerj, "elsevier": elsevier,
}


def candidate_pdf_urls(doi: str, landing_url: str | None = None) -> list[str]:
    """Dispatcher: publisher recipe chosen from the DOI prefix, else from the landing host.

    Returns [] when no recipe applies. Recipes in NO_GO_RECIPES are still returned
    (cheap to try once per run; the script stops at the first 403 per host).
    """
    name = publisher_of(doi)
    if name is None and landing_url:
        host = urlparse(landing_url).netloc
        for key, hint in (("wiley", "wiley.com"), ("oxford", "oup.com"), ("mdpi", "mdpi.com"),
                          ("royal_society", "royalsocietypublishing"), ("springer", "springer"),
                          ("csp", "cdnsciencepub")):
            if hint in host:
                name = key
                break
    fn = RECIPES.get(name or "")
    return fn(doi, landing_url) if fn else []


# --- preprint detection -----------------------------------------------------------

PREPRINT_HOSTS = ("biorxiv.org", "arxiv.org", "eartharxiv.org", "ecoevorxiv.org", "preprints.org",
                  "essoar.org", "peerj.com/preprints", "medrxiv.org", "osf.io/preprints")


def is_preprint(url: str, version: str | None = None) -> bool:
    """True for preprint servers, or when OpenAlex/Unpaywall say 'submittedVersion'."""
    if version and version.lower() in ("submittedversion", "submitted"):
        return True
    return any(h in (url or "").lower() for h in PREPRINT_HOSTS)
