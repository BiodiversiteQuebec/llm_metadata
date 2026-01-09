"""
PDF parsing and structure extraction using GROBID.

This module provides interfaces to GROBID (GeneRation Of BIbliographic Data)
for extracting section-aware document structure from scientific PDFs.
Parses TEI XML output into structured section trees for downstream chunking.
"""

import os
import hashlib
import subprocess
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import json

from lxml import etree
from pydantic import BaseModel, Field

from llm_metadata.schemas.chunk_metadata import SectionType, ParserInfo


# TEI namespace for XML parsing
TEI_NS = {"tei": "http://www.tei-c.org/ns/1.0"}

# Default paths
DEFAULT_TEI_DIR = Path(__file__).parent.parent.parent / "artifacts" / "tei"
DEFAULT_CHUNKS_DIR = Path(__file__).parent.parent.parent / "artifacts" / "chunks"


class Section(BaseModel):
    """
    Hierarchical section representation from TEI parsing.

    Captures section metadata and text content for chunking.
    """
    section_id: str = Field(
        ...,
        description="Section ID within document"
    )
    title: str = Field(
        ...,
        description="Section heading (raw)"
    )
    level: int = Field(
        ...,
        ge=1,
        description="Nesting level (1=top, 2=subsection, etc.)"
    )
    text: str = Field(
        default="",
        description="Section text content (all paragraphs concatenated)"
    )
    subsections: List["Section"] = Field(
        default_factory=list,
        description="Nested subsections"
    )
    page_start: Optional[int] = Field(
        default=None,
        description="Starting page number (if available)"
    )
    page_end: Optional[int] = Field(
        default=None,
        description="Ending page number (if available)"
    )


class ParsedDocument(BaseModel):
    """
    Complete parsed document structure.

    Output of GROBID parsing with hierarchical sections and metadata.
    """
    work_id: str = Field(
        ...,
        description="OpenAlex work ID"
    )
    title: Optional[str] = Field(
        default=None,
        description="Document title from GROBID"
    )
    abstract: Optional[str] = Field(
        default=None,
        description="Abstract text"
    )
    language: Optional[str] = Field(
        default=None,
        description="Document language (ISO code)"
    )
    keywords: Optional[List[str]] = Field(
        default=None,
        description="Keywords from header"
    )
    sections: List[Section] = Field(
        default_factory=list,
        description="Top-level sections"
    )
    parser: ParserInfo = Field(
        ...,
        description="Parser metadata"
    )

    class Config:
        """Pydantic configuration."""
        populate_by_name = True


def compute_pdf_hash(pdf_path: Path) -> str:
    """
    Compute SHA256 hash of PDF file.

    Args:
        pdf_path: Path to PDF file

    Returns:
        Hex digest of SHA256 hash

    Example:
        >>> hash_val = compute_pdf_hash(Path("paper.pdf"))
        >>> print(f"PDF hash: {hash_val}")
    """
    sha256 = hashlib.sha256()
    with open(pdf_path, "rb") as f:
        while chunk := f.read(8192):
            sha256.update(chunk)
    return sha256.hexdigest()


def call_grobid(
    pdf_path: Path,
    grobid_url: str = "http://localhost:8070",
    output_dir: Optional[Path] = None
) -> Path:
    """
    Call GROBID processFulltextDocument endpoint using direct REST API.

    Sends PDF to GROBID service and retrieves TEI XML output.
    Saves TEI XML output to artifacts/tei/{work_id}.tei.xml.

    Args:
        pdf_path: Path to input PDF
        grobid_url: GROBID service URL
        output_dir: Output directory for TEI XML (default: artifacts/tei/)

    Returns:
        Path to generated TEI XML file

    Raises:
        RuntimeError: If GROBID processing fails

    Example:
        >>> tei_path = call_grobid(Path("data/pdfs/2024/paper.pdf"))
        >>> print(f"TEI XML saved to {tei_path}")
    """
    import requests
    
    if output_dir is None:
        output_dir = DEFAULT_TEI_DIR

    output_dir.mkdir(parents=True, exist_ok=True)

    # Call GROBID REST API directly
    url = f"{grobid_url}/api/processFulltextDocument"
    
    try:
        with open(pdf_path, 'rb') as pdf_file:
            files = {'input': pdf_file}
            response = requests.post(
                url,
                files=files,
                timeout=120
            )
            response.raise_for_status()
            
        # Save TEI XML output
        tei_path = output_dir / f"{pdf_path.stem}.grobid.tei.xml"
        with open(tei_path, 'w', encoding='utf-8') as f:
            f.write(response.text)
            
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"GROBID processing failed: {e}") from e
    except Exception as e:
        raise RuntimeError(f"Failed to save TEI output: {e}") from e

    if not tei_path.exists():
        raise RuntimeError(f"GROBID output not found at {tei_path}")

    return tei_path


