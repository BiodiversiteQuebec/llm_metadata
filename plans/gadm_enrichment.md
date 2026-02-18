# GADM Geographic Enrichment — Enrichment-Based Evaluation

## Context

The `spatial_range_km2` field records study area size in km², and `geospatial_info_dataset` classifies _how_ spatial data is represented (sample points, administrative units, etc.), but neither field captures _where_ a study took place. Geographic coverage is a core dimension of biodiversity data gap analysis — knowing whether a dataset covers Quebec vs. Ontario vs. the full boreal region is essential for the Biodiversité Québec mandate.

**Gap:** The current schema has no text field for study location names (e.g., "Quebec, Canada", "North America", "Laurentian Highlands").

**Approach:** Following the enrichment pattern established by GBIF species matching:

1. Add `location_text: Optional[list[str]]` to `DatasetFeatures` — raw location strings extracted as-is by the LLM (mirrors `species` field design).
2. Add `gadm_codes: Optional[list[str]]` — GADM GID codes derived from `location_text` via geocoding. Populated by preprocessing, not extracted by LLM.
3. Create `gadm.py` — geocoding wrapper using the Nominatim (OpenStreetMap) API, which is free, key-free, and returns admin-level hierarchy data matching GADM's structure.

GADM GID format: `"CAN"` (country), `"CAN.10_1"` (province/state), `"CAN.10.3_1"` (county/district).

The existing evaluation framework handles both fields independently:
- `location_text` → string-based comparison (exact/fuzzy)
- `gadm_codes` → set comparison on GID codes (trivial, no new matching logic)

Strategy comparison: `report.metrics_for("location_text")` vs `report.metrics_for("gadm_codes")`.

**Outcome:** Geographic extraction and GADM-resolved evaluation as parallel fields, zero changes to the evaluation framework internals.

---

## Geocoding Backend: Nominatim + GADM Mapping

GADM does not provide a REST API for text-to-GID resolution. The practical approach:

1. **Nominatim (OSM)**: `GET https://nominatim.openstreetmap.org/search?q={location}&addressdetails=1&format=json`
   - Returns structured address with country, state, county hierarchy
   - Free, no API key, 1 req/sec polite limit
2. **GID construction**: Map Nominatim `country_code` + `state` hierarchy to GADM GID format using a local reference table (country ISO → GADM GID, province/state names → GADM level-1 GIDs)
3. **Fallback**: ISO 3166-1 alpha-3 country codes only when province/state resolution fails

The reference table (`data/gadm_reference.json`) is a small static lookup: ISO country → GADM GID, major admin-1 names → GADM GID. Bootstrapped from GADM's own CSV download (no Geopandas/spatial join required).

---

## Work Units

### WU-1: Schema field — `location_text`
`model: sonnet` | deps: none

Add `location_text` extraction field to `DatasetFeatures` and update the LLM system prompts to extract it.

**Schema change in `schemas/fuster_features.py`:**
```python
# Alongside species field in the Taxonomic/Geospatial section
location_text: Optional[list[str]] = Field(
    None,
    description=(
        "Study location names extracted as-is from the text. List of geographic areas, "
        "regions, administrative units, or place names where data was collected "
        "(e.g. ['Quebec, Canada', 'Laurentian Highlands', 'North America']). "
        "Do not interpret or standardize — copy text verbatim."
    )
)
```

**`DatasetFeaturesNormalized` validator** (mirrors `parse_species_list`):
```python
@field_validator('location_text', mode='before')
@classmethod
def parse_location_list(cls, v: Any) -> Optional[list[str]]:
    """Split comma/semicolon-separated location strings into list."""
    # Same pattern as parse_species_list — split by ;,, strip, deduplicate
```

**System prompt updates in `gpt_classify.py`** — all three (SYSTEM_MESSAGE, SECTION_SYSTEM_MESSAGE, PDF_SYSTEM_MESSAGE):
- Add `location_text` bullet describing it as verbatim location names (country, province, region, site name)
- Place after `geospatial_info_dataset` field description
- Emphasize: copy-paste from text, do not standardize to ISO codes

**`schemas/__init__.py`** — no new exports needed (field is on existing models)

**Files:**
- `schemas/fuster_features.py`
- `gpt_classify.py`

**Tests:** `tests/test_schema_location_text.py`
- String input → list split (comma, semicolon)
- NaN/None → None
- Already-a-list passthrough
- Whitespace stripping, empty string removal

---

### WU-2: `location_parsing.py` — shared preprocessing module
`model: sonnet` | deps: WU-1

Structured parsing of raw location strings before geocoding, analogous to `species_parsing.py`.

**New file:** `src/llm_metadata/location_parsing.py`

**`ParsedLocation` Pydantic model:**
```python
@dataclass
class ParsedLocation:
    original: str          # raw input
    query: str             # cleaned query for geocoding API
    country_hint: str | None    # ISO 3166-1 alpha-2 if detectable ("CA", "US")
    is_global: bool        # True for "global", "worldwide", "international"
    is_marine: bool        # True for ocean/sea names (skip GADM — terrestrial only)
```

