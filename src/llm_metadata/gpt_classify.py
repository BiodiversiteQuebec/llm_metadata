from openai import OpenAI
import json
import os
from pathlib import Path
from typing import Dict, Optional

from llm_metadata.schemas import DatasetAbstractMetadata

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


def classify_abstract(
    abstract: str,
    system_message: str = SYSTEM_MESSAGE,
    temperature: Optional[float] = TEMPERATURE,
    model: str = MODEL,
    max_output_tokens: int = MAX_OUTPUT_TOKENS,
    text_format: type = DatasetAbstractMetadata,
    reasoning: Optional[Dict] = REASONING,
):
    client = OpenAI()

    response = client.responses.parse(
        model=model,
        input=[
            {"role": "system", "content": system_message},
            {"role": "user", "content": abstract},
        ],
        text_format=text_format,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
    )

    out = {
        "prompt": system_message,
        "abstract": abstract,
        "model": model,
        "response": response,  # full response object
        "output": response.output_parsed,  # parsed Pydantic model
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

    # print OpenAI API key for debugging
    print(f"OpenAI API Key: {os.getenv('OPENAI_API_KEY')}")

    # Get the abstract from the user
    abstract_text = """
    Future human land use and climate change may disrupt movement behaviors of terrestrial animals, thereby altering the ability of individuals to move across a landscape. Some of the expected changes result from processes whose effects will be difficult to alter, such as global climate change. We present a novel framework in which we use models to (1) identify the ecological changes from these difficult-to-alter processes, as well as (2) the potential conservation measures that are best able to compensate for these changes. We illustrated this framework with the case of an endangered caribou population in Québec, Canada. We coupled a spatially explicit individual-based movement model with a range of landscape scenarios to assess the impacts of varying degrees of climate change, and the ability of conservation actions to compensate for such impacts on caribou movement behaviors. We found that (1) climate change impacts reduced movement potential, and that (2) the complete restoration of secondary roads inside protected areas was able to fully offset this reduction, suggesting that road restoration would be an effective compensatory conservation action. By evaluating conservation actions via landscape use simulated by an individual-based model, we were able to identify compensatory conservation options for an endangered species facing climate change.
    """
    # Get the classification from GPT
    classification = classify_abstract(abstract_text)
    # Print the classification
    print(classification)