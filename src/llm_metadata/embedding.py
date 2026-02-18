"""
OpenAI embedding generation with caching and batch processing.

Wraps OpenAI embeddings API (text-embedding-3-large) with local caching
for reproducibility and cost efficiency. Supports batch processing for
throughput optimization.
"""

import os
import json
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import hashlib

from pydantic import BaseModel, Field

from llm_metadata.schemas.chunk_metadata import ChunkMetadata
from llm_metadata.openai_io import get_openai_client, get_openai_api_base


# Default embedding model
DEFAULT_MODEL = "text-embedding-3-large"
DEFAULT_DIMENSIONS = 3072  # Full dimensionality for text-embedding-3-large

# Default cache directory
DEFAULT_CACHE_DIR = Path(__file__).parent.parent.parent / "artifacts" / "chunks"


class EmbeddingRecord(BaseModel):
    """
    Single embedding record for caching.

    Stores embedding vector with metadata for cache validation.
    """
    chunk_id: str = Field(
        ...,
        description="Unique chunk identifier"
    )
    text_hash: str = Field(
        ...,
        description="SHA256 hash of chunk text (for cache validation)"
    )
    model: str = Field(
        ...,
        description="OpenAI model name"
    )
    dimensions: int = Field(
        ...,
        description="Embedding dimensionality"
    )
    embedding: List[float] = Field(
        ...,
        description="Embedding vector"
    )

    class Config:
        """Pydantic configuration."""
        populate_by_name = True


@dataclass
class EmbeddingConfig:
    """
    Configuration for embedding generation.

    Attributes:
        model: OpenAI embedding model name
        dimensions: Embedding dimensionality (None for full dims)
        batch_size: Maximum texts per API request (OpenAI recommends < 2048)
        cache_dir: Directory for embedding cache files
    """
    model: str = DEFAULT_MODEL
    dimensions: Optional[int] = DEFAULT_DIMENSIONS
    batch_size: int = 100
    cache_dir: Path = DEFAULT_CACHE_DIR


def compute_text_hash(text: str) -> str:
    """
    Compute SHA256 hash of text for cache validation.

    Args:
        text: Input text

    Returns:
        Hex digest of SHA256 hash

    Example:
        >>> hash_val = compute_text_hash("Hello, world!")
        >>> print(f"Text hash: {hash_val}")
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_embedding_cache(
    work_id: str,
    cache_dir: Path = DEFAULT_CACHE_DIR
) -> Dict[str, EmbeddingRecord]:
    """
    Load embedding cache for a document.

    Reads from {cache_dir}/{work_id}.embeddings.jsonl

    Args:
        work_id: OpenAlex work ID
        cache_dir: Cache directory path

    Returns:
        Dictionary mapping chunk_id to EmbeddingRecord

    Example:
        >>> cache = load_embedding_cache("W123")
        >>> if "W123_chunk_1" in cache:
        ...     print("Chunk already embedded")
    """
    cache_path = cache_dir / f"{work_id}.embeddings.jsonl"

    if not cache_path.exists():
        return {}

    cache = {}
    with open(cache_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                record = EmbeddingRecord.model_validate_json(line)
                cache[record.chunk_id] = record

    return cache


def save_embedding_cache(
    work_id: str,
    cache: Dict[str, EmbeddingRecord],
    cache_dir: Path = DEFAULT_CACHE_DIR
) -> Path:
    """
    Save embedding cache for a document.

    Writes to {cache_dir}/{work_id}.embeddings.jsonl (JSONL format for streaming).

    Args:
        work_id: OpenAlex work ID
        cache: Dictionary mapping chunk_id to EmbeddingRecord
        cache_dir: Cache directory path

    Returns:
        Path to saved cache file

    Example:
        >>> save_embedding_cache("W123", cache)
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{work_id}.embeddings.jsonl"

    with open(cache_path, "w", encoding="utf-8") as f:
        for record in cache.values():
            f.write(record.model_dump_json() + "\n")

    return cache_path


