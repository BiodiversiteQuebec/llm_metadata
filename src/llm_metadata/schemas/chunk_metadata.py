"""
Schema for PDF chunking and section-aware RAG indexing.

This module defines Pydantic models for document structure, section normalization,
and chunk metadata for vector database storage. Integrates with OpenAlexWork schema
for document-level metadata propagation.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum
from pathlib import Path


class SectionType(str, Enum):
    """
    Canonical section type classification for scientific papers.

    Used for section normalization and metadata-based retrieval filtering.
    Maps raw section headings to standardized categories.
    """
    ABSTRACT = "ABSTRACT"
    INTRO = "INTRO"
    METHODS = "METHODS"
    RESULTS = "RESULTS"
    DISCUSSION = "DISCUSSION"
    CONCLUSION = "CONCLUSION"
    REFERENCES = "REFERENCES"
    ACK = "ACK"
    DATA_AVAILABILITY = "DATA_AVAILABILITY"
    SUPPLEMENT = "SUPPLEMENT"
    OTHER = "OTHER"


class ParserInfo(BaseModel):
    """
    Parser metadata for reproducibility and cache invalidation.

    Tracks which tool and version was used to extract document structure,
    enabling re-parsing when parser versions change.
    """
    tool: str = Field(
        ...,
        description="Parser tool name (e.g., 'grobid', 'pymupdf')"
    )
    version: str = Field(
        ...,
        description="Parser version (e.g., '0.8.0')"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Parse timestamp (UTC)"
    )


class SectionMetadata(BaseModel):
    """
    Section-level metadata for hierarchical document structure.

    Captures section boundaries and hierarchical relationships for
    section-aware chunking and retrieval.
    """
    section_id: str = Field(
        ...,
        description="Stable section ID within document (e.g., '{work_id}_sec_{n}')"
    )
    section_title_raw: str = Field(
        ...,
        description="Original section heading from document"
    )
    section_type_normalized: SectionType = Field(
        ...,
        description="Canonical section type from SectionType enum"
    )
    section_path: str = Field(
        ...,
        description="Hierarchical path (e.g., 'Methods > Sampling > DNA extraction')"
    )
    section_level: int = Field(
        ...,
        ge=1,
        description="Nesting depth (1=top-level, 2=subsection, etc.)"
    )


class ChunkMetadata(BaseModel):
    """
    Chunk-level metadata for vector database payload.

    Contains all information needed for retrieval, citation, and display,
    including document metadata, section context, and chunk position.
    """
    # Chunk identifiers
    chunk_id: str = Field(
        ...,
        description="Globally unique chunk ID (e.g., '{work_id}_chunk_{n}')"
    )
    chunk_index_in_section: int = Field(
        ...,
        ge=0,
        description="Zero-indexed position within section"
    )

    # Document-level metadata (from OpenAlexWork)
    work_id: str = Field(
        ...,
        description="OpenAlex work ID (openalex_id from OpenAlexWork)"
    )
    doi: Optional[str] = Field(
        default=None,
        description="Digital Object Identifier"
    )
    title: str = Field(
        ...,
        description="Paper title"
    )
    publication_year: Optional[int] = Field(
        default=None,
        description="Publication year"
    )
    authors: Optional[List[str]] = Field(
        default=None,
        description="Author names (display names from OpenAlexWork)"
    )
    author_orcids: Optional[List[str]] = Field(
        default=None,
        description="Flattened list of author ORCID IDs for filtering"
    )
    venue: Optional[str] = Field(
        default=None,
        description="Publication venue (from primary_location)"
    )
    oa_status: Optional[str] = Field(
        default=None,
        description="Open access status"
    )

    # PDF metadata
    pdf_sha256: str = Field(
        ...,
        description="SHA256 hash of source PDF (for deduplication and cache invalidation)"
    )
    local_pdf_path: Optional[Path] = Field(
        default=None,
        description="Local path to source PDF"
    )
    pdf_url: Optional[str] = Field(
        default=None,
        description="Original PDF download URL"
    )

    # Parser metadata
    parser: ParserInfo = Field(
        ...,
        description="Parser tool and version info"
    )
    language: Optional[str] = Field(
        default=None,
        description="Document language (from GROBID or OpenAlex)"
    )
    keywords: Optional[List[str]] = Field(
        default=None,
        description="Document keywords (from GROBID header)"
    )

    # Section context
    section: SectionMetadata = Field(
        ...,
        description="Section metadata for this chunk"
    )

    # Chunk content metadata
    text: str = Field(
        ...,
        description="Chunk text content"
    )
    token_count: int = Field(
        ...,
        ge=0,
        description="Token count (tiktoken cl100k_base encoding)"
    )
    char_start: int = Field(
        ...,
        ge=0,
        description="Character offset start in section text"
    )
    char_end: int = Field(
        ...,
        ge=0,
        description="Character offset end in section text"
    )

    # Page information (best-effort)
    page_start: Optional[int] = Field(
        default=None,
        ge=1,
        description="Starting page number (if available from GROBID)"
    )
    page_end: Optional[int] = Field(
        default=None,
        ge=1,
        description="Ending page number (if available from GROBID)"
    )

    # Content flags
    is_abstract: bool = Field(
        default=False,
        description="True if chunk is from abstract section"
    )
    is_references: bool = Field(
        default=False,
        description="True if chunk is from references section (exclude from retrieval by default)"
    )
    has_equation: bool = Field(
        default=False,
        description="True if chunk contains equation markers (best-effort detection)"
    )
    has_table_mention: bool = Field(
        default=False,
        description="True if chunk mentions tables (e.g., 'Table 1', 'see table')"
    )
    has_figure_mention: bool = Field(
        default=False,
        description="True if chunk mentions figures (e.g., 'Figure 2', 'see fig.')"
    )

    class Config:
        """Pydantic configuration."""
        populate_by_name = True


class DocumentMetadata(BaseModel):
    """
    Document-level metadata for registry and processing tracking.

    Extended from OpenAlexWork with additional fields for PDF processing pipeline.
    Stored in registry.sqlite for idempotency checks.
    """
    # Core identifiers
    work_id: str = Field(
        ...,
        description="OpenAlex work ID (primary key)"
    )
    doi: Optional[str] = Field(
        default=None,
        description="Digital Object Identifier"
    )

    # PDF metadata
    pdf_sha256: str = Field(
        ...,
        description="SHA256 hash of source PDF"
    )
    source_path: Path = Field(
        ...,
        description="Local path to source PDF"
    )

    # Processing status
    status: str = Field(
        default="PENDING",
        description="Processing status: PENDING, PARSED, CHUNKED, INDEXED, ERROR"
    )
    parser_version: Optional[str] = Field(
        default=None,
        description="Parser version string (e.g., 'grobid-0.8.0')"
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Last update timestamp (UTC)"
    )
    error_message: Optional[str] = Field(
        default=None,
        description="Error message if status is ERROR"
    )

    # Bibliographic metadata (from OpenAlexWork)
    title: Optional[str] = Field(
        default=None,
        description="Paper title"
    )
    publication_year: Optional[int] = Field(
        default=None,
        description="Publication year"
    )

    class Config:
        """Pydantic configuration."""
        populate_by_name = True
