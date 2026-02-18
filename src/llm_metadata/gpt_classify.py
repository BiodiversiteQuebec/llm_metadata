from openai import OpenAI
from openai.types.responses.parsed_response import ParsedResponse
from pydantic import BaseModel
import base64
import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Union
from joblib import Memory
import pypdf

from llm_metadata.schemas import DatasetAbstractMetadata

# Setup cache
memory = Memory("./cache", verbose=0)

MODEL_COST_PER_1M_TOKENS = {
    "gpt-5-nano": {"input": 0.05, "output": 0.40, "cache": 0.005},
    "gpt-5-mini": {"input": 0.25, "output": 2.00, "cache": 0.025},
    "gpt-5": {"input": 1.25, "output": 10.00, "cache": 0.125},
    "gpt-5.1": {"input": 1.25, "output": 10.00, "cache": 0.125},
    "gpt-5.2": {"input": 1.75, "output": 14.00, "cache": 0.175},
    "gpt-4.1": {"input": 2.00, "output": 8.00, "cache": 0.50},
    "gpt-4o": {"input": 2.50, "output": 10.00, "cache": 1.25},

    # "gpt-4": legacy; not consistently listed on the current pricing table.
}

MODEL = "gpt-5-mini"
MAX_OUTPUT_TOKENS = 4096  # Increased from 1024 to allow complete JSON generation for complex schemas
TEMPERATURE = None # Pas valid pour les modèles à raisonnement (GPT-5 / o-series), utilisé pour gpt-4o, et gpt-5.1 et gpt-5.2 sans raisonnement
REASONING = {"effort": "low"} # options: low, medium, high, none (pour gpt-5.1, gpt-5.2)
SYSTEM_MESSAGE = """
You are EcodataGPT, a structured data extraction engine.

Goal: extract fields from the user's abstract into the provided schema.

Rules:
- Only use information explicitly supported by the text. Do NOT guess or infer.
- If a field is not clearly stated, set it to null (or an empty list) as allowed by the schema.
- Prefer conservative outputs over over-extraction.
- Output must conform exactly to the schema (types, enums, lists).

## Modulator Boolean Fields

Set each to true only when the text provides explicit evidence; otherwise set to null.

- **time_series**: true if the dataset contains repeated measurements at the same locations/populations over time (e.g. "annual surveys from 2005 to 2015", "monitored monthly"). A single snapshot is NOT a time series.
- **multispecies**: true if the dataset covers more than one species or taxonomic group.
- **threatened_species**: true if any studied species are described as threatened, endangered, vulnerable, at-risk, or listed under IUCN/CITES/national red lists.
- **new_species_science**: true if the study describes or names a species new to science (newly described taxon).
- **new_species_region**: true if the study reports a species recorded in a region for the first time (range extension, first regional record).
- **bias_north_south**: true if the text explicitly discusses geographic bias toward the Global North or underrepresentation of the Global South.
""".strip()

