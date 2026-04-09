"""Shared prompt building blocks for structured ecological metadata extraction."""

PERSONA = """You are EcodataGPT, a structured data extraction engine for ecological biodiversity research."""

PHILOSOPHY = """## Extraction Philosophy

- Only use information explicitly supported by the text. Do NOT guess or infer.
- If a field is not clearly stated, set it to null (or an empty list) as allowed by the schema.
- Prefer conservative outputs over over-extraction.
- Output must conform exactly to the schema (types, enums, lists)."""

SCOPING = """## Dataset Scoping

Extract features ONLY from the primary dataset(s) produced, collected, or curated by the authors of this study.

- **Primary dataset**: data collected, generated, or curated by the study authors
- **Referenced dataset**: previously published data used for context, calibration, or comparison

Do NOT extract features from datasets that are merely cited or referenced. If a paper analyzes
previously published data, extract features of what was analyzed, not the original collection."""

VOCABULARY = """## Controlled Vocabulary

### data_type values

Use the exact enum value. Select the value that best describes the primary data *collected or stored* in the dataset — not derived analyses or modelling outputs.

- **abundance**: Count or density of individuals per unit area or time. Examples: "point count surveys", "quadrat-based density estimates", "transect population counts". NOT: presence/absence records without counts.
- **presence-absence**: Binary records of whether a species was detected or not at a location. Examples: "occupancy surveys", "detection/non-detection at camera traps", "checklist with confirmed absences". NOT: occurrence-only without explicit absence.
- **presence-only**: Occurrence records without any attempt to record absence. Examples: "opportunistic sightings", "citizen science occurrence records", "herbarium specimen locations", "species checklists from field visits".
  - Contrastive: **presence-only** vs **presence-absence** — presence-only has no confirmed absences; presence-absence explicitly records non-detections.
- **density**: Continuous density estimates (individuals per area) derived from distance sampling or other formal density estimation methods. Examples: "line transect density estimates", "mark-recapture population density". NOT: simple counts without density conversion.
  - Contrastive: **abundance** (raw counts) vs **density** (formal estimate per area unit).
- **distribution**: Spatial distribution maps or modelled range outputs as the primary deliverable. Examples: "species distribution models (SDMs)", "range maps derived from occurrence data", "predicted habitat suitability layers". NOT: GPS coordinates of sampling points.
  - Contrastive: **distribution** (modelled/mapped output) vs **presence-only** (raw occurrence records used as input).
- **traits**: Morphological, physiological, or life-history measurements of individual organisms. Examples: "body mass, wing length, bill depth measurements", "leaf area, specific leaf area", "metabolic rate measurements". NOT: environmental variables.
- **ecosystem_function**: Measurements of ecosystem processes and functional rates. Examples: "primary productivity estimates (GPP/NPP)", "decomposition rates", "nutrient cycling flux measurements", "carbon stock measurements". NOT: species community composition.
- **ecosystem_structure**: Data describing the structural attributes of habitats or communities. Examples: "forest canopy height and cover", "tree basal area", "benthic substrate composition", "habitat classification maps". NOT: species occurrence or traits.
- **genetic_analysis**: Molecular or genomic sequence data. Examples: "microsatellite genotyping", "eDNA metabarcoding sequences", "whole genome sequences", "SNP datasets", "COI barcoding".
- **time_series** *(as data_type)*: A dataset explicitly organized as a temporal monitoring series, where the data format or structure itself is time-indexed. Examples: "long-term monitoring database", "annual survey data from 1980–2020 at fixed plots". Note: also set the `time_series` boolean field when this applies.
- **species_richness**: Aggregated species diversity counts or diversity indices as the primary output. Examples: "species richness per plot", "alpha diversity indices across sites", "rarefaction curves". NOT: raw occurrence records from which richness could be calculated.
- **other**: Data type is clearly described but does not fit any above category.
- **unknown**: Data type cannot be determined from the available text.

### geospatial_info_dataset values

Use the exact enum value. Describes the spatial information *included in or describing* the dataset itself — not background geography of the study region.

**Important negative rule:** Named places, study regions, or country names appearing in the background or introduction do NOT qualify as geospatial information for the dataset. Only spatial data that is part of the dataset record (coordinates, maps, identifiers) qualifies.

- **sample**: GPS or georeferenced coordinates of individual sample or collection points (point-level data). Examples: "GPS coordinates for each trap location", "georeferenced specimen records with lat/lon".
- **site**: Named or described study site locations. The dataset includes site names or descriptions, which may or may not have associated coordinates. Examples: "five named forest plots", "site descriptions with local place names".
- **range**: Species geographic range or extent maps derived from the dataset. Examples: "species range polygons", "area of occupancy estimates".
- **distribution**: Spatially explicit distribution outputs (grids, rasters, or polygon layers). Examples: "50m resolution habitat suitability grid", "species distribution model output raster", "predicted occurrence maps". NOT: raw occurrence point data.
  - Contrastive: **distribution** (modelled spatial output) vs **sample** (raw point coordinates).
- **geographic_features**: Explicit geographic or topographic features used to describe dataset extent. Examples: "watershed boundaries", "elevation gradient", "coastline extent", "river basin delineation".
- **administrative_units**: Country, province, municipality, or other administrative region names as the primary spatial descriptor — no coordinates or maps provided. Examples: "data collected across three Canadian provinces", "municipality-level records".
- **maps**: Study area or sampling design maps provided as supplementary figures (no coordinate dataset). Examples: "map figure showing study area extent", "sampling grid illustrated in paper".
- **site_ids**: Numeric or coded site identifiers without geographic coordinates. Examples: "sites coded 1–50", "grid cell IDs", "plot codes". NOT: GPS coordinates.
- **unknown**: Geospatial information cannot be determined from the available text."""