**Preprocessing pipeline (`parse_location_string(raw: str) -> ParsedLocation`):**
1. Strip leading/trailing whitespace and punctuation
2. Detect global/worldwide terms → `is_global=True`, skip geocoding
3. Detect marine/ocean names (Atlantic, Pacific, "ocean", "sea", "bay", "gulf") → `is_marine=True`
4. Detect country hints from common patterns: "X, Canada" → `country_hint="CA"`; "Province of X" → strip prefix for cleaner query
5. Normalize common abbreviations: "Que." → "Quebec", "Ont." → "Ontario", "BC" → "British Columbia"
6. Build `query` string (cleaned, geocoding-ready)

**Top-level function `parse_location_list(locations: list[str]) -> list[ParsedLocation]`**

**Files to modify:**
- `schemas/__init__.py` — export `ParsedLocation`

**Tests:** `tests/test_location_parsing.py`
- Scientific site names: `"Laurentian Highlands, Quebec"` → query preserved, country_hint="CA"
- Global terms: `"global"`, `"worldwide"` → is_global=True
- Marine terms: `"North Atlantic Ocean"` → is_marine=True
- Country extraction: `"Ontario, Canada"` → country_hint="CA"
- Abbreviation normalization: `"Que."` → query contains "Quebec"
- Province prefix stripping: `"Province of British Columbia"` → query="British Columbia"

---

### WU-3: `gadm.py` — GADM resolution wrapper
`model: sonnet` | deps: WU-2

**New file:** `src/llm_metadata/gadm.py`

Follow `semantic_scholar.py` / `gbif.py` patterns: module docstring, `requests`, `joblib.Memory` cache, logging, polite delay.

**Core types:**
```python
@dataclass
class GADMMatch:
    gid: str                 # GADM GID code (e.g. "CAN.10_1")
    name: str                # canonical English name
    level: int               # 0=country, 1=state/province, 2=county
    country_code: str        # ISO 3166-1 alpha-3 (e.g. "CAN")
    source: str              # "nominatim" | "reference_table" | "iso_only"
    confidence: str          # "high" | "medium" | "low"

@dataclass
class ResolvedLocation:
    original: str
    parsed: ParsedLocation
    gadm_match: GADMMatch | None
```

**Internal helpers:**

`_load_reference_table() -> dict` — Load `data/gadm_reference.json`. Structure:
```json
{
  "CA": {"gid": "CAN", "name": "Canada", "level1": {"Quebec": "CAN.10_1", "Ontario": "CAN.8_1", ...}},
  "US": {"gid": "USA", "name": "United States", "level1": {...}},
  ...
}
```
Bootstrapped from GADM CSV download. Covers the ~50 countries most likely to appear in biodiversity literature.

`_nominatim_geocode(query: str, country_hint: str | None) -> dict | None`
- `GET https://nominatim.openstreetmap.org/search?q={query}&addressdetails=1&format=json&limit=1`
- Add `countrycodes={country_hint}` param when country_hint is set
- Returns first result's address dict or None
- `@memory.cache`, 1.0s delay (Nominatim usage policy)
- Custom `User-Agent` header (Nominatim requirement): `"llm_metadata/1.0 biodiversite-quebec"`

`_address_to_gid(address: dict) -> GADMMatch | None`
- Extract `country_code`, `state` from Nominatim address
- Look up in reference table for level-1 GID
- Fall back to country-only GID if state not found
- Returns `None` if country_code not in reference table

**Main functions:**

`match_location(location: str) -> GADMMatch | None`
- Parse with `ParsedLocation`
- Skip if `is_global` or `is_marine` (return None)
- Geocode with `_nominatim_geocode`
- Convert to GID with `_address_to_gid`

`resolve_location_list(locations: list[str]) -> list[ResolvedLocation]`
- Map `match_location` over each location string
- Returns `ResolvedLocation` for each (with `gadm_match=None` for skipped/unresolved)

**Tests:** `tests/test_gadm.py`
- Mock `requests.get` for Nominatim responses
- Test GID construction from address dict (country-only, with province)
- Test global/marine skip logic
- Test country_hint filtering in geocode request
- Test caching behavior (second call with same input → no HTTP request)
- Test reference table fallback when Nominatim returns unknown state

---

### WU-4: Schema `gadm_codes` field + enrichment function
`model: sonnet` | deps: WU-3

**Schema change in `schemas/fuster_features.py`:**
```python
# Alongside source-tracking and future derived fields
gadm_codes: Optional[list[str]] = Field(
    None,
    description=(
        "GADM GID codes resolved from location_text field. "
        "Populated by preprocessing, not extracted by LLM. "
        "Format: 'CAN' (country), 'CAN.10_1' (province/state)."
    )
)
```