SECTION_SYSTEM_MESSAGE = """
You are EcodataGPT, a structured data extraction engine for scientific article analysis.

Goal: Extract biodiversity dataset features from the provided sections of a scientific article (Abstract, Methods, Data, Results, etc.) into the provided schema.

## Section-Specific Guidance

Different sections contain different types of information:
- **Abstract**: High-level summary; use for overview but prefer details from full sections
- **Methods / Materials**: Primary source for sampling protocols, study sites, temporal coverage, species studied
- **Data / Data Availability**: Dataset descriptions, spatial extent, data types collected
- **Study Area / Site Description**: Geographic coordinates, spatial range, administrative regions
- **Results**: Actual values and measurements (may confirm temporal/spatial extent)

## Field Extraction Rules

1. **data_type**: Classify what kind of data was collected (abundance counts, presence/absence, genetic sequences, etc.)
   - Look for measurement descriptions in Methods
   - "counted individuals" → abundance; "recorded presence" → presence-only; "DNA samples" → genetic_analysis

2. **geospatial_info_dataset**: How is location data represented?
   - GPS coordinates of samples → "sample"; named study sites → "site"; species range maps → "range"
   - Country/region names → "administrative_units"; map figures → "maps"

3. **spatial_range_km2**: Total study area extent in square kilometers
   - Look for explicit area mentions ("500 km²", "across 10,000 hectares")
   - Convert units if needed (1 ha = 0.01 km²; 1 mi² = 2.59 km²)
   - If only bounding box given, calculate area

4. **temporal_range / temp_range_i / temp_range_f**: When was data collected?
   - Look for date ranges in Methods ("sampled from 2005 to 2010")
   - temp_range_i = start year, temp_range_f = end year
   - temporal_range = verbatim text describing the period

5. **species**: Taxonomic entities studied
   - Extract scientific names, common names, and taxonomic groups exactly as written
   - Include counts if given ("12 mammal species", "41 fish species")
   - Do NOT expand abbreviations or infer genera

## Modulator Boolean Fields

Set each to true only when the text provides explicit evidence; otherwise set to null.

- **time_series**: true if the dataset contains repeated measurements at the same locations/populations over time (e.g. "annual surveys from 2005 to 2015", "monitored monthly"). A single snapshot is NOT a time series.
- **multispecies**: true if the dataset covers more than one species or taxonomic group.
- **threatened_species**: true if any studied species are described as threatened, endangered, vulnerable, at-risk, or listed under IUCN/CITES/national red lists.
- **new_species_science**: true if the study describes or names a species new to science (newly described taxon).
- **new_species_region**: true if the study reports a species recorded in a region for the first time (range extension, first regional record).
- **bias_north_south**: true if the text explicitly discusses geographic bias toward the Global North or underrepresentation of the Global South.

## General Rules

- Only use information EXPLICITLY stated in the text. Do NOT guess or infer.
- If a field is not clearly stated, set it to null (or empty list).
- Prefer conservative outputs over over-extraction.
- When sections contradict, prefer Methods/Data sections over Abstract.
- Output must conform exactly to the schema (types, enums, lists).
""".strip()

PDF_SYSTEM_MESSAGE = """
You are EcodataGPT, a structured data extraction engine for scientific PDF analysis.

Goal: Extract biodiversity dataset features from the provided PDF document into the provided schema.

## PDF Document Analysis

This PDF has been processed to provide both:
1. **Extracted text** from each page for detailed content analysis
2. **Visual rendering** of each page for tables, figures, and layout understanding

Use BOTH the text and visual information to extract accurate metadata. Pay special attention to:
- **Tables**: Often contain structured data about sampling sites, species lists, temporal coverage
- **Figures/Maps**: May show study area extent, spatial distribution, geographic coordinates
- **Supplementary materials**: Sometimes contain detailed methods or data descriptions

## Document Structure Guidance

Scientific papers typically follow this structure - prioritize sections accordingly:

| Section | Primary Information |
|---------|-------------------|
| Abstract | Overview summary (use for context, prefer details from body) |
| Introduction | Study objectives, geographic scope |
| Methods/Materials | **PRIMARY SOURCE**: Sampling protocols, study sites, dates, species |
| Study Area | Geographic coordinates, spatial extent, region names |
| Data/Data Availability | Dataset descriptions, data types, access information |
| Results | Actual measurements, confirmed values |
| Supplementary | Detailed species lists, coordinate tables, extended methods |

## Field Extraction Rules

1. **data_type**: What kind of biodiversity data was collected?
   - Look for measurement descriptions in Methods section
   - "counted individuals" → abundance; "recorded presence" → presence-only
   - "DNA samples/sequences" → genetic_analysis; "GPS tracks" → tracking
   - Check tables for data structure clues

2. **geospatial_info_dataset**: How is location data represented?
   - GPS coordinates in tables → "sample"; named sites → "site"
   - Range maps in figures → "range"; country/region text → "administrative_units"
   - Check figure captions for map descriptions

3. **spatial_range_km2**: Total study area extent in square kilometers
   - Look for explicit area mentions ("500 km²", "10,000 hectares")
   - Check maps for scale bars; calculate from bounding coordinates
   - Convert units: 1 ha = 0.01 km²; 1 mi² = 2.59 km²

4. **temporal_range / temp_range_i / temp_range_f**: Data collection period
   - Look in Methods for date ranges ("sampled from 2005 to 2010")
   - Check figure captions for time series dates
   - temp_range_i = start year, temp_range_f = end year

5. **species**: Taxonomic entities studied
   - Extract scientific names, common names exactly as written
   - Check tables for complete species lists
   - Include counts if given ("12 mammal species")
   - Do NOT expand abbreviations or infer genera

## Modulator Boolean Fields

Set each to true only when the text provides explicit evidence; otherwise set to null.

- **time_series**: true if the dataset contains repeated measurements at the same locations/populations over time (e.g. "annual surveys from 2005 to 2015", "monitored monthly"). A single snapshot is NOT a time series.
- **multispecies**: true if the dataset covers more than one species or taxonomic group.
- **threatened_species**: true if any studied species are described as threatened, endangered, vulnerable, at-risk, or listed under IUCN/CITES/national red lists.
- **new_species_science**: true if the study describes or names a species new to science (newly described taxon).
- **new_species_region**: true if the study reports a species recorded in a region for the first time (range extension, first regional record).
- **bias_north_south**: true if the text explicitly discusses geographic bias toward the Global North or underrepresentation of the Global South.

## Extraction Philosophy

- Only use information EXPLICITLY stated or shown in the PDF. Do NOT guess or infer.
- If a field is not clearly stated, set it to null (or empty list).
- Prefer conservative outputs over over-extraction.
- When text and figures contradict, prefer quantitative data from tables/figures.
- Cross-reference Methods text with Results tables for verification.
- Output must conform exactly to the schema (types, enums, lists).
""".strip()


