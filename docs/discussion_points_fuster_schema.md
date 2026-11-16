# Discussion points on the Fuster relevance schema

For Alex Fuster. Raised while reproducing the relevance rules in code and tuning LLM extraction on the 30-record dev subset (November 2026). Each point says what we observed, why it matters, and a question. Record-level cases are in [`results/gt_issue_register.csv`](results/gt_issue_register.csv).

## 1. Thresholds we had to reconstruct

The rules in `src/llm_metadata/relevance_rules.py` reproduce 178 of the 180 released relevance classes, but three of them differ from the paper's prose:

- **Temporal extent:** the released labels behave like "12 years or more = High" (counted inclusively), while the paper says "more than 10 years".
- **Plain "genetic analysis":** it is ranked Low (non-EBV) unless written "EBV genetic analysis".
- **Modulators:** they also lift "not relevant" (X) to Low, and `multispecies` counts like the other four modulators. The paper treats multispecies apart and upgrades only relevant datasets.

*Question:* which version is intended for the article: the prose, or the released labels?

## 2. EBV versus non-EBV genetic data

The rules rank genetic data describing variation within species (the "genetic composition" EBV) High and other genetic data Low. Annotators wrote "EBV genetic" 28 times and plain "genetic" 3 times among valid records. An extraction vocabulary with a single genetic value cannot reach High; we added an explicit yes/no field for it.

*Question:* is our definition the one you used (population genetic diversity, structure, gene flow, relatedness, effective size = EBV; barcoding, eDNA detection, phylogenies = not)?

## 3. Spatial extent is mostly estimated by the annotator

In 56 of 107 annotated areas, the position column says the value is written nowhere: the annotator estimated it from place names. That practice is not applied every time. Some records with a named river or named orchards in Quebec are left "not given", while others get an estimated area for a whole range.

This one choice drives the rule-based results. When the LLM was forbidden to estimate areas, spatial extent was "not stated" for 19 of 30 dev abstracts and rule-based relevance underrated 17 of 30 datasets. When it could estimate from named places, binary F1 against the rule label rose from 0.43 to about 0.8.

*Question:* can we state the rule as "estimate the area of the smallest named unit that contains the sites; X only when no place is named"?

## 4. Two missing classes outvote the data type

With a majority vote over three classes, a dataset with High data type but no stated temporal or spatial extent gets X (two X against one H). "Not stated" therefore counts like "low quality", and the score reflects how the text is written as much as what the dataset holds. Fixing the data type alone did not move any relevance category for that reason.

*Question:* should missing classes be ignored in the vote (vote among the stated ones), or is penalising undocumented datasets intended?

## 5. The modulators inflate relevance

Any one modulator lifts the category by one level, and `multispecies` is true for nearly every community dataset (the LLM flags it on 16 of 30 dev abstracts, precision 0.56 against the annotation: 9 of the 16 are annotated multispecies). Against the human judgement, the rules are higher in 60 of the 83 records where the two disagree.

*Question:* should multispecies require a threshold (the "> 10 species" of the earlier prompt), or stop counting as a modulator?

## 6. The north–south flag is a crude gap proxy

The flag treats "north of the 49th parallel" as one gap for all taxa. The Atlas shows the gap depends on the group. North of the 49th parallel (75 % of Quebec's area), the Atlas holds 3.7 % of bird records, 5.9 % of insect records, but 18 % of vascular plant and 49 % of non-vascular plant records.

*Question:* would a group-specific gap (the Atlas contribution scores in `docs/atlas_contribution/`) be closer to what relevance should mean for Biodiversité Québec?

## 7. Relevance ignores what is already known

A 20-year abundance series on a species the Atlas already covers well scores High; a short presence-only survey of an under-sampled group in the North scores Low. Relevance is generic; it says nothing about what a dataset would add. This is the motivation for the second track.

## 8. Annotation conventions to write down

- **Density or abundance:** counts per trap, plot or transect are annotated "density" in some records and "abundance" in others. Both are High, so relevance is unaffected, but the feature field cannot be scored fairly.
- **Genetic samples as occurrences:** genetic samples of located individuals are also annotated "presence only". This is sensible, but not obvious to an extractor.
- **False or not stated:** flags are annotated False where the text is silent. We now score flags with "not stated" equal to False, as the rules do.
- **Species lists or counts:** a summarised count is sometimes used ("c.30 bird species") and an enumerated list elsewhere, and caribou is written three ways across 7 records.

## 9. The human–rule gap is the ceiling

The human label and the rule label agree on 54 % of records (four classes) and 76 % (relevant vs not), Cohen's kappa 0.37 and 0.52. On dev, LLM approaches reach 0.4–0.6 four-class agreement with the rule label and 0.2–0.4 with the human label. Any claim about LLM relevance needs this ceiling next to it.

*Question:* for the article, which label is "relevance": the rules (reproducible) or the expert judgement (what the rules try to approximate)?
