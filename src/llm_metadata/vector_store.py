"""
Qdrant vector store client for chunk indexing and retrieval.

Provides interface to Qdrant for storing chunk embeddings with rich metadata,
filtered search, and RAG retrieval. Designed for scientific paper chunks with
section-aware metadata.
"""

import os
import hashlib
from typing import List, Dict, Optional, Any
from dataclasses import dataclass

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    FieldCondition,
    Filter,
    MatchValue,
    Range,
    SearchRequest
)

from llm_metadata.schemas.chunk_metadata import ChunkMetadata


# Default collection name
DEFAULT_COLLECTION = "papers_chunks"


def chunk_id_to_int(chunk_id: str) -> int:
    """
    Convert chunk_id string to a stable integer for Qdrant.
    
    Uses MD5 hash to generate a consistent 64-bit integer.
    
    Args:
        chunk_id: String chunk identifier
        
    Returns:
        Integer representation of chunk_id
    """
    # Use MD5 hash and convert first 8 bytes to int
    hash_bytes = hashlib.md5(chunk_id.encode('utf-8')).digest()[:8]
    return int.from_bytes(hash_bytes, byteorder='big', signed=False)


@dataclass
class VectorStoreConfig:
    """
    Configuration for Qdrant vector store.

    Attributes:
        url: Qdrant server URL
        api_key: Optional API key for authentication
        collection_name: Collection name for chunks
        vector_size: Embedding dimensionality
        distance: Distance metric (Cosine, Dot, Euclidean)
    """
    url: str = "http://localhost:6333"
    api_key: Optional[str] = None
    collection_name: str = DEFAULT_COLLECTION
    vector_size: int = 3072  # text-embedding-3-large default
    distance: Distance = Distance.COSINE


def get_client(config: VectorStoreConfig = VectorStoreConfig()) -> QdrantClient:
    """
    Create Qdrant client with configuration.

    Args:
        config: Vector store configuration

    Returns:
        QdrantClient instance

    Example:
        >>> client = get_client()
        >>> print(f"Connected to Qdrant at {config.url}")
    """
    return QdrantClient(
        url=config.url,
        api_key=config.api_key
    )


def init_collection(
    config: VectorStoreConfig = VectorStoreConfig(),
    recreate: bool = False
) -> None:
    """
    Initialize Qdrant collection for paper chunks.

    Creates collection with appropriate vector configuration and payload indexes
    for filtered retrieval.

    Args:
        config: Vector store configuration
        recreate: If True, delete and recreate collection

    Raises:
        RuntimeError: If collection creation fails

    Example:
        >>> init_collection()  # Create collection if not exists
        >>> init_collection(recreate=True)  # Recreate collection
    """
    client = get_client(config)

    # Check if collection exists
    collections = client.get_collections().collections
    collection_exists = any(c.name == config.collection_name for c in collections)

    if recreate and collection_exists:
        print(f"Deleting existing collection: {config.collection_name}")
        client.delete_collection(config.collection_name)
        collection_exists = False

    if not collection_exists:
        print(f"Creating collection: {config.collection_name}")
        client.create_collection(
            collection_name=config.collection_name,
            vectors_config=VectorParams(
                size=config.vector_size,
                distance=config.distance
            )
        )

        # Create payload indexes for common filters
        print("Creating payload indexes...")

        # DOI index (keyword)
        client.create_payload_index(
            collection_name=config.collection_name,
            field_name="doi",
            field_schema="keyword"
        )

        # Publication year index (integer)
        client.create_payload_index(
            collection_name=config.collection_name,
            field_name="publication_year",
            field_schema="integer"
        )

        # Section type index (keyword)
        client.create_payload_index(
            collection_name=config.collection_name,
            field_name="section_type",
            field_schema="keyword"
        )

        # is_references flag (bool)
        client.create_payload_index(
            collection_name=config.collection_name,
            field_name="is_references",
            field_schema="bool"
        )

        # is_abstract flag (bool)
        client.create_payload_index(
            collection_name=config.collection_name,
            field_name="is_abstract",
            field_schema="bool"
        )

        # Author ORCID index (keyword array)
        client.create_payload_index(
            collection_name=config.collection_name,
            field_name="author_orcids",
            field_schema="keyword"
        )

        print(f"✓ Collection '{config.collection_name}' initialized")
    else:
        print(f"Collection '{config.collection_name}' already exists")