**Enrichment function in `gadm.py`:**
```python
def enrich_with_gadm(
    model: DatasetFeatures,
) -> DatasetFeatures:
    """Resolve location_text strings to GADM GID codes and return enriched copy."""
    if not model.location_text:
        return model.model_copy(update={"gadm_codes": None})
    resolved = resolve_location_list(model.location_text)
    codes = [r.gadm_match.gid for r in resolved if r.gadm_match]
    # Deduplicate: multiple city/region names may resolve to same country
    unique_codes = list(dict.fromkeys(codes))
    return model.model_copy(update={"gadm_codes": unique_codes or None})
```

**Notebook usage pattern:**
```python
# Preprocess both sides
true_enriched = {doi: enrich_with_gadm(m) for doi, m in true_by_id.items()}
pred_enriched = {doi: enrich_with_gadm(m) for doi, m in pred_by_id.items()}

# Single evaluation run — both fields evaluated independently
report = evaluate_indexed(
    true_by_id=true_enriched,
    pred_by_id=pred_enriched,
    fields=["location_text", "gadm_codes", ...],
    config=EvaluationConfig(),
)

# Compare strategies
report.metrics_for("location_text")   # fuzzy string matching P/R/F1
report.metrics_for("gadm_codes")      # set comparison on GID codes P/R/F1
```

**Files:**
- `schemas/fuster_features.py` — add `gadm_codes` field
- `gadm.py` — add `enrich_with_gadm()` function
- `schemas/__init__.py` — no new exports needed

**Tests:** `tests/test_gadm_enrichment.py`
- Enrich model with known locations → `gadm_codes` populated
- Enrich model with `location_text=None` → `gadm_codes` stays None
- Enrich model with only global/marine locations → `gadm_codes` is None
- Duplicate codes deduplicated (two Quebec cities → one "CAN.10_1")
- End-to-end: enrich both sides, run `evaluate_indexed`, verify `gadm_codes` metrics present

---

### WU-5: Bootstrap `data/gadm_reference.json`
`model: haiku` | deps: none (can run in parallel with WU-1)

Create the static GADM reference table covering countries most likely to appear in biodiversity literature.

**Script:** `scripts/build_gadm_reference.py`
- Download GADM level-1 data from `https://geodata.ucdavis.edu/gadm/gadm4.1/gadm_410-csv.zip`
- Extract country + admin-1 names and GID codes from CSV
- Filter to top ~80 countries by biodiversity literature frequency (use a hardcoded priority list or include all)
- Output: `data/gadm_reference.json` with structure described in WU-3
- Script is a one-time utility; output is committed to the repo

**Files:**
- `scripts/build_gadm_reference.py` (new, one-time utility)
- `data/gadm_reference.json` (committed reference table)

---

## Execution Rounds

```
Round 1:  WU-1 (location_text schema)     ← no deps, start immediately
          WU-5 (gadm_reference.json)       ← no deps, run in parallel
          model: sonnet / haiku

Round 2:  WU-2 (location_parsing.py)      ← deps: WU-1
          model: sonnet

Round 3:  WU-3 (gadm.py wrapper)          ← deps: WU-2, WU-5
          model: sonnet

Round 4:  WU-4 (gadm_codes + enrichment)  ← deps: WU-3
          model: sonnet
```

---

## Verification

1. `uv run python -m pytest tests/test_schema_location_text.py` — field parsing
2. `uv run python -m pytest tests/test_location_parsing.py` — location preprocessing
3. `uv run python -m pytest tests/test_gadm.py` — GADM wrapper with mocked Nominatim
4. `uv run python -m pytest tests/test_gadm_enrichment.py` — enrichment + eval integration
5. `uv run python -m pytest tests/` — full suite green
6. Notebook smoke test: extract `location_text` from a few real abstracts, enrich with GADM, compare `location_text` vs `gadm_codes` metrics

---

## Notes & Decisions

**Why Nominatim vs. other geocoders?**
- Free, no API key, permissive usage for research
- Returns structured admin hierarchy (country + state + county) matching GADM levels
- Nominatim usage policy: 1 req/sec, custom User-Agent required — enforced in wrapper

**Why a local reference table?**
- Nominatim returns OSM admin names which may differ from GADM names
- Reference table acts as the canonical OSM→GADM translation layer
- Also enables fast lookups for common country names without a network call
- The table is small enough to commit to the repo (~200KB JSON)

**Scope of `location_text`:**
- Extract verbatim from text — do not interpret
- Include: country names, province/state names, protected area names, watershed names, ecosystem region names
- The geocoder handles normalization; validators just split strings

**What `gadm_codes` does NOT capture:**
- Ocean/marine areas (GADM is terrestrial only) → `is_marine=True` → skip
- Global/worldwide studies → `is_global=True` → skip, `gadm_codes=None` is correct
- Protected areas narrower than county level → resolve to enclosing admin unit

**Ground truth annotation:**
The `location_text` field requires annotating the existing ground truth data. Before running evaluation:
- Add `location_text` column to `data/dataset_092624.xlsx` for a representative sample
- Alternatively, evaluate `gadm_codes` only on the subset where ground truth can be inferred from existing dataset metadata (e.g., study country/province noted in title or repository keywords)