def _response_usage_cost(usage: dict, model: str = MODEL) -> dict:
    # Get model-specific costs
    try:
        costs = MODEL_COST_PER_1M_TOKENS[model]
    except KeyError:
        raise ValueError(f"Unknown model '{model}' for cost calculation.")
    
    input_tokens = usage.get('input_tokens', 0)
    cached_tokens = usage.get('input_tokens_details', {}).get('cached_tokens', 0)
    reasoning_tokens = usage.get('output_tokens_details', {}).get('reasoning_tokens', 0)
    output_tokens = usage.get('output_tokens', 0)

    input_cost = round((input_tokens - cached_tokens) * costs["input"] / 1_000_000, 4)
    cache_cost = round(cached_tokens * costs["cache"] / 1_000_000, 4)
    reasoning_cost = round(reasoning_tokens * costs["output"] / 1_000_000, 4)
    output_cost = round(output_tokens * costs["output"] / 1_000_000, 4)

    total_cost = round(input_cost + cache_cost + output_cost + reasoning_cost, 4)

    return {
        'input_tokens': input_tokens,
        'cached_tokens': cached_tokens,
        'reasoning_tokens': reasoning_tokens,
        'output_tokens': output_tokens,
        'input_cost': input_cost,
        'cache_cost': cache_cost,
        'reasoning_cost': reasoning_cost,
        'output_cost': output_cost,
        'total_cost': total_cost,
    }

def classify_abstract(
    abstract: str,
    system_message: str = SYSTEM_MESSAGE,
    temperature: Optional[float] = TEMPERATURE,
    model: str = MODEL,
    max_output_tokens: int = MAX_OUTPUT_TOKENS,
    text_format: type = DatasetAbstractMetadata,
    reasoning: Optional[Dict] = REASONING,
):
    # Create a unique str for the parameters to use for caching
    parameters_str = json.dumps({
        "abstract": abstract,
        "system_message": system_message,
        "temperature": temperature,
        "model": model,
        "max_output_tokens": max_output_tokens,
        "text_format": json.dumps(text_format.model_json_schema(), sort_keys=True),
        "reasoning": reasoning,
    }, sort_keys=True)

    # _response_parse is defined within classify_abstract to allow caching with joblib while passing parameters
    @memory.cache
    def _response_parse(parameters_json_dump: str) -> dict:
        openai = OpenAI()
        response = openai.responses.parse(
            model=model,
            input=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": abstract},
            ],
            text_format=text_format,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )
        return response.model_dump()
    
    response_dict = _response_parse(parameters_str)

    # Cast response dict to ParsedResponse using model_construct (bypasses validation)
    response: ParsedResponse = ParsedResponse[text_format].model_construct(**response_dict)

    out = {
        "prompt": system_message,
        "abstract": abstract,
        "model": model,
        "response": response,  # full response as ParsedResponse
        "output": response.output_parsed,  # parsed output only
        "usage_cost": _response_usage_cost(response_dict["usage"], model=model) if response_dict.get("usage") else None,
    }

    if temperature is not None:
        out["temperature"] = temperature

    if reasoning is not None:
        out["reasoning"] = reasoning

    return out

