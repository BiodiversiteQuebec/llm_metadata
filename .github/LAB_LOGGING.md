# Lab Logging & Experiment Documentation

## Overview
This document defines the standard process for documenting experimental work in the `llm_metadata` project. Consistent lab logging enables reproducibility, tracks progress, and builds institutional knowledge.

## Lab Book Location
**Central log:** `notebooks/README.md`

This file serves as the project's lab book, maintaining a chronological record of all experimental work, evaluations, and significant analyses.

## Lab Entry Format

Each experiment should be logged with the following structure:

```markdown
### YYYY-MM-DD: Brief Title of Work
**Task:** One-sentence description of the objective.

**Work Performed:**
- **Notebook:** `notebooks/notebook_name.ipynb`
- Bullet points describing key steps taken
- Methods, tools, or frameworks used
- Data sources and filtering criteria
- Validation or preprocessing steps

**Results:**
- Quantitative metrics in table format when applicable
- Key findings summarized clearly
- Performance breakdown by component/field

**Key Issues Identified:** (if applicable)
- Numbered list of problems discovered
- Root causes when known

**Next Steps:** (if applicable)
- Actionable items for follow-up work
- Prioritized recommendations

**Report:**
📊 [View HTML Report](results/notebook_name_YYYYMMDD_NN/index.html)
```

### Example Entry Structure
See `notebooks/README.md` entries for 2026-01-06 and 2026-01-07 as reference implementations.

## Archiving Results with HTML Export

### When to Create HTML Archives
Create HTML snapshots for:
- Completed experiments with final results
- Milestone evaluations requiring permanent record
- Work that will be referenced in future analyses
- Notebooks with visualizations or complex outputs

### HTML Export Process

**Step 1: Create timestamped results folder**
```bash
cd notebooks/results
mkdir notebook_name_YYYYMMDD_NN
```

**Naming Convention:**
- `notebook_name` — Descriptive notebook identifier (no `.ipynb`)
- `YYYYMMDD` — ISO date (e.g., `20260107`)
- `NN` — Two-digit run index (01, 02, 03...)

**Step 2: Convert notebook to HTML**
```bash
cd notebooks
jupyter nbconvert --to html \
    --output-dir="results/notebook_name_YYYYMMDD_NN" \
    --output="index.html" \
    notebook_name.ipynb
```

**Step 3: Link in lab book**
Add the report link in the corresponding lab entry:
```markdown
**Report:**
📊 [View HTML Report](results/notebook_name_YYYYMMDD_NN/index.html)
```

### Run Index Guidelines
- `_01` — First run of the day
- `_02` — Second run (e.g., after parameter changes)
- `_03+` — Subsequent iterations

Check existing folders to determine next index:
```bash
ls notebooks/results/ | grep "notebook_name_YYYYMMDD"
```

## Result Folder Structure

```
notebooks/
├── README.md                          # Lab book
├── results/                           # Archived HTML reports
│   ├── notebook_a_20260107_01/
│   │   └── index.html
│   ├── notebook_a_20260107_02/
│   │   └── index.html
│   └── notebook_b_20260108_01/
│       └── index.html
└── [working notebooks].ipynb
```

## Best Practices

### Before Starting Work
1. Review recent entries in `notebooks/README.md` for context
2. Check if related experiments exist in `results/` folder
3. Understand the current state from previous "Next Steps"

### During Experimental Work
1. Keep notebook cells well-documented with markdown explanations
2. Structure work in logical sections (load data, validate, process, evaluate, conclude)
3. Include intermediate outputs for transparency
4. Add synthesis and analysis sections at the end

### After Completing Work
1. Write a results synthesis in the notebook (markdown cell)
2. Export to HTML with proper naming convention
3. Log entry in `notebooks/README.md` following standard format
4. Commit both notebook and HTML to version control

### Logging Metrics
- Use markdown tables for quantitative results
- Include precision/recall/F1 when evaluating ML tasks
- Specify model versions, parameters, and dataset sizes
- Report both micro and macro averages when applicable

### Issue Documentation
When logging issues:
- Be specific about what failed or underperformed
- Include hypotheses about root causes
- Link to error evidence when available
- Prioritize by impact on project goals

### Next Steps Section
- Make recommendations concrete and actionable
- Organize by timeline (immediate, short-term, long-term)
- Link to relevant code or documentation
- Assign clear success criteria when possible

## Version Control

### What to Commit
- ✅ Executed notebooks with outputs (`.ipynb`)
- ✅ HTML reports in `results/` folders
- ✅ Updated `notebooks/README.md`
- ❌ Temporary or exploratory notebooks without documentation

### Commit Message Format
```
docs: Add lab entry for [experiment name] (YYYY-MM-DD)

- Brief description of work
- Key results or findings
- Reference to HTML report
```

## Integration with Agentic Workflows

### For AI Agents Reading This
When asked to document experimental work:
1. **Always** check `notebooks/README.md` first to understand the current state
2. Follow the entry format strictly for consistency
3. Use the HTML export process to preserve results
4. Increment the run index appropriately (`_01`, `_02`, etc.)
5. Link the HTML report in the lab entry

### For AI Agents Creating Experiments
1. Structure notebooks with clear markdown sections
2. End with "Results Synthesis & Analysis" and "Next Steps" sections
3. After execution, follow this logging protocol automatically
4. Suggest HTML export when results are significant

## Template for Quick Reference

```markdown
### YYYY-MM-DD: [Title]
**Task:** [One sentence objective]

**Work Performed:**
- **Notebook:** `notebooks/[name].ipynb`
- [Key step 1]
- [Key step 2]

**Results:**
| Metric | Value |
|--------|-------|
| [metric] | [value] |

**Key Issues Identified:**
1. [Issue with context]

**Next Steps:**
- [Action item 1]
- [Action item 2]

**Report:**
📊 [View HTML Report](results/[name]_YYYYMMDD_NN/index.html)
```

---

**Last Updated:** 2026-01-07
**Maintained by:** Project AI agents and human collaborators
