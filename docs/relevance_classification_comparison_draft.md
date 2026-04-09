# Relevance Classification Comparison Draft

This note is a manuscript-ready draft subsection comparing our automated relevance classification experiments to the original automated classification approach in Fuster-Calvo et al. (2025). It is written to be reusable in a Methods, Results, or Discussion section with light editing.

## Draft Subsection

### Comparison with the original automated relevance classifier

Fuster-Calvo et al. (2025) evaluated the feasibility of automating dataset relevance assessment using a supervised text-classification pipeline based on TF-IDF features extracted from dataset titles and repository descriptions, or from titles and abstracts in the Semantic Scholar subset. After lowercasing and removing special characters, they compared several standard preprocessing variants, including stop-word removal, lemmatization, and unigram versus unigram-plus-bigram representations. The resulting document vectors were used to train Logistic Regression, Random Forest, and linear Support Vector Machine classifiers with balanced class weights. Because of the limited corpus size, they simplified the target into a binary distinction, collapsing high and moderate relevance into a single relevant class and low and non-relevant into a single not relevant class. Performance was evaluated with five-fold cross-validation over the annotated corpus.

Our experiments depart from that setup in two important ways. First, rather than learning relevance directly from a bag-of-words representation, we tested whether large language models could recover the semantic features that underpin the manual framework introduced by Fuster-Calvo et al. Second, we preserved the original four-level relevance structure as the primary target, using the mechanistic label `MC_relevance_modifiers` as the reference output of the published scoring system and treating binary relevance only as a secondary collapsed view. This produced two complementary pipelines. In the mechanistic approach, the model first extracts structured ecological features such as data type, temporal extent, spatial extent, and modulators, after which deterministic rules reproduce the Fuster scoring logic. In the direct-LLM approach, the model predicts both the structured features and the final relevance category in a single structured-output call.

This distinction is important conceptually. The supervised TF-IDF classifier in the original paper is best interpreted as a document triage model that learns lexical correlates of relevance from the annotated corpus. By contrast, our mechanistic pipeline is an explicit operationalization of the paper's own classification framework. It asks whether the relevance system itself can be reproduced from text-extracted metadata. The direct-LLM pipeline goes one step further and asks whether a semantic model can infer the same relevance construct more robustly than a feature-extraction-plus-rules workflow when the underlying evidence is sparse or only weakly expressed.

### Comparative results

In the original paper, the best-performing binary classifier for the Main Classifier target was Logistic Regression with stop-word removal and unigrams, which achieved a relevant-class precision of 0.57, recall of 0.44, and F-score of 0.50, with a weighted F-score of 0.68. For the Main Classifier plus Modulators target, the best model was a Random Forest over lemmatized text with unigrams and bigrams, which achieved a relevant-class precision of 0.62, recall of 0.71, and F-score of 0.67, with a weighted F-score of 0.61. The paper emphasized that these results were only moderate, and that the classifier especially struggled to recover relevant datasets consistently.

Our results should not be read as a direct benchmark replacement because the evaluation protocol differs. We worked on a 30-record development subset, not the full annotated corpus, and we preserved the four-class relevance structure before collapsing it to binary relevance for orientation. Within that setting, the mechanistic ceiling test performed on ground-truth features (`R1-A`) reproduced the annotated Fuster relevance system exactly on the development subset, with perfect agreement on all audited intermediate `MC_*` columns and a binary F1 of 1.00 after collapse. This result indicates that the relevance framework itself is internally coherent and can be implemented faithfully when the required features are already available.

The end-to-end mechanistic pipeline using LLM-extracted features (`R1-B`) performed much worse. Against `MC_relevance_modifiers`, it reached a macro F1 of 0.125 and a binary relevant-class F1 of 0.00. This sharp degradation shows that the main weakness is not the rule system but the difficulty of recovering sufficiently accurate data type, temporal, spatial, and modulator features from short repository descriptions and abstracts. In practice, errors or omissions in the extracted features propagate directly into the final rule-based relevance decision.

