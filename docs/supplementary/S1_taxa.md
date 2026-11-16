# S1: Taxa extraction and how we score it

*Supplementary material. Results below come from the 30-record development subset only (`data/manifests/dev_subset_data_paper.csv`). They are indicative, not final: the held-out records are scored once, at the end.*

## Why a dedicated evaluation

Taxa are the weakest extracted feature, but part of that weakness is in the scoring, not in the extraction. Exact string matching treats these pairs as errors:

| Annotation | Extraction | Same taxon? |
|---|---|---|
| Atlantic salmon | Atlantic salmon (Salmo salar) | yes |
| raccoons | Procyon lotor | yes |
| black-legged tick | Ixodes scapularis | yes |
| sapin baumier | balsam fir (Abies balsamea) | yes |
| caribou | Rangifer tarandus caribou | same species, finer rank |
| Vaccinium spp | Vaccinium angustifolium, Vaccinium myrtilloides | inside the annotated genus |
| 73 weevil species | weevils (Curculionoidea) + 8 named weevil species | same group, no count list to compare |

So we resolve every string, on both sides, to the GBIF backbone taxonomy and compare taxa, not strings, at several ranks. Count statements ("73 weevil species") and broad-group labels ("benthic macroinvertebrates") are scored as their own signals, never as missed species.

## Method

### 1. Splitting a species list into mentions

Each item of the `species` list is split into mentions before resolution:

- on semicolons ("Histeridae; Silphidae; Nicrophorus sayi");
- on a colon followed by a list ("16 damselfly species (Coenagrionidae): Amphiagrion saucium, Chromagrion conditum, …");
- never inside parentheses ("weevils (Coleoptera: Curculionoidea)" stays whole);
- parentheses left open by a badly split list are dropped ("Benthic intertidal community (c.20 algae").

Each mention is then classified:

| Kind | Example | How it is scored |
|---|---|---|
| Count statement | "c.30 bird species", "16 damselfly species (Coenagrionidae)" | Count signal, group signal, broad group |
| Named taxon (family rank or finer) | "Salmo salar", "Histeridae", "Vaccinium spp" | Every rank it reaches |
| Group label (above family rank, or a curated label) | "birds", "small mammals", "Coleoptera", "benthic communities" | Group signal, broad group |
| Not a taxon | "hybrids", "shade-tolerant species", "and others)" | Listed, not scored |

A number counts as a count when it is followed by words ("203 species inventoried", "15 OTUs"); a four-digit year in an authorship ("Linnaeus, 1758") does not.

### 2. Resolution to the GBIF backbone

`resolve_taxon(name)` (in `src/llm_metadata/gbif.py`) tries, in order, and keeps the first success:

1. **Whole string is a broad-group label** from a curated list of about 110 labels (`GROUP_LABELS`) ("fish", "birds", "trees", "benthic community", "Curculionoidea", …), each tied to a backbone taxon when one exists (birds → Aves, beetles and weevils → Coleoptera, mites → Arachnida, trees → Tracheophyta) or only to broad groups when none does (fish, invertebrates, algae).
2. **Scientific names inside the string**, binomials and trinomials first, anywhere in the string: "wood turtle (Glyptemys insculpta)", "migratory caribou Rangifer tarandus caribou". Authorship is ignored ("Acer saccharum Marshall"); "sp." and "spp." give the genus. GBIF species matching is used with guards: exact matches are accepted, fuzzy matches only for a misspelt epithet in the same genus ("Typhlodromus conspicuous" → T. conspicuus), and a higher-rank fallback only when it is the genus written in the string.
3. **Single capitalised words** that are higher taxa: "Histeridae", "Nematoda (adults)".
4. **Vernacular names**, through GBIF vernacular search on the backbone, in any language GBIF holds. Only exact name matches count, after removing case, accents, hyphens and plurals. Among exact matches the species is preferred over subspecies and genus, then the taxon with the most vernacular names (the well-known one: Procyon lotor rather than a raccoon subspecies). A vernacular name shared by more than two genera ("water mite" is attached to taxa in over twenty genera and families) is treated as ambiguous and falls through to step 5.
5. **Group label from the last words**: "resident bird species" → birds, "coprophilous and necrophagous beetles" → Coleoptera, "Tetranychid mites" → Arachnida.
6. **Vernacular name after dropping leading qualifiers**: "Atlantic-Gaspésie caribou" → "caribou" → Rangifer tarandus. This step is flagged in the record and skipped for strings that hold a scientific name.

