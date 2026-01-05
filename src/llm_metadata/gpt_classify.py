from openai import OpenAI
import json
import os
from pathlib import Path
from typing import Dict

from llm_metadata.schemas import DatasetAbstractMetadata

MODEL = "gpt-4o-mini"
MAX_TOKENS = 2000
TEMPERATURE = 0
SYSTEM_MESSAGE = """
You are EcodataGPT. Your task is to analyze an open data abstract and generate a JSON output with structured information.
"""


def classify_abstract(abstract,
                      system_message=SYSTEM_MESSAGE,
                      temperature=TEMPERATURE,
                      model=MODEL, max_tokens=MAX_TOKENS,
                      response_format=DatasetAbstractMetadata):

    # Define the user message with the abstract
    user_message = abstract

    # Create chat completion using OpenAI's Chat API
    client = OpenAI()
    response = client.beta.chat.completions.parse(
        model=model,
        messages=[
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message}
        ],
        max_tokens=max_tokens,
        temperature=temperature,
        response_format=response_format
    )

    # Process the response
    out = {
        "prompt": system_message,
        "abstract": abstract,
        "model": model,
        "temperature": temperature,
        "response": response.choices[0],
        "output": response.choices[0].message.parsed
    }

    return out


if __name__ == "__main__":
    # Load .env
    from dotenv import load_dotenv
    dotenv_path = Path(__file__).parent.parent / '.env'
    load_dotenv(dotenv_path)

    # Get the abstract from the user
    abstract_text = """
    Future human land use and climate change may disrupt movement behaviors of terrestrial animals, thereby altering the ability of individuals to move across a landscape. Some of the expected changes result from processes whose effects will be difficult to alter, such as global climate change. We present a novel framework in which we use models to (1) identify the ecological changes from these difficult-to-alter processes, as well as (2) the potential conservation measures that are best able to compensate for these changes. We illustrated this framework with the case of an endangered caribou population in Québec, Canada. We coupled a spatially explicit individual-based movement model with a range of landscape scenarios to assess the impacts of varying degrees of climate change, and the ability of conservation actions to compensate for such impacts on caribou movement behaviors. We found that (1) climate change impacts reduced movement potential, and that (2) the complete restoration of secondary roads inside protected areas was able to fully offset this reduction, suggesting that road restoration would be an effective compensatory conservation action. By evaluating conservation actions via landscape use simulated by an individual-based model, we were able to identify compensatory conservation options for an endangered species facing climate change.
    """
    # Get the classification from GPT-4
    classification = classify_abstract(abstract_text)
    # Print the classification
    print(classification)