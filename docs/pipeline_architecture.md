# Pipeline Architecture

## Before Refactoring

```
┌─────────────────────────────────────────────────────┐
│         fulltext_pipeline.py (1100+ lines)          │
│                                                      │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────┐ │
│  │   Config    │──│ extraction_  │──│  Multiple  │ │
│  │   + flags   │  │   method     │  │  code      │ │
│  │             │  │   (if/else)  │  │  paths     │ │
│  └─────────────┘  └──────────────┘  └────────────┘ │
│                                                      │
│  • Confusing configuration                           │
│  • Mixed responsibilities                            │
│  • Hard to maintain                                  │
└─────────────────────────────────────────────────────┘
```

## After Refactoring

```
┌──────────────────────────────────────────────────────────────────┐
│                      extraction.py                                 │
│              Unified Interface - extract()                       │
│          Auto-detection & routing to specialized extraction        │
└────────────┬──────────────┬──────────────┬────────────────────────┘
             │              │              │
             ▼              ▼              ▼
    ┌────────────┐  ┌────────────┐  ┌────────────┐
    │   text_    │  │   pdf_     │  │  section_  │
    │  pipeline  │  │  pipeline  │  │  pipeline  │
    │  (345 L)   │  │  (437 L)   │  │  (592 L)   │
    └────────────┘  └────────────┘  └────────────┘
         │               │               │
         ▼               ▼               ▼
    Text Only      pypdf Extract    GROBID Parse
         │               │               │
         │               │               ▼
         │               │          Section Select
         │               │               │
         └───────────────┴───────────────┘
                         │
                         ▼
                   GPT Classify
                         │
                         ▼
              Structured Output
```

## Flow Diagrams

### Text Pipeline (Fastest)
```
Input: Raw Text
    │
    ├─> Count Tokens
    │
    ├─> GPT Classification
    │
    └─> Output Record
        (~1-2 seconds)
```

### PDF Pipeline (Fast)
```
Input: PDF File
    │
    ├─> pypdf Extract Text
    │       │
    │       ├─> Handle page limits
    │       └─> Error handling
    │
    ├─> Count Tokens
    │
    ├─> GPT Classification
    │
    └─> Output Record
        (~3-5 seconds)
```

### Section Pipeline (Comprehensive)
```
Input: PDF File
    │
    ├─> GROBID Parsing
    │       │
    │       ├─> Extract sections
    │       ├─> Parse structure
    │       └─> Extract abstract
    │
    ├─> Section Selection
    │       │
    │       ├─> Filter by type (METHODS, ABSTRACT, etc.)
    │       ├─> Match keywords
    │       └─> Build section list
    │
    ├─> Build Prompt
    │       │
    │       ├─> Format abstract
    │       ├─> Format sections
    │       └─> Combine text
    │
    ├─> Count Tokens
    │
    ├─> GPT Classification
    │
    └─> Output Record
        (~10-15 seconds)
```

## Configuration Hierarchy

```
BaseConfig (implicit)
├─> model: str
├─> reasoning: Dict
├─> max_output_tokens: int
├─> temperature: Optional[float]
└─> text_format: Type[BaseModel]

TextClassificationConfig
├─> (inherits base)
└─> output_dir: Path

PDFClassificationConfig
├─> (inherits base)
├─> max_pdf_pages: Optional[int]  ◄─ PDF specific
└─> pdf_dir: Path

SectionClassificationConfig
├─> (inherits base)
├─> section_config: SectionSelectionConfig  ◄─ Section specific
├─> grobid_url: str                         ◄─ GROBID specific
└─> pdf_dir: Path
```

## Data Flow

```
┌─────────────────┐
│  Input Source   │
│ (text/PDF/list) │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   InputRecord   │
│  id, content,   │
│    metadata     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Process Task   │
│ (extraction +   │
│ classification) │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  OutputRecord   │
│ status, tokens, │
│ cost, results   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  CSV Manifest   │
│   (optional)    │
└─────────────────┘
```

## Usage Patterns

### Pattern 1: Direct Import
```python
from llm_metadata.text_pipeline import text_classification_flow
results = text_classification_flow(records, config)
```

### Pattern 2: Unified Interface
```python
from llm_metadata.extraction import extract
results = extract(source, pipeline="text")
```

### Pattern 3: Auto-detection
```python
from llm_metadata.extraction import extract
results = extract("raw text")          # → text_pipeline
results = extract(Path("file.pdf"))    # → pdf_pipeline
```

## Migration Path

```
Old Code (fulltext_pipeline.py)
        │
        ├─> extraction_method="raw_pdf"
        │       └─> Use pdf_pipeline.py
        │
        ├─> extraction_method="grobid"
        │       └─> Use section_pipeline.py
        │
        └─> Direct text input
                └─> Use text_pipeline.py
```

## Decision Tree

```
                    Start
                      │
                      ▼
            ┌─────────────────┐
            │ What input type?│
            └─────────────────┘
                      │
          ┌───────────┼───────────┐
          │           │           │
          ▼           ▼           ▼
       [Text]      [PDF]    [Already
                              extracted?]
          │           │           │
          │           │           ▼
          │           │         [YES]
          │           │           │
          │           │           └──> text_pipeline
          │           │
          │           ▼
          │   ┌──────────────────┐
          │   │ Need sections?   │
          │   └──────────────────┘
          │           │
          │      ┌────┴────┐
          │      │         │
          │      ▼         ▼
          │    [YES]     [NO]
          │      │         │
          │      │         └──> pdf_pipeline
          │      │
          │      ▼
          │  section_pipeline
          │
          └──> text_pipeline
```