The direct-LLM approach (`R2`) substantially improved over the mechanistic LLM-plus-rules pipeline. On the same development subset, and evaluated against the mechanistic reference target, it achieved a relevant-class precision of 0.773, recall of 0.773, and F1 of 0.773 after binary collapse. On the four-class task, it reached a macro F1 of 0.498 over the labels present in the split. Although these results are not directly comparable to the full-corpus cross-validation results reported by Fuster-Calvo et al., they suggest that end-to-end semantic inference can recover the intended relevance construct more effectively than a strict intermediate-feature pipeline under sparse textual evidence.

### Interpretation

Taken together, these experiments suggest that the main bottleneck identified by Fuster-Calvo et al. remains valid: critical metadata, especially temporal and spatial information, are often absent or dispersed across publication components rather than stated clearly in the abstract or repository description. Our results sharpen that conclusion by separating three distinct issues.

First, the manual relevance framework itself is not the limiting factor. The exact reconstruction obtained in `R1-A` shows that once the relevant features are available, the Fuster system can be reproduced deterministically and transparently.

Second, explicit feature extraction from short text is currently the most fragile step. The failure of `R1-B` shows that a deterministic relevance scorer cannot compensate for missing or weakly extracted metadata. In that sense, our mechanistic notebook empirically validates the paper's discussion claim that spatiotemporal sparsity imposes a hard ceiling on automated approaches built from short textual descriptions alone.

Third, direct semantic inference appears to recover part of that lost information. The improvement of `R2` over `R1-B` suggests that a large language model can use weak contextual cues that do not survive cleanly as structured intermediate features. This does not mean that direct LLM classification solves the problem entirely. Rather, it suggests that semantic models may better approximate the intended relevance judgment than a pipeline that depends on perfect feature emission at every step.

### Relationship to the paper's discussion

One of the most interesting aspects of this comparison is that the original paper explicitly anticipated this direction. In the Discussion, Fuster-Calvo et al. note that an alternative to supervised bag-of-words classification would be to directly extract key features from text, such as data type and temporal extent, and then combine them afterward in the same manual framework. Our mechanistic pipeline is precisely that experiment. They also suggest that large language models could improve semantic sensitivity relative to bag-of-words methods, while still being constrained by the absence of spatiotemporal metadata. Our direct-LLM results are consistent with that expectation: semantic modeling helps, but it does not eliminate the structural limitation imposed by missing metadata.

For this reason, the safest interpretation is not that LLMs definitively outperform the original automated classifier. Instead, the comparison suggests that the relevance framework proposed by Fuster-Calvo et al. remains a strong conceptual backbone, but that the evidence-recovery layer deserves more attention than the final scoring rule itself. From that perspective, the most promising next steps are likely to involve richer textual inputs, section-aware or full-text retrieval, stronger grounding of temporal and spatial evidence, and explicit evidence tracking rather than relying exclusively on short abstract-level descriptions.

### Recommended manuscript framing

If this comparison is integrated into the paper, a strong framing is:

1. establish that the original mechanistic framework is reproducible from curated features;
2. show that feature extraction, not rule design, is the dominant failure point under sparse metadata;
3. position direct LLM classification as a semantic shortcut that partially bypasses the fragile intermediate extraction layer;
4. state clearly that differences in corpus size, target definition, and evaluation protocol prevent a strict benchmark-style claim against the original paper's supervised baseline.

A concise concluding sentence that can be reused almost verbatim is:

> These results suggest that the main challenge is not the definition of dataset relevance itself, but the reliable recovery of the metadata required to instantiate that definition from short and often incomplete textual descriptions.

## Source Notes

- Primary comparison source: `docs/fuster_et_al_2024/peerj-18853.pdf`
- Relevant paper sections used:
  - Dataset relevance assignment
  - Automatic relevance classification
  - Table 3 results
  - Discussion paragraphs on sparse metadata, direct feature extraction, and future LLM-based approaches
