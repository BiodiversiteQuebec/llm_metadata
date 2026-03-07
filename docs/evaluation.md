Evaluation is performed first with pair-wise comparing ground truth annotated values to predicted extraction values and obtain prediction outcomes (true positives, false positives, true negatives, and false negatives). Field specific comparison stategy must be defined from the feature underlaying information properties and variability and the expected validation requirements. Typical strategies include exact matching, fuzzy matching and domain-aware matching with relying on techniques such as pre-processing, normalization, reference matching and llm comparison.

For example ... Species (vernacular, scientific, format, authorship, kinship, additionnal details such as habitat, location, etc). Alternatively, some features are defined by a well defined list of accepted values, such as for the `data_type` feature, with possible values only including list of the EBV variables.

Table x present complete list of features annotated by Fuster et al 2024 that were used for this study, including the original definition from the study, example values, and our arbitrary assesment of the semantic variability 

Tools for ground truth evaluation for pairwise comparison (TP/FP/TN/FN). Openai evals api method and llm as judge. List of studies using openai evals api (Laskar et al., 2025, ...), preferably from biomedical, bioscience or more general ones. Table X present stategy for each field.

Pre-processing and normalization using pydantic validation functions - capitalization, blablabla ... from script.

Domain specific strategy for species used for this study.

Scoring (precision, recall, accuracy and f1) definition and equations. Interpretation in the context of llm ... precision is often associated with hallucination, over prediction - such as including details that were deemed unrelevant by the human annotator, or including information outside of intended scope. An example would be a study that amassed observations for 34 beetles, but also mentionning interacting species (ex. bird predator species) its ecology in the introduction or discussion – that get's wrongly picked up as dataset material. <!-- Find specific example to replace the 34 beetles --> Recall is a good metric to understand how well the model was able to interpret the accurate information in the same way than the human annotator. Good example is datatype.  <!-- Find specific example ... Not sure about this interpretation though ... and how to explain why I keep on looking at it-->


## Discussion

About the original aim for the annotation. The original feature annotation were done to make decision about dataset relevancy, based on species richness (<!--L/M/H threshold-->)



---

Laskar et al., 2025 — “Improving Automatic Evaluation of Large Language Models (LLMs) in Biomedical Relation Extraction via LLMs-as-the-Judge)