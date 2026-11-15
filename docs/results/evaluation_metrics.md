# Evaluation metrics for the article

What the scoring reports and how to read it. Code: `src/llm_metadata/groundtruth_eval.py`,
`evidence_ceiling.py`, `run_summary.py`. Config: `configs/eval_article.json`.

One-line summary of any run (dev records only by default, no API call):

    uv run python -m llm_metadata.run_summary artifacts/runs/<run>.json

## Class-level scores for spatial and temporal range

Exact match on a surface in km2 or on a year is harsh, and the relevance rules do
not use the exact number. They use classes. Two extra fields score the same
extractions at the class level, with the class functions of `relevance_rules.py`:

- `spatial_range_class`: more than 15,000 km2 = H, 5,000 to 15,000 = M, below 5,000 = L.
- `temporal_range_class`: from start and end year, 12 years or more = H, 3 to 11 = M, 1 to 2 = L.
- "Not stated" is no class. Right class counts as a hit, wrong class as a miss plus a
  false alarm, a class given where none is annotated as a false alarm, a class
  annotated but none given as a miss, both not stated as a true negative. The
  exact-match column for these fields is the class accuracy, "not stated" included.
- The rules have no separate duration class: duration is computed from start and end
  year, so `temporal_range_class` is the duration class.

## Bootstrap intervals

`bootstrap_report(report_or_path)` resamples records with replacement (all fields of a
record together), 1000 replicates, seed 0, and gives 95 % percentile intervals for
precision, recall, F1 and exact-match rate of every field and for the micro average.
It accepts an `EvaluationReport` or a run file. A metric with nothing in its denominator
(no predicted positives, for precision) is shown as N/A. With 30 records, intervals are
wide: expect plus or minus 0.15 to 0.25 on most fields. Differences smaller than that
between two prompts are not distinguishable.

## Evidence ceiling

From the annotators' position columns, for each record and field, where the annotated
value was found. Phrases in the spreadsheet and what we make of them:

| Spreadsheet phrase | Meaning | Counted as |
|---|---|---|
| `source link abstract`, `source link` | repository description / page | abstract |
| `source publication text`, `article` | article body | article |
| `dataset` | inside the data files | dataset |
| `not given`, `no` | not stated anywhere; the annotator derived or estimated it | none |
| empty cell although a value exists | position not recorded | unrecorded |

Fields with a ceiling: start and end year, the temporal class (column
`temporal_range_position`), spatial range and class (`spatial_range_position`), duration
in years (`temporal_duration_position`), and `geospatial_info_dataset` (from
`geospatial_info_repo_page_text` and `geospatial_info_article_text`). Data type,
species and the yes/no fields have no position column.

`ceiling_recall(field, input)` gives the highest recall reachable: `abstract` reads
the abstract/repository text, `fulltext` and `pdf` read that plus the article. Records
with no recorded position are left out of the figure; `recall_low` and `recall_high`
count them as unreachable or reachable.

Valid records (all 299), share of annotated values reachable:

| Field | Values | Abstract | Full text | Only in data files | Not stated (derived) |
|---|---|---|---|---|---|
| start and end year | 112 | 24 % | 97 % | 2 | 1 |
| spatial range (km2) | 107 | 7 % | 43 % | 0 | 56 |
| duration (years) | 129 | 10 % | 17 % | 12 | 91 |
| geospatial info | 92 | 10 % | 100 % | 0 | 0 |

Read this with care:

- More than half of the spatial values (56 of 107) are not written in any text. The
  annotator estimated the area. Exact km2 from text is capped well below 50 %, even with
  the full article. This is the main argument for scoring the class instead.
- The ceiling is cautious. Annotators say where they found a value, not every place it
  appears. On the dev subset, recall for start year with the abstract (0.62) is above the
  ceiling (0.33), so the repository description often repeats what the annotator took
  from the article. Treat the ceiling as "where the annotator looked", not a hard limit.
- For geospatial info the full-text ceiling of 100 % is by construction: the two columns
  are the places where the annotator saw the information.

## The `geospatial_info` N/A

In the Haiku 5.5 abstract run (`20261115_082643_haiku55_abstract_low`) the field
`geospatial_info` showed N/A for precision, recall and F1. Cause: an evaluation config
bug, not a model result. The run used `configs/eval_default.json`, which still named the
field `geospatial_info`. The model has no such field (it is `geospatial_info_dataset`), so
both annotated and predicted values were read as empty on all 30 records and counted as
true negatives, which leaves precision and recall without a denominator. The three
checked-in configs (default, strict, fuzzy species) are fixed, the evaluator now warns
when a config names a field that exists on neither model, and a test checks that every
checked-in config uses real field names. Rescored, the field is
precision 0.23, recall 0.50, F1 0.31 on the 30 dev records (the run's other fields do
not change). Earlier saved runs that used these configs carry the same blind spot for
that field.