def chunk_to_payload(chunk: ChunkMetadata) -> Dict[str, Any]:
    """
    Convert ChunkMetadata to Qdrant payload dictionary.

    Flattens nested structures for indexing and filtering.

    Args:
        chunk: ChunkMetadata object

    Returns:
        Payload dictionary

    Example:
        >>> payload = chunk_to_payload(chunk)
        >>> print(payload.keys())
    """
    return {
        # Chunk identifiers
        "chunk_id": chunk.chunk_id,
        "chunk_index_in_section": chunk.chunk_index_in_section,

        # Document metadata
        "work_id": chunk.work_id,
        "doi": chunk.doi,
        "title": chunk.title,
        "publication_year": chunk.publication_year,
        "authors": chunk.authors,
        "author_orcids": chunk.author_orcids,
        "venue": chunk.venue,
        "oa_status": chunk.oa_status,

        # PDF metadata
        "pdf_sha256": chunk.pdf_sha256,
        "pdf_url": chunk.pdf_url,

        # Parser metadata
        "parser_tool": chunk.parser.tool,
        "parser_version": chunk.parser.version,
        "language": chunk.language,
        "keywords": chunk.keywords,

        # Section metadata (flattened)
        "section_id": chunk.section.section_id,
        "section_title": chunk.section.section_title_raw,
        "section_type": chunk.section.section_type_normalized.value,
        "section_path": chunk.section.section_path,
        "section_level": chunk.section.section_level,

        # Chunk content
        "text": chunk.text,
        "token_count": chunk.token_count,
        "char_start": chunk.char_start,
        "char_end": chunk.char_end,
        "page_start": chunk.page_start,
        "page_end": chunk.page_end,

        # Content flags
        "is_abstract": chunk.is_abstract,
        "is_references": chunk.is_references,
        "has_equation": chunk.has_equation,
        "has_table_mention": chunk.has_table_mention,
        "has_figure_mention": chunk.has_figure_mention,
    }


def upsert_chunks(
    chunks: List[ChunkMetadata],
    embeddings: List[List[float]],
    config: VectorStoreConfig = VectorStoreConfig(),
    batch_size: int = 100
) -> None:
    """
    Upsert chunks with embeddings into Qdrant.

    Inserts or updates chunks in batches for efficiency.

    Args:
        chunks: List of ChunkMetadata objects
        embeddings: List of embedding vectors (same order as chunks)
        config: Vector store configuration
        batch_size: Upsert batch size

    Raises:
        ValueError: If chunks and embeddings lengths don't match
        RuntimeError: If upsert fails

    Example:
        >>> upsert_chunks(chunks, embeddings)
        >>> print(f"Upserted {len(chunks)} chunks")
    """
    if len(chunks) != len(embeddings):
        raise ValueError(
            f"Chunks ({len(chunks)}) and embeddings ({len(embeddings)}) length mismatch"
        )

    if not chunks:
        return

    client = get_client(config)

    # Convert chunks to points
    points = []
    for chunk, embedding in zip(chunks, embeddings):
        # Convert chunk_id to integer for Qdrant
        numeric_id = chunk_id_to_int(chunk.chunk_id)
        
        # Get payload and ensure chunk_id is included
        payload = chunk_to_payload(chunk)
        payload['chunk_id_str'] = chunk.chunk_id  # Store original string ID
        
        point = PointStruct(
            id=numeric_id,
            vector=embedding,
            payload=payload
        )
        points.append(point)

    # Upsert in batches
    print(f"Upserting {len(points)} points to collection '{config.collection_name}'...")
    for batch_start in range(0, len(points), batch_size):
        batch_end = min(batch_start + batch_size, len(points))
        batch = points[batch_start:batch_end]

        client.upsert(
            collection_name=config.collection_name,
            points=batch
        )

    print(f"✓ Upserted {len(points)} chunks")


