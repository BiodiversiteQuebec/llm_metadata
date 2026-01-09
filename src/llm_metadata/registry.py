"""
Registry database for PDF processing pipeline.

Tracks document processing status, parser versions, and chunk indexing state
for idempotent pipeline execution. Uses SQLite for simplicity and portability.
"""

import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict
from contextlib import contextmanager


DEFAULT_REGISTRY_PATH = Path(__file__).parent.parent.parent / "data" / "registry.sqlite"


@contextmanager
def get_connection(db_path: Path = DEFAULT_REGISTRY_PATH):
    """
    Context manager for SQLite connection with automatic commit/rollback.

    Args:
        db_path: Path to registry database file

    Yields:
        sqlite3.Connection: Database connection
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # Enable column access by name
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_registry(db_path: Path = DEFAULT_REGISTRY_PATH) -> None:
    """
    Initialize registry database with documents and chunks tables.

    Creates tables if they don't exist. Safe to call multiple times (idempotent).

    Args:
        db_path: Path to registry database file

    Example:
        >>> from llm_metadata.registry import init_registry
        >>> init_registry()  # Creates data/registry.sqlite
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with get_connection(db_path) as conn:
        cursor = conn.cursor()

        # Documents table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                work_id TEXT PRIMARY KEY,
                pdf_sha256 TEXT UNIQUE NOT NULL,
                source_path TEXT NOT NULL,
                doi TEXT,
                title TEXT,
                publication_year INTEGER,
                status TEXT NOT NULL DEFAULT 'PENDING',
                parser_version TEXT,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                error_message TEXT,
                CHECK (status IN ('PENDING', 'PARSED', 'CHUNKED', 'INDEXED', 'ERROR'))
            )
        """)

        # Chunks table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chunks (
                chunk_id TEXT PRIMARY KEY,
                work_id TEXT NOT NULL REFERENCES documents(work_id) ON DELETE CASCADE,
                section_id TEXT NOT NULL,
                chunk_index_in_section INTEGER NOT NULL,
                vector_indexed BOOLEAN NOT NULL DEFAULT FALSE,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Indexes for common queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_documents_status
            ON documents(status)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_documents_sha256
            ON documents(pdf_sha256)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_chunks_work_id
            ON chunks(work_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_chunks_indexed
            ON chunks(vector_indexed)
        """)


def upsert_document(
    work_id: str,
    pdf_sha256: str,
    source_path: Path,
    doi: Optional[str] = None,
    title: Optional[str] = None,
    publication_year: Optional[int] = None,
    status: str = "PENDING",
    parser_version: Optional[str] = None,
    error_message: Optional[str] = None,
    db_path: Path = DEFAULT_REGISTRY_PATH
) -> None:
    """
    Insert or update document record in registry.

    Updates updated_at timestamp automatically.

    Args:
        work_id: OpenAlex work ID (primary key)
        pdf_sha256: SHA256 hash of PDF file
        source_path: Local path to PDF
        doi: Digital Object Identifier (optional)
        title: Paper title (optional)
        publication_year: Publication year (optional)
        status: Processing status (PENDING, PARSED, CHUNKED, INDEXED, ERROR)
        parser_version: Parser version string (e.g., 'grobid-0.8.0')
        error_message: Error message if status is ERROR
        db_path: Path to registry database

    Example:
        >>> upsert_document(
        ...     work_id="W12345",
        ...     pdf_sha256="abc123...",
        ...     source_path=Path("data/pdfs/2024/paper.pdf"),
        ...     doi="10.1234/example",
        ...     status="PARSED",
        ...     parser_version="grobid-0.8.0"
        ... )
    """
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO documents (
                work_id, pdf_sha256, source_path, doi, title, publication_year,
                status, parser_version, error_message, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(work_id) DO UPDATE SET
                pdf_sha256 = excluded.pdf_sha256,
                source_path = excluded.source_path,
                doi = excluded.doi,
                title = excluded.title,
                publication_year = excluded.publication_year,
                status = excluded.status,
                parser_version = excluded.parser_version,
                error_message = excluded.error_message,
                updated_at = excluded.updated_at
        """, (
            work_id,
            pdf_sha256,
            str(source_path),
            doi,
            title,
            publication_year,
            status,
            parser_version,
            error_message,
            datetime.utcnow().isoformat()
        ))


def get_document(work_id: str, db_path: Path = DEFAULT_REGISTRY_PATH) -> Optional[Dict]:
    """
    Retrieve document record by work_id.

    Args:
        work_id: OpenAlex work ID
        db_path: Path to registry database

    Returns:
        Dictionary with document fields, or None if not found

    Example:
        >>> doc = get_document("W12345")
        >>> if doc and doc['status'] == 'INDEXED':
        ...     print("Already indexed, skipping")
    """
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM documents WHERE work_id = ?", (work_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def list_documents_by_status(
    status: str,
    db_path: Path = DEFAULT_REGISTRY_PATH
) -> List[Dict]:
    """
    List all documents with given status.

    Args:
        status: Processing status to filter by
        db_path: Path to registry database

    Returns:
        List of document dictionaries

    Example:
        >>> pending = list_documents_by_status("PENDING")
        >>> print(f"Found {len(pending)} documents to process")
    """
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM documents WHERE status = ?", (status,))
        return [dict(row) for row in cursor.fetchall()]


def update_document_status(
    work_id: str,
    status: str,
    error_message: Optional[str] = None,
    db_path: Path = DEFAULT_REGISTRY_PATH
) -> None:
    """
    Update document processing status.

    Args:
        work_id: OpenAlex work ID
        status: New status (PENDING, PARSED, CHUNKED, INDEXED, ERROR)
        error_message: Error message if status is ERROR
        db_path: Path to registry database

    Example:
        >>> update_document_status("W12345", "ERROR", "GROBID timeout")
    """
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE documents
            SET status = ?, error_message = ?, updated_at = ?
            WHERE work_id = ?
        """, (status, error_message, datetime.utcnow().isoformat(), work_id))


