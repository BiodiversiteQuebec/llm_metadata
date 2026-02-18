# Geographic Location Enrichment — Nominatim-Based Evaluation

## Context

The `spatial_range_km2` field records study area size in km², and `geospatial_info_dataset` classifies _how_ spatial data is represented (sample points, administrative units, etc.), but neither field captures _where_ a study took place. Geographic coverage is a core dimension of biodiversity data gap analysis — knowing whether a dataset covers Quebec vs. Ontario vs. the full boreal region is essential for the Biodiversité Québec mandate.

**Gap:** The current schema has no text field for study location names (e.g., "Quebec, Canada", "North America", "Laurentian Highlands").

**Approach:** Following the enrichment pattern established by GBIF species matching:

1. Add `location_text: Optional[list[str]]` to `DatasetFeatures` — raw location strings extracted as-is by the LLM (mirrors `species` field design).
2. Add `location_ids: Optional[list[str]]` — stable place identifiers derived from `location_text` via Nominatim geocoding. Populated by preprocessing, not extracted by LLM.
3. Create `nominatim.py` — geocoding wrapper using the Nominatim (OpenStreetMap) API, which is free, key-free, and returns structured admin hierarchy plus Wikidata QIDs.

**Identifier strategy (tiered):**
- **Primary: Wikidata QID** (e.g., `"Q176"` for Quebec province) — globally unique, persistent across Nominatim versions, works for cities/provinces/national parks. Present in ~60–70% of geocoding results.
- **Fallback: `osm_type:osm_id`** (e.g., `"relation:61549"`) — always present, reasonably stable for major features, OSM-specific.

Example `location_ids` values: `["Q176", "Q340", "relation:15421717"]`

The existing evaluation framework handles both fields independently:
- `location_text` → string-based comparison (exact/fuzzy)
- `location_ids` → set comparison on identifier strings (trivial, no new matching logic)

Strategy comparison: `report.metrics_for("location_text")` vs `report.metrics_for("location_ids")`.

**Outcome:** Geographic extraction and Nominatim-resolved evaluation as parallel fields, zero changes to the evaluation framework internals.

---

## Geocoding Backend: Nominatim

**API:** `GET https://nominatim.openstreetmap.org/search?q={location}&addressdetails=1&extratags=1&format=jsonv2`

**Identifier extraction:**
1. Check `extratags.wikidata` → use as-is (e.g., `"Q176"`)
2. If absent → construct `f"{osm_type}:{osm_id}"` (e.g., `"relation:61549"`)

**Known search quality issues (from empirical testing):**
- MRC-level admin boundaries: Nominatim OSM coverage is inconsistent — may return wrong entity (e.g., a police station instead of the MRC boundary)
- Physiographic regions (e.g., "Laurentian Highlands"): may resolve to a local park with the same name in another province
- Park visitor centres vs. park boundaries: may hit a POI instead of the park relation

**Search quality mitigations in `_nominatim_geocode()`:**
- Pass `countrycodes={country_hint}` when country hint is detected (narrows to correct country)
- Use structured query params (`city=`, `state=`, `country=`) for common patterns like "X, Quebec"
- Filter by `featuretype` when entity type is detectable (`featuretype=city`, `featuretype=state`)
- Log `category`, `type`, and `importance` score for every result so failures are auditable
- Accept `limit=3` and pick highest-importance result with `category=boundary` when present, falling back to top result

**Usage policy:**
- 1 req/sec polite limit
- Custom `User-Agent` header required: `"llm_metadata/1.0 biodiversite-quebec"`

**Note on `place_id`:** Nominatim's `place_id` is explicitly documented as non-persistent (changes across servers and reimports). Never use it as a stable identifier.

---

## Work Units

### WU-1: Schema field — `location_text`
`model: sonnet` | deps: none

Add `location_text` extraction field to `DatasetFeatures` and update the LLM system prompts to extract it.

**Schema change in `schemas/fuster_features.py`:**
```python
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

**`ParsedLocation` dataclass:**
```python
@dataclass
class ParsedLocation:
    original: str               # raw input
    query: str                  # cleaned query for geocoding API
    country_hint: str | None    # ISO 3166-1 alpha-2 if detectable ("CA", "US")
    is_global: bool             # True for "global", "worldwide", "international"
    is_marine: bool             # True for ocean/sea names (skip — Nominatim unreliable for marine)