def classify_pdf(
    pdf_path: Union[str, Path],
    system_message: str = SYSTEM_MESSAGE,
    temperature: Optional[float] = TEMPERATURE,
    model: str = MODEL,
    max_output_tokens: int = MAX_OUTPUT_TOKENS,
    text_format: type = DatasetAbstractMetadata,
    reasoning: Optional[Dict] = REASONING,
):
    """
    Extract text from a PDF file and classify it using GPT.
    
    Args:
        pdf_path: Path to PDF file
        system_message: System prompt for classification
        temperature: Temperature for sampling (None for reasoning models)
        model: Model name to use
        max_output_tokens: Maximum output tokens
        text_format: Pydantic model for structured output
        reasoning: Reasoning configuration for GPT-5 series
        max_pages: Optional limit on pages to extract (None = all pages)
    
    Returns:
        Classification result dict with same structure as classify_abstract
    """
    # Extract text from PDF
    @memory.cache
    def _extract_text_from_pdf(pdf_path_str: str) -> str:
        pdf_path = Path(pdf_path_str)
        reader = pypdf.PdfReader(str(pdf_path))
        text_pages = []
        for page in reader.pages:
            text_pages.append(page.extract_text() or "")
        return "\n".join(text_pages)

    pdf_text = _extract_text_from_pdf(str(pdf_path))

    # Classify the extracted text
    result = classify_abstract(
        abstract=pdf_text,
        system_message=system_message,
        temperature=temperature,
        model=model,
        max_output_tokens=max_output_tokens,
        text_format=text_format,
        reasoning=reasoning,
    )

    # Add PDF path to the result
    result["pdf_path"] = str(pdf_path)
    result["extraction_method"] = "raw_pdf"

    return result

@memory.cache
def upload_pdf_to_openai(
    pdf_path: Union[str, Path],
    purpose: str = "user_data"
) -> str:
    """
    Upload a PDF file to OpenAI's File API.

    Args:
        pdf_path: Path to PDF file
        purpose: Purpose for the file upload (default: "user_data")

    Returns:
        File ID from OpenAI

    Note:
        Files are automatically deleted by OpenAI after a retention period.
        For production use, consider implementing file cleanup.
    """
    pdf_path = Path(pdf_path)

    # Do NOT persistently cache uploads.
    # OpenAI file IDs can expire or be deleted (e.g., via cleanup_file=True),
    # and persisting them across runs causes flaky 404s when reused.
    client = OpenAI()
    with open(str(pdf_path), "rb") as f:
        file = client.files.create(file=f, purpose=purpose)
    return file.id


def delete_openai_file(file_id: str) -> bool:
    """
    Delete a file from OpenAI's File API.

    Args:
        file_id: OpenAI file ID to delete

    Returns:
        True if deletion was successful
    """
    client = OpenAI()
    try:
        client.files.delete(file_id)
        return True
    except Exception as e:
        print(f"Failed to delete file {file_id}: {e}")
        return False


def list_openai_files() -> List[Dict]:
    """
    List files uploaded to OpenAI's File API.

    Returns:
        List of file metadata dicts
    """
    client = OpenAI()
    files = client.files.list()
    return [file.model_dump() for file in files.data]


