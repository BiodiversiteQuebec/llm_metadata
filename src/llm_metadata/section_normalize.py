"""
Section heading normalization for scientific papers.

Maps raw section headings to canonical SectionType categories using
regex pattern matching. Handles common variations, multilingual headings,
and numbered sections.
"""

import re
from typing import Dict, List
from llm_metadata.schemas.chunk_metadata import SectionType


# Section normalization patterns (case-insensitive regex)
SECTION_PATTERNS: Dict[SectionType, List[str]] = {
    SectionType.ABSTRACT: [
        r"^abstract$",
        r"^summary$",
        r"^r[ée]sum[ée]$",  # French
    ],
    SectionType.INTRO: [
        r"^introduction$",
        r"^background$",
        r"^overview$",
        r"^introductory\s+remarks?$",
        r"^preamble$",
    ],
    SectionType.METHODS: [
        r"^methods?$",
        r"^materials?\s*(and|&|\+)\s*methods?$",
        r"^methodology$",
        r"^methodologies$",
        r"^experimental\s*(design|procedures?|methods?)?$",
        r"^study\s*(design|area|site)$",
        r"^procedures?$",
        r"^techniques?$",
        r"^approach(es)?$",
        r"^sampling$",
        r"^data\s*collection$",
        r"^field\s*(work|methods?|sampling)$",
        r"^laboratory\s*methods?$",
        r"^statistical\s*analysis$",
        r"^model(s|ling)?$",
    ],
    SectionType.RESULTS: [
        r"^results?$",
        r"^findings?$",
        r"^outcomes?$",
        r"^observations?$",
        r"^data\s*analysis$",
    ],
    SectionType.DISCUSSION: [
        r"^discussion$",
        r"^interpretation$",
        r"^implications?$",
        r"^results?\s*(and|&|\+)\s*discussion$",
        r"^discussion\s*(and|&|\+)\s*conclusions?$",
    ],
    SectionType.CONCLUSION: [
        r"^conclusions?$",
        r"^concluding\s*remarks?$",
        r"^summary\s*(and|&|\+)\s*conclusions?$",
        r"^final\s*remarks?$",
        r"^perspectives?$",
        r"^outlook$",
        r"^future\s*(work|directions?|research)$",
    ],
    SectionType.REFERENCES: [
        r"^references?$",
        r"^bibliography$",
        r"^literature\s*cited$",
        r"^works?\s*cited$",
        r"^citations?$",
    ],
    SectionType.ACK: [
        r"^acknowledgem?ents?$",
        r"^acknowledgem?ent$",
        r"^thanks$",
        r"^funding$",
        r"^author\s*contributions?$",
        r"^conflict\s*of\s*interest$",
        r"^competing\s*interests?$",
    ],
    SectionType.DATA_AVAILABILITY: [
        r"^data\s*availability(\s*statement)?$",
        r"^data\s*access(ibility)?(\s*statement)?$",
        r"^code\s*availability(\s*statement)?$",
        r"^materials?\s*availability(\s*statement)?$",
        r"^resource\s*availability(\s*statement)?$",
        r"^data\s*(and\s*)?code\s*availability(\s*statement)?$",
        r"^supporting\s*information$",
        r"^supplementary\s*information$",
    ],
    SectionType.SUPPLEMENT: [
        r"^supplement(ary)?(\s*(material|data|information|methods?|results?))?$",
        r"^appendix(\s*[a-z0-9])?(\s+\w+)*$",  # Matches "appendix", "appendix a", "appendix a supplementary methods"
        r"^appendices$",
        r"^additional\s*(files?|information|materials?)$",
        r"^online\s*(resources?|supplement)$",
        r"^supporting\s*(files?|materials?|methods?)$",
    ],
}


