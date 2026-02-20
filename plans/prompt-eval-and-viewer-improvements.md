## Phases

1. Fix bugs / changes in prompt eval module

* [ ] --skip-cache don't seem to work

* [ ] Default timestamp neither.

* [ ] Prompt eval results in /data subfolder

* [ ] Add "schema" to the output of prompt eval module in json format. (What is sent to the model, with field descriptions and types). This is the "schema" that the prompt is working with.

2. Fix dev subset and its usage

  * Do all of the records have available abstracts and oa pdfs ?

  * Is the right column in the dev subset csv used to filter the records in the prompt eval module ?

  * Tests accordingly.

3. Small edits in prompt eval viewer

  * Add collapsible text box for schema between GT and prompt in overview.

  * Detailed metrics : Move "Select field for mismatches" dropdown in mismatch section.

  * Dataset results : Display the authors, date published and doi from dryad/zenodo/SS in a similar way than on DRYAD. Add source column to results table and use that to show author/source info. Does that introduce anti-patterns or is limited by current pattern in current implementation of prompt eval module and dependencies ?

  ![Capture of what needs to be shown](image.png). Make sure that relevant info are passed in the output by prompt eval module and are available in the viewer.

  * Dataset results : Rename 'Dataset' link diplayed text to "Source" (Dryad, Zenodo, Semantic Scholar)

  * Remove json extension from lines in json selection dropdown in viewer.


4. Implement --batch-mode for batch evaluation (abstracts, full-text, section-based) using prefect workflow

  * Should respect cache and skip-cache flags, but run end-to-end on all records in batch (not per-record)
  * Does the prefect / direct module usage introduce anti-patterns or is limited by current pattern in implementation of 

5. Implement --evidence-mode for evidence extraction evaluation (new eval mode that runs separate prompt to extract evidence using features (from gt or preds)
  * Clarify evidence extraction flow and module design and usage and refactor as needed
  * Add evidence mode to prompt_eval.py
  * Add evidence to viewer as new tab