Synonyms resolve to their accepted taxon ("Sambucus pubens" → Sambucus racemosa). When GBIF declines to choose between homonyms, the exact-name alternatives are used: the single accepted one ("Eteone", a polychaete genus, rather than a butterfly synonym), else the first synonym in GBIF's order (noted in the record). The raw string is always kept.

Each resolved record holds the backbone key, the rank, the classification from kingdom to species (names and keys) and a broad group. The same function will be reused to match taxa against the Biodiversité Québec Atlas.

GBIF answers are cached in `data/gbif/name_resolution_cache.json` (committed, about 330 KB for the dev subset), so re-running the evaluation makes no network call and gives identical results.

### 3. Broad groups

Broad groups follow how Biodiversité Québec reports taxa. They are derived from the GBIF classification:

| Broad group | GBIF classification |
|---|---|
| birds | class Aves |
| mammals | class Mammalia |
| fish | chordates with an order but no class (ray-finned fishes have no class in the current backbone), or a fish class (Elasmobranchii, Petromyzonti, …) |
| amphibians | class Amphibia |
| reptiles | classes Testudines, Squamata, Crocodylia |
| insects | class Insecta |
| other arthropods | other Arthropoda (arachnids, crustaceans, springtails) |
| molluscs | phylum Mollusca |
| other invertebrates | other animal phyla (annelids, nematodes, echinoderms, …) |
| vascular plants | phylum Tracheophyta |
| bryophytes | Bryophyta, Marchantiophyta, Anthocerotophyta |
| algae | Chlorophyta, Rhodophyta, Charophyta, and Ochrophyta (brown algae, diatoms) |
| fungi and lichens | kingdom Fungi |
| other | bacteria, protists, everything else |

A label that spans several groups keeps all of them: "benthic macroinvertebrates" is insects, other arthropods, molluscs and other invertebrates; it matches an extraction that names any of these.

### 4. Ranks and scores

For each record and each rank, both sides become a set of entries, so two strings for the same taxon count once ("Procyon lotor" and "raccoon" in one extraction are one entry).

| Rank | Entry | Which mentions take part |
|---|---|---|
| Exact taxon | accepted backbone key | named taxa, family rank or finer |
| Species | species key | named taxa at species rank or finer |
| Genus | genus key | named taxa at genus rank or finer |
| Family | family key | named taxa at family rank or finer |
| Broad group | broad group(s) | named taxa, group labels, counted groups |

Precision is the share of extracted entries that match an annotated entry; recall is the share of annotated entries matched by an extracted entry. Both are summed over records before dividing (micro average). A name GBIF cannot resolve stays in the scoring as its own label at every rank: it can only match the identical string on the other side, so resolution failures stay visible.

**Extracted taxa inside a coarser annotation are not false positives.** When the annotation gives a genus ("Vaccinium spp"), a species ("caribou", resolved to Rangifer tarandus) or a group or count ("c.30 bird species"), extracted taxa inside it cannot be judged at the finer ranks: the annotation is not detailed enough. They are counted as "within annotation", reported separately, and left out of precision at that rank. The annotated entry itself is still a miss at the ranks it does not match (nobody named the genus Vaccinium itself). The rule is one-sided on purpose: an extraction coarser than the annotation ("beetles" when the annotation names species) is a miss.

**Two separate signals:**

- *Group mentioned*: each annotated group label or counted group is matched when the extraction names that group or any taxon inside it ("73 weevil species" is matched by "Barypeithes pellucidus"). The reverse gives precision.
- *Count present*: a yes/no per record, whether each side gives a count statement. We also report whether the count values agree (exactly, or within 10% when one side says "about").

Two string baselines are kept for comparison: exact string match after case folding, and the fuzzy, vernacular-aware matching used so far in the main tables (similarity threshold 70).

## Results on the development subset

Two runs, the same 30 records:

- **Claude Haiku 5.5 on abstracts**, low reasoning effort (`20261115_082643_haiku55_abstract_low`).
- **GPT-5.4 on native PDFs**, medium reasoning effort, improved prompt (`20260401_123152_pe_model_medium_pdf_native`).

*⚠️ Only 30 records (the development subset). Indicative, not final results.*

