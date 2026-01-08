"""
Schema for OpenAlex work metadata.

This module defines Pydantic models for scientific papers retrieved from OpenAlex,
designed for ecology paper retrieval from Quebec researchers with ORCID tracking.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import date
from pathlib import Path


class OpenAlexAuthor(BaseModel):
    """
    Author metadata with ORCID and institutional affiliations.

    Captures author information including persistent identifiers (ORCID)
    and affiliated institutions (ROR IDs) for researcher tracking.
    """

    name: str = Field(
        ...,
        description="Author display name"
    )
    orcid: Optional[str] = Field(
        default=None,
        description="ORCID identifier (without https://orcid.org/ prefix)"
    )
    institutions: Optional[List[str]] = Field(
        default=None,
        description="List of institution ROR IDs"
    )


class OpenAlexWork(BaseModel):
    """
    OpenAlex work metadata for ecology papers.

    Designed for Quebec ecology/biodiversity researcher paper retrieval.
    Captures essential metadata for paper categorization, PDF access,
    and author tracking with persistent identifiers.
    """

    # Core identifiers
    openalex_id: str = Field(
        ...,
        description="OpenAlex work ID (e.g., https://openalex.org/W2741809807)"
    )
    doi: Optional[str] = Field(
        default=None,
        description="Digital Object Identifier"
    )

    # Bibliographic metadata
    title: str = Field(
        ...,
        description="Work title"
    )
    abstract: Optional[str] = Field(
        default=None,
        description="Abstract text (reconstructed from inverted index)"
    )
    publication_date: Optional[date] = Field(
        default=None,
        description="Full publication date"
    )
    publication_year: Optional[int] = Field(
        default=None,
        description="Publication year"
    )

    # Authors and affiliations
    authors: Optional[List[OpenAlexAuthor]] = Field(
        default=None,
        description="List of authors with ORCID and affiliations"
    )

    # Open access metadata
    is_oa: bool = Field(
        default=False,
        description="Open access flag"
    )
    oa_status: Optional[str] = Field(
        default=None,
        description="OA type: diamond, gold, green, hybrid, bronze, closed"
    )
    pdf_url: Optional[str] = Field(
        default=None,
        description="Best available PDF URL from best_oa_location"
    )
    landing_page_url: Optional[str] = Field(
        default=None,
        description="Landing page URL"
    )

    # Work type and classification
    work_type: Optional[str] = Field(
        default=None,
        description="Work type: article, preprint, letter, editorial, etc."
    )
    is_preprint: bool = Field(
        default=False,
        description="Derived flag: True if work_type is preprint"
    )

    # Topics
    topics: Optional[List[str]] = Field(
        default=None,
        description="List of OpenAlex topic IDs"
    )

    # Institutional affiliations
    institutions: Optional[List[str]] = Field(
        default=None,
        description="List of unique institution ROR IDs from all authors"
    )

    # Local storage
    local_pdf_path: Optional[Path] = Field(
        default=None,
        description="Local path to downloaded PDF (populated after download)"
    )

    @field_validator('is_preprint', mode='before')
    @classmethod
    def set_is_preprint(cls, v, info):
        """Auto-set is_preprint from work_type if not explicitly provided."""
        # If is_preprint is already set, use that value
        if v is not None and isinstance(v, bool):
            return v

        # Otherwise derive from work_type
        work_type = info.data.get('work_type', '').lower()
        return work_type == 'preprint'

    class Config:
        """Pydantic configuration."""
        populate_by_name = True


def work_dict_to_model(work: dict) -> OpenAlexWork:
    """
    Convert OpenAlex API work dict to Pydantic model.

    Handles field mapping and nested data extraction from OpenAlex API response.

    Args:
        work: OpenAlex work dictionary from API response

    Returns:
        OpenAlexWork model instance

    Example:
        >>> response = search_works(ror_id="...", publication_year=2025)
        >>> models = [work_dict_to_model(w) for w in response['results']]
    """
    from llm_metadata.openalex import (
        extract_abstract,
        extract_pdf_url,
        extract_authors,
        is_preprint
    )

    # Extract basic fields
    openalex_id = work.get('id', '')
    doi = work.get('doi')
    title = work.get('title', '')

    # Extract dates
    publication_date_str = work.get('publication_date')
    publication_date_obj = None
    if publication_date_str:
        try:
            publication_date_obj = date.fromisoformat(publication_date_str)
        except (ValueError, TypeError):
            pass

    publication_year = work.get('publication_year')

    # Extract abstract
    abstract = extract_abstract(work)

    # Extract authors
    authors = extract_authors(work)
    author_models = [OpenAlexAuthor(**author) for author in authors]

    # Extract open access info
    open_access = work.get('open_access', {})
    is_oa = open_access.get('is_oa', False)
    oa_status = open_access.get('oa_status')

    # Extract PDF URL
    pdf_url = extract_pdf_url(work)

    # Extract landing page
    best_oa_location = work.get('best_oa_location', {})
    landing_page_url = best_oa_location.get('landing_page_url')

    # Extract work type
    work_type = work.get('type')
    is_preprint_flag = is_preprint(work)

    # Extract topics
    topics_list = work.get('topics', [])
    topic_ids = [topic.get('id') for topic in topics_list if topic.get('id')]

    # Extract unique institution ROR IDs from all authors
    institutions = set()
    for author in authors:
        if author.get('institutions'):
            institutions.update(author['institutions'])
    institutions_list = list(institutions) if institutions else None

    return OpenAlexWork(
        openalex_id=openalex_id,
        doi=doi,
        title=title,
        abstract=abstract,
        publication_date=publication_date_obj,
        publication_year=publication_year,
        authors=author_models if author_models else None,
        is_oa=is_oa,
        oa_status=oa_status,
        pdf_url=pdf_url,
        landing_page_url=landing_page_url,
        work_type=work_type,
        is_preprint=is_preprint_flag,
        topics=topic_ids if topic_ids else None,
        institutions=institutions_list
    )


def works_to_dict_list(works: List[OpenAlexWork]) -> List[dict]:
    """
    Convert list of OpenAlexWork models to list of dictionaries.

    Useful for DataFrame conversion and CSV export.

    Args:
        works: List of OpenAlexWork models

    Returns:
        List of dictionaries

    Example:
        >>> import pandas as pd
        >>> df = pd.DataFrame(works_to_dict_list(works))
        >>> df.to_csv("works.csv", index=False)
    """
    return [work.model_dump() for work in works]
