# Plan: Full-Text Schema Extraction Without Vector DB

Test whether feeding complete document sections directly to GPT (without embeddings or chunking) improves Fuster metadata extraction quality over abstract-only baseline.

## Steps

1. **Download test PDF** - Check if `data/pdfs/10.5061_dryad.3nh72` exists; if not, use `download_pdf_with_fallback()` from `pdf_download.py` with DOI `10.5061/dryad.3nh72`

2. **Parse PDF to sections** - Use `process_pdf()` from `pdf_parsing.py` to extract `ParsedDocument` with hierarchical `Section` objects containing `.title` and `.text`

3. **Select relevant sections by keywords** - Filter sections where `classify_section(section.title)` returns `ABSTRACT`, `METHODS`, or where `section.title` contains keywords: `data|dataset|survey|site|area|species|sampling|collection`

4. **Count tokens per section** - Use `count_tokens(section.text)` from `chunking.py` with tiktoken `cl100k_base` encoding to measure each section's token footprint

5. **Construct prompt with full sections** - Build user message: concatenate abstract + filtered sections with clear delimiters (e.g., `## {section.title}\n{section.text}\n\n`), ensuring total stays under context window limit.

6. **Extract metadata with token logging** - Call `classify_abstract()` from `gpt_classify.py` with full-text prompt; capture `result['usage']` dict containing `prompt_tokens`, `completion_tokens`, `total_tokens`. May need to create a new function `classify_fulltext()` if necessary.

7. **Evaluate vs ground truth** - Load manual annotation for DOI `10.5061/dryad.3nh72` from `fuster_annotations_validation.ipynb`, use `evaluate_indexed()` from `schemas/evaluation.py` to compute per-field precision/recall/F1

8. **Compare with abstract-only baseline** - Re-run extraction using only `doc.abstract`, log token usage difference, compare F1 scores to quantify full-text benefit

9. **Run additional test cases** - If successful, repeat for other Fuster validation DOIs (e.g., `10.1002/ece3.1476`, `10.5061/dryad.xgxd254k5`) to confirm generalizability.

10. **Document findings** - Summarize results, token usage, and extraction quality improvements in a report for future reference. Estimate cost implications based on token usage.(Input $0.25 Cached input $0.025 Output $2.005 per 1M tokens). Weigh pros/cons of going embedding-free for this use case.

## Further Considerations

1. **Context window strategy?** If selected sections exceed ~80k tokens, we should abort.

2. **Batch evaluation?** Should we test on all 5 Fuster validation DOIs (from `fuster_test_extraction_evaluation.ipynb`) or just the single DOI to start? No, out of scope for now.

3. **Section selection heuristic refinement?** Current regex-based keyword matching may miss relevant content in non-standard section titles. Should we add fuzzy matching or expand keyword list? No, out of scope for now.