| Scoring | Haiku 5.5, abstract: P / R / F1 | GPT-5.4, PDF: P / R / F1 |
|---|---|---|
| Exact string | 0.16 / 0.29 / 0.20 | 0.06 / 0.21 / 0.09 |
| Fuzzy string (current) | 0.32 / 0.60 / 0.42 | 0.17 / 0.62 / 0.27 |
| Exact taxon | 0.78 / 0.81 / 0.80 | 0.57 / 0.86 / 0.69 |
| Species | 0.82 / 0.91 / 0.86 | 0.61 / 0.97 / 0.75 |
| Genus | 0.88 / 0.94 / 0.91 | 0.63 / 0.97 / 0.76 |
| Family | 0.86 / 0.96 / 0.91 | 0.68 / 0.96 / 0.79 |
| Broad group | 0.94 / 0.94 / 0.94 | 0.93 / 0.94 / 0.93 |
| Group mentioned | 1.00 / 0.93 / 0.96 | 1.00 / 0.93 / 0.96 |
| Count present | 1.00 / 0.22 / 0.36 | 1.00 / 0.56 / 0.71 |

Counts behind the table, exact-taxon rank: 36 annotated taxa in both runs; Haiku gives 37 scorable extracted taxa (29 matched) plus 33 inside a coarser annotation; GPT-5.4 on PDFs gives 54 scorable (31 matched) plus 156 inside a coarser annotation. Count values agree in 2 of 2 records where both sides give a count for Haiku, 3 of 5 for GPT-5.4.

Per-mention tables with the status and reason of every match and miss: `docs/supplementary/data/S1_taxa_items_haiku55_abstract_low.csv` and `docs/supplementary/data/S1_taxa_items_pe_model_medium_pdf_native.csv`.

**Reading.** Most of what looked like species errors is wording: exact-taxon F1 is four times the exact-string F1 for Haiku and seven times for GPT-5.4. Recall is high at every rank once names are resolved (0.81 to 0.97). What remains is a precision question, and it depends on input length: with the full PDF, GPT-5.4 lists many more taxa than the annotator (210 extracted taxa against 36 annotated), Most of them sit inside an annotated group or count (156); 23 do not match any annotated taxon at the exact rank, and most of these are incidental taxa (see below). At the broad-group rank both runs agree with the annotation in about 94% of cases, which is the level that matters for a gap analysis by taxonomic group. Count statements are the weak spot: Haiku drops most of them (2 of 9 records), the PDF run keeps more (5 of 9).

**Name resolution.** 36 of the 37 annotated names resolve (97%): 21 through scientific names, 14 through vernacular names (5 of them French), and 1 group label; the 13 annotated count statements all yield a counted group. On the extraction side, 89 of 90 names resolve for Haiku and 223 of 224 for GPT-5.4.

## Failure modes, with examples from the development subset

**Decorated strings.** Extractions mix vernacular and scientific names, authorship and qualifiers: "woodland caribou (Rangifer tarandus caribou)", "Amblyseius fallacis (Garman)", "Acer saccharum Marshall", "migratory caribou Rangifer tarandus caribou" (record 30). String matching fails on all of them; resolution handles all of them through the embedded scientific name. Long items that pack a whole list into one string ("coprophilous and necrophagous beetles; Histeridae; Hydrophilidae; …; Nicrophorus tomentosus" in record 315, PDF run) are split before resolution.

**Count statements.** Annotators often summarise: "73 weevil species" (record 351), "c.30 bird species" (record 343), "c.132 species of benthic community" (record 208). The PDF extraction for record 343 lists 37 resident bird species by name; string scoring counts them as 37 false positives and the annotation as a miss. Here they are "within annotation", the broad group (birds) matches, and the group is mentioned. The count itself is a separate signal: GPT-5.4 on the PDF keeps "73 species in three families of Curculionoidea" for record 351 (count agrees), but gives "203 species inventoried" for record 71 where the annotation says "c.150 plant species" (count disagrees: worth checking in the paper, see below).

**Broad groups.** Labels such as "small mammals", "beetles" (record 38), "benthic communities" (record 208), "Tetranychid mites" (record 271) resolve to a backbone taxon or a set of broad groups. Two traps: a vernacular name can be attached to a single species in GBIF while being a group name in practice ("water mite" points to one Atractides species among many; we treat it as ambiguous), and functional or trait groups are not taxa ("non-native species", "shade-tolerant species", "light-demanding species" in record 71, Haiku run), so they are listed and not scored.

