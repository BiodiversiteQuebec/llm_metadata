from typing import List, Optional, Type
from pydantic import BaseModel, Field, create_model

class Evidence(BaseModel):
    """
    Supporting evidence for a single field extraction.
    
    Provides confidence scores, direct quotes, and reasoning to explain
    why a particular value was extracted from text. Enables analysis of
    extraction quality and debugging of low-confidence extractions.
    
    **Multiple Evidence Strategy:**
    Create multiple FieldEvidence entries for the same field when:
    - Multiple distinct quotes support the same extracted value (corroborating evidence)
    - Multiple values are identified for list fields (e.g., different species mentioned in different parts)
    - Same value has different confidence levels depending on source/context
    - Conflicting or ambiguous evidence requires separate documentation
    
    This approach enables fine-grained provenance tracking and confidence analysis per evidence piece.
    """
    field_name: str = Field(
        ...,
        description="Name of the field this evidence supports (e.g., 'species', 'data_type')"
    )
    value: Optional[str] = Field(
        None,
        description="Extracted value as string. Cast to string if numerical, list, or other type (e.g., '[\"Tamias striatus\", \"Mammalia\"]', '100000', 'abundance')."
    )
    confidence: Optional[int] = Field(
        None,
        ge=0,
        le=5,
        description=(
            "Confidence score (0-5) for this extraction. Score based on DIRECTNESS of evidence, not reasoning confidence.\n\n"
            "  5 = Value explicitly stated using exact terminology\n"
            "      Example: Text says 'presence-absence data' → data_type: presence-absence (confidence: 5)\n\n"
            "  4 = Value stated using synonyms or clear direct paraphrasing\n"
            "      Example: Text says 'occurrence records' → data_type: presence-absence (confidence: 4)\n\n"
            "  3 = Value inferred from domain-specific evidence or methodology\n"
            "      Example: Text says 'identified individuals' → data_type: presence-absence (confidence: 3)\n"
            "      Example: Text says 'counted birds at each site' → data_type: abundance (confidence: 3)\n\n"
            "  2 = Value inferred from weak, ambiguous, or indirect evidence\n"
            "      Example: Text says 'studied wildlife' → data_type: ??? (confidence: 2)\n\n"
            "  1 = Value highly speculative, requires significant interpretation\n"
            "      Example: Guessing data type from unrelated context (confidence: 1)\n\n"
            "  0 = No supporting evidence found, or unable to extract reliably\n\n"
            "CRITICAL: Use 5 ONLY when the value appears explicitly in text. Inferred values should be ≤3."
        )
    )
    quote: Optional[str] = Field(
        None,
        description="Direct quote from the text supporting this extraction"
    )
    reasoning: Optional[str] = Field(
        None,
        description="Brief explanation of why this value was extracted"
    )
    source_section: Optional[str] = Field(
        None,
        description="Text section where evidence was found (e.g., 'abstract', 'methods', 'results')"
    )

def EvidenceListField(**kwargs):
    """
    Pydantic Field for a list of FieldEvidence objects.

    This field can be used in any metadata schema to capture multiple pieces
    of evidence supporting various field extractions.
    """
    return Field(
        ...,
        description=(
            "List of evidence supporting extracted fields. Include confidence scores, quotes, and reasoning for key extractions.\n\n"
            "**IMPORTANT:** Create multiple evidence entries for the same field when:\n"
            "  - Multiple quotes support the same value (corroborating evidence)\n"
            "  - Different values extracted for list fields (e.g., each species mention)\n"
            "  - Same value with varying confidence based on different contexts\n"
            "  - Conflicting or ambiguous evidence needs separate documentation\n\n"
            "Example: For species=['Tamias striatus', 'raccoons'], provide two FieldEvidence objects with field_name='species', "
            "each containing its own value, quote, confidence, and reasoning."
        ),
        **kwargs
    )

class Evidences(BaseModel):
    """
    Container for multiple pieces of evidence supporting various field extractions.
    """
    evidences: List[Evidence] = EvidenceListField()

def add_evidence_field(model: Type[BaseModel]) -> Type[BaseModel]:
    """
    Dynamically adds an 'evidences' field to the given Pydantic model.

    This function modifies the provided model class to include an 'evidences' field,
    which is a list of FieldEvidence instances. This allows any metadata schema
    to incorporate detailed evidence tracking for its fields.

    Args:
        model (Type[BaseModel]): The Pydantic model class to modify.
    Returns:
        Type[BaseModel]: The modified Pydantic model class with the 'evidence' field added.
    """
    new_model = create_model(
        f"{model.__name__}WithEvidence",
        __base__=model,
        evidence=(
            Optional[List[Evidence]],
            EvidenceListField()
        )
    )
    # Set __module__ and __qualname__ to make the model picklable for joblib caching
    new_model.__module__ = model.__module__
    new_model.__qualname__ = f"{model.__qualname__}WithEvidence"
    return new_model

