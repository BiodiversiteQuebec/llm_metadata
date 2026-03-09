## Evidence mode

Use gpt to obtain evidence that that helps understand how the annotation/extraction was made for each values and fields. Run using out data in pydantic model + og context and data. Can be used on both manual annotations, and gpt extractions.

Will be used in a context of prompt engineering, to give insight on how to either improve gpt based extraction or discuss the results.

Basically, an evidence should help me understand the quote and rationale behind the linking 

Basically a post extraction process, where full input with extraction results are fed to gpt_extract_from_text.

## Relevant context

Mismatches in artifacts\runs\20260306_124634_dev_subset_pdf_file.json run.

| doi | true_value | pred_value | tp | fp | fn |
| --- | --- | --- | --- | --- | --- |
| 10.1371/journal.pone.0077514 | None | ['sample', 'site', 'administrative_units', 'maps'] | 0 | 4 | 0 |
| 10.1038/s41598-018-34822-9 | ['distribution'] | ['maps', 'sample', 'site', 'range'] | 0 | 4 | 1 |
| 10.1371/journal.pone.0073695 | None | ['sample', 'site', 'range', 'maps', 'administrative_units'] | 0 | 5 | 0 |
| 10.1002/ece3.4685 | None | ['sample', 'site', 'range', 'maps', 'site_ids'] | 0 | 5 | 0 |
| 10.1098/rspb.2014.0502 | ['sample'] | ['sample', 'site', 'range', 'maps', 'administrative_units'] | 1 | 4 | 0 |
| 10.5558/tfc76653-4 | None | ['sample', 'site', 'site_ids', 'administrative_units'] | 0 | 4 | 0 |
| 10.1093/jhered/esw073 | ['sample'] | ['sample', 'site', 'maps', 'administrative_units', 'site_ids'] | 1 | 4 | 0 |
| 10.1086/671900 | None | ['site', 'sample', 'site_ids', 'maps', 'administrative_units'] | 0 | 5 | 0 |
| 10.3389/fmars.2021.637546 | ['site_ids'] | ['sample', 'site', 'site_ids', 'maps', 'administrative_units', 'geographic_features'] | 1 | 5 | 0 |
| 10.1371/journal.pone.0109261 | None | ['site', 'sample', 'administrative_units'] | 0 | 3 | 0 |
| 10.1002/ece3.3906 | ['site_ids'] | ['site', 'maps', 'site_ids', 'administrative_units'] | 1 | 3 | 0 |
| 10.1111/eva.13248 | ['site'] | ['sample', 'site', 'site_ids', 'maps', 'geographic_features'] | 1 | 4 | 0 |
| 10.1111/ecog.00997 | None | ['site', 'site_ids', 'maps'] | 0 | 3 | 0 |
| 10.1111/ddi.12496 | ['sample'] | ['sample', 'site', 'maps', 'administrative_units'] | 1 | 3 | 0 |
| 10.1603/0013-8746%282006%2999%5b536%3aiopmiq%5d2.0.co%3b2 | ['administrative_units'] | ['sample', 'site', 'administrative_units'] | 1 | 2 | 0 |
| 10.1002/ece3.1476 | None | ['sample', 'site', 'maps', 'distribution', 'site_ids', 'administrative_units'] | 0 | 6 | 0 |
| 10.1186/s40462-016-0079-4 | ['sample'] | ['sample', 'site', 'range', 'maps'] | 1 | 3 | 0 |
| 10.1111/eva.12028 | None | ['sample', 'site', 'administrative_units'] | 0 | 3 | 0 |
| 10.1603/en10045 | None | ['site', 'administrative_units'] | 0 | 2 | 0 |
| 10.3390/ijgi7090335 | None | ['sample', 'site', 'maps', 'distribution', 'administrative_units'] | 0 | 5 | 0 |
| 10.1603/0013-8746%282005%29098%5b0565%3awccdaa%5d2.0.co%3b2 | None | ['site', 'site_ids', 'administrative_units'] | 0 | 3 | 0 |
| 10.1002/ece3.1029 | None | ['site', 'sample', 'administrative_units', 'maps'] | 0 | 4 | 0 |
| 10.1371/journal.pone.0204445 | ['site_ids'] | ['site', 'site_ids', 'maps', 'administrative_units'] | 1 | 3 | 0 |
| 10.1098/rspb.2014.0649 | ['site'] | ['sample', 'site', 'administrative_units', 'site_ids'] | 1 | 3 | 0 |
| 10.1093/jhered/esx103 | None | ['site', 'sample', 'administrative_units'] | 0 | 3 | 0 |
| 10.1111/eva.12315 | ['sample'] | ['site', 'sample', 'maps', 'administrative_units'] | 1 | 3 | 0 |
| 10.1111/1365-2664.12675 | ['site_ids'] | ['sample', 'site', 'administrative_units', 'site_ids'] | 1 | 3 | 0 |
| 10.1890/12-2118.1 | None | ['sample', 'site', 'maps', 'geographic_features', 'administrative_units', 'range'] | 0 | 6 | 0 |
| 10.1371/journal.pone.0128238 | ['sample'] | ['sample', 'site', 'maps', 'administrative_units'] | 1 | 3 | 0 |
| 10.1002/ece3.1266 | None | ['site', 'site_ids', 'maps'] | 0 | 3 | 0 |

