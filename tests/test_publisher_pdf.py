"""Recipes only build URLs, so no network is needed; PMC bucket parsing uses a canned listing."""

from llm_metadata import publisher_pdf as pp

LISTING = """<ListBucketResult><Contents><Key>PMC6309006.1/ECE3-8-12629-g001.jpg</Key></Contents>
<Contents><Key>PMC6309006.1/PMC6309006.1.pdf</Key></Contents>
<Contents><Key>PMC6309006.1/PMC6309006.1.xml</Key></Contents>
<Contents><Key>PMC6309006.2/PMC6309006.2.pdf</Key></Contents></ListBucketResult>"""


def test_clean_doi_decodes_and_strips_prefix():
    assert pp.clean_doi("https://doi.org/10.1155%2f2012%2f387564") == "10.1155/2012/387564"


def test_publisher_of_known_prefixes():
    assert pp.publisher_of("10.1002/ece3.4685") == "wiley"
    assert pp.publisher_of("10.1007/s10980-021-01300-z") == "springer"
    assert pp.publisher_of("10.9999/unknown") is None


def test_springer_recipe():
    assert pp.candidate_pdf_urls("10.1007/s10980-021-01300-z") == [
        "https://link.springer.com/content/pdf/10.1007/s10980-021-01300-z.pdf"
    ]


def test_mdpi_uses_landing_url():
    urls = pp.candidate_pdf_urls("10.3390/rs12060922", "https://www.mdpi.com/2072-4292/12/6/922")
    assert urls == ["https://www.mdpi.com/2072-4292/12/6/922/pdf"]


def test_dispatcher_falls_back_on_landing_host_and_returns_empty_otherwise():
    assert pp.candidate_pdf_urls("10.9999/x", "https://onlinelibrary.wiley.com/doi/10.9999/x")
    assert pp.candidate_pdf_urls("10.9999/x") == []


def test_peerj_and_elsevier_need_their_ids():
    assert pp.peerj("10.7717/peerj.1234") == ["https://peerj.com/articles/1234.pdf"]
    assert pp.elsevier("10.1016/x") == []


def test_pmc_s3_picks_latest_version():
    urls = pp.pmc_s3_urls(pp.pmc_s3_keys_from_listing(LISTING))
    assert urls["pdf"].endswith("PMC6309006.2/PMC6309006.2.pdf")
    assert urls["xml"].endswith("PMC6309006.1/PMC6309006.1.xml")


def test_pmcid_from_url():
    assert pp.pmcid_from_url("https://pmc.ncbi.nlm.nih.gov/articles/PMC6309006/") == "PMC6309006"
    assert pp.pmcid_from_url("https://example.org/x") is None


def test_preprint_flag():
    assert pp.is_preprint("https://www.biorxiv.org/content/10.1101/1.full.pdf")
    assert pp.is_preprint("https://repo.edu/x.pdf", "submittedVersion")
    assert not pp.is_preprint("https://repo.edu/x.pdf", "publishedVersion")