```

**Preprocessing pipeline (`parse_location_string(raw: str) -> ParsedLocation`):**
1. Strip leading/trailing whitespace and punctuation
2. Detect global/worldwide terms → `is_global=True`, skip geocoding
3. Detect marine/ocean names (Atlantic, Pacific, "ocean", "sea", "bay", "gulf") → `is_marine=True`
4. Detect country hints from common patterns: "X, Canada" → `country_hint="CA"`; "Province of X" → strip prefix
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

### WU-3: `nominatim.py` — Nominatim geocoding wrapper
`model: sonnet` | deps: WU-2

**New file:** `src/llm_metadata/nominatim.py`

Follow `semantic_scholar.py` / `gbif.py` patterns: module docstring, `requests`, `joblib.Memory` cache, logging, polite delay.

**Core types:**
```python
@dataclass
class LocationMatch:
    location_id: str    # Wikidata QID ("Q176") or "osm_type:osm_id" ("relation:61549")
    id_type: str        # "wikidata" | "osm"
    name: str           # display_name from Nominatim (for logging/debugging)
    category: str       # Nominatim category (e.g. "boundary")
    osm_type: str       # "node" | "way" | "relation"
    osm_id: int
    importance: float   # Nominatim importance score (0–1)

@dataclass
class ResolvedLocation:
    original: str
    parsed: ParsedLocation
    match: LocationMatch | None
```

**Internal helpers:**

`_nominatim_geocode(query: str, country_hint: str | None, feature_type: str | None = None) -> dict | None`
- `GET https://nominatim.openstreetmap.org/search` with:
  - `q={query}`, `format=jsonv2`, `addressdetails=1`, `extratags=1`, `limit=3`
  - `countrycodes={country_hint}` when country_hint is set
  - `featuretype={feature_type}` when feature_type is set (e.g. `"city"`, `"state"`)
- Pick best result: prefer highest-importance result with `category="boundary"`, fall back to top result
- Returns the selected result dict or None
- `@memory.cache`, 1.0s delay (Nominatim usage policy)
- Custom `User-Agent` header: `"llm_metadata/1.0 biodiversite-quebec"`
- Log `category`, `type`, and `importance` for every top result

`_extract_location_id(result: dict) -> tuple[str, str]`
- Returns `(location_id, id_type)` tuple
- If `result["extratags"].get("wikidata")` → return `(qid, "wikidata")`
- Else → return `(f"{result['osm_type']}:{result['osm_id']}", "osm")`

**Main functions:**

`match_location(location: str) -> LocationMatch | None`
- Parse with `parse_location_string`
- Skip if `is_global` or `is_marine` (return None)
- Geocode with `_nominatim_geocode`
- Extract identifier with `_extract_location_id`

`resolve_location_list(locations: list[str]) -> list[ResolvedLocation]`
- Map `match_location` over each location string
- Returns `ResolvedLocation` for each (with `match=None` for skipped/unresolved)

**Tests:** `tests/test_nominatim.py`
- Mock `requests.get` for Nominatim responses
- Wikidata QID extracted when present in extratags → id_type="wikidata"
- OSM fallback when wikidata absent → `"relation:XXXXXX"`, id_type="osm"
- Boundary-preference logic: boundary result chosen over higher-ranked POI
- `countrycodes` param passed when country_hint set
- Global/marine skip → returns None
- Caching: second call with same input → no HTTP request

---

### WU-4: Schema `location_ids` field + enrichment function
`model: sonnet` | deps: WU-3

**Schema change in `schemas/fuster_features.py`:**
```python
location_ids: Optional[list[str]] = Field(
    None,
    description=(
        "Stable place identifiers resolved from location_text via Nominatim geocoding. "
        "Populated by preprocessing, not extracted by LLM. "
        "Format: Wikidata QID preferred (e.g. 'Q176'), "
        "osm_type:osm_id as fallback (e.g. 'relation:61549')."
    )
)
```

**Enrichment function in `nominatim.py`:**
```python
def enrich_with_location_ids(model: DatasetFeatures) -> DatasetFeatures:
    """Resolve location_text strings to stable place identifiers and return enriched copy."""
    if not model.location_text:
        return model.model_copy(update={"location_ids": None})
    resolved = resolve_location_list(model.location_text)
    ids = [r.match.location_id for r in resolved if r.match]
    unique_ids = list(dict.fromkeys(ids))  # deduplicate, preserve order
    return model.model_copy(update={"location_ids": unique_ids or None})
```

