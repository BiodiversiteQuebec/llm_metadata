"""Section typing in reading order (flat GROBID subsections, letter-spaced headings)."""

from llm_metadata.extraction import SectionSelectionConfig, collect_relevant_sections
from llm_metadata.pdf_parsing import Section
from llm_metadata.schemas.chunk_metadata import SectionType
from llm_metadata.section_normalize import classify_in_reading_order, extract_from_section


def test_letter_spaced_headings():
    assert extract_from_section("ME THODS") == SectionType.METHODS
    assert extract_from_section("INTRODUC TI ON") == SectionType.INTRO
    assert extract_from_section("R E S U LT S") == SectionType.RESULTS
    # an ordinary multi-word title is not glued together into a section name
    assert extract_from_section("Caribou capture and telemetry") == SectionType.OTHER


def test_subsections_take_the_block_type():
    heads = ["Introduction", "Materials and Methods", "Study area", "Sampling", "Results", "Model", "Discussion"]
    types = classify_in_reading_order(heads)
    assert types[2] == types[3] == SectionType.METHODS
    assert types[5] == SectionType.RESULTS  # "Model" under Results stays Results
    assert types[6] == SectionType.DISCUSSION


def test_untitled_first_section_nature_style():
    # Record 104 (Nature layout): the first section comes back "Untitled".
    heads = ["Untitled", "Methods", "Compensatory conservation", "Climate scenarios.", "Results"]
    types = classify_in_reading_order(heads)
    assert types[0] == SectionType.OTHER
    assert types[2] == types[3] == SectionType.METHODS


def test_collect_keeps_methods_subsections_and_drops_results_ones():
    def s(i, title):
        return Section(section_id=str(i), title=title, level=1, text=f"text of {title}", subsections=[])

    secs = [s(0, "Introduction"), s(1, "Methods"), s(2, "Field protocol"), s(3, "Results"), s(4, "Model fit")]
    cfg = SectionSelectionConfig(keywords=[])
    kept = [x.title for x in collect_relevant_sections(secs, cfg)]
    assert kept == ["Methods", "Field protocol"]