<!-- Rows sampled from: Mismatches for geospatial_info_dataset — all 30 rows -->

| doi | true_value | pred_value | tp | fp | fn |
| --- | --- | --- | --- | --- | --- |
| 10.1371/journal.pone.0077514 | ['other'] | ['traits', 'time_series', 'other'] | 1 | 2 | 0 |
| 10.1038/s41598-018-34822-9 | ['distribution'] | ['distribution', 'density', 'time_series'] | 1 | 2 | 0 |
| 10.1371/journal.pone.0073695 | ['presence-only'] | ['time_series', 'presence-only', 'distribution', 'other'] | 1 | 3 | 0 |
| 10.1002/ece3.4685 | ['other'] | ['time_series', 'distribution'] | 0 | 2 | 1 |
| 10.1098/rspb.2014.0502 | ['presence-only', 'genetic_analysis'] | ['genetic_analysis', 'presence-only', 'time_series', 'distribution'] | 2 | 2 | 0 |
| 10.5558/tfc76653-4 | ['density'] | ['abundance', 'density', 'presence-absence', 'distribution', 'traits', 'ecosystem_structure'] | 1 | 5 | 0 |
| 10.1093/jhered/esw073 | ['presence-only', 'genetic_analysis'] | ['genetic_analysis', 'time_series'] | 1 | 1 | 1 |
| 10.1086/671900 | ['presence-only'] | ['presence-absence', 'abundance', 'traits', 'time_series', 'other'] | 0 | 5 | 1 |
| 10.3389/fmars.2021.637546 | ['density'] | ['abundance', 'density', 'traits', 'ecosystem_structure', 'ecosystem_function', 'species_richness'] | 1 | 5 | 0 |
| 10.1371/journal.pone.0109261 | ['density'] | ['abundance', 'presence-absence', 'ecosystem_function', 'ecosystem_structure', 'species_richness', 'traits'] | 0 | 6 | 1 |
| 10.1002/ece3.3906 | ['genetic_analysis'] | ['genetic_analysis', 'abundance', 'ecosystem_structure'] | 1 | 2 | 0 |
| 10.1111/eva.13248 | ['genetic_analysis', 'presence-only'] | ['genetic_analysis'] | 1 | 0 | 1 |
| 10.1111/ecog.00997 | ['abundance', 'presence-only'] | ['abundance', 'presence-absence', 'species_richness', 'genetic_analysis', 'time_series', 'distribution', 'traits', 'other'] | 1 | 7 | 1 |
| 10.1603/0013-8746%282006%2999%5b536%3aiopmiq%5d2.0.co%3b2 | ['abundance', 'presence-only'] | ['abundance', 'presence-absence', 'species_richness', 'time_series'] | 1 | 3 | 1 |
| 10.1002/ece3.1476 | ['abundance'] | ['abundance', 'distribution'] | 1 | 1 | 0 |
| 10.1186/s40462-016-0079-4 | ['presence-only'] | ['traits', 'time_series', 'distribution', 'other'] | 0 | 4 | 1 |
| 10.1111/eva.12028 | ['genetic_analysis'] | ['abundance', 'genetic_analysis', 'time_series', 'traits'] | 1 | 3 | 0 |
| 10.1603/en10045 | ['abundance'] | ['abundance', 'species_richness'] | 1 | 1 | 0 |
| 10.3390/ijgi7090335 | None | ['abundance', 'presence-absence', 'distribution', 'species_richness'] | 0 | 4 | 0 |
| 10.1603/0013-8746%282005%29098%5b0565%3awccdaa%5d2.0.co%3b2 | ['abundance'] | ['abundance', 'presence-absence', 'species_richness', 'time_series'] | 1 | 3 | 0 |
| 10.1002/ece3.1029 | ['genetic_analysis', 'other'] | ['genetic_analysis', 'traits', 'abundance', 'presence-absence', 'time_series', 'ecosystem_structure'] | 1 | 5 | 1 |
| 10.1371/journal.pone.0204445 | ['presence-absence'] | ['abundance', 'presence-absence', 'species_richness'] | 1 | 2 | 0 |
| 10.1098/rspb.2014.0649 | ['genetic_analysis'] | ['abundance', 'presence-absence', 'traits', 'time_series'] | 0 | 4 | 1 |
| 10.1111/eva.12315 | ['density'] | ['traits', 'density', 'presence-absence', 'time_series', 'abundance'] | 1 | 4 | 0 |
| 10.1111/1365-2664.12675 | ['density'] | ['abundance', 'ecosystem_structure', 'species_richness'] | 0 | 3 | 1 |
| 10.1890/12-2118.1 | ['presence-only'] | ['time_series', 'presence-only', 'traits', 'distribution', 'presence-absence', 'traits', 'other', 'abundance', 'distribution'] | 1 | 6 | 0 |
| 10.1371/journal.pone.0128238 | ['density'] | ['abundance'] | 0 | 1 | 1 |
| 10.1002/ece3.1266 | ['genetic_analysis'] | ['genetic_analysis', 'time_series'] | 1 | 1 | 0 |

