# Section parsing without Docker (WU-C2)

Date: 2026-11-15. Branch: `feat/anthropic-extraction`.

## Short answer

Run GROBID 0.7.3 directly with Java 11. It builds and runs on this server without Docker. The existing `call_grobid` works unchanged. It found Methods and Results in 7 of 7 test PDFs, at about 3 seconds per PDF.

A PyMuPDF-only parser also finds the headings (7 of 7). It is a good fallback, but it needs more code of our own and its text is dirtier.

## Test set

7 open-access PDFs from the dev subset only (`data/manifests/dev_subset_data_paper.csv`). Saved in `data/pdfs/fuster/` (git-ignored).

Record ids: 9, 11, 38, 101, 104, 208, 225.

Not downloaded: 5, 19, 39, 123, 271, 343 (HTTP 403 for scripts); 30 (the link returned a web page, not a PDF). The Wiley links (12, 24, 27, 29, 31, 37, 56, 71, 89, 91) were not tried, since Wiley normally blocks scripts. Only 7 PDFs, so every percentage below is rough. Six are PLOS ONE or Frontiers papers with very standard headings, so these results are probably better than what we will see on all 30.

## Comparison

| | A. GROBID 0.7.3 via Java 11 | B1. PyMuPDF font-size headings (own code) | B2. pymupdf4llm headings |
|---|---|---|---|
| Installs and runs | Yes | Yes (already a dependency) | Yes (extra package) |
| Methods found | 7/7 | 7/7 | 7/7 |
| Results found | 7/7 | 7/7 | 7/7 |
| Text per section | Yes, from TEI, with `Section` model unchanged | Only after our own slicing code (prototype done) | Markdown, needs slicing |
| Speed per PDF | 2.7 to 3.8 s (first call 36 s, warm-up) | 0.1 to 0.7 s | 5 to 8 s |
| Works with `call_grobid` unchanged | Yes | No, needs a new parser module | No |
| Setup effort | About 4 min of build, no root | None | `uv add pymupdf4llm` |
| Disk | 1.3 GB in `scratch/` + 0.6 GB in `~/.gradle` | 0 | Small, but pulls onnx and other libraries |
| Maintenance | Medium: Java plus Gradle, a service to start | Low to medium: a heuristic we own | Low, but a black box |

## Evidence per PDF

GROBID (option A). Subsections count as sections. "M" and "R" mean the project's `extract_from_section` returned METHODS or RESULTS for some heading.

| gt_record_id | DOI suffix | Seconds | Top-level sections | M | R | Body chars |
|---|---|---|---|---|---|---|
| 104 | s41598-018-34822-9 | 35.8 (warm-up) | 12 | yes | yes | 34,200 |
| 11 | pone.0073695 | 3.1 | 19 | yes | yes | 38,012 |
| 101 | pone.0077514 | 3.2 | 15 | yes | yes | 28,352 |
| 225 | pone.0109261 | 2.8 | 15 | yes | yes | 37,112 |
| 9 | pone.0128238 | 2.7 | 9 | yes | yes | 40,152 |
| 38 | pone.0204445 | 2.9 | 10 | yes | yes | 39,836 |
| 208 | fmars.2021.637546 | 3.8 | 20 | yes | yes | 44,744 |

PyMuPDF (option B1) found the headings too. A prototype that slices the text between canonical headings gave 12,000 to 23,000 characters for Methods and 5,000 to 18,000 for Results, in 0.2 to 0.7 s per PDF.

## Text quality problems seen

GROBID:
- Subsections often come out as separate top-level sections (the parser reads a flat list). Example: "Study Area", "Statistical Analyses" appear next to "Methods". The project's normalizer maps only some of them to METHODS (for example "Study Area" yes, "Small mammal sampling" no). A rule such as "everything between Methods and Results is Methods" is needed to use them.
- The Nature paper (104) has no "Introduction" heading. GROBID gives it an "Untitled" first section.
- A subsection called "Model" under Results was classified as METHODS by the normalizer (a normalizer false positive, not a GROBID error).
- The Supporting Information list produced three empty "(DOCX)" sections in paper 11.
- Body text is clean: references, page headers and footers are removed and kept apart (57 to 116 references per paper).

PyMuPDF:
- Raw text keeps running headers and footers (for example "PLOS ONE | www.plosone.org"), 20 to 75 hits per paper. They land inside section text.
- The font heuristic also picks up noise as headings: title lines, author names, "OPEN", "RESEARCH ARTICLE", "OPEN ACCESS".
- It does not nest subsections, and two-column order was fine on these 7 PDFs only.
- Section text is about 40 percent longer than GROBID's body, because it includes headers, captions and tables.

## Version note

GROBID 0.8.x asks for JDK 17 or newer. GROBID 0.7.3 builds and runs on the installed JDK 11, so no extra JDK download was needed. 0.7.3 is the CRF model (no deep learning), which is enough for headings and body text.

## Recommendation

Use option A (GROBID 0.7.3 on Java 11) if section-based input is to be tested. It reproduces the Docker setup the code was written for, with no code change. Keep PyMuPDF as the backup. Run option A on all 30 dev PDFs before deciding that section input goes into the final runs, since only 7 were available here.

Why not B: it works, but we would own and tune a heading heuristic, and the text still has headers and footers in it.

Cost to the team: a 1.9 GB folder and a Java process to start before parsing. No root and no Docker.

## Steps to reproduce option A

Run from the repo root. Paths below assume `scratch/` (git-ignored).

```bash
mkdir -p scratch/grobid && cd scratch/grobid
curl -sL -o g073.zip https://github.com/kermitt2/grobid/archive/refs/tags/0.7.3.zip   # 390 MB, about 1 min
unzip -q g073.zip && cd grobid-0.7.3
export JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64
./gradlew clean install -x test        # about 3 min, downloads Gradle and dependencies
nohup ./gradlew run > ../run.log 2>&1 &   # service ready in under 60 s
curl localhost:8070/api/isalive           # prints: true
```

Then, from the repo root:

```bash
uv run python scratch/evalA.py   # call_grobid + parse_tei_to_document + extract_from_section on every PDF
```

Stop the server: `pkill -f GrobidServiceApplication`. Restart: repeat the `nohup ./gradlew run` line from `scratch/grobid/grobid-0.7.3`.

Test scripts: `scratch/evalA.py` (GROBID), `scratch/evalB.py` and `scratch/evalB2.py` (PyMuPDF), `scratch/dl.py` (downloads).

## Not verified

- Behaviour on Wiley, Oxford and Royal Society PDFs (blocked here).
- The Docker image of GROBID 0.8.x, which could give slightly different output than 0.7.3.
- A small local server that imitates the GROBID endpoint on top of PyMuPDF was not built. It would only add code to maintain; the PyMuPDF path would rather get its own parser module returning `ParsedDocument`.
- Concurrent load (one PDF at a time was used).
- The first `parse_tei_to_document` default `parser_version` says "grobid-0.8.0"; the scripts passed "grobid-0.7.3" explicitly.
