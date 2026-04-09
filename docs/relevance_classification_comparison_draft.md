# Relevance Classification Comparison Draft

This note is a manuscript-ready draft subsection comparing our automated relevance classification experiments to the original automated classification approach in Fuster-Calvo et al. (2025). It is written to be reusable in a Methods, Results, or Discussion section with light editing.

## Draft Subsection

### Comparison with the original automated relevance classifier

Fuster-Calvo et al. (2025) evaluated the feasibility of automating dataset relevance assessment using a supervised text-classification pipeline based on TF-IDF features extracted from dataset titles and repository descriptions, or from titles and abstracts in the Semantic Scholar subset. After lowercasing and removing special characters, they compared several standard preprocessing variants, including stop-word removal, lemmatization, and unigram versus unigram-plus-bigram representations. The resulting document vectors were used to train Logistic Regression, Random Forest, and linear Support Vector Machine classifiers with balanced class weights. Because of the limited corpus size, they simplified the target into a binary distinction, collapsing high and moderate relevance into a single relevant class and low and non-relevant into a single not relevant class. Performance was evaluated with five-fold cross-validation over the annotated corpus.

Our experiments depart from that setup in two important ways. First, rather than learning relevance directly from a bag-of-words representation, we tested whether large language models could recover the semantic features that underpin the manual framework introduced by Fuster-Calvo et al. Second, we preserved the original four-level relevance structure as the primary target, using the mechanistic label `MC_relevance_modifiers` as the reference output of the published scoring system and treating binary relevance only as a secondary collapsed view. This produced a split LLM-centered comparison. Step `R0` validates the deterministic scoring rules themselves by reconstructing the published mechanistic labels from curated features. Step `R1` applies those same validated rules to LLM-extracted features, with `R1-A` using abstract or repository-description text and `R1-B` using PDF-native full text. Step `R2` is now divided into `R2-A`, a direct structured-output LLM classifier over abstract or repository-description text, and `R2-B`, the same direct relevance classifier applied to PDF files.

This distinction is important conceptually. The supervised TF-IDF classifier in the original paper is best interpreted as a document triage model that learns lexical correlates of relevance from the annotated corpus. By contrast, our mechanistic pipeline is an explicit operationalization of the paper's own classification framework. It asks whether the relevance system itself can be reproduced from text-extracted metadata. The direct-LLM pipeline goes one step further and asks whether a semantic model (e.g., GPT-5) can infer the same relevance construct more robustly than a feature-extraction-plus-rules workflow, and whether that answer changes materially when the model sees richer PDF-native evidence instead of short repository text alone.

### Comparative results

In the original paper, the best-performing binary classifier for the Main Classifier target was Logistic Regression with stop-word removal and unigrams, which achieved a relevant-class precision of 0.57, recall of 0.44, and F-score of 0.50, with a weighted F-score of 0.68. For the Main Classifier plus Modulators target, the best model was a Random Forest over lemmatized text with unigrams and bigrams, which achieved a relevant-class precision of 0.62, recall of 0.71, and F-score of 0.67, with a weighted F-score of 0.61. The paper emphasized that these results were only moderate, and that the classifier especially struggled to recover relevant datasets consistently.


| Automated classification method | Method family | Relevant-class Precision | Relevant-class Recall | Relevant-class F1 | Four-class macro F1 | Evaluation setting |
|---|---|---|---|---|---|---|
| Supervised bag-of-words classifier (Fuster-Calvo et al. 2025 baseline) | TF-IDF text classification with classical ML | 0.62 | 0.71 | 0.67 | not reported | Full annotated corpus, 5-fold cross-validation, binary relevance only |
| Mechanistic relevance scoring from abstract/repository-description features | LLM feature extraction from abstract or repository description, then deterministic Fuster scoring rules | 1.000 | 0.364 | 0.533 | 0.317 | 30-record dev subset, `MC_relevance_modifiers` target |
| Mechanistic relevance scoring from PDF-derived features | LLM feature extraction from PDF-native full text, then deterministic Fuster scoring rules | 0.750 | 0.682 | 0.714 | 0.486 | 30-record dev subset, `MC_relevance_modifiers` target, reusing `20260331_120734_prompt_engineering_pdf_native.json` |
| Direct LLM relevance classification from abstract/repository-description text | Single structured-output LLM call for features plus final relevance from short text | 1.000 | 0.318 | 0.483 | 0.381 | 30-record dev subset, fresh 2026-04-09 API run, `MC_relevance_modifiers` target |
| Direct LLM relevance classification from PDF files | Single structured-output LLM call for features plus final relevance from PDF-native full text | 0.778 | 0.955 | 0.857 | 0.501 | 30-record dev subset, fresh 2026-04-09 API run, `MC_relevance_modifiers` target |

Our results should not be read as a direct benchmark replacement because the evaluation protocol differs. We worked on a 30-record development subset, not the full annotated corpus, and we preserved the four-class relevance structure before collapsing it to binary relevance for orientation. Within that setting, the rule-validation step performed on ground-truth features (`R0`) reproduced the annotated Fuster relevance system exactly on the development subset, with perfect agreement on all audited intermediate `MC_*` columns and a binary F1 of 1.00 after collapse. This result indicates that the relevance framework itself is internally coherent and can be implemented faithfully when the required features are already available.

