from openai import OpenAI
from openai.types.responses.parsed_response import ParsedResponse
from pydantic import BaseModel
import json
import os
from pathlib import Path
from typing import Dict, Optional, Union
from joblib import Memory

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

if __name__ == "__main__":
    # Load .env
    from dotenv import load_dotenv
    dotenv_path = Path('.env')
    load_dotenv(dotenv_path)

    # Print os.getwd for debugging
    print(f"Current working directory: {os.getcwd()}")

    # Get the abstract from the user
    abstract_text = """
    Future human land use and climate change may disrupt movement behaviors of terrestrial animals, thereby altering the ability of individuals to move across a landscape. Some of the expected changes result from processes whose effects will be difficult to alter, such as global climate change. We present a novel framework in which we use models to (1) identify the ecological changes from these difficult-to-alter processes, as well as (2) the potential conservation measures that are best able to compensate for these changes. We illustrated this framework with the case of an endangered caribou population in Québec, Canada. We coupled a spatially explicit individual-based movement model with a range of landscape scenarios to assess the impacts of varying degrees of climate change, and the ability of conservation actions to compensate for such impacts on caribou movement behaviors. We found that (1) climate change impacts reduced movement potential, and that (2) the complete restoration of secondary roads inside protected areas was able to fully offset this reduction, suggesting that road restoration would be an effective compensatory conservation action. By evaluating conservation actions via landscape use simulated by an individual-based model, we were able to identify compensatory conservation options for an endangered species facing climate change.
    """
    # Get the classification from GPT
    classification = classify_abstract(abstract_text)
    # Print the classification
    print(classification)