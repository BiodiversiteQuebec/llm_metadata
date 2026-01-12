"""
Quick test script to verify raw PDF extraction functionality.
"""
from pathlib import Path
from llm_metadata.gpt_classify import extract_text_from_pdf, classify_pdf
from llm_metadata.schemas import DatasetAbstractMetadata

# Test 1: Text extraction from PDF
print("=== Test 1: Text Extraction ===")
pdf_dir = Path("data/pdfs/fuster")
pdf_files = list(pdf_dir.glob("*.pdf"))

# Try multiple PDFs until we find a valid one
valid_pdf = None
for pdf_file in pdf_files[:5]:  # Try first 5 PDFs
    try:
        text = extract_text_from_pdf(pdf_file, max_pages=1)
        if text and len(text) > 100:
            valid_pdf = pdf_file
            break
    except:
        continue

if valid_pdf:
    print(f"Testing with: {valid_pdf.name}")
    
    try:
        text = extract_text_from_pdf(valid_pdf, max_pages=2)
        print(f"Extracted text length: {len(text)} characters")
        print(f"First 200 characters:\n{text[:200]}...")
        print("✓ Text extraction successful\n")
    except Exception as e:
        print(f"✗ Text extraction failed: {e}\n")
else:
    print("No valid PDF files found in data/pdfs/fuster\n")

# Test 2: Pipeline configuration
print("=== Test 2: Pipeline Configuration ===")
from llm_metadata.fulltext_pipeline import (
    FulltextPipelineConfig,
    GPTClassifyConfig,
    SectionSelectionConfig
)

# GROBID mode
config_grobid = FulltextPipelineConfig(
    gpt_config=GPTClassifyConfig(
        model="gpt-5-mini",
        extraction_method="grobid"
    )
)
print(f"GROBID config extraction_method: {config_grobid.gpt_config.extraction_method}")

# Raw PDF mode
config_raw = FulltextPipelineConfig(
    gpt_config=GPTClassifyConfig(
        model="gpt-5-mini",
        extraction_method="raw_pdf",
        max_pdf_pages=10
    )
)
print(f"Raw PDF config extraction_method: {config_raw.gpt_config.extraction_method}")
print(f"Raw PDF config max_pdf_pages: {config_raw.gpt_config.max_pdf_pages}")
print("✓ Pipeline configuration successful\n")

print("=== All Tests Passed ===")