def generate_embeddings_batch(
    texts: List[str],
    config: EmbeddingConfig = EmbeddingConfig(),
    api_key: Optional[str] = None
) -> List[List[float]]:
    """
    Generate embeddings for a batch of texts using OpenAI API.

    Args:
        texts: List of input texts
        config: Embedding configuration
        api_key: OpenAI API key (default: from OPENAI_API_KEY env var)

    Returns:
        List of embedding vectors (same order as input texts)

    Raises:
        ValueError: If texts list is empty or exceeds batch size
        RuntimeError: If API call fails

    Example:
        >>> texts = ["Hello, world!", "Another text"]
        >>> embeddings = generate_embeddings_batch(texts)
        >>> print(f"Generated {len(embeddings)} embeddings")
    """
    if not texts:
        raise ValueError("texts list cannot be empty")

    if len(texts) > config.batch_size:
        raise ValueError(
            f"Batch size {len(texts)} exceeds maximum {config.batch_size}"
        )

    if api_key is None:
        api_key = os.getenv("OPENAI_API_KEY")

    openai_api_base = get_openai_api_base()
    if not api_key and openai_api_base == "https://api.openai.com/v1":
        raise ValueError(
            "OpenAI credentials not found. Set OPENAI_API_KEY for direct API calls "
            "or set OPENAI_API_BASE/OPENAI_BASE_URL to route through a proxy."
        )

    client = get_openai_client(api_key=api_key)

    # Call embeddings API
    try:
        response = client.embeddings.create(
            input=texts,
            model=config.model,
            dimensions=config.dimensions
        )
    except Exception as e:
        raise RuntimeError(f"OpenAI embeddings API call failed: {e}") from e

    # Extract embeddings in input order
    embeddings = [data.embedding for data in response.data]

    return embeddings


def embed_chunks(
    chunks: List[ChunkMetadata],
    config: EmbeddingConfig = EmbeddingConfig(),
    use_cache: bool = True,
    api_key: Optional[str] = None
) -> Tuple[List[List[float]], Dict[str, EmbeddingRecord]]:
    """
    Generate embeddings for chunks with caching.

    Checks cache for existing embeddings (validated by text hash),
    generates new embeddings for cache misses, and updates cache.

    Args:
        chunks: List of ChunkMetadata objects
        config: Embedding configuration
        use_cache: Whether to use/update cache
        api_key: OpenAI API key (default: from env)

    Returns:
        Tuple of (embeddings list, updated cache dict)

    Example:
        >>> embeddings, cache = embed_chunks(chunks, EmbeddingConfig())
        >>> print(f"Generated {len(embeddings)} embeddings")
        >>> print(f"Cache size: {len(cache)}")
    """
    if not chunks:
        return [], {}

    # Load cache if enabled
    work_id = chunks[0].work_id
    cache = load_embedding_cache(work_id, config.cache_dir) if use_cache else {}

    embeddings = []
    chunks_to_embed = []
    chunk_indices = []

    # Check cache and collect chunks needing embedding
    for i, chunk in enumerate(chunks):
        text_hash = compute_text_hash(chunk.text)

        # Check cache
        if use_cache and chunk.chunk_id in cache:
            cached_record = cache[chunk.chunk_id]

            # Validate cache: same text hash, model, and dimensions
            if (
                cached_record.text_hash == text_hash and
                cached_record.model == config.model and
                cached_record.dimensions == config.dimensions
            ):
                # Use cached embedding
                embeddings.append(cached_record.embedding)
                continue

        # Cache miss: need to embed
        chunks_to_embed.append(chunk)
        chunk_indices.append(i)
        embeddings.append(None)  # Placeholder

    # Generate embeddings in batches
    if chunks_to_embed:
        print(f"Embedding {len(chunks_to_embed)}/{len(chunks)} chunks (cache misses)")

        for batch_start in range(0, len(chunks_to_embed), config.batch_size):
            batch_end = min(batch_start + config.batch_size, len(chunks_to_embed))
            batch_chunks = chunks_to_embed[batch_start:batch_end]
            batch_texts = [chunk.text for chunk in batch_chunks]

            # Generate embeddings
            batch_embeddings = generate_embeddings_batch(
                batch_texts,
                config,
                api_key
            )

            # Store embeddings and update cache
            for j, chunk in enumerate(batch_chunks):
                embedding = batch_embeddings[j]
                original_index = chunk_indices[batch_start + j]
                embeddings[original_index] = embedding

                # Update cache
                text_hash = compute_text_hash(chunk.text)
                record = EmbeddingRecord(
                    chunk_id=chunk.chunk_id,
                    text_hash=text_hash,
                    model=config.model,
                    dimensions=config.dimensions or len(embedding),
                    embedding=embedding
                )
                cache[chunk.chunk_id] = record

    # Save cache if enabled
    if use_cache and chunks_to_embed:
        save_embedding_cache(work_id, cache, config.cache_dir)
        print(f"Updated embedding cache: {config.cache_dir / f'{work_id}.embeddings.jsonl'}")

    return embeddings, cache


