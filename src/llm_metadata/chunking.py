"""
Section-aware text chunking with token-based sizing.

Implements chunking strategy that respects section boundaries and uses
tiktoken for deterministic token counting. Optimized for OpenAI embedding
models (text-embedding-3-large, 8191 token limit).
"""

import re
from pathlib import Path
from typing import List, Optional, Tuple
from dataclasses import dataclass

import tiktoken

from llm_metadata.schemas.chunk_metadata import (
    ChunkMetadata,
    SectionMetadata,
    SectionType,
    ParserInfo
)
from llm_metadata.section_normalize import extract_from_section, get_section_path
from llm_metadata.pdf_parsing import Section, ParsedDocument


# Default chunking parameters (tuned for text-embedding-3-large)
DEFAULT_TARGET_TOKENS = 450
DEFAULT_MAX_TOKENS = 650
DEFAULT_OVERLAP_TOKENS = 80

# Tiktoken encoding for OpenAI models
ENCODING_NAME = "cl100k_base"


@dataclass
class ChunkingConfig:
    """
    Configuration for chunking strategy.

    Attributes:
        target_tokens: Target chunk size in tokens (soft limit)
        max_tokens: Maximum chunk size in tokens (hard limit)
        overlap_tokens: Token overlap between consecutive chunks
        encoding_name: Tiktoken encoding name
    """
    target_tokens: int = DEFAULT_TARGET_TOKENS
    max_tokens: int = DEFAULT_MAX_TOKENS
    overlap_tokens: int = DEFAULT_OVERLAP_TOKENS
    encoding_name: str = ENCODING_NAME

    def __post_init__(self):
        """Validate configuration."""
        if self.target_tokens > self.max_tokens:
            raise ValueError("target_tokens must be <= max_tokens")
        if self.overlap_tokens >= self.target_tokens:
            raise ValueError("overlap_tokens must be < target_tokens")


def count_tokens(text: str, encoding_name: str = ENCODING_NAME) -> int:
    """
    Count tokens in text using tiktoken.

    Args:
        text: Input text
        encoding_name: Tiktoken encoding name

    Returns:
        Token count

    Example:
        >>> count_tokens("Hello, world!")
        4
    """
    encoding = tiktoken.get_encoding(encoding_name)
    return len(encoding.encode(text))


def detect_content_flags(text: str) -> Tuple[bool, bool, bool, bool]:
    """
    Detect content type flags for chunk metadata.

    Detects:
    - Equation markers (LaTeX, MathML)
    - Table mentions
    - Figure mentions

    Args:
        text: Chunk text

    Returns:
        Tuple of (has_equation, has_table_mention, has_figure_mention, has_references_pattern)

    Example:
        >>> has_eq, has_table, has_fig, has_refs = detect_content_flags(text)
    """
    text_lower = text.lower()

    # Equation detection (LaTeX markers, MathML tags)
    has_equation = bool(
        re.search(r"\$.*?\$", text) or  # Inline LaTeX
        re.search(r"\\\[.*?\\\]", text) or  # Display LaTeX
        re.search(r"<math", text_lower) or  # MathML
        re.search(r"\\begin\{equation", text_lower)  # LaTeX environment
    )

    # Table mentions
    has_table_mention = bool(
        re.search(
            r"\b(table|tab\.?)\s+\d+",
            text_lower
        ) or
        re.search(
            r"\bsee\s+table",
            text_lower
        )
    )

    # Figure mentions
    has_figure_mention = bool(
        re.search(
            r"\b(figure|fig\.?)\s+\d+",
            text_lower
        ) or
        re.search(
            r"\bsee\s+fig(ure)?",
            text_lower
        )
    )

    # Reference patterns (unlikely in chunk text, but check anyway)
    has_references_pattern = bool(
        re.search(
            r"^\[\d+\]",  # [1] Author et al.
            text,
            flags=re.MULTILINE
        )
    )

    return has_equation, has_table_mention, has_figure_mention, has_references_pattern