The abstract/repository-description step-1 pipeline (`R1-A`) still underperformed both the ground-truth-feature rule-validation step and the direct-LLM approach. On the latest live notebook run under the current prompt state, and after correcting the scorer so predicted `data_type` is actually passed into the mechanistic rules, it reached a macro F1 of 0.317 and a binary relevant-class F1 of 0.533 against `MC_relevance_modifiers`. This remaining gap still shows that the main weakness is not the rule system but the difficulty of recovering sufficiently accurate data type, temporal, spatial, and modulator features from short repository descriptions and abstracts. In practice, errors or omissions in the extracted features still propagate directly into the final rule-based relevance decision.

The PDF-derived step-1 pipeline (`R1-B`) improved substantially when the same scoring framework was applied to PDF-native feature extraction instead of abstract or repository-description features. Using the saved March 31 PDF-native run artifact, it reached a macro F1 of 0.486 and a binary relevant-class F1 of 0.714, with precision 0.750 and recall 0.682. This places it slightly above the paper's supervised bag-of-words baseline on the binary F1 view and shows that richer evidence helps the feature-plus-rules approach considerably.

The direct-LLM results turned out to be strongly evidence-dependent. The short-text direct classifier (`R2-A`) reached a macro F1 of 0.381 and a binary relevant-class F1 of 0.483, with perfect precision but only 0.318 recall. In practice, it over-predicted low relevance and remained constrained by the same sparse-evidence problem that limits the abstract-based mechanistic path. The PDF-file direct classifier (`R2-B`) was much stronger: it achieved a macro F1 of 0.501 and a binary relevant-class F1 of 0.857, with precision 0.778 and recall 0.955. Although these results are not directly comparable to the full-corpus cross-validation results reported by Fuster-Calvo et al., they suggest that end-to-end semantic inference becomes notably more effective once the model can use full-text PDF evidence.

### Interpretation

Taken together, these experiments suggest that the main bottleneck identified by Fuster-Calvo et al. remains valid: critical metadata, especially temporal and spatial information, are often absent or dispersed across publication components rather than stated clearly in the abstract or repository description. Our results sharpen that conclusion by separating three distinct issues.

First, the manual relevance framework itself is not the limiting factor. The exact reconstruction obtained in `R0` shows that once the relevant features are available, the Fuster system can be reproduced deterministically and transparently.

Second, explicit feature extraction from short text is currently the most fragile step. The weaker abstract-based mechanistic pipeline shows that a deterministic relevance scorer cannot compensate for missing or weakly extracted metadata when the available evidence is sparse. In that sense, our mechanistic notebooks empirically validate the paper's discussion claim that spatiotemporal sparsity imposes a hard ceiling on automated approaches built from short textual descriptions alone.

Third, richer textual evidence materially improves the mechanistic approach. `R1-B` performs much better than `R1-A`, which suggests that the rule system itself is not the principal problem; rather, the decisive factor is whether the extraction stage can access enough temporal, spatial, and modulator evidence.

Fourth, direct semantic inference on short text is not a universal shortcut. `R2-A` modestly improved four-class balance over `R1-A`, but it did not improve binary screening performance and remained recall-limited. That result suggests that direct prompting alone cannot compensate for thin repository descriptions.

Fifth, direct semantic inference becomes much more compelling with full-text evidence. `R2-B` outperformed both `R1-B` and the paper's supervised baseline on the binary task, while also producing the strongest non-ceiling four-class macro F1 in this notebook family. This does not mean that direct LLM classification solves the problem entirely. Rather, it suggests that semantic models are most useful when paired with richer evidence rather than expected to infer relevance from sparse metadata alone.

### Relationship to the paper's discussion

One of the most interesting aspects of this comparison is that the original paper explicitly anticipated this direction. In the Discussion, Fuster-Calvo et al. note that an alternative to supervised bag-of-words classification would be to directly extract key features from text, such as data type and temporal extent, and then combine them afterward in the same manual framework. Our mechanistic pipeline is precisely that experiment. They also suggest that large language models could improve semantic sensitivity relative to bag-of-words methods, while still being constrained by the absence of spatiotemporal metadata. Our split direct-LLM results are consistent with that expectation: semantic modeling helps most when it sees full-text evidence, but it remains structurally limited when only sparse abstract or repository-description text is available.

For this reason, the safest interpretation is not that LLMs definitively outperform the original automated classifier. Instead, the comparison suggests that the relevance framework proposed by Fuster-Calvo et al. remains a strong conceptual backbone, but that the evidence-recovery layer deserves more attention than the final scoring rule itself. From that perspective, the most promising next steps are likely to involve richer textual inputs, section-aware or full-text retrieval, stronger grounding of temporal and spatial evidence, and explicit evidence tracking rather than relying exclusively on short abstract-level descriptions.

### Recommended manuscript framing

If this comparison is integrated into the paper, a strong framing is:

1. establish that the original mechanistic framework is reproducible from curated features;
2. show that feature extraction, not rule design, is the dominant failure point under sparse metadata;
3. position direct LLM classification as an evidence-sensitive semantic shortcut, weak on short text (`R2-A`) but strong on PDF files (`R2-B`);
4. state clearly that differences in corpus size, target definition, and evaluation protocol prevent a strict benchmark-style claim against the original paper's supervised baseline.

A concise concluding sentence that can be reused almost verbatim is:

> These results suggest that the main challenge is not the definition of dataset relevance itself, but the reliable recovery of the metadata required to instantiate that definition, and that direct LLM relevance classification is most effective when richer full-text evidence is available.

## Source Notes

- Primary comparison source: `docs/fuster_et_al_2024/peerj-18853.pdf`
- Relevant paper sections used:
  - Dataset relevance assignment
  - Automatic relevance classification
  - Table 3 results
  - Discussion paragraphs on sparse metadata, direct feature extraction, and future LLM-based approaches