**Notebook usage pattern:**
```python
# Preprocess both sides
true_enriched = {doi: enrich_with_location_ids(m) for doi, m in true_by_id.items()}
pred_enriched = {doi: enrich_with_location_ids(m) for doi, m in pred_by_id.items()}

# Single evaluation run — both fields evaluated independently
report = evaluate_indexed(
    true_by_id=true_enriched,
    pred_by_id=pred_enriched,
    fields=["location_text", "location_ids", ...],
    config=EvaluationConfig(),
)

# Compare strategies
report.metrics_for("location_text")   # fuzzy string matching P/R/F1
report.metrics_for("location_ids")    # set comparison on place identifiers P/R/F1
```

**Files:**
- `schemas/fuster_features.py` — add `location_ids` field
- `nominatim.py` — add `enrich_with_location_ids()` function

**Tests:** `tests/test_nominatim_enrichment.py`
- Enrich model with known locations → `location_ids` populated
- Enrich model with `location_text=None` → `location_ids` stays None
- Enrich model with only global/marine locations → `location_ids` is None
- Duplicate ids deduplicated (two Montreal neighbourhoods → one `"Q340"`)
- Mixed Wikidata + OSM ids in same list (some locations have wikidata, some don't)
- End-to-end: enrich both sides, run `evaluate_indexed`, verify `location_ids` metrics present

---

## Execution Rounds

```
Round 1:  WU-1 (location_text schema)     ← no deps, start immediately
          model: sonnet

Round 2:  WU-2 (location_parsing.py)      ← deps: WU-1
          model: sonnet

Round 3:  WU-3 (nominatim.py wrapper)     ← deps: WU-2
          model: sonnet

Round 4:  WU-4 (location_ids + enrich)    ← deps: WU-3
          model: sonnet
```

---

## Verification

1. `uv run python -m pytest tests/test_schema_location_text.py` — field parsing
2. `uv run python -m pytest tests/test_location_parsing.py` — location preprocessing
3. `uv run python -m pytest tests/test_nominatim.py` — Nominatim wrapper with mocked HTTP
4. `uv run python -m pytest tests/test_nominatim_enrichment.py` — enrichment + eval integration
5. `uv run python -m pytest tests/` — full suite green
6. Notebook smoke test: extract `location_text` from a few real abstracts, enrich with `location_ids`, compare `location_text` vs `location_ids` metrics

---

## Notes & Decisions

**Why Nominatim?**
Free, no API key, permissive usage for research. Returns `extratags.wikidata` QIDs for major administrative entities and parks. Usage policy: 1 req/sec, custom User-Agent required — enforced in wrapper.

**Why Wikidata QID as primary, not ISO 3166-2?**
ISO 3166-2 only reaches province/state level (e.g., `CA-QC`). It cannot represent cities, MRCs, admin regions, or national parks. Wikidata QIDs cover any named entity at any granularity — countries, provinces, municipalities, MRCs, national parks, ecosystems — and are globally unique and persistent (merges produce redirects, not dead links). QIDs are returned directly by Nominatim in `extratags.wikidata` with no mapping table required.

**Why not GADM GIDs?**
GADM does not provide a geocoding API. Mapping from Nominatim's OSM admin names to GADM GIDs requires a custom reference table, and OSM admin names frequently differ from GADM names. This creates a fragile two-step translation with no benefit over Wikidata QIDs for evaluation purposes.

**Why `osm_type:osm_id` as fallback, not ISO 3166-2?**
For entities where Wikidata QID is absent, ISO 3166-2 would only give the parent province — losing all specificity. The composite OSM ID identifies the correct specific entity. Stability: OSM IDs for major features (cities, provincial parks, national parks) are practically stable over research timescales.

**Never use `place_id`:** Nominatim's internal `place_id` is explicitly documented as non-persistent. It changes across servers and reimports. It must never be used as a stable identifier.

**Known limitations:**
- **MRC coverage in OSM is inconsistent** — Nominatim may return wrong entity for MRC queries. The `location_parsing.py` preprocessing and `countrycodes` filtering reduce this but don't eliminate it. MRC resolution is best-effort.
- **Physiographic regions** ("Laurentian Highlands", "Canadian Shield") often lack precise OSM boundaries and may resolve to wrong features.
- **Marine areas**: Nominatim is unreliable for ocean/sea names. `is_marine=True` skips geocoding; `location_ids=None` for marine-only studies is correct behaviour.
- **National parks**: Well-known parks (Jacques-Cartier, Banff) resolve correctly with Wikidata QIDs. The `category="boundary"` preference in `_nominatim_geocode` helps avoid visitor-centre POI hits.

**Ground truth annotation:**
The `location_text` field requires annotating the existing ground truth data. Before running evaluation, add a `location_text` column to `data/dataset_092624.xlsx` for a representative sample, or evaluate `location_ids` only on the subset where ground truth can be inferred from existing dataset metadata.