def parse_tei_xml(tei_path: Path) -> etree._Element:
    """
    Parse TEI XML file into lxml Element tree.

    Args:
        tei_path: Path to TEI XML file

    Returns:
        lxml Element tree root

    Example:
        >>> root = parse_tei_xml(Path("artifacts/tei/paper.tei.xml"))
        >>> title = root.find(".//tei:title", namespaces=TEI_NS)
    """
    parser = etree.XMLParser(remove_blank_text=True, resolve_entities=False)
    tree = etree.parse(str(tei_path), parser)
    return tree.getroot()


def extract_abstract(root: etree._Element) -> Optional[str]:
    """
    Extract abstract text from TEI XML.

    Args:
        root: TEI XML root element

    Returns:
        Abstract text, or None if not found

    Example:
        >>> root = parse_tei_xml(tei_path)
        >>> abstract = extract_abstract(root)
    """
    abstract_div = root.find(".//tei:profileDesc//tei:abstract", namespaces=TEI_NS)
    if abstract_div is None:
        return None

    # Concatenate all paragraph text
    paragraphs = abstract_div.findall(".//tei:p", namespaces=TEI_NS)
    text_parts = []
    for p in paragraphs:
        text = "".join(p.itertext()).strip()
        if text:
            text_parts.append(text)

    return "\n\n".join(text_parts) if text_parts else None


def extract_keywords(root: etree._Element) -> Optional[List[str]]:
    """
    Extract keywords from TEI XML header.

    Args:
        root: TEI XML root element

    Returns:
        List of keywords, or None if not found

    Example:
        >>> root = parse_tei_xml(tei_path)
        >>> keywords = extract_keywords(root)
    """
    keywords_elem = root.find(".//tei:profileDesc//tei:keywords", namespaces=TEI_NS)
    if keywords_elem is None:
        return None

    terms = keywords_elem.findall(".//tei:term", namespaces=TEI_NS)
    keywords = [term.text.strip() for term in terms if term.text]

    return keywords if keywords else None


def extract_language(root: etree._Element) -> Optional[str]:
    """
    Extract document language from TEI XML.

    Args:
        root: TEI XML root element

    Returns:
        ISO language code, or None if not found

    Example:
        >>> root = parse_tei_xml(tei_path)
        >>> lang = extract_language(root)
    """
    # Check <text> element xml:lang attribute
    text_elem = root.find(".//tei:text", namespaces=TEI_NS)
    if text_elem is not None:
        lang = text_elem.get("{http://www.w3.org/XML/1998/namespace}lang")
        if lang:
            return lang

    # Fallback: check fileDesc
    lang_elem = root.find(".//tei:langUsage//tei:language", namespaces=TEI_NS)
    if lang_elem is not None:
        return lang_elem.get("ident")

    return None


def extract_sections_recursive(
    div_elem: etree._Element,
    work_id: str,
    parent_path: str = "",
    level: int = 1,
    section_counter: List[int] = None
) -> Section:
    """
    Recursively extract section hierarchy from TEI <div> elements.

    Args:
        div_elem: TEI <div> element
        work_id: Document work ID for section ID generation
        parent_path: Parent section path for hierarchy
        level: Nesting level
        section_counter: Mutable counter for section IDs

    Returns:
        Section model with nested subsections

    Example:
        >>> body = root.find(".//tei:body", namespaces=TEI_NS)
        >>> sections = [extract_sections_recursive(div, "W123", level=1)
        ...             for div in body.findall("tei:div", namespaces=TEI_NS)]
    """
    if section_counter is None:
        section_counter = [0]

    section_counter[0] += 1
    section_id = f"{work_id}_sec_{section_counter[0]}"

    # Extract heading
    head_elem = div_elem.find("tei:head", namespaces=TEI_NS)
    title = "".join(head_elem.itertext()).strip() if head_elem is not None else "Untitled"

    # Extract paragraph text (excluding nested divs)
    paragraphs = []
    for p in div_elem.findall("tei:p", namespaces=TEI_NS):
        text = "".join(p.itertext()).strip()
        if text:
            paragraphs.append(text)

    text = "\n\n".join(paragraphs)

    # Extract page info from coordinates attribute (if available)
    page_start = None
    page_end = None
    coords = div_elem.get("coords")
    if coords:
        # coords format: "page1,x1,y1,x2,y2;page2,..."
        try:
            page_nums = [int(c.split(",")[0]) for c in coords.split(";") if c]
            if page_nums:
                page_start = min(page_nums)
                page_end = max(page_nums)
        except (ValueError, IndexError):
            pass

    # Recursively extract subsections
    subsections = []
    for subdiv in div_elem.findall("tei:div", namespaces=TEI_NS):
        subsection = extract_sections_recursive(
            subdiv,
            work_id,
            parent_path=f"{parent_path}/{title}" if parent_path else title,
            level=level + 1,
            section_counter=section_counter
        )
        subsections.append(subsection)

    return Section(
        section_id=section_id,
        title=title,
        level=level,
        text=text,
        subsections=subsections,
        page_start=page_start,
        page_end=page_end
    )


