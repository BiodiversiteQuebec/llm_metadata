"""Prompt for the Atlas contribution extraction (schema ``AtlasContributionExtraction``).

Same input modes as the Fuster prompts (abstract, PDF text, native PDF); the
task differs: describe what the dataset would add to an occurrence atlas, not
whether it is relevant in general.
"""

from llm_metadata.prompts.common import PERSONA, SCOPING

TASK = """## Task

You describe a biodiversity dataset so that it can be compared with what the
Biodiversité Québec Atlas (an occurrence database for the province of Quebec,
Canada) already holds. Report what the dataset itself contains.

- **focal_taxa**: the organisms the dataset has records for. List each named taxon once.
  Use rank `broad_group` for labels such as "birds", "pollinators" or "benthic
  macroinvertebrates". Skip taxa only mentioned as context, hosts, prey, predators
  or comparison. If the text gives a count instead of names ("73 weevil species"),
  add the group ("weevils", rank family or broad_group) and set `taxon_count`.
- **places**: where the data were collected, most specific places first. Set
  `in_quebec` and `north_of_49` only when you can tell. Landmarks: southern Quebec,
  the St. Lawrence valley, Lac Saint-Jean (48.5°N) and Amos (48.6°N) are south of
  the 49th parallel; Chibougamau (49.9°N), Matagami, James Bay, Eeyou Istchee,
  Nunavik and the Côte-Nord from Baie-Comeau (49.2°N) eastward are north.
- **year_start / year_end**: the years of data collection, not of publication.
- **record_kind**: occurrence (where and when a taxon was seen), presence_absence
  (detections and non-detections at surveyed sites), abundance (counts or densities),
  traits_or_genetics, or environmental_or_other.
- **occurrence_records_available**: whether the deposited data include taxon records
  with place and date.
- Leave a field null when the text does not say. Do not guess numbers."""

SYSTEM_MESSAGE = "\n\n".join([PERSONA, SCOPING, TASK])