def split_text_by_sentences(text: str) -> List[str]:
    """
    Split text into sentences using heuristic rules.

    Attempts to preserve sentence integrity while splitting.
    Handles common abbreviations and decimal points.

    Args:
        text: Input text

    Returns:
        List of sentences

    Example:
        >>> split_text_by_sentences("Hello. World. How are you?")
        ['Hello.', 'World.', 'How are you?']
    """
    # Simple sentence splitting (can be improved with spaCy/NLTK for production)
    # Heuristic: split on ". " or ".\n" but not on abbreviations like "et al."

    # Protect common abbreviations
    text = text.replace("et al.", "et al@")
    text = text.replace("e.g.", "e@g@")
    text = text.replace("i.e.", "i@e@")
    text = text.replace("Fig.", "Fig@")
    text = text.replace("fig.", "fig@")
    text = text.replace("Tab.", "Tab@")
    text = text.replace("Dr.", "Dr@")
    text = text.replace("Mr.", "Mr@")
    text = text.replace("Mrs.", "Mrs@")
    text = text.replace("Ms.", "Ms@")

    # Split on sentence boundaries
    sentences = re.split(r"(?<=[.!?])\s+", text)

    # Restore abbreviations
    sentences = [
        s.replace("@", ".").strip()
        for s in sentences
        if s.strip()
    ]

    return sentences


def chunk_text(
    text: str,
    config: ChunkingConfig = ChunkingConfig()
) -> List[Tuple[str, int, int]]:
    """
    Chunk text into token-sized pieces with overlap.

    Respects sentence boundaries when possible. Returns chunks with
    character offsets for metadata.

    Args:
        text: Input text
        config: Chunking configuration

    Returns:
        List of (chunk_text, char_start, char_end) tuples

    Example:
        >>> chunks = chunk_text("Long text...", ChunkingConfig())
        >>> for chunk_text, start, end in chunks:
        ...     print(f"Chunk: {start}-{end}, tokens={count_tokens(chunk_text)}")
    """
    if not text.strip():
        return []

    # Get encoding
    encoding = tiktoken.get_encoding(config.encoding_name)

    # Count total tokens
    total_tokens = count_tokens(text, config.encoding_name)

    # If text fits in one chunk, return as-is
    if total_tokens <= config.max_tokens:
        return [(text, 0, len(text))]

    # Split into sentences
    sentences = split_text_by_sentences(text)

    chunks = []
    current_chunk_sentences = []
    current_chunk_tokens = 0
    char_offset = 0

    for sentence in sentences:
        sentence_tokens = count_tokens(sentence, config.encoding_name)

        # If single sentence exceeds max_tokens, split by encoding
        if sentence_tokens > config.max_tokens:
            # Flush current chunk if any
            if current_chunk_sentences:
                chunk_text = " ".join(current_chunk_sentences)
                chunk_start = char_offset - len(chunk_text)
                chunks.append((chunk_text, chunk_start, char_offset))
                current_chunk_sentences = []
                current_chunk_tokens = 0

            # Split long sentence by tokens
            encoded = encoding.encode(sentence)
            for i in range(0, len(encoded), config.max_tokens):
                chunk_encoded = encoded[i:i + config.max_tokens]
                chunk_text = encoding.decode(chunk_encoded)
                chunks.append((chunk_text, char_offset, char_offset + len(chunk_text)))
                char_offset += len(chunk_text)
            continue

        # Check if adding sentence would exceed max
        if current_chunk_tokens + sentence_tokens > config.max_tokens:
            # Flush current chunk
            chunk_text = " ".join(current_chunk_sentences)
            chunk_start = char_offset - len(chunk_text)
            chunks.append((chunk_text, chunk_start, char_offset))

            # Start new chunk with overlap
            # Keep last N sentences for overlap
            overlap_sentences = []
            overlap_tokens = 0
            for s in reversed(current_chunk_sentences):
                s_tokens = count_tokens(s, config.encoding_name)
                if overlap_tokens + s_tokens <= config.overlap_tokens:
                    overlap_sentences.insert(0, s)
                    overlap_tokens += s_tokens
                else:
                    break

            current_chunk_sentences = overlap_sentences
            current_chunk_tokens = overlap_tokens

        # Add sentence to current chunk
        current_chunk_sentences.append(sentence)
        current_chunk_tokens += sentence_tokens
        char_offset += len(sentence) + 1  # +1 for space

    # Flush remaining sentences
    if current_chunk_sentences:
        chunk_text = " ".join(current_chunk_sentences)
        chunk_start = max(0, char_offset - len(chunk_text))
        chunks.append((chunk_text, chunk_start, char_offset))

    return chunks


