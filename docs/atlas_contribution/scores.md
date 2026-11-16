# What would a dataset add to the Atlas? Four contribution scores

**Track:** Atlas contribution potential (candidate second article). Code: `src/llm_metadata/atlas_match.py` (matching) and `src/llm_metadata/atlas_contribution.py` (scores). Results: [`results.md`](results.md).

## Why four scores and not one

The Fuster relevance asks "is this dataset good in general?": long, large, many species. It does not ask what the Biodiversité Québec Atlas already holds. A 20-year moose series in the Laurentians scores high; three midge species never recorded in Québec, collected north of the 49th parallel, score low.

The scores below ask the other question: **given what the Atlas holds, what would this dataset add?** A dataset can add in four different ways, and one number would hide which:

| Score | Plain question | 1 means | 0 means |
|---|---|---|---|
| **Taxonomic novelty** | Are its taxa absent or rare in the Atlas, where the dataset was collected? | The Atlas holds no record of these taxa there | The Atlas already holds 100 or more records of each |
| **Spatial novelty** | Is the place under-sampled for its groups? | The place is 10 times or more sparser (records per km²) than the province, for these groups | The place is at or above the provincial density |
| **Temporal gain** | Does it cover decades the Atlas lacks? | Those decades hold 10 times fewer records (or none) than the best-covered decade, for these groups and places | It covers the Atlas's best decade |
| **Group gap** | Does it hold groups the Atlas under-represents? | The group has 10 times less sampling effort (records per known species) than the median group | The group is at or above the median effort |

Each score is between 0 and 1. A score is **missing**, not zero, when the dataset does not give what it needs (no year, no place, no taxon named precisely enough). Missing means "cannot tell", not "adds nothing".

## How each score is computed

All four use the same shape: compare the Atlas count with a reference, on a log scale, and cut at a threshold `k`. On a log scale, "10 times fewer" counts the same for birds and for mosses, which matters because birds are 84 % of the Atlas records.

**Taxonomic novelty.** For each taxon the dataset names at family rank or finer (species, genus, family), count `n`, the Atlas records of that taxon in the dataset's regions, all decades:

    novelty = 1 − min(1, log10(1 + n) / log10(1 + k_taxon)),   k_taxon = 100

0 records → 1; 9 records → 0.5; 100 records or more → 0. The dataset score is the mean over its taxa. Orders and classes ("beetles", "ants") are not judged: the Atlas is never empty at that rank, so a low score would only mean "too coarse to tell".

**Spatial novelty.** For each group of the dataset and each of its regions, `ratio` = (Atlas records of the group per km² in the region) / (the same for the whole province):

    spatial = clip(log10(1 / ratio) / log10(k_spatial), 0, 1),   k_spatial = 10

The dataset score is the mean over groups (weighted by how many of its taxa fall in each) and regions.

**Temporal gain.** For each group, region and decade the dataset covers, `q` = Atlas records in that decade / records in the best-covered decade of the same group and region:

    temporal = clip(log10(1 / q) / log10(k_temporal), 0, 1),   k_temporal = 10

Most Atlas records are recent (2010s, 2020s), so older decades score high. That is intended: old records are what change detection lacks.

**Group gap.** For each group, `effort` = Atlas records per species the Atlas holds for the group (whole province), compared with the median group (152 records per species):

    group_gap = clip(log10(median / effort) / log10(k_group), 0, 1),   k_group = 10

| Group | Records per species | Gap |
|---|---|---|
| Fungi and lichens | 26 | 0.77 |
| Algae | 51 | 0.47 |
| Molluscs | 63 | 0.38 |
| Other invertebrates | 64 | 0.38 |
| Insects | 74 | 0.32 |
| Other arthropods | 77 | 0.30 |
| Microorganisms | 93 | 0.21 |
| Mosses and liverworts, vascular plants, fish, reptiles, amphibians, mammals, birds | 212 to 78 000 | 0 |

Full table: `group_effort.csv`. The species count is the number the Atlas has *seen*, not the true richness, so poorly known groups look better sampled than they are: this score is conservative.

**Mixed datasets.** Each taxon mention weighs 1, split over its groups: "benthic invertebrates" counts a quarter for each of the four invertebrate groups.