<!-- Rows sampled from: Mismatches for data_type — all 28 rows -->

| doi | true_value | pred_value | tp | fp | fn |
| --- | --- | --- | --- | --- | --- |
| 10.1371/journal.pone.0073695 | ['Rangifer tarandus caribou'] | ['Rangifer tarandus caribou', 'woodland caribou', 'Canis lupus', 'wolves', 'Ursus americanus', 'black bear', 'Alces alces', 'moose'] | 1 | 7 | 0 |
| 10.1002/ece3.4685 | ['Rangifer tarandus caribou'] | ['Rangifer tarandus caribou', 'woodland caribou'] | 1 | 1 | 0 |
| 10.5558/tfc76653-4 | ['sapin baumier', 'epinette blanche', 'bouleau jaune', 'bouleau a papier', 'Crable a epis', 'cerisier de Pennsylvanie'] | ['Abies balsamea', 'Picea glauca', 'Betula alleghaniensis', 'Betula papyrifera', 'Acer spicatum', 'Prunus pensylvanica', 'Rubus idaeus', 'Epilobium angustifolium', 'Corylus cornuta', 'Sorbus americana', 'Sambucus pubens'] | 0 | 11 | 6 |
| 10.1093/jhered/esw073 | ['black-legged tick'] | ['Ixodes scapularis', 'black-legged tick'] | 1 | 1 | 0 |
| 10.3389/fmars.2021.637546 | ['c.132 species of benthic community'] | ['132 taxa (8 phyla)', 'Micronephthys neotena', 'Eudorellopsis integra', 'Protomedeia grandimana', 'Nematoda (adults)', 'Macoma calcarea', 'Echinarachnius parma', 'Strongylocentrotus sp.', 'Cossura longocirrata', 'Eteone sp.', 'Hediste diversicolor', 'Praxillella praetermissa', 'Ameroculodes edwardsi', 'Ampelisca vadorum', 'Byblis gaimardii', 'Lysianassidae', 'Maera danae', 'Phoxocephalus holbolli', 'Pontoporeia femorata', 'Quasimelita formosa', 'Quasimelita quadrispinosa'] | 0 | 21 | 1 |
| 10.1371/journal.pone.0109261 | ['Benthic intertidal community (c.20 algae', 'c.15 molluscs', 'c.15 annelid species', 'and others)'] | ['Fucus distichus edentatus', 'Fucus vesiculosus', 'Mytilus spp.', 'Mytilus edulis', 'Mytilus trossulus', 'Ralfsia clavata', 'Gammarus spp.', 'Lacuna vincta', 'Margarites helicinus', 'Polychaeta'] | 0 | 10 | 4 |
| 10.1111/ecog.00997 | ['16 damselfly species', 'water mite'] | ['Amphiagrion saucium', 'Chromagrion conditum', 'Coenagrion interrogatum', 'Coenagrion resolutum', 'Enallagma aspersum', 'Enallagma boreale', 'Enallagma carunculatum', 'Enallagma cyathigerum', 'Enallagma ebrium', 'Enallagma geminatum', 'Enallagma hageni', 'Enallagma signatum', 'Ischnura posita', 'Ischnura verticalis', 'Nehalennia gracilis', 'Nehalennia irene'] | 0 | 16 | 2 |
| 10.1111/ddi.12496 | ['Eastern coyote', 'eastern wolf'] | ['Eastern Wolf (Canis lycaon)', 'Eastern Coyote (Canis latrans)', 'Great Lakes-Boreal Wolf (Canis lupus × lycaon)', 'Domestic Dog (Canis familiaris)'] | 2 | 2 | 0 |
| 10.1603/0013-8746%282006%2999%5b536%3aiopmiq%5d2.0.co%3b2 | ['11 mite species'] | ['Amblyseius fallacis (Garman)', 'Typhlodromus caudiglans Schuster', 'Agistemus fleschneri Summers', 'Anystis baccarum (L.)', 'Balaustium sp.', 'Typhlodromus conspicuus (Garman)', 'Typhlodromus herbertae Chant', 'Typhlodromus longipilis Nesbitt', 'Typhlodromus bakeri (Garman)', 'Typhlodromus pyri Scheuten', 'Amblyseius okanagensis (Chant)', 'Amblyseius finlandicus (Oudemans)', 'Phytoseius sp.'] | 0 | 13 | 1 |
| 10.1002/ece3.1476 | ['Rhododendron groenlandicum', 'Kalmia angustifolia', 'Chamaedaphne calyculata', 'Vaccinium spp'] | ['Rhododendron groenlandicum', 'Kalmia angustifolia', 'Chamaedaphne calyculata', 'Vaccinium angustifolium', 'Vaccinium myrtilloides', 'Vaccinium spp'] | 4 | 2 | 0 |
| 10.1186/s40462-016-0079-4 | ['Rangifer tarandus'] | ['Rangifer tarandus (caribou)', 'Rivière-aux-Feuilles herd', '96 caribou (80 F, 16 M); 181 individual-years'] | 1 | 2 | 0 |
| 10.1603/en10045 | ['c.30 beetle species'] | ['Histeridae', 'Hydrophilidae', 'Leiodidae', 'Ptilidae', 'Scarabaeidae', 'Silphidae', 'Staphylinidae', 'Trogidae', 'Hister furtivus LeConte', 'Margarinotus egregius (Casey)', 'Margarinotus faedatus (LeConte)', 'Margarinotus hudsonicus (Casey)', 'Margarinotus lecontei Wenzel', 'Cercyon assecla Smetana', 'Cercyon minusculus Melsheimer', 'Cercyon pygmaeus (Illiger)', 'Cryptopleurum minutum Fabricius', 'Gnathoncus communis (Marseul)', 'Dialytes striatulus (Say)', 'Onthophagus hecate hecate (L.)', 'Necrodes surinamensis Fabricius', 'Necrophila americana L.', 'Oiceoptoma noveboracense (Forster)', 'Nicrophorus defodiens Mannerheim', 'Nicrophorus investigator Zetterstedt', 'Nicrophorus orbicollis Say', 'Nicrophorus pustulatus Herschel', 'Nicrophorus sayi Laporte', 'Nicrophorus tomentosus Weber', 'Aphodius leopardus Horn', 'Aphodius rufipes L.', 'Nicrophorus americanus'] | 0 | 32 | 1 |
| 10.3390/ijgi7090335 | ['c.30 bird species'] | ['Setophaga ruticilla American Redstard', 'Setophaga castanea Bay-breasted Warbler', 'Poecile atricapillus Black-capped Chickadee', 'Poecile hudsonicus Boreal Chickadee', 'Melanitta americana Black Scoter', 'Mniotilta varia Black-and-white Warbler', 'Corvus corax Common Raven', 'Acanthis flammea Common Redpoll', 'Junco hyemalis Dark-eyed Junco', 'Hesperiphona vespertina Evening Grosbeak', 'Passerella iliaca Fox Sparrow', 'Regulus satrapa Golden-crowned Kinglet', 'Perisoreus canadensis Gray Jay', 'Melospiza lincolnii Lincoln’s Sparrow', 'Lanius excubitor Northern Shrike', 'Contopus cooperi Olive-sided Flycatcher', 'Haemorhous purpureus Purple Finch', 'Pinicola enucleator Pine Grosbeak', 'Setophaga pinus Pine Warbler', 'Euphagus carolinus Rusty Blackbird', 'Sitta canadensis Red-breasted Nuthatch', 'Regulus calendula Ruby-crowned Kinglet', 'Loxia curvirostra Red Crossbill', 'Vireo olivaceus Red-eyed Vireo', 'Bonasa umbellus Ruffed Grouse', 'Falcipennis canadensis Spruce Grouse', 'Tringa solitaria Solitary Sandpiper', 'Actitis macularius Spotted Sandpiper', 'Melanitta perspicillata Surf Scoter', 'Melospiza georgiana Swamp Sparrow', 'Catharus ustulatus Swainson’s Thrush', 'Catharus fuscescens Veery', 'Zonotrichia leucophrys White-crowned Sparrow', 'Numenius phaeopus Whimbrel', 'Loxia leucoptera White-winged Crossbill', 'Melanitta deglandi White-winged Scoter', 'Empidonax flaviventris Yellow-bellied Flycatcher'] | 0 | 37 | 1 |
| 10.1603/0013-8746%282005%29098%5b0565%3awccdaa%5d2.0.co%3b2 | ['73 weevil species'] | ['Eurymycter fasciatus', 'Trigonorhinus sticticus', 'Apion sp.', 'Baris interstitialis', 'Cosmobaris americana', 'Dirabius rectirostris', 'Madarellus undulatus', 'Acanthoscelidius acephalus', 'Amalus scortillum', 'Auleutes nebulosus', 'Ceutorhynchus americanus', 'Ceutorhynchus erysimi', 'Ceutorhynchus neglectus', 'Ceutorhynchus omissus', 'Ceutorhynchus oregonensis', 'Ceutorhynchus typhae', 'Glocianus punctiger', 'Homorosoma sulcipenne', 'Mononychus vulpeculus', 'Pelenomus fuliginosus', 'Pelenomus waltoni', 'Perigaster cretura', 'Rhinoncus bruchoides', 'Rhinoncus castor', 'Rhinoncus pericarpius', 'Rhinoncus perpendicularis', 'Acoptus suturalis', 'Cryptorhynchus lapathi', 'Tyloderma nigrum', 'Anthonomus corvulus', 'Anthonomus quadrigibbus', 'Anthonomus rubidus', 'Anthonomus signatus', 'Gymnetron antirrhini', 'Gymnetron tetrum', 'Isochnus rufipes', 'Pseudanthonomus sp.', 'Smicronyx sp.', 'Tachyerges niger', 'Tachyerges salicis', 'Tychius meliloti', 'Tychius picirostris', 'Tychius stephensi', 'Listronotus delumbis', 'Listronotus o. oregonensis', 'Listronotus sparsus', 'Dryophthorus americanus', 'Sphenophorus callosus', 'Sphenophorus minimus', 'Sphenophorus parvulus', 'Sphenophorus zeae', 'Barypeithes pellucidus', 'Otiorhynchus ovatus', 'Otiorhynchus sulcatus', 'Phyllobius oblongus', 'Polydrusus cervinus', 'Polydrusus impressifrons', 'Polydrusus sericeus', 'Sciaphilus asperatus', 'Sitona cylindricollis', 'Sitona flavescens', 'Sitona hispidulus', 'Sitona lineellus', 'Trachyphloeus bifoveolatus', 'Grypus equiseti', 'Tanysphyrus lemnae', 'Hypera nigrirostris', 'Hypera zoilus', 'Cleonis pigra', 'Magdalis barbita', 'Lepyrus palustris', 'Piazorhinus pictus', 'Piazorhinus scutellaris'] | 0 | 73 | 1 |
| 10.1002/ece3.1029 | ['Populus balsamifera', 'Populus deltoides', 'hybrids'] | ['Populus balsamifera', 'Populus deltoides', 'Populus deltoides × Populus balsamifera (native hybrids)'] | 2 | 0 | 1 |
| 10.1371/journal.pone.0204445 | ['12 mammal', '199 ground-dwelling beetles', '240 flying-beetles species'] | ['Tamiasciurus hudsonicus', 'Tamias striatus', 'Sorex spp.', 'Peromiscus maniculatus', 'Myodes gapperi', 'Microtus chrotorrhinus', 'Synaptomys cooperi', 'ground-dwelling beetles (3894 individuals, 199 species collected; 58 species used in analyses)', 'flying beetles (2411 individuals, 240 species collected; 48 species used in analyses)'] | 0 | 9 | 3 |
| 10.1111/1365-2664.12675 | ['c.150 plant species'] | ['203 herbaceous species inventoried across 784 1-m2 plots (see Appendix S4)', 'Bromus inermis L.', 'Phalaris arundinacea L.', 'Equisetum arvense L.', 'Artemisia vulgaris L.', 'Solidago canadensis L.', 'Dryopteris carthusiana (Vill.) H.P. Fuchs', 'Athyrium filix-femina (L.) Roth', 'Trillium erectum L.', 'Rubus pubescens Raf.', 'Agrimonia striata Michx.', 'Fragaria virginiana Duchesne', 'Onoclea sensibilis L.', 'Solidago rugosa Mill.'] | 0 | 14 | 1 |
| 10.1371/journal.pone.0128238 | ['raccoons', 'striped skunks'] | ['raccoon (Procyon lotor): 610 individuals captured', 'striped skunk (Mephitis mephitis): 121 individuals captured'] | 0 | 2 | 2 |
| 10.1002/ece3.1266 | ['Myotis lucifugus'] | ['Myotis lucifugus (little brown bat); tissue samples collected from 768 adults and 174 young-of-the-year (YOY)', 'mtDNA control region sequenced for 356 individuals', 'Microsatellite genotypes obtained for 735 adults and 168 YOY (successfully genotyped at ≥7 of 9 loci)'] | 1 | 2 | 0 |