def upsert_chunk(
    chunk_id: str,
    work_id: str,
    section_id: str,
    chunk_index_in_section: int,
    vector_indexed: bool = False,
    db_path: Path = DEFAULT_REGISTRY_PATH
) -> None:
    """
    Insert or update chunk record in registry.

    Args:
        chunk_id: Unique chunk ID
        work_id: Parent document work_id
        section_id: Parent section ID
        chunk_index_in_section: Chunk position within section
        vector_indexed: Whether chunk has been indexed in Qdrant
        db_path: Path to registry database

    Example:
        >>> upsert_chunk(
        ...     chunk_id="W12345_chunk_0",
        ...     work_id="W12345",
        ...     section_id="W12345_sec_1",
        ...     chunk_index_in_section=0,
        ...     vector_indexed=True
        ... )
    """
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO chunks (
                chunk_id, work_id, section_id, chunk_index_in_section,
                vector_indexed, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(chunk_id) DO UPDATE SET
                vector_indexed = excluded.vector_indexed,
                updated_at = excluded.updated_at
        """, (
            chunk_id,
            work_id,
            section_id,
            chunk_index_in_section,
            vector_indexed,
            datetime.utcnow().isoformat()
        ))


def get_chunks_for_document(
    work_id: str,
    db_path: Path = DEFAULT_REGISTRY_PATH
) -> List[Dict]:
    """
    Retrieve all chunks for a document.

    Args:
        work_id: OpenAlex work ID
        db_path: Path to registry database

    Returns:
        List of chunk dictionaries

    Example:
        >>> chunks = get_chunks_for_document("W12345")
        >>> indexed_count = sum(1 for c in chunks if c['vector_indexed'])
        >>> print(f"Indexed {indexed_count}/{len(chunks)} chunks")
    """
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM chunks WHERE work_id = ?", (work_id,))
        return [dict(row) for row in cursor.fetchall()]


def delete_document_and_chunks(
    work_id: str,
    db_path: Path = DEFAULT_REGISTRY_PATH
) -> None:
    """
    Delete document and all associated chunks.

    Cascades to chunks table via foreign key constraint.

    Args:
        work_id: OpenAlex work ID
        db_path: Path to registry database

    Example:
        >>> delete_document_and_chunks("W12345")
    """
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM documents WHERE work_id = ?", (work_id,))


if __name__ == "__main__":
    # Initialize database when run as script
    print(f"Initializing registry at {DEFAULT_REGISTRY_PATH}")
    init_registry()
    print("Registry initialized successfully")
