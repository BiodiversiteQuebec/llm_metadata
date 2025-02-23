import openai
import json
import os
from pathlib import Path

MODEL = "gpt-4-0613"
MAX_TOKENS = 800
TEMPERATURE = 0
CATEGORY_LIST = ["population time-series", "trait data", "abundances", "presence/absence", "plots", "specimens", "museum collection", "trajectory"]
PROMPT = """
You are EcodataGPT. Your task is to analyze an open data abstract and generate a JSON output with structured information. The output should be created using the following JSON_template and fields descriptions : 
"""

JSON_TEMPLATE = """
{
  "categories": {
    // List each applicable category with a confidence score. Accepted values:
    // "population time-series", "trait data", "abundances", "presence/absence",
    // "plots", "specimens", "museum collection", "trajectory"
    // Example: {"population time-series": 0.9, "abundances": 0.8,}
  },
  "taxonomic_groups": [
    // List all species, taxonomic entities or groups mentioned in the abstract.
    // Example: "Mammals"
  ],
  "additional_keywords": [
    // List additional keywords relevant to the dataset.
    // Example: "Biodiversity"
  ],
  "additional_data": [
    // Describe any additional data types used in relation to the ecological dataset.
    // Example: "Satellite imagery"
  ],
  "dataset_year_start": // Provide the start year of the dataset, if mentioned.
  // Example: 2001
  "dataset_year_end": // Provide the end year of the dataset, if mentioned.
  // Example: 2020
  "regions_of_interest": [
    // List geographical regions relevant to the dataset.
    // Example: "Amazon Rainforest"
  ]
}"""

def classify_abstract(abstract, json_template = JSON_TEMPLATE, open_api_key=None, temperature=TEMPERATURE, model=MODEL, max_tokens=MAX_TOKENS):
    if not open_api_key:
        open_api_key = os.getenv("OPENAI_API_KEY")
    openai.api_key = open_api_key

    # Define the system message to instruct the model, including the JSON JSON_template
    system_message = f"You are EcodataGPT. Your task is to analyze an open data abstract and generate a JSON output with structured information. Use the following JSON JSON_template: \n{json_template}"

    # Define the user message with the abstract
    user_message = abstract

    # Create chat completion using OpenAI's Chat API
    response = openai.ChatCompletion.create(
        model=model,
        messages=[
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message}
        ],
        max_tokens=max_tokens,
        temperature=temperature
    )

    # Process the response
    out = {
        "prompt": system_message,
        "abstract": abstract,
        "JSON_template": json_template,
        "model": model,
        "temperature": temperature,
        "response_raw": response.choices[0].message["content"].strip()
    }

    try:
        out["response"] = json.loads(out["response_raw"])
    except json.decoder.JSONDecodeError:
        print("Error: JSONDecodeError")
        out["response"] = None

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

    # Prompt alternative
    # Using the following ecological dataset abstract, provide a JSON structure detailing: dataset `categories` with confidence scores, `taxonomic_groups`, `additional_keywords`, `environmental_data`, `dataset_year_start`, `dataset_year_end`, and `regions_of_interest`. Categories should describe type of contained data from list : population time-series, trait data, abundances, presence/absence, plots, specimens, museum collection, trajectory.