def chunk_section(
    section: Section,
    work_id: str,
    config: ChunkingConfig = ChunkingConfig(),
    parent_path: str = "",
    chunk_counter: Optional[List[int]] = None
) -> List[ChunkMetadata]:
    """
    Chunk a single section into ChunkMetadata objects.

    Recursively processes subsections. Never crosses section boundaries.

    Args:
        section: Section to chunk
        work_id: OpenAlex work ID
        config: Chunking configuration
        parent_path: Parent section path for hierarchy
        chunk_counter: Mutable counter for global chunk IDs

    Returns:
        List of ChunkMetadata objects

    Example:
        >>> chunks = chunk_section(section, "W123", ChunkingConfig())
        >>> print(f"Generated {len(chunks)} chunks from section")
    """
    if chunk_counter is None:
        chunk_counter = [0]

    all_chunks = []

    # Build section path
    section_path = get_section_path(section.title, parent_path)

    # Classify section type
    section_type = extract_from_section(section.title)

    # Create section metadata
    section_metadata = SectionMetadata(
        section_id=section.section_id,
        section_title_raw=section.title,
        section_type_normalized=section_type,
        section_path=section_path,
        section_level=section.level
    )

    # Chunk section text
    if section.text.strip():
        text_chunks = chunk_text(section.text, config)

        for chunk_index, (text_content, char_start, char_end) in enumerate(text_chunks):
            chunk_counter[0] += 1
            chunk_id = f"{work_id}_chunk_{chunk_counter[0]}"

            # Count tokens
            token_count = count_tokens(text_content, config.encoding_name)

            # Detect content flags
            has_eq, has_table, has_fig, has_refs_pat = detect_content_flags(text_content)

            # Create chunk metadata (minimal version - full metadata added later)
            chunk = ChunkMetadata(
                chunk_id=chunk_id,
                chunk_index_in_section=chunk_index,
                work_id=work_id,
                doi=None,  # Populated from document metadata
                title="",  # Populated from document metadata
                publication_year=None,
                authors=None,
                author_orcids=None,
                venue=None,
                oa_status=None,
                pdf_sha256="",  # Populated from document metadata
                local_pdf_path=None,
                pdf_url=None,
                parser=ParserInfo(tool="grobid", version="0.8.0"),  # Placeholder
                language=None,
                keywords=None,
                section=section_metadata,
                text=text_content,
                token_count=token_count,
                char_start=char_start,
                char_end=char_end,
                page_start=section.page_start,
                page_end=section.page_end,
                is_abstract=(section_type == SectionType.ABSTRACT),
                is_references=(section_type == SectionType.REFERENCES),
                has_equation=has_eq,
                has_table_mention=has_table,
                has_figure_mention=has_fig
            )

            all_chunks.append(chunk)

    # Recursively chunk subsections
    for subsection in section.subsections:
        subsection_chunks = chunk_section(
            subsection,
            work_id,
            config,
            parent_path=section_path,
            chunk_counter=chunk_counter
        )
        all_chunks.extend(subsection_chunks)

    return all_chunks