def classify_pdf_file(
    pdf_path: Union[str, Path],
    system_message: str = PDF_SYSTEM_MESSAGE,
    temperature: Optional[float] = TEMPERATURE,
    model: str = MODEL,
    max_output_tokens: int = MAX_OUTPUT_TOKENS,
    text_format: type = DatasetAbstractMetadata,
    reasoning: Optional[Dict] = REASONING,
    file_id: Optional[str] = None,
    cleanup_file: bool = False,
) -> Dict:
    """
    Classify a PDF file using OpenAI's File API with native PDF support.

    This method uploads the raw PDF to OpenAI's File API and uses the
    model's native PDF understanding capabilities (text + visual analysis
    of each page) for structured extraction.

    Args:
        pdf_path: Path to PDF file
        system_message: System prompt for classification (default: PDF_SYSTEM_MESSAGE)
        temperature: Temperature for sampling (None for reasoning models)
        model: Model name to use (must support vision: gpt-4o, gpt-4o-mini, o1, gpt-5-mini)
        max_output_tokens: Maximum output tokens
        text_format: Pydantic model for structured output
        reasoning: Reasoning configuration for GPT-5 series
        file_id: Optional pre-uploaded file ID (skips upload if provided)
        cleanup_file: Whether to delete the file from OpenAI after classification

    Returns:
        Classification result dict with:
        - output: Parsed Pydantic model instance
        - usage_cost: Token usage and cost breakdown
        - file_id: OpenAI file ID used
        - pdf_path: Original PDF path
        - extraction_method: "openai_file_api"

    Note:
        OpenAI extracts both text and images from PDFs. Models with vision
        capabilities can use both to generate responses. This is useful when
        figures, tables, or maps contain key information not in the text.

        Limitations:
        - Maximum 100 pages per PDF
        - Maximum 32MB total content per request
        - Only vision-capable models supported (gpt-4o, gpt-4o-mini, o1, gpt-5-mini)
    """
    pdf_path = Path(pdf_path)

    # Upload file if not provided
    if file_id is None:
        file_id = upload_pdf_to_openai(pdf_path)

    # Create cache key from parameters
    parameters_str = json.dumps({
        "file_id": file_id,
        "pdf_path": str(pdf_path),
        "system_message": system_message,
        "temperature": temperature,
        "model": model,
        "max_output_tokens": max_output_tokens,
        "text_format": json.dumps(text_format.model_json_schema(), sort_keys=True),
        "reasoning": reasoning,
    }, sort_keys=True)

    @memory.cache
    def _response_parse_pdf(parameters_json_dump: str, file_id: str) -> dict:
        client = OpenAI()
        response = client.responses.parse(
            model=model,
            input=[
                {"role": "system", "content": system_message},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_file",
                            "file_id": file_id
                        },
                        {
                            "type": "input_text",
                            "text": "Extract the biodiversity dataset features from this scientific paper PDF according to the schema."
                        }
                    ]
                }
            ],
            text_format=text_format,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )
        return response.model_dump()

    response_dict = _response_parse_pdf(parameters_str, file_id)

    # Cast response dict to ParsedResponse
    response: ParsedResponse = ParsedResponse[text_format].model_construct(**response_dict)

    out = {
        "prompt": system_message,
        "pdf_path": str(pdf_path),
        "file_id": file_id,
        "model": model,
        "response": response,
        "output": response.output_parsed,
        "usage_cost": _response_usage_cost(response_dict["usage"], model=model) if response_dict.get("usage") else None,
        "extraction_method": "openai_file_api",
    }

    if temperature is not None:
        out["temperature"] = temperature

    if reasoning is not None:
        out["reasoning"] = reasoning

    # Cleanup file if requested
    if cleanup_file:
        delete_openai_file(file_id)

    return out