<!-- Rows sampled from: Mismatches for species — all 19 rows -->

## Let's discuss

* Let's clarify the problem statement and the wording

* What context should be added to the text ? (Pydantic field description ? Og prompt instructions – for extraction, not annotations ?)

* Should I only extract evidence for all 

## Phases

0. Research - write synthesis to evidence in docs/evidence-research.md

Are there any other names and concepts than what I used that uses similar meta extraction using structured outputs ?

What works presents similar techniques for evidence / rationale ? (openai / claude / langchain documentation and cookbooks, medium and blog articles, scientific articles, etc)

What works in scientific litterature have used similar techniques (Biodiversity data, Ecology data, bioscience, medical science, else ?)

Rank concepts, techniques flows and sources by relevance based on criterias you choose.

I propose to extract evidence in two steps way, first regular extraction/annotation, then evidence that sticks to the value. Other comparable techniques and flow in other works ?

Should we reword and clarify the problem statement and the plan following what we learned.

How do other work evaluates the quality of the extraction ? Do they even do that ?

What is the scope of the work ? Only evidence and meta understanding of structured output extraction ? Larger scope ? Contains only bits relevant to what we want to do, but not whole workflow ...

What are schema option for pydantic evidence model from previous works ?

Be honest, any publishable contribution from the work wer'e doing with extraction if we have good results ? A) Separate scientific contribution just for evidence extraction B) Should be combined with larger scoped work C) No D) ...

1. Basics to notebook for experimentation and results exploration.

Run on first 5 dev subset datasets.

This phase should not generate 

* Revise evidence and EvidenceList schema ? Let
* Evidence extraction system prompt
* Prompt builder function (using extracted data (pydantic), ...) Let's discuss
* Run extractions
* Compare results : Df with columns article title, doi, field, value, match (bool), annotation_evidence, gpt_extraction_evidence

Let's discuss ... else ?


2. Update the plan 

3. Implement in src/llm_metadata/evidence.py as single module

* Move stuff from schemas/evidence.py to there

* Schemas
* Evidence extraction (Returns pydantic object)

3. Implement in src modules, prompt_eval modif as --evidence-mode, eval_viewer_app as new tab.


Out of scope : Additionnal extraction for comparison between manual annotation and automated extraction