# Two-Stage Evidence Extraction Strategy

**Status:** Proposal for pilot testing  
**Date:** 2026-01-09  
**Context:** Alternative to current single-pass extraction to improve accuracy and debuggability

---

## Overview

Implement a two-stage pipeline that separates evidence retrieval from structured extraction:

1. **Stage 1: Evidence Extraction** - Find all relevant text spans (quotes) that could support metadata fields
2. **Post-Processing** - Clean, deduplicate, and categorize evidence
3. **Stage 2: Structured Extraction** - Use evidence as grounding context to extract structured schema

This approach aims to reduce hallucination, improve accuracy, and provide better provenance tracking.

---

## Proposed Architecture

### Stage 1: Evidence Extraction

**Goal:** Identify all text spans relevant to biodiversity metadata extraction.

**Schema:**
```python
class EvidenceQuote(BaseModel):
    quote: str = Field(
        ..., 
        description="Exact text span from the document"
    )
    likely_field: str = Field(
        ..., 
        description="Field this quote likely supports: species, temporal, spatial, data_type, geospatial_info, etc."
    )
    confidence: int = Field(
        ..., 
        ge=0, 
        le=5,
        description="Confidence (0-5) that this quote is relevant"
    )
    source_section: Optional[str] = Field(
        None,
        description="Document section: abstract, methods, results, etc."
    )

class EvidenceExtractionResult(BaseModel):
    quotes: list[EvidenceQuote]
```

**Prompt Strategy:**
- Simple retrieval-focused prompt (no complex schema)
- Few-shot examples showing what constitutes relevant evidence
- Emphasize: "Extract quotes even if you're unsure which field they support"

**Model:** GPT-3.5-turbo or Claude Haiku (fast, cheap, good at retrieval)

---

### Post-Processing Layer

Between stages, apply:

1. **Deduplication** - Remove overlapping/redundant quotes
2. **Prioritization** - Rank by confidence and source section (abstract > methods > discussion)
3. **Filtering** - Remove quotes below confidence threshold (e.g., < 2)
4. **Augmentation** (optional) - Add regex-extracted patterns (years, coordinates, numbers)

Output: Cleaned list of high-quality evidence quotes

---

### Stage 2: Structured Extraction

**Goal:** Extract `DatasetFeatureExtraction` schema using evidence as grounding context.

**Input:**
- Original text (or just evidence quotes to save tokens)
- Extracted evidence from Stage 1
- Target schema: `DatasetFeatureExtraction`

**Prompt Strategy:**
```
Based on these extracted quotes:
- "eastern chipmunks (Tamias striatus)" → species
- "sampled from 2000-2008" → temporal
- "100 km² study area" → spatial

Extract structured metadata using the DatasetFeatureExtraction schema.
Use ONLY the provided quotes as evidence. If a field cannot be extracted from the quotes, leave it as None.
```

**Model:** GPT-4 or GPT-5-mini (needs to handle complex schema and reasoning)

---

## Comparison: Single-Pass vs Two-Stage

| Aspect | **Single-Pass (Current)** | **Two-Stage (Proposed)** |
|--------|---------------------------|--------------------------|
| **Latency** | 1 API call (~5s) | 2 API calls (~10s) |
| **Token Cost** | ~3,000 tokens | ~4,500 tokens (+50%) |
| **Accuracy Potential** | Model-dependent | Higher (grounded extraction) |
| **Recall Risk** | Medium | Higher (Stage 1 miss = permanent loss) |
| **Debuggability** | Low (opaque extraction) | High (inspect evidence artifact) |
| **Complexity** | Low (1 function) | High (2 functions + post-processing) |
| **Flexibility** | Fixed schema | Can re-run Stage 2 with different schemas |
| **Hallucination Risk** | Higher | Lower (forced grounding) |
| **Best Use Case** | Production speed | Research, high-accuracy needs |

---

## Hybrid Approach (Recommended)

**Don't replace single-pass entirely.** Instead, implement **conditional evidence extraction**:

### Option A: Mode-Based Extraction
```python
def extract_metadata(text, mode='fast'):
    """
    mode options:
    - 'fast': Single-pass extraction (production)
    - 'accurate': Two-stage with evidence (evaluation)
    - 'debug': Two-stage + detailed evidence tracking
    """
    if mode == 'fast':
        return single_pass_extraction(text)
    elif mode in ['accurate', 'debug']:
        evidence = extract_evidence(text)  # Stage 1
        result = extract_structured(text, evidence)  # Stage 2
        if mode == 'debug':
            return result, evidence  # Return both for analysis
        return result
```