def embed_single_chunk(
    chunk: ChunkMetadata,
    config: EmbeddingConfig = EmbeddingConfig(),
    use_cache: bool = True,
    api_key: Optional[str] = None
) -> List[float]:
    """
    Embed a single chunk (convenience wrapper).

    Args:
        chunk: ChunkMetadata object
        config: Embedding configuration
        use_cache: Whether to use/update cache
        api_key: OpenAI API key (default: from env)

    Returns:
        Embedding vector

    Example:
        >>> embedding = embed_single_chunk(chunk)
        >>> print(f"Embedding dimensionality: {len(embedding)}")
    """
    embeddings, _ = embed_chunks([chunk], config, use_cache, api_key)
    return embeddings[0]


if __name__ == "__main__":
    # Test embedding generation
    from llm_metadata.schemas.chunk_metadata import (
        ChunkMetadata,
        SectionMetadata,
        SectionType,
        ParserInfo
    )

    print("Embedding Generation Test:")
    print("-" * 60)

    # Create test chunk
    test_chunk = ChunkMetadata(
        chunk_id="TEST_chunk_1",
        chunk_index_in_section=0,
        work_id="TEST",
        doi="10.1234/test",
        title="Test Paper",
        publication_year=2024,
        authors=["Test Author"],
        author_orcids=None,
        venue="Test Journal",
        oa_status="gold",
        pdf_sha256="abc123",
        local_pdf_path=None,
        pdf_url=None,
        parser=ParserInfo(tool="grobid", version="0.8.0"),
        language="en",
        keywords=["test"],
        section=SectionMetadata(
            section_id="TEST_sec_1",
            section_title_raw="Introduction",
            section_type_normalized=SectionType.INTRO,
            section_path="Introduction",
            section_level=1
        ),
        text="This is a test chunk for embedding generation. It contains multiple sentences.",
        token_count=15,
        char_start=0,
        char_end=80,
        page_start=1,
        page_end=1,
        is_abstract=False,
        is_references=False,
        has_equation=False,
        has_table_mention=False,
        has_figure_mention=False
    )

    # Test with small dimensions for quick testing
    config = EmbeddingConfig(
        model="text-embedding-3-small",
        dimensions=512,
        batch_size=10,
        cache_dir=Path("./test_cache")
    )

    try:
        # Generate embedding
        print("Generating embedding...")
        embedding = embed_single_chunk(test_chunk, config, use_cache=False)
        print(f"✓ Embedding generated: {len(embedding)} dimensions")
        print(f"  First 5 values: {embedding[:5]}")
        print()
        print("Note: To test full functionality, ensure OPENAI_API_KEY is set")

    except Exception as e:
        print(f"✗ Error: {e}")
        print("  This is expected if OPENAI_API_KEY is not set")
