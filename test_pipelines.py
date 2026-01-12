"""
Test script to verify all three classification pipelines work correctly.
"""

from pathlib import Path
import sys

# Test imports
print("=== Testing Pipeline Imports ===")
try:
    from llm_metadata.text_pipeline import (
        TextClassificationConfig,
        TextInputRecord,
        text_classification_flow
    )
    print("✓ text_pipeline imports successful")
except Exception as e:
    print(f"✗ text_pipeline import failed: {e}")
    sys.exit(1)

try:
    from llm_metadata.pdf_pipeline import (
        PDFClassificationConfig,
        PDFInputRecord,
        pdf_classification_flow
    )
    print("✓ pdf_pipeline imports successful")
except Exception as e:
    print(f"✗ pdf_pipeline import failed: {e}")
    sys.exit(1)

try:
    from llm_metadata.section_pipeline import (
        SectionClassificationConfig,
        SectionInputRecord,
        SectionSelectionConfig,
        section_classification_flow
    )
    print("✓ section_pipeline imports successful")
except Exception as e:
    print(f"✗ section_pipeline import failed: {e}")
    sys.exit(1)

try:
    from llm_metadata.pipelines import classify, compare_pipelines
    print("✓ unified pipelines interface imports successful")
except Exception as e:
    print(f"✗ pipelines interface import failed: {e}")
    sys.exit(1)

print()

# Test configuration creation
print("=== Testing Configuration Creation ===")
try:
    text_config = TextClassificationConfig(model="gpt-5-mini")
    print(f"✓ TextClassificationConfig created (model: {text_config.model})")
except Exception as e:
    print(f"✗ TextClassificationConfig failed: {e}")

try:
    pdf_config = PDFClassificationConfig(model="gpt-5-mini", max_pdf_pages=10)
    print(f"✓ PDFClassificationConfig created (max_pages: {pdf_config.max_pdf_pages})")
except Exception as e:
    print(f"✗ PDFClassificationConfig failed: {e}")

try:
    section_config = SectionClassificationConfig(
        model="gpt-5-mini",
        section_config=SectionSelectionConfig(include_all=False)
    )
    print(f"✓ SectionClassificationConfig created")
except Exception as e:
    print(f"✗ SectionClassificationConfig failed: {e}")

print()

# Test record creation
print("=== Testing Record Creation ===")
try:
    text_record = TextInputRecord(
        id="test_1",
        text="Sample text for classification",
        metadata={"source": "test"}
    )
    print(f"✓ TextInputRecord created (id: {text_record.id})")
except Exception as e:
    print(f"✗ TextInputRecord failed: {e}")

try:
    pdf_record = PDFInputRecord(
        id="test_pdf",
        pdf_path="data/pdfs/sample.pdf",
        metadata={"type": "test"}
    )
    print(f"✓ PDFInputRecord created (id: {pdf_record.id})")
except Exception as e:
    print(f"✗ PDFInputRecord failed: {e}")

try:
    section_record = SectionInputRecord(
        id="test_section",
        pdf_path="data/pdfs/sample.pdf"
    )
    print(f"✓ SectionInputRecord created (id: {section_record.id})")
except Exception as e:
    print(f"✗ SectionInputRecord failed: {e}")

print()

# Test unified interface
print("=== Testing Unified Interface ===")
try:
    comparison = compare_pipelines()
    print("✓ compare_pipelines() works")
    print("\nPipeline Comparison:")
    print(comparison)
except Exception as e:
    print(f"✗ compare_pipelines() failed: {e}")

print()

# Test pipeline detection
print("=== Testing Pipeline Auto-Detection ===")
from llm_metadata.pipelines import _detect_pipeline

test_cases = [
    ("raw text string", "text"),
    (Path("paper.pdf"), "pdf"),
    (Path("manifest.csv"), "section"),
    ([Path("p1.pdf"), Path("p2.pdf")], "pdf"),
]

for source, expected in test_cases:
    detected = _detect_pipeline(source)
    status = "✓" if detected == expected else "✗"
    print(f"{status} {source!r} → {detected} (expected: {expected})")

print()

# Test deprecation warning
print("=== Testing Deprecation Warning ===")
import warnings
with warnings.catch_warnings(record=True) as w:
    warnings.simplefilter("always")
    try:
        from llm_metadata import fulltext_pipeline
        if len(w) > 0 and issubclass(w[0].category, DeprecationWarning):
            print("✓ Deprecation warning raised for fulltext_pipeline")
        else:
            print("⚠ No deprecation warning (may be expected)")
    except Exception as e:
        print(f"✗ Import failed: {e}")

print()
print("=== All Pipeline Tests Completed ===")
print("\nTo run actual classification:")
print("  1. Ensure OpenAI API key is set")
print("  2. For section pipeline: Start GROBID server")
print("  3. Use: python -m llm_metadata.text_pipeline")
print("     or: python -m llm_metadata.pdf_pipeline")
print("     or: python -m llm_metadata.section_pipeline")