**Vernacular vs scientific, and rank.** Vernacular annotations resolve well, including French ones (record 175: "sapin baumier" → Abies balsamea, "cerisier de Pennsylvanie" → Prunus pensylvanica). Rank is the harder part: "caribou" resolves to the species Rangifer tarandus while extractions give the subspecies R. t. caribou (records 101, 104), so the pair matches at the species rank, not at the exact rank. Misspellings in the source or in the extraction stay unresolved, by design: "Ptilidae" (record 315, both runs) is a misspelling of the beetle family Ptiliidae; GBIF finds no exact name, and fuzzy matches on single words are refused because they jump to unrelated families (Psilidae, Ptinidae).

**Focal vs incidental taxa.** This is the main source of extra taxa. Record 11 (caribou fitness under human disturbance): the PDF extraction adds wolves, black bear and moose, which the paper most likely mentions as predators and alternative prey; the annotation keeps only caribou. Record 38 (small mammals and beetles): the PDF extraction adds black spruce, balsam fir, paper birch and trembling aspen, which describe the habitat. They match at no rank (the trees) or only at the broad group (the mammals). The line is not always clear: in record 37 (poplar hybrid zone) the three Melampsora rust fungi are extra for both runs, yet the dataset includes a file on inoculation with them (see doubtful annotations).

## Reproducing

```bash
# metrics, then the mismatching mentions
uv run python -m llm_metadata.taxonomy_eval artifacts/runs/<run>.json --manifest data/manifests/dev_subset_data_paper.csv
# options: --show all|mismatches|none, --items-csv <path>, --json <path>
```

```python
from llm_metadata.taxonomy_eval import evaluate_run_taxa
ev = evaluate_run_taxa("artifacts/runs/<run>.json")
ev.metrics_frame()    # per-rank precision, recall, F1
ev.items_frame()      # one row per mention, with status and reason
ev.records_frame()    # one row per record

from llm_metadata.gbif import resolve_taxon
resolve_taxon("Atlantic salmon (Salmo salar)")   # key, rank, classification, broad group
```

Tests with mocked GBIF answers: `tests/test_taxa_multirank.py`.

## Doubtful species annotations (development subset)

To be carried into the register of doubtful annotations.

| Record | Annotated value | Why doubtful |
|---|---|---|
| 175 | "Crable a epis" | Typo for "Érable à épis" (mountain maple, Acer spicatum); does not resolve. The other names in the list are French without accents ("epinette blanche", "bouleau a papier"), while most records use scientific or English names |
| 225 | "Benthic intertidal community (c.20 algae", "c.15 molluscs", "c.15 annelid species", "and others)" | One statement split into four items at the commas inside its parenthesis. The habitat-forming species manipulated in the study and named in the abstract (Fucus distichus edentatus, F. vesiculosus, Mytilus spp.) are not annotated |
| 30 | "Rangifer tarandus" | The abstract names "migratory caribou Rangifer tarandus caribou"; the annotation is coarser than the text |
| 89 | "Rangifer tarandus" (with Alces alces, Canis lupus) | The abstract names "caribou (Rangifer tarandus caribou)"; same coarsening |
| 11, 12, 30, 89, 101, 104, 123 | "Rangifer tarandus caribou", "Rangifer tarandus", "caribou", "Caribou" | The same taxon is annotated at three levels of detail across records (subspecies, species, vernacular). A convention is needed, otherwise exact-taxon scores depend on which record an annotator handled |
| 37 | "hybrids" | Not a taxon (the hybrids of Populus balsamifera × P. deltoides). The dataset also holds inoculation results for three rust fungi (Melampsora larici-populina, M. medusae f. sp. deltoidae, M. occidentalis), which are not annotated |
| 258 | "16 damselfly species", "water mite" | The damselflies get a count, the mites none, although the abstract gives "15 operational taxonomic units (OTUs) for mite species"; the two families named in the abstract (Coenagrionidae, Arrenuridae) are not annotated |
| 315 | "c.30 beetle species" | The abstract states that four families were identified to species (Histeridae, Hydrophilidae, Scarabaeidae, Silphidae); the annotation could name them. The count "c.30" is not in the abstract: to check in the paper |
| 71 | "c.150 plant species" | The PDF extraction reports "203 species inventoried"; the count is not in the abstract: to check in the paper |
| 343 | "c.30 bird species" | The count is not in the abstract; the PDF extraction lists 37 resident species by name: to check in the paper |
| 208 | "c.132 species of benthic community" | The paper reports "132 taxa belonging to eight phyla" (PDF extraction): taxa, not species |