def chunk_document(
    doc: ParsedDocument,
    config: ChunkingConfig = ChunkingConfig(),
    openalex_work: Optional[dict] = None
) -> List[ChunkMetadata]:
    """
    Chunk entire document into ChunkMetadata objects.

    Processes all sections and subsections, enriching chunks with
    document-level metadata from OpenAlexWork if provided.

    Args:
        doc: ParsedDocument from GROBID parsing
        config: Chunking configuration
        openalex_work: Optional OpenAlexWork dict for metadata enrichment

    Returns:
        List of ChunkMetadata objects ready for embedding

    Example:
        >>> chunks = chunk_document(doc, ChunkingConfig())
        >>> print(f"Generated {len(chunks)} chunks from document")
        >>> print(f"Total tokens: {sum(c.token_count for c in chunks)}")
    """
    all_chunks = []
    chunk_counter = [0]

    # Chunk abstract separately if available
    if doc.abstract:
        abstract_section = Section(
            section_id=f"{doc.work_id}_sec_abstract",
            title="Abstract",
            level=1,
            text=doc.abstract,
            subsections=[],
            page_start=None,
            page_end=None
        )
        abstract_chunks = chunk_section(
            abstract_section,
            doc.work_id,
            config,
            chunk_counter=chunk_counter
        )
        all_chunks.extend(abstract_chunks)

    # Chunk body sections
    for section in doc.sections:
        section_chunks = chunk_section(
            section,
            doc.work_id,
            config,
            chunk_counter=chunk_counter
        )
        all_chunks.extend(section_chunks)

    # Enrich with document-level metadata if provided
    if openalex_work:
        # Extract author names and ORCIDs
        authors = None
        author_orcids = None
        if openalex_work.get("authors"):
            authors = [a["name"] for a in openalex_work["authors"]]
            author_orcids = [
                a["orcid"] for a in openalex_work["authors"]
                if a.get("orcid")
            ]

        # Update all chunks with metadata
        for chunk in all_chunks:
            chunk.doi = openalex_work.get("doi")
            chunk.title = openalex_work.get("title", doc.title or "")
            chunk.publication_year = openalex_work.get("publication_year")
            chunk.authors = authors
            chunk.author_orcids = author_orcids if author_orcids else None
            chunk.venue = openalex_work.get("venue")
            chunk.oa_status = openalex_work.get("oa_status")
            chunk.pdf_url = openalex_work.get("pdf_url")
            chunk.local_pdf_path = openalex_work.get("local_pdf_path")
    else:
        # Use GROBID metadata only
        for chunk in all_chunks:
            chunk.title = doc.title or ""
            chunk.language = doc.language
            chunk.keywords = doc.keywords

    # Update parser info
    for chunk in all_chunks:
        chunk.parser = doc.parser

    return all_chunks


if __name__ == "__main__":
    # Test chunking
    test_text = """
    This is a test paragraph with multiple sentences. It demonstrates the chunking algorithm.
    The algorithm should split text based on token counts. It should also respect sentence boundaries.
    Tables and figures are mentioned here. See Table 1 for details. Figure 2 shows the results.
    We also have equations: $E = mc^2$ and \\[x^2 + y^2 = z^2\\].
    """

    print("Chunking Test:")
    print("-" * 60)
    print(f"Input text: {len(test_text)} chars, {count_tokens(test_text)} tokens")
    print()

    config = ChunkingConfig(target_tokens=50, max_tokens=80, overlap_tokens=10)
    chunks = chunk_text(test_text, config)

    print(f"Generated {len(chunks)} chunks:")
    print()
    for i, (chunk_text, start, end) in enumerate(chunks):
        tokens = count_tokens(chunk_text)
        has_eq, has_table, has_fig, _ = detect_content_flags(chunk_text)
        print(f"Chunk {i+1}: {start}-{end} ({tokens} tokens)")
        print(f"  Text: {chunk_text[:100]}...")
        print(f"  Flags: eq={has_eq}, table={has_table}, fig={has_fig}")
        print()
