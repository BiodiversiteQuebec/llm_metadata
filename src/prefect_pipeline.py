from prefect import task, flow
from prefect.task_runners import ThreadPoolTaskRunner

from pydantic import BaseModel
from typing import Optional, List
from zenodo import get_record_by_doi, get_record_by_doi_list
from gpt_classify import classify_abstract
from fuster_model import DatasetFeatures

class ClassificationResult(BaseModel):
    prompt: str
    abstract: str
    model: str
    temperature: float
    response: dict
    output: dict

@task
def fetch_abstract(doi: str) -> str:
    record = get_record_by_doi(doi)
    if record and 'metadata' in record and 'description' in record['metadata']:
        return record['metadata']['description']
    else:
        raise ValueError(f"No abstract found for DOI: {doi}")

@task
def fetch_abstracts(dois: List[str]) -> List[str]:
    abstracts = []
    for i in range(0, len(dois), 20):
        batch = dois[i:i+20]
        records = get_record_by_doi_list(batch)
        for record in records:
            if 'metadata' in record and 'description' in record['metadata']:
                abstracts.append(record['metadata']['description'])
            else:
                abstracts.append(None)
    return abstracts

@task
def classify_abstract_task(abstract: str, response_format:BaseModel = DatasetFeatures) -> ClassificationResult:
    classification = classify_abstract(abstract, response_format=response_format)
    return classification

@flow(task_runner=ThreadPoolTaskRunner(max_workers=10))
def doi_classification_pipeline(dois: List[str]) -> List[ClassificationResult]:
    abstracts = fetch_abstracts(dois)
    futures = classify_abstract_task.map(abstracts)
    return futures.result()

if __name__ == "__main__":
    # 10.5061/dryad.2n5h6
    # 10.5061/dryad.3nh72
    # 10.5061/dryad.4k275

    # Run the flow
    flow_state = doi_classification_pipeline(dois=["10.5061/dryad.2n5h6"])
    
    # Get the results
    results = flow_state.result()
    for result in results:
        print(result.output)