def classify_pdf_url(
    pdf_url: str,
    system_message: str = PDF_SYSTEM_MESSAGE,
    temperature: Optional[float] = TEMPERATURE,
    model: str = MODEL,
    max_output_tokens: int = MAX_OUTPUT_TOKENS,
    text_format: type = DatasetAbstractMetadata,
    reasoning: Optional[Dict] = REASONING,
) -> Dict:
    """
    Classify a PDF from a public URL using OpenAI's native PDF support.

    This method directly references the PDF URL without uploading,
    which is useful for open access papers with stable URLs.

    Args:
        pdf_url: Public URL to PDF file
        system_message: System prompt for classification
        temperature: Temperature for sampling (None for reasoning models)
        model: Model name to use (must support vision)
        max_output_tokens: Maximum output tokens
        text_format: Pydantic model for structured output
        reasoning: Reasoning configuration for GPT-5 series

    Returns:
        Classification result dict (same structure as classify_pdf_file)

    Note:
        The URL must be publicly accessible. For paywalled content,
        use classify_pdf_file with a local file instead.
    """
    # Create cache key
    parameters_str = json.dumps({
        "pdf_url": pdf_url,
        "system_message": system_message,
        "temperature": temperature,
        "model": model,
        "max_output_tokens": max_output_tokens,
        "text_format": json.dumps(text_format.model_json_schema(), sort_keys=True),
        "reasoning": reasoning,
    }, sort_keys=True)

    @memory.cache
    def _response_parse_pdf_url(parameters_json_dump: str) -> dict:
        client = OpenAI()
        response = client.responses.parse(
            model=model,
            input=[
                {"role": "system", "content": system_message},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_file",
                            "file_url": pdf_url
                        },
                        {
                            "type": "input_text",
                            "text": "Extract the biodiversity dataset features from this scientific paper PDF according to the schema."
                        }
                    ]
                }
            ],
            text_format=text_format,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )
        return response.model_dump()

    response_dict = _response_parse_pdf_url(parameters_str)

    # Cast response dict to ParsedResponse
    response: ParsedResponse = ParsedResponse[text_format].model_construct(**response_dict)

    out = {
        "prompt": system_message,
        "pdf_url": pdf_url,
        "model": model,
        "response": response,
        "output": response.output_parsed,
        "usage_cost": _response_usage_cost(response_dict["usage"], model=model) if response_dict.get("usage") else None,
        "extraction_method": "openai_url_api",
    }

    if temperature is not None:
        out["temperature"] = temperature

    if reasoning is not None:
        out["reasoning"] = reasoning

    return out


if __name__ == "__main__":
    # Load .env
    from dotenv import load_dotenv
    dotenv_path = Path('.env')
    load_dotenv(dotenv_path)

    # Print os.getwd for debugging
    print(f"Current working directory: {os.getcwd()}")

    # Example 1: Classify from abstract text
    print("=== Example 1: Classifying from abstract text ===")
    abstract_text = """
    Future human land use and climate change may disrupt movement behaviors of terrestrial animals, thereby altering the ability of individuals to move across a landscape. Some of the expected changes result from processes whose effects will be difficult to alter, such as global climate change. We present a novel framework in which we use models to (1) identify the ecological changes from these difficult-to-alter processes, as well as (2) the potential conservation measures that are best able to compensate for these changes. We illustrated this framework with the case of an endangered caribou population in Québec, Canada. We coupled a spatially explicit individual-based movement model with a range of landscape scenarios to assess the impacts of varying degrees of climate change, and the ability of conservation actions to compensate for such impacts on caribou movement behaviors. We found that (1) climate change impacts reduced movement potential, and that (2) the complete restoration of secondary roads inside protected areas was able to fully offset this reduction, suggesting that road restoration would be an effective compensatory conservation action. By evaluating conservation actions via landscape use simulated by an individual-based model, we were able to identify compensatory conservation options for an endangered species facing climate change.
    """
    classification = classify_abstract(abstract_text)
    print(f"Classification result: {classification['output']}")
    print(f"Cost: ${classification['usage_cost']['total_cost']}")
    print()

    # Example 2: Classify from raw PDF file
    print("=== Example 2: Classifying from raw PDF ===")
    # Uncomment and update the PDF path to test:
    # pdf_path = Path("data/pdfs/sample.pdf")
    # if pdf_path.exists():
    #     pdf_classification = classify_pdf(
    #         pdf_path=pdf_path,
    #         max_pages=10  # Limit to first 10 pages
    #     )
    #     print(f"PDF Classification result: {pdf_classification['output']}")
    #     print(f"Cost: ${pdf_classification['usage_cost']['total_cost']}")
    # else:
    #     print(f"PDF file not found: {pdf_path}")
    print("(Example commented out - update PDF path to test)")