def search_chunks(
    query_vector: List[float],
    config: VectorStoreConfig = VectorStoreConfig(),
    limit: int = 10,
    exclude_references: bool = True,
    doi_filter: Optional[str] = None,
    year_range: Optional[tuple] = None,
    section_types: Optional[List[str]] = None,
    author_orcid: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Search for similar chunks using vector similarity.

    Supports filtered retrieval by metadata fields.

    Args:
        query_vector: Query embedding vector
        config: Vector store configuration
        limit: Maximum number of results
        exclude_references: Exclude reference section chunks
        doi_filter: Filter by specific DOI
        year_range: Filter by publication year range (min_year, max_year)
        section_types: Filter by section types (e.g., ["METHODS", "RESULTS"])
        author_orcid: Filter by author ORCID

    Returns:
        List of search result dictionaries with payload and score

    Example:
        >>> results = search_chunks(
        ...     query_vector,
        ...     limit=5,
        ...     section_types=["METHODS"],
        ...     year_range=(2020, 2025)
        ... )
        >>> for result in results:
        ...     print(f"{result['payload']['title']}: {result['score']}")
    """
    client = get_client(config)

    # Build filter conditions
    must_conditions = []

    if exclude_references:
        must_conditions.append(
            FieldCondition(
                key="is_references",
                match=MatchValue(value=False)
            )
        )

    if doi_filter:
        must_conditions.append(
            FieldCondition(
                key="doi",
                match=MatchValue(value=doi_filter)
            )
        )

    if year_range:
        min_year, max_year = year_range
        must_conditions.append(
            FieldCondition(
                key="publication_year",
                range=Range(gte=min_year, lte=max_year)
            )
        )

    if section_types:
        must_conditions.append(
            FieldCondition(
                key="section_type",
                match=MatchValue(value=section_types[0]) if len(section_types) == 1 else {
                    "any": section_types
                }
            )
        )

    if author_orcid:
        must_conditions.append(
            FieldCondition(
                key="author_orcids",
                match=MatchValue(value=author_orcid)
            )
        )

    # Build filter
    query_filter = None
    if must_conditions:
        query_filter = Filter(must=must_conditions)

    # Query points (new API)
    results = client.query_points(
        collection_name=config.collection_name,
        query=query_vector,
        query_filter=query_filter,
        limit=limit
    )

    # Convert to dictionaries
    return [
        {
            "id": result.id,
            "score": result.score,
            "payload": result.payload
        }
        for result in results.points
    ]


def delete_document_chunks(
    work_id: str,
    config: VectorStoreConfig = VectorStoreConfig()
) -> int:
    """
    Delete all chunks for a document from Qdrant.

    Args:
        work_id: OpenAlex work ID
        config: Vector store configuration

    Returns:
        Number of deleted chunks

    Example:
        >>> count = delete_document_chunks("W123")
        >>> print(f"Deleted {count} chunks")
    """
    client = get_client(config)

    # Delete by work_id filter
    result = client.delete(
        collection_name=config.collection_name,
        points_selector=Filter(
            must=[
                FieldCondition(
                    key="work_id",
                    match=MatchValue(value=work_id)
                )
            ]
        )
    )

    return result.operation_id  # Returns number of deleted points


def get_collection_stats(config: VectorStoreConfig = VectorStoreConfig()) -> Dict[str, Any]:
    """
    Get collection statistics.

    Args:
        config: Vector store configuration

    Returns:
        Dictionary with collection stats (point count, etc.)

    Example:
        >>> stats = get_collection_stats()
        >>> print(f"Collection has {stats['points_count']} points")
    """
    client = get_client(config)

    collection_info = client.get_collection(config.collection_name)

    return {
        "collection_name": config.collection_name,
        "points_count": collection_info.points_count,
        "vectors_count": collection_info.vectors_count if hasattr(collection_info, 'vectors_count') else collection_info.points_count,
        "indexed_vectors_count": collection_info.indexed_vectors_count if hasattr(collection_info, 'indexed_vectors_count') else None,
        "status": collection_info.status.value if hasattr(collection_info.status, 'value') else str(collection_info.status),
    }


if __name__ == "__main__":
    # Test Qdrant connection and collection initialization
    print("Qdrant Vector Store Test:")
    print("-" * 60)

    config = VectorStoreConfig(
        url=os.getenv("QDRANT_URL", "http://localhost:6333"),
        collection_name="test_papers_chunks",
        vector_size=512  # Small for testing
    )

    try:
        # Test connection
        print(f"Connecting to Qdrant at {config.url}...")
        client = get_client(config)
        print("✓ Connected")
        print()

        # Initialize collection
        print("Initializing collection...")
        init_collection(config, recreate=True)
        print()

        # Get stats
        print("Collection statistics:")
        stats = get_collection_stats(config)
        for key, value in stats.items():
            print(f"  {key}: {value}")
        print()

        # Clean up test collection
        print("Cleaning up test collection...")
        client.delete_collection(config.collection_name)
        print("✓ Test completed successfully")

    except Exception as e:
        print(f"✗ Error: {e}")
        print("  Make sure Qdrant is running (docker compose up -d)")