## Thresholds and how much they matter

| Threshold | Default | Meaning | ±50 % changes ranks? |
|---|---|---|---|
| `k_taxon` | 100 records | A taxon with this many records in the region is well covered | Barely (Spearman 0.91 to 0.97) |
| `k_spatial` | 10× sparser | Full spatial gap | No (1.00) |
| `k_temporal` | 10× fewer | Full temporal gap | No (≥ 0.99) |
| `k_group` | 10× less effort | Full group gap | No (1.00) |
| `gap_cut` | 0.5 | A score at or above this "fills" that gap (summary count only) | **Yes** (0.63 to 0.72) |
| absent species | not scored | Taxa missing from the Atlas extract are left out of taxonomic novelty | Some (0.86) |

The `k` thresholds rescale the scores and move where they saturate at 1; they do not reorder datasets. The values were chosen as round, explainable orders of magnitude, not fitted. The count of gaps filled depends on `gap_cut`, so it is a reading aid, not a measure. Details: `ceiling_sensitivity.csv`.

## No composite score

The four scores barely correlate with each other (Spearman between −0.11 and 0.12), except taxonomic novelty with group gap (0.60): rare taxa belong to under-sampled groups, which is expected, not redundant. They also rest on different information, so each is missing for a different set of datasets (taxonomic novelty can be computed for 79 of the 231 records, group gap for 153). A weighted average would mostly reflect which scores happen to be computable. We therefore keep the four scores side by side, and report the **number of gaps filled** (scores at 0.5 or more) only as a summary for tables.

## Matching: what the scores rest on

**Taxa.** Each name goes through GBIF (`llm_metadata.gbif.resolve_taxon`), then to the Atlas at the rank the dataset states:

| Status | Meaning |
|---|---|
| matched | The Atlas holds records at that rank (species, genus, family, order or class) |
| absent | GBIF knows the name, the Atlas extract does not: never recorded, **or a sensitive species** |
| group only | Only a broad group is known ("fish", "c. 30 lichen species") |
| unresolved | GBIF found nothing, or the answer is ambiguous |

Ambiguous answers are treated as unresolved while the GBIF homonym fix is in progress: GBIF homonyms, a count statement ("c. 90 collembola species") resolved to one species, and a common name landing on a family the Atlas never saw ("parasites" → a tongue-worm). When a species is absent under its GBIF name, an Atlas species with the same epithet in the same group is accepted if GBIF confirms it is the same taxon (the Atlas files *Notropis hudsonius* as *Hudsonius hudsonius*).

**Places.** Names are matched to the 18 administrative regions (with aliases: "Gaspé Peninsula", "Nunavik", "Eastern Townships"), else to north or south of the 49th parallel, else to the whole province. The **annotations hold no place names**: their only clue is the Fuster flag `bias_north_south` (north → north of the 49th; not north → south; missing → unknown).

**Years.** The year range becomes Atlas decades (before 1950, 1950s … 2020s).

## Limits to keep in mind

- **Sensitive species are absent from the Atlas side.** Caribou, wood turtle, lake sturgeon, American eel, Bicknell's thrush and other species at risk look "absent". The scores cannot reward data on species at risk; by default these taxa are left out of taxonomic novelty rather than scored as new. For insects, which rarely have a legal status in Québec, absent most likely means truly absent.
- **Place information from the annotations is crude.** Two regions only, and the flag was written for another purpose: an arctic fox study in the eastern Subarctic is flagged "not north". Spatial novelty from the annotations is therefore close to a north/south indicator. Extraction with place names (schema `schemas/atlas_contribution.py`) is needed for region-level scores.
- **Atlas counts are records, not effort.** A region with one large bird survey looks well sampled for birds.
- **The Atlas extract is a staging snapshot** (2026-11-15) of a materialized view.
- **Taxon resolution has known errors** (common-name homonyms, the "ants" label mapped to the order Hymenoptera). They affect which group a dataset counts toward more than the scores themselves.
- **Data availability is not scored.** A dataset whose records are not deposited adds nothing to the Atlas, whatever its scores. The extraction schema asks whether occurrence records are available; the annotations do not.