### Option B: Post-Hoc Evidence (Lighter Alternative)
```python
# Stage 1: Extract features (existing approach)
result = extract_from_text(text, schema=DatasetFeatureExtraction)

# Stage 2 (optional): Explain extractions only when needed
if need_evidence:
    evidence = explain_extraction(
        text=text,
        extraction=result,
        fields=['species', 'data_type']  # Only fields needing explanation
    )
```

**Stage 2 Prompt (Post-Hoc):**
```
Given these extracted values:
- species: ['Tamias striatus', 'raccoons']
- data_type: ['abundance']

For each value, provide:
1. Direct quote from text supporting it
2. Confidence (0-5)
3. Brief reasoning

Output: list[FieldEvidence]
```

**Benefits:**
- ✅ No latency penalty for production (opt-in Stage 2)
- ✅ Lower token cost (text sent once)
- ✅ Evidence available for evaluation/debugging
- ✅ Can batch Stage 2 calls separately

---

## Implementation Plan

### Phase 1: Pilot (1 Week)
1. **Implement both strategies** in `single_doi_extraction_with_evidence.ipynb`
2. **Test on 5 DOIs** (from existing test set)
3. **Measure:**
   - Token cost per strategy
   - Latency per strategy
   - F1 scores per strategy
   - Evidence quality (usefulness for debugging)

### Phase 2: Evaluation (1 Week)
1. **Expand to 20 DOIs** if pilot shows promise
2. **Compare metrics:**
   - Does two-stage improve F1 (target: >0.10 improvement to justify cost)
   - Is evidence quality sufficient for debugging false positives?
   - Does Stage 1 have acceptable recall (>90%)?

### Phase 3: Integration (Optional, 1 Week)
1. **If metrics justify:** Implement mode-based extraction in `gpt_extract.py`
2. **Add evidence storage:** Save evidence artifacts for later analysis
3. **Update notebooks:** Use two-stage for evaluation workflows

---

## Success Criteria

**Pilot Phase:**
- [ ] Two-stage implementation functional
- [ ] Token cost measured (<2x single-pass)
- [ ] Latency measured (<15s total)
- [ ] Evidence quality validated (human review of 10 examples)

**Evaluation Phase:**
- [ ] F1 improvement >0.10 (e.g., 0.47 → 0.57+)
- [ ] Stage 1 recall >90% (few missed relevant quotes)
- [ ] Evidence useful for debugging in 80%+ of error cases

**Go/No-Go Decision:**
- **Go:** F1 improvement ≥0.10 AND evidence quality high
- **No-Go:** Minimal accuracy gain OR token cost >2x

---

## Alternative Architectures Considered

### 1. Single-Pass with Evidence (Current Approach)
**Pros:** Simple, fast, lower cost  
**Cons:** Evidence quality inconsistent, potential hallucination

### 2. Three-Stage (Evidence → Extraction → Validation)
**Pros:** Maximum accuracy  
**Cons:** 3x latency, 3x cost, diminishing returns

### 3. Retrieval-Augmented Generation (RAG)
**Pros:** Scales to long documents  
**Cons:** Requires vector DB, adds infrastructure complexity

### 4. Chain-of-Thought Prompting
**Pros:** Single pass with better reasoning  
**Cons:** Longer outputs, less structured evidence

---

## Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| **Stage 1 misses evidence** | Use high recall prompting; test on diverse papers |
| **Token cost exceeds budget** | Implement token limits; use cheaper models for Stage 1 |
| **Latency too high** | Batch processing; parallel API calls where possible |
| **Post-processing bugs** | Unit tests for deduplication, filtering logic |
| **Evidence doesn't improve accuracy** | Pivot to post-hoc explanation approach |

---

## Open Questions

1. **Should Stage 2 see original text or only evidence quotes?**
   - Pro (original): Can catch missed evidence
   - Pro (quotes only): Forces grounding, reduces tokens

2. **What confidence threshold for Stage 1 filtering?**
   - Test thresholds: 0, 1, 2, 3
   - Measure precision/recall tradeoff

3. **Should evidence categorization be model-driven or rule-based?**
   - Model: More flexible, can learn patterns
   - Rules: More reliable, easier to debug

4. **How to handle conflicting evidence?**
   - Return all with confidence scores
   - Use ensemble/voting
   - Flag for human review

---

## References

- Current implementation: `src/llm_metadata/gpt_extract.py`
- Evaluation framework: `src/llm_metadata/groundtruth_eval.py`
- Evidence schema: `src/llm_metadata/schemas/fuster_features.py` (`FieldEvidence`)
- Test notebook: `notebooks/single_doi_extraction_with_evidence.ipynb`

---

## Next Steps

1. **Discuss with team:** Is 50% token cost increase acceptable for >10% F1 gain?
2. **Implement pilot:** Create `two_stage_extraction.py` module
3. **Run experiment:** Test on 5 DOIs, document results
4. **Decision point:** Continue to Phase 2 or pivot to post-hoc approach