def parse_tei_to_document(
    tei_path: Path,
    work_id: str,
    parser_version: str = "grobid-0.8.0"
) -> ParsedDocument:
    """
    Parse TEI XML into structured ParsedDocument model.

    Extracts title, abstract, keywords, language, and hierarchical sections.

    Args:
        tei_path: Path to TEI XML file
        work_id: OpenAlex work ID
        parser_version: Parser version string

    Returns:
        ParsedDocument with complete structure

    Example:
        >>> doc = parse_tei_to_document(
        ...     Path("artifacts/tei/paper.tei.xml"),
        ...     work_id="W123"
        ... )
        >>> print(f"Found {len(doc.sections)} top-level sections")
    """
    root = parse_tei_xml(tei_path)

    # Extract metadata
    title_elem = root.find(".//tei:titleStmt//tei:title", namespaces=TEI_NS)
    title = "".join(title_elem.itertext()).strip() if title_elem is not None else None

    abstract = extract_abstract(root)
    keywords = extract_keywords(root)
    language = extract_language(root)

    # Extract sections from body
    body = root.find(".//tei:body", namespaces=TEI_NS)
    sections = []
    section_counter = [0]

    if body is not None:
        for div in body.findall("tei:div", namespaces=TEI_NS):
            section = extract_sections_recursive(
                div,
                work_id,
                level=1,
                section_counter=section_counter
            )
            sections.append(section)

    # Create parser info
    parser = ParserInfo(
        tool="grobid",
        version=parser_version,
        timestamp=datetime.utcnow()
    )

    return ParsedDocument(
        work_id=work_id,
        title=title,
        abstract=abstract,
        language=language,
        keywords=keywords,
        sections=sections,
        parser=parser
    )


def save_document_json(
    doc: ParsedDocument,
    output_dir: Optional[Path] = None
) -> Path:
    """
    Save ParsedDocument to JSON file.

    Saves to artifacts/chunks/{work_id}.doc.json for downstream processing.

    Args:
        doc: ParsedDocument model
        output_dir: Output directory (default: artifacts/chunks/)

    Returns:
        Path to saved JSON file

    Example:
        >>> json_path = save_document_json(doc)
        >>> print(f"Document structure saved to {json_path}")
    """
    if output_dir is None:
        output_dir = DEFAULT_CHUNKS_DIR

    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / f"{doc.work_id}.doc.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(doc.model_dump(mode="json"), f, indent=2, ensure_ascii=False)

    return output_path


def process_pdf(
    pdf_path: Path,
    work_id: str,
    grobid_url: Optional[str] = None,
    parser_version: str = "grobid-0.8.0"
) -> Tuple[Path, ParsedDocument]:
    """
    End-to-end PDF processing: GROBID → TEI → ParsedDocument.

    Saves TEI XML and document JSON to artifacts directories.

    Args:
        pdf_path: Path to input PDF
        work_id: OpenAlex work ID
        grobid_url: GROBID service URL (default: from env or localhost:8070)
        parser_version: Parser version string

    Returns:
        Tuple of (TEI XML path, ParsedDocument)

    Raises:
        RuntimeError: If GROBID processing or TEI parsing fails

    Example:
        >>> tei_path, doc = process_pdf(
        ...     Path("data/pdfs/2024/paper.pdf"),
        ...     work_id="W123"
        ... )
        >>> print(f"Extracted {len(doc.sections)} sections")
    """
    if grobid_url is None:
        grobid_url = os.getenv("GROBID_URL", "http://localhost:8070")

    # Step 1: Call GROBID
    tei_path = call_grobid(pdf_path, grobid_url)

    # Step 2: Parse TEI to document structure
    doc = parse_tei_to_document(tei_path, work_id, parser_version)

    # Step 3: Save document JSON
    save_document_json(doc)

    return tei_path, doc