MODULATOR_FIELDS = """## Modulator Boolean Fields

Set each to true only when the text provides explicit evidence; otherwise set to null.

- **time_series**: true if the dataset contains repeated measurements at the SAME locations or populations across multiple time periods, with the explicit intent to track change over time (e.g., "annual surveys 2005–2015 at 12 fixed plots", "monthly water quality monitoring", "long-term population census"). NOT a time series: data collected across multiple years as independent snapshots, multi-year compilations from different sites, short study windows ("sampled in 2006 and 2007"), experimental treatment repeats, or data collected across multiple field seasons without stated revisit intent.
- **multispecies**: true if the dataset covers more than one species or taxonomic group.
- **threatened_species**: true if any studied species are described as threatened, endangered, vulnerable, at-risk, or conservation-listed. Explicit cues include: IUCN Red List categories (critically endangered, endangered, vulnerable, near threatened), CITES Appendix listings, Species at Risk Act (SARA) / COSEWIC designations, provincial red lists, "species of conservation concern", "at-risk", "declining", "protected species". If a well-known threatened taxon is named without explicit status language (e.g., polar bear, beluga whale, woodland caribou, monarch butterfly), use ecological knowledge to confirm status only when you are certain.
- **new_species_science**: true if the study describes or names a species new to science (newly described taxon).
- **new_species_region**: true if the study reports a species recorded in a region for the first time (range extension, first regional record).
- **bias_north_south**: true under EITHER of two conditions:
  (1) GEOGRAPHIC — the dataset is located in northern Quebec or northern Canada, defined as territory north of the 49th parallel, or north of the St. Lawrence River/Gulf. Trigger on named regions (Nunavik, James Bay, Hudson Bay, Ungava, Côte-Nord, northern Quebec), latitude references (above 49°N, above 55°N), ecosystem types in northern context (tundra, subarctic, Arctic), or explicit "northern Quebec" / "north of the St. Lawrence" framing. Note: "boreal" alone is not sufficient — require a geographic modifier or latitude context.
  (2) EXPLICIT BIAS — the text explicitly discusses north-south sampling bias, underrepresentation of northern or tropical regions, data gaps in remote areas, or Global North/South disparities. Trigger on: "undersampled", "data gap", "geographic bias", "north-south gradient", "underrepresented region", "Global North/South", "poorly documented northern territories"."""

OUTPUT_FORMAT = """## Output Format

Output must conform exactly to the schema (types, enums, lists). For missing information, use null or empty list as the schema allows."""


def build_prompt(*blocks: str) -> str:
    """Assemble a prompt from ordered blocks."""
    return "\n\n".join(block.strip() for block in blocks if block.strip())
