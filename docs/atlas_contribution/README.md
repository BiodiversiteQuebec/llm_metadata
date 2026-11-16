# Atlas contribution potential: reference tables

> Scores built on these tables: [`scores.md`](scores.md) (method) and [`results.md`](results.md) (first results on the annotations, insect case, recommendation).

**Track:** candidate second article. Kept separate from the article 1 results.
**Database:** Biodiversité Québec Atlas, **staging**, read-only role, queried 2026-11-15 through `atlas_api.obs_counts` (pre-aggregated observations per region × taxon × dataset × year; a materialized view, so it may lag the source tables by one refresh).

## What is committed, what is not

| File | In git | Content |
|---|---|---|
| `group_region_decade.csv` | yes | Observations, species and datasets per broad taxonomic group × region × decade |
| `region_area.csv` | yes | Area of each region (km²), to read counts as densities |
| `artifacts/atlas/species_region_decade.csv` | **no** (git-ignored, 50 MB) | Same counts per species, with genus, family, order, class. Needed to score taxonomic novelty |
| `sql/atlas_contribution/*.sql` | yes | The queries that rebuild all three files |

Rebuild (on the agent server; the runner and read-only credentials come with the `bq-atlas-db` skill):

```bash
PY="uv run --no-project --with psycopg2-binary python"
Q=~/.agents/custom-skills/bq-atlas-db/scripts/q.py
$PY $Q -f sql/atlas_contribution/group_region_decade.sql --csv docs/atlas_contribution/group_region_decade.csv
$PY $Q -f sql/atlas_contribution/region_area.sql --csv docs/atlas_contribution/region_area.csv
$PY $Q -f sql/atlas_contribution/species_region_decade.sql --csv artifacts/atlas/species_region_decade.csv
```

## Choices

- **Regions:** the 18 administrative regions (Côte-Nord has two polygons in the database; they are summed under one name) and the split north / south of the 49th parallel. The north–south split is the one the Fuster schema uses for its `bias_north_south` modifier, so both tracks speak the same geography.
- **Broad groups:** the Atlas level-1 taxon groups (the website filter), with arthropods split into **insects** (class Insecta) and **other arthropods**, because insects are the case study. Taxa outside every group are kept as `UNGROUPED` rather than dropped.
- **Periods:** decades from 1950, one bin before 1950.
- **Sensitive species:** excluded from every file, including the git-ignored one. "Sensitive" is the Atlas flag `api.taxa.sensitive`: the SENSITIVE list or any Québec legal status (threatened, vulnerable, likely to be so designated, vulnerable to harvest). No committed number can reveal where a sensitive species was seen. Side effect: the scores cannot reward a dataset for adding records of a species at risk. This is a known limit, to discuss.
- **No coordinates** are queried or stored anywhere.

## First reading (all decades, sensitive taxa excluded)

Share of observations north of the 49th parallel, which covers **75 %** of Québec's area (1 256 070 of 1 680 833 km²):

| Group | Share north | Group | Share north |
|---|---|---|---|
| Reptiles | 0.7 % | Fungi | 36 % |
| Birds | 3.7 % | Other invertebrates | 40 % |
| Amphibians | 4.8 % | Non-vascular plants | 49 % |
| **Insects** | **5.9 %** | Mollusks | 31 % |
| Microorganisms | 8.1 % | Algae | 31 % |
| Fish | 12 % | Other arthropods | 25 % |
| Mammals | 15 % | Vascular plants | 18 % |

Insects: 865 351 observations in total, 51 455 north of the 49th. This is the gap the "insects in northern Québec" case study is about. Birds dominate the Atlas (41.8 M of 49.9 M observations in the administrative regions), so any score built on raw counts must be computed per group.