def normalize_heading(heading: str) -> str:
    """
    Normalize heading text for pattern matching.

    Removes:
    - Leading/trailing whitespace
    - Section numbers (e.g., "1.", "2.1", "II.", "A.")
    - Special characters
    - Extra whitespace

    Converts to lowercase for case-insensitive matching.

    Args:
        heading: Raw section heading

    Returns:
        Normalized heading string

    Example:
        >>> normalize_heading("1. Introduction")
        'introduction'
        >>> normalize_heading("2.3 Materials and Methods")
        'materials and methods'
    """
    # Strip whitespace
    heading = heading.strip()

    # Remove leading section numbers (various formats)
    # Patterns: "1.", "1.1", "II.", "A.", "(a)", etc.
    heading = re.sub(
        r"^(\d+\.)*\d+\.?\s+",  # "1." or "1.1" or "1.2.3"
        "",
        heading,
        flags=re.IGNORECASE
    )
    heading = re.sub(
        r"^[IVXLCDM]+\.?\s+",  # Roman numerals "II." or "IV"
        "",
        heading,
        flags=re.IGNORECASE
    )
    heading = re.sub(
        r"^[A-Z]\.?\s+",  # "A." or "B"
        "",
        heading
    )
    heading = re.sub(
        r"^\([a-z0-9]+\)\s+",  # "(a)" or "(1)"
        "",
        heading,
        flags=re.IGNORECASE
    )

    # Remove special characters (keep letters, numbers, spaces, &, +, -)
    heading = re.sub(r"[^\w\s&+\-é]", "", heading)

    # Collapse multiple spaces
    heading = re.sub(r"\s+", " ", heading)

    # Lowercase
    heading = heading.lower().strip()

    return heading


def extract_from_section(heading: str) -> SectionType:
    """
    Classify section heading into canonical SectionType.

    Uses regex pattern matching against SECTION_PATTERNS dictionary.
    Returns SectionType.OTHER if no match found.

    Args:
        heading: Raw section heading

    Returns:
        Canonical SectionType enum value

    Example:
        >>> extract_from_section("1. Introduction")
        <SectionType.INTRO: 'INTRO'>
        >>> extract_from_section("Materials and Methods")
        <SectionType.METHODS: 'METHODS'>
        >>> extract_from_section("Novel Section Name")
        <SectionType.OTHER: 'OTHER'>
    """
    # Normalize heading
    normalized = normalize_heading(heading)

    if not normalized:
        return SectionType.OTHER

    # Try matching against patterns
    for section_type, patterns in SECTION_PATTERNS.items():
        for pattern in patterns:
            if re.match(pattern, normalized, flags=re.IGNORECASE):
                return section_type

    return SectionType.OTHER


def get_section_path(
    section_title: str,
    parent_path: str = ""
) -> str:
    """
    Build hierarchical section path string.

    Args:
        section_title: Current section title
        parent_path: Parent section path (empty for top-level)

    Returns:
        Full section path separated by " > "

    Example:
        >>> get_section_path("DNA extraction", "Methods > Sampling")
        'Methods > Sampling > DNA extraction'
        >>> get_section_path("Introduction")
        'Introduction'
    """
    if parent_path:
        return f"{parent_path} > {section_title}"
    return section_title


def is_likely_heading(text: str, max_length: int = 150) -> bool:
    """
    Heuristic check if text is likely a section heading.

    Headings are typically:
    - Short (< 150 chars)
    - No sentence-ending punctuation
    - Title case or ALL CAPS

    Args:
        text: Text to check
        max_length: Maximum character length for headings

    Returns:
        True if text is likely a heading

    Example:
        >>> is_likely_heading("Introduction")
        True
        >>> is_likely_heading("This is a long paragraph with multiple sentences.")
        False
    """
    if not text or len(text) > max_length:
        return False

    # Check if ends with sentence-ending punctuation
    if text.rstrip().endswith((".", "!", "?")):
        return False

    # Check if multiple sentences (contains ". ")
    if ". " in text:
        return False

    return True


if __name__ == "__main__":
    # Test section classification
    test_headings = [
        "1. Introduction",
        "2. Materials and Methods",
        "2.1 Study Area",
        "3. Results",
        "4. Discussion and Conclusions",
        "References",
        "Appendix A: Supplementary Methods",
        "Acknowledgements",
        "Data Availability Statement",
        "Some Novel Section",
    ]

    print("Section Classification Tests:")
    print("-" * 60)
    for heading in test_headings:
        section_type = extract_from_section(heading)
        normalized = normalize_heading(heading)
        print(f"{heading:40s} → {section_type.value:15s} ('{normalized}')")
