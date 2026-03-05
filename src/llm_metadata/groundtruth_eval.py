"""llm_metadata.groundtruth_eval

Tools to compare manual vs automated extraction and compute evaluation scores.

Design choice: this module accepts **Pydantic BaseModel instances only**.

Rationale:
- Keeps a single input path (no "dict or model" branching).
- Leverages your existing Pydantic schemas/validators/normalization.
- Makes comparisons stable across notebooks/pipelines.

If you currently have dicts (e.g. rows from a DataFrame), validate first:
	DatasetFeatureExtraction.model_validate(row_dict)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Hashable, Iterable, Optional, Sequence

from pydantic import BaseModel


@dataclass(frozen=True)
class FuzzyMatchConfig:
	"""Configuration for fuzzy string matching on specific fields."""

	threshold: int = 80  # Minimum similarity score (0-100)


@dataclass(frozen=True)
class FieldEvalStrategy:
	"""Per-field evaluation strategy declaring the matching algorithm to use.

	Attributes:
		match: Matching algorithm for this field. One of:
			- "exact": Standard normalized comparison (case-fold, whitespace collapse, set-based).
			- "fuzzy": Fuzzy string matching via rapidfuzz using `threshold`.
			- "enhanced_species": Enhanced vernacular/scientific name matching using `threshold`.
		threshold: Similarity threshold (0-100) used by "fuzzy" and "enhanced_species" algorithms.
			Default: 80. Lower values are more permissive.
	"""

	match: str = "exact"
	threshold: int = 80


@dataclass(frozen=True)
class EvaluationConfig:
	"""Configuration for how values are normalized and compared during evaluation.

	This dataclass controls string normalization, list comparison behavior,
	fuzzy matching, and enhanced species matching for biodiversity metadata evaluation.

	Attributes:
		casefold_strings: If True, convert strings to lowercase before comparison.
			Enables case-insensitive matching (e.g., "Caribou" matches "caribou").
			Default: True.

		strip_strings: If True, remove leading/trailing whitespace from strings.
			Default: True.

		collapse_whitespace: If True, normalize multiple spaces to single space.
			Handles variations like "Rangifer  tarandus" vs "Rangifer tarandus".
			Default: True.

		treat_lists_as_sets: If True, compare list fields as unordered sets.
			Order-independent matching where ["A", "B"] equals ["B", "A"].
			When False, lists are compared element-by-element in order.
			Default: True.

		fuzzy_match_fields: Dict mapping field names to FuzzyMatchConfig.
			Enables fuzzy string matching for specific fields using rapidfuzz.
			Example: {"species": FuzzyMatchConfig(threshold=70)} allows
			"Tamias striatus" to match "Tamias striata" (typo tolerance).
			Default: {} (no fuzzy matching).

		enhanced_species_matching: If True, use enhanced matching for 'species' field.
			Handles vernacular/scientific name combinations by:
			- Extracting scientific names from parentheses: "wood turtle (Glyptemys insculpta)"
			- Matching ground truth against either vernacular or scientific parts
			- Substring containment: "Glyptemys insculpta" matches if contained in prediction
			Supersedes fuzzy_match_fields for the species field when enabled.
			Default: False.

		enhanced_species_threshold: Similarity threshold (0-100) for enhanced species matching.
			Used when enhanced_species_matching=True. Lower values are more permissive.
			Default: 70.

	Examples:
		Basic evaluation with case-insensitive set comparison:
		>>> config = EvaluationConfig()
		>>> # "Caribou" matches "caribou", ["A", "B"] matches ["B", "A"]

		Fuzzy matching for species field:
		>>> config = EvaluationConfig(
		...     fuzzy_match_fields={"species": FuzzyMatchConfig(threshold=70)}
		... )

		Enhanced species matching (recommended for biodiversity metadata):
		>>> config = EvaluationConfig(
		...     enhanced_species_matching=True,
		...     enhanced_species_threshold=70
		... )
		>>> # "Glyptemys insculpta" now matches "wood turtle (Glyptemys insculpta)"
		field_strategies: Per-field matching strategies (overrides global fuzzy_match).
	"""

	casefold_strings: bool = True
	strip_strings: bool = True
	collapse_whitespace: bool = True
	treat_lists_as_sets: bool = True
	fuzzy_match_fields: dict[str, FuzzyMatchConfig] = field(default_factory=dict)
	enhanced_species_matching: bool = False
	enhanced_species_threshold: int = 70
	field_strategies: dict[str, FieldEvalStrategy] = field(default_factory=dict)

	def to_dict(self) -> dict:
		"""Serialize config to a plain dict (JSON-compatible)."""
		d = {
			"casefold_strings": self.casefold_strings,
			"strip_strings": self.strip_strings,
			"collapse_whitespace": self.collapse_whitespace,
			"treat_lists_as_sets": self.treat_lists_as_sets,
			"enhanced_species_matching": self.enhanced_species_matching,
			"enhanced_species_threshold": self.enhanced_species_threshold,
			"fuzzy_match_fields": {
				k: {"threshold": v.threshold}
				for k, v in self.fuzzy_match_fields.items()
			},
			"field_strategies": {
				k: {"match": v.match, "threshold": v.threshold}
				for k, v in self.field_strategies.items()
			},
		}
		return d

	@classmethod
	def from_dict(cls, d: dict) -> "EvaluationConfig":
		"""Reconstruct config from a plain dict."""
		fuzzy_match_fields = {
			k: FuzzyMatchConfig(threshold=v["threshold"])
			for k, v in d.get("fuzzy_match_fields", {}).items()
		}
		field_strategies = {
			k: FieldEvalStrategy(match=v["match"], threshold=v.get("threshold", 80))
			for k, v in d.get("field_strategies", {}).items()
		}
		return cls(
			casefold_strings=d.get("casefold_strings", True),
			strip_strings=d.get("strip_strings", True),
			collapse_whitespace=d.get("collapse_whitespace", True),
			treat_lists_as_sets=d.get("treat_lists_as_sets", True),
			enhanced_species_matching=d.get("enhanced_species_matching", False),
			enhanced_species_threshold=d.get("enhanced_species_threshold", 70),
			fuzzy_match_fields=fuzzy_match_fields,
			field_strategies=field_strategies,
		)

	def to_json(self, path) -> None:
		"""Write config to a JSON file."""
		import json
		from pathlib import Path
		Path(path).write_text(json.dumps(self.to_dict(), indent=2))

	@classmethod
	def from_json(cls, path) -> "EvaluationConfig":
		"""Load config from a JSON file."""
		import json
		from pathlib import Path
		d = json.loads(Path(path).read_text())
		return cls.from_dict(d)


DEFAULT_FIELD_STRATEGIES: dict[str, FieldEvalStrategy] = {
	# Numeric — exact
	"temp_range_i":        FieldEvalStrategy(match="exact"),
	"temp_range_f":        FieldEvalStrategy(match="exact"),
	"spatial_range_km2":   FieldEvalStrategy(match="exact"),

	# Controlled vocabulary — exact (enums handle synonyms via Pydantic validators)
	"data_type":           FieldEvalStrategy(match="exact"),
	"geospatial_info_dataset":  FieldEvalStrategy(match="exact"),

	# Free-text list — enhanced species matching
	"species":             FieldEvalStrategy(match="enhanced_species", threshold=70),

	# Booleans — exact
	"time_series":         FieldEvalStrategy(match="exact"),
	"multispecies":        FieldEvalStrategy(match="exact"),
	"threatened_species":  FieldEvalStrategy(match="exact"),
	"new_species_science": FieldEvalStrategy(match="exact"),
	"new_species_region":  FieldEvalStrategy(match="exact"),
	"bias_north_south":    FieldEvalStrategy(match="exact"),
}
# temporal_range: DROPPED — redundant with temp_range_i/temp_range_f
# referred_dataset: DROPPED — too rare in GT, noisy annotations


@dataclass
class FieldResult:
	"""Per-record, per-field comparison result."""

	record_id: Hashable
	field: str
	true_value: Any
	pred_value: Any
	match: bool
	# counts are populated for aggregation (scalar or set-like)
	tp: int = 0
	fp: int = 0
	fn: int = 0
	tn: int = 0

	def to_dict(self) -> dict[str, Any]:
		return {
			"record_id": self.record_id,
			"field": self.field,
			"true_value": self.true_value,
			"pred_value": self.pred_value,
			"match": self.match,
			"tp": self.tp,
			"fp": self.fp,
			"fn": self.fn,
			"tn": self.tn,
		}


@dataclass
class FieldMetrics:
	"""Aggregated metrics for a single field across records."""

	field: str
	tp: int = 0
	fp: int = 0
	fn: int = 0
	tn: int = 0
	n: int = 0
	exact_matches: int = 0

	@property
	def precision(self) -> Optional[float]:
		denom = self.tp + self.fp
		return (self.tp / denom) if denom else None

	@property
	def recall(self) -> Optional[float]:
		denom = self.tp + self.fn
		return (self.tp / denom) if denom else None

	@property
	def f1(self) -> Optional[float]:
		p = self.precision
		r = self.recall
		if p is None or r is None or (p + r) == 0:
			return None
		return 2 * p * r / (p + r)

	@property
	def accuracy(self) -> Optional[float]:
		return ((self.tp + self.tn) / self.n) if self.n else None

	@property
	def exact_match_rate(self) -> Optional[float]:
		return (self.exact_matches / self.n) if self.n else None

	def to_dict(self) -> dict[str, Any]:
		return {
			"field": self.field,
			"tp": self.tp,
			"fp": self.fp,
			"fn": self.fn,
			"tn": self.tn,
			"n": self.n,
			"precision": self.precision,
			"recall": self.recall,
			"f1": self.f1,
			"accuracy": self.accuracy,
			"exact_match_rate": self.exact_match_rate,
		}


@dataclass
class EvaluationReport:
	"""Full evaluation output with per-field aggregates and per-record detail."""

	field_results: list[FieldResult]
	field_metrics: dict[str, FieldMetrics]
	config: EvaluationConfig
	abstracts: dict[str, str] = field(default_factory=dict)
	"""Mapping of record_id -> abstract text.  Populated by prompt_eval.run_eval();
	empty for reports loaded from files produced before this feature was added."""

	def fields(self) -> list[str]:
		return sorted(self.field_metrics.keys())

	def metrics_for(self, field: str) -> FieldMetrics:
		return self.field_metrics[field]

	def errors_for_field(self, field: str) -> list[FieldResult]:
		return [r for r in self.field_results if r.field == field and not r.match]

	def results_for_record(self, record_id: Hashable) -> list[FieldResult]:
		return [r for r in self.field_results if r.record_id == record_id]

	def to_rows(self) -> list[dict[str, Any]]:
		"""Tidy rows (one row per record+field) for DataFrame creation."""
		return [r.to_dict() for r in self.field_results]

	def to_pandas(self):
		"""Return a pandas DataFrame (requires pandas installed)."""
		try:
			import pandas as pd  # type: ignore
		except ImportError as e:
			raise ImportError(
				"pandas is required for EvaluationReport.to_pandas(); install with `pip install -e .[dev]`."
			) from e
		return pd.DataFrame(self.to_rows())

	def metrics_to_pandas(self):
		"""Return a pandas DataFrame of per-field metrics (requires pandas)."""
		try:
			import pandas as pd  # type: ignore
		except ImportError as e:
			raise ImportError(
				"pandas is required for EvaluationReport.metrics_to_pandas(); install with `pip install -e .[dev]`."
			) from e
		return pd.DataFrame([m.to_dict() for m in self.field_metrics.values()]).sort_values(
			by="field"
		)

	def save(self, path, **run_metadata) -> None:
		"""Save report to JSON with optional run metadata.

		Args:
			path: File path to write (str or Path).
			**run_metadata: Optional run-level metadata, e.g.:
				run_id="abstract_20260219_01",
				prompt_module="prompts.abstract",
				model="gpt-5-mini",
				manifest_path="data/manifests/dev_subset_data_paper.csv",
				cost_usd=0.12
		"""
		import json
		from datetime import datetime, timezone
		from pathlib import Path

		def _make_serializable(v):
			"""Recursively convert sets and other non-JSON types."""
			if isinstance(v, set):
				return sorted(str(x) for x in v)
			if isinstance(v, list):
				return [_make_serializable(x) for x in v]
			if isinstance(v, dict):
				return {k: _make_serializable(val) for k, val in v.items()}
			return v

		doc = {
			**run_metadata,
			"timestamp": datetime.now(timezone.utc).isoformat(),
			"config": self.config.to_dict(),
			"abstracts": self.abstracts,
			"field_metrics": {
				fname: {
					"tp": m.tp, "fp": m.fp, "fn": m.fn, "tn": m.tn, "n": m.n,
					"precision": m.precision, "recall": m.recall, "f1": m.f1,
				}
				for fname, m in self.field_metrics.items()
			},
			"field_results": [
				{
					"record_id": str(r.record_id),
					"field": r.field,
					"true_value": _make_serializable(r.true_value),
					"pred_value": _make_serializable(r.pred_value),
					"match": r.match,
					"tp": r.tp, "fp": r.fp, "fn": r.fn, "tn": r.tn,
				}
				for r in self.field_results
			],
		}
		Path(path).parent.mkdir(parents=True, exist_ok=True)
		Path(path).write_text(json.dumps(doc, indent=2))

	@classmethod
	def load(cls, path) -> "EvaluationReport":
		"""Load a report from a JSON file saved by save().

		Returns an EvaluationReport reconstructed from the persisted data.
		Run metadata (run_id, model, etc.) is available by re-reading the JSON
		directly; it is not stored on the report object.
		"""
		import json
		from pathlib import Path

		doc = json.loads(Path(path).read_text())
		config = EvaluationConfig.from_dict(doc.get("config", {}))

		field_results = []
		for r in doc.get("field_results", []):
			field_results.append(FieldResult(
				record_id=r["record_id"],
				field=r["field"],
				true_value=r.get("true_value"),
				pred_value=r.get("pred_value"),
				match=r["match"],
				tp=r.get("tp", 0),
				fp=r.get("fp", 0),
				fn=r.get("fn", 0),
				tn=r.get("tn", 0),
			))

		field_metrics = {}
		for fname, m in doc.get("field_metrics", {}).items():
			fm = FieldMetrics(field=fname)
			fm.tp = m.get("tp", 0)
			fm.fp = m.get("fp", 0)
			fm.fn = m.get("fn", 0)
			fm.tn = m.get("tn", 0)
			fm.n = m.get("n", 0)
			field_metrics[fname] = fm

		return cls(
			field_results=field_results,
			field_metrics=field_metrics,
			config=config,
			abstracts=doc.get("abstracts", {}),
		)


def _fuzzy_match_strings(s1: str, s2: str, threshold: int) -> bool:
	"""Check if two strings match within fuzzy threshold."""
	try:
		from rapidfuzz import fuzz
	except ImportError:
		raise ImportError(
			"rapidfuzz is required for fuzzy matching; install with `pip install rapidfuzz`"
		)
	return fuzz.ratio(s1, s2) >= threshold


def _fuzzy_match_lists(
	true_items: list[str], pred_items: list[str], threshold: int
) -> tuple[set[str], set[str]]:
	"""Fuzzy match two lists and return normalized sets using true values as canonical.
	
	Returns (true_normalized, pred_normalized) where matching items use the same string.
	"""
	try:
		from rapidfuzz import fuzz
	except ImportError:
		raise ImportError(
			"rapidfuzz is required for fuzzy matching; install with `pip install rapidfuzz`"
		)
	
	true_normalized = set()
	pred_normalized = set()
	
	# Create mapping from pred to true based on fuzzy matching
	for pred_item in pred_items:
		if not isinstance(pred_item, str):
			pred_normalized.add(str(pred_item))
			continue
		
		pred_lower = pred_item.lower().strip()
		best_match = None
		best_score = 0
		
		for true_item in true_items:
			if not isinstance(true_item, str):
				continue
			true_lower = true_item.lower().strip()
			score = fuzz.ratio(pred_lower, true_lower)
			if score > best_score:
				best_score = score
				if score >= threshold:
					best_match = true_lower
		
		if best_match:
			pred_normalized.add(best_match)
		else:
			pred_normalized.add(pred_lower)
	
	# Add all true items (normalized)
	for true_item in true_items:
		if isinstance(true_item, str):
			true_normalized.add(true_item.lower().strip())
		else:
			true_normalized.add(str(true_item))
	
	return true_normalized, pred_normalized


def _normalize_string(value: str, config: EvaluationConfig) -> str:
	s = value
	if config.strip_strings:
		s = s.strip()
	if config.collapse_whitespace:
		s = " ".join(s.split())
	if config.casefold_strings:
		s = s.casefold()
	return s


def _normalize_value(value: Any, config: EvaluationConfig) -> Any:
	if value is None:
		return None

	if isinstance(value, str):
		return _normalize_string(value, config)

	if isinstance(value, (list, tuple, set, frozenset)):
		normalized_items = [
			_normalize_value(item, config) for item in list(value) if item is not None
		]
		if config.treat_lists_as_sets:
			# Preserve hashability by converting unhashables to repr; this is conservative.
			out: set[Any] = set()
			for item in normalized_items:
				try:
					hash(item)
					out.add(item)
				except TypeError:
					out.add(repr(item))
			return out
		return normalized_items

	return value


def _is_set_like(value: Any) -> bool:
	return isinstance(value, (set, frozenset))


def compare_models(
	*,
	true_model: BaseModel,
	pred_model: BaseModel,
	record_id: Hashable,
	fields: Optional[Sequence[str]] = None,
	config: EvaluationConfig = EvaluationConfig(),
) -> list[FieldResult]:
	"""Compare two Pydantic models record-by-record and return FieldResult rows."""

	if not isinstance(true_model, BaseModel) or not isinstance(pred_model, BaseModel):
		raise TypeError("compare_models requires Pydantic BaseModel inputs")

	true_data = true_model.model_dump(mode="python")
	pred_data = pred_model.model_dump(mode="python")

	if config.field_strategies:
		# Strategy-registry mode: use registry keys as the canonical field list.
		registry_keys = list(config.field_strategies.keys())
		if fields is None:
			fields = sorted(registry_keys)
		else:
			fields = sorted(set(fields) & set(registry_keys))
	else:
		if fields is None:
			# Compare common fields only to avoid accidental mismatch across schemas.
			fields = sorted(set(true_data.keys()) & set(pred_data.keys()))

	results: list[FieldResult] = []
	for field in fields:
		true_raw = true_data.get(field)
		pred_raw = pred_data.get(field)

		# --- Strategy-registry dispatch (takes priority when field_strategies is populated) ---
		if config.field_strategies:
			strategy = config.field_strategies[field]

			if strategy.match == "enhanced_species":
				if isinstance(true_raw, (list, tuple)) or isinstance(pred_raw, (list, tuple)):
					true_list = list(true_raw) if true_raw else []
					pred_list = list(pred_raw) if pred_raw else []

					true_set, pred_set = _enhanced_species_match_lists(
						[str(x) for x in true_list],
						[str(x) for x in pred_list],
						strategy.threshold,
					)

					tp = len(true_set & pred_set)
					fp = len(pred_set - true_set)
					fn = len(true_set - pred_set)
					match = fp == 0 and fn == 0

					results.append(
						FieldResult(
							record_id=record_id,
							field=field,
							true_value=true_raw,
							pred_value=pred_raw,
							match=match,
							tp=tp,
							fp=fp,
							fn=fn,
							tn=0,
						)
					)
					continue

				# Scalar fallback for enhanced_species: treat as exact
				true_norm = _normalize_value(true_raw, config)
				pred_norm = _normalize_value(pred_raw, config)
				# (falls through to scalar comparison below — handled by shared scalar block)

			elif strategy.match == "fuzzy":
				if isinstance(true_raw, (list, tuple)) or isinstance(pred_raw, (list, tuple)):
					true_list = list(true_raw) if true_raw else []
					pred_list = list(pred_raw) if pred_raw else []

					true_set, pred_set = _fuzzy_match_lists(
						[str(x) for x in true_list],
						[str(x) for x in pred_list],
						strategy.threshold,
					)

					tp = len(true_set & pred_set)
					fp = len(pred_set - true_set)
					fn = len(true_set - pred_set)
					match = fp == 0 and fn == 0

					results.append(
						FieldResult(
							record_id=record_id,
							field=field,
							true_value=true_raw,
							pred_value=pred_raw,
							match=match,
							tp=tp,
							fp=fp,
							fn=fn,
							tn=0,
						)
					)
					continue

				if isinstance(true_raw, str) and isinstance(pred_raw, str):
					if _fuzzy_match_strings(true_raw, pred_raw, strategy.threshold):
						results.append(
							FieldResult(
								record_id=record_id,
								field=field,
								true_value=true_raw,
								pred_value=pred_raw,
								match=True,
								tp=1,
								fp=0,
								fn=0,
								tn=0,
							)
						)
					else:
						results.append(
							FieldResult(
								record_id=record_id,
								field=field,
								true_value=true_raw,
								pred_value=pred_raw,
								match=False,
								tp=0,
								fp=1,
								fn=1,
								tn=0,
							)
						)
					continue

				# Non-string scalar fallback: treat as exact
				true_norm = _normalize_value(true_raw, config)
				pred_norm = _normalize_value(pred_raw, config)

			else:
				# strategy.match == "exact" (or any unrecognised value)
				true_norm = _normalize_value(true_raw, config)
				pred_norm = _normalize_value(pred_raw, config)

			# Shared scalar/set comparison for strategy-dispatch paths that reach here.
			if _is_set_like(true_norm) or _is_set_like(pred_norm):
				true_set_n = true_norm if _is_set_like(true_norm) else (set() if true_norm is None else {true_norm})
				pred_set_n = pred_norm if _is_set_like(pred_norm) else (set() if pred_norm is None else {pred_norm})

				tp = len(true_set_n & pred_set_n)
				fp = len(pred_set_n - true_set_n)
				fn = len(true_set_n - pred_set_n)
				match = fp == 0 and fn == 0

				results.append(
					FieldResult(
						record_id=record_id,
						field=field,
						true_value=true_raw,
						pred_value=pred_raw,
						match=match,
						tp=tp,
						fp=fp,
						fn=fn,
						tn=0,
					)
				)
				continue

			if true_norm is None and pred_norm is None:
				results.append(
					FieldResult(
						record_id=record_id,
						field=field,
						true_value=true_raw,
						pred_value=pred_raw,
						match=True,
						tp=0,
						fp=0,
						fn=0,
						tn=1,
					)
				)
				continue

			if true_norm is None and pred_norm is not None:
				results.append(
					FieldResult(
						record_id=record_id,
						field=field,
						true_value=true_raw,
						pred_value=pred_raw,
						match=False,
						tp=0,
						fp=1,
						fn=0,
						tn=0,
					)
				)
				continue

			if true_norm is not None and pred_norm is None:
				results.append(
					FieldResult(
						record_id=record_id,
						field=field,
						true_value=true_raw,
						pred_value=pred_raw,
						match=False,
						tp=0,
						fp=0,
						fn=1,
						tn=0,
					)
				)
				continue

			if true_norm == pred_norm:
				results.append(
					FieldResult(
						record_id=record_id,
						field=field,
						true_value=true_raw,
						pred_value=pred_raw,
						match=True,
						tp=1,
						fp=0,
						fn=0,
						tn=0,
					)
				)
			else:
				results.append(
					FieldResult(
						record_id=record_id,
						field=field,
						true_value=true_raw,
						pred_value=pred_raw,
						match=False,
						tp=0,
						fp=1,
						fn=1,
						tn=0,
					)
				)
			continue
		# --- End strategy-registry dispatch ---

		# Apply enhanced species matching for species field if configured
		if field == "species" and config.enhanced_species_matching:
			if isinstance(true_raw, (list, tuple)) or isinstance(pred_raw, (list, tuple)):
				true_list = list(true_raw) if true_raw else []
				pred_list = list(pred_raw) if pred_raw else []

				true_set, pred_set = _enhanced_species_match_lists(
					[str(x) for x in true_list],
					[str(x) for x in pred_list],
					config.enhanced_species_threshold
				)

				tp = len(true_set & pred_set)
				fp = len(pred_set - true_set)
				fn = len(true_set - pred_set)
				match = (fp == 0 and fn == 0)

				results.append(
					FieldResult(
						record_id=record_id,
						field=field,
						true_value=true_raw,
						pred_value=pred_raw,
						match=match,
						tp=tp,
						fp=fp,
						fn=fn,
						tn=0,
					)
				)
				continue

		# Apply fuzzy matching BEFORE general normalization if configured
		fuzzy_config = config.fuzzy_match_fields.get(field)
		if fuzzy_config:
			# Handle fuzzy matching for lists
			if isinstance(true_raw, (list, tuple)) or isinstance(pred_raw, (list, tuple)):
				true_list = list(true_raw) if true_raw else []
				pred_list = list(pred_raw) if pred_raw else []
				
				true_set, pred_set = _fuzzy_match_lists(
					[str(x) for x in true_list],
					[str(x) for x in pred_list],
					fuzzy_config.threshold
				)
				
				tp = len(true_set & pred_set)
				fp = len(pred_set - true_set)
				fn = len(true_set - pred_set)
				match = (fp == 0 and fn == 0)
				
				results.append(
					FieldResult(
						record_id=record_id,
						field=field,
						true_value=true_raw,
						pred_value=pred_raw,
						match=match,
						tp=tp,
						fp=fp,
						fn=fn,
						tn=0,
					)
				)
				continue
			
			# Handle fuzzy matching for scalars
			if isinstance(true_raw, str) and isinstance(pred_raw, str):
				if _fuzzy_match_strings(true_raw, pred_raw, fuzzy_config.threshold):
					results.append(
						FieldResult(
							record_id=record_id,
							field=field,
							true_value=true_raw,
							pred_value=pred_raw,
							match=True,
							tp=1,
							fp=0,
							fn=0,
							tn=0,
						)
					)
					continue
				else:
					results.append(
						FieldResult(
							record_id=record_id,
							field=field,
							true_value=true_raw,
							pred_value=pred_raw,
							match=False,
							tp=0,
							fp=1,
							fn=1,
							tn=0,
						)
					)
					continue

		# Standard normalization (no fuzzy matching)
		true_norm = _normalize_value(true_raw, config)
		pred_norm = _normalize_value(pred_raw, config)

		# Set-like comparison (covers list fields after normalization when treat_lists_as_sets=True)
		if _is_set_like(true_norm) or _is_set_like(pred_norm):
			true_set = true_norm if _is_set_like(true_norm) else (set() if true_norm is None else {true_norm})
			pred_set = pred_norm if _is_set_like(pred_norm) else (set() if pred_norm is None else {pred_norm})

			tp = len(true_set & pred_set)
			fp = len(pred_set - true_set)
			fn = len(true_set - pred_set)
			match = (fp == 0 and fn == 0)

			results.append(
				FieldResult(
					record_id=record_id,
					field=field,
					true_value=true_raw,
					pred_value=pred_raw,
					match=match,
					tp=tp,
					fp=fp,
					fn=fn,
					tn=0,
				)
			)
			continue

		# Scalar comparison
		if true_norm is None and pred_norm is None:
			results.append(
				FieldResult(
					record_id=record_id,
					field=field,
					true_value=true_raw,
					pred_value=pred_raw,
					match=True,
					tp=0,
					fp=0,
					fn=0,
					tn=1,
				)
			)
			continue

		if true_norm is None and pred_norm is not None:
			results.append(
				FieldResult(
					record_id=record_id,
					field=field,
					true_value=true_raw,
					pred_value=pred_raw,
					match=False,
					tp=0,
					fp=1,
					fn=0,
					tn=0,
				)
			)
			continue

		if true_norm is not None and pred_norm is None:
			results.append(
				FieldResult(
					record_id=record_id,
					field=field,
					true_value=true_raw,
					pred_value=pred_raw,
					match=False,
					tp=0,
					fp=0,
					fn=1,
					tn=0,
				)
			)
			continue

		if true_norm == pred_norm:
			results.append(
				FieldResult(
					record_id=record_id,
					field=field,
					true_value=true_raw,
					pred_value=pred_raw,
					match=True,
					tp=1,
					fp=0,
					fn=0,
					tn=0,
				)
			)
		else:
			# Scalar wrong value counts as both a FP and FN for precision/recall.
			results.append(
				FieldResult(
					record_id=record_id,
					field=field,
					true_value=true_raw,
					pred_value=pred_raw,
					match=False,
					tp=0,
					fp=1,
					fn=1,
					tn=0,
				)
			)

	return results


def evaluate_pairs(
	*,
	true_models: Sequence[BaseModel],
	pred_models: Sequence[BaseModel],
	key: Callable[[BaseModel], Hashable],
	fields: Optional[Sequence[str]] = None,
	config: EvaluationConfig = EvaluationConfig(),
) -> EvaluationReport:
	"""Evaluate two aligned collections of models keyed by `key(model)`.

	The key must uniquely identify records (e.g., DOI).
	Records present only on one side are still evaluated with missing values.
	"""

	true_by_id = {key(m): m for m in true_models}
	pred_by_id = {key(m): m for m in pred_models}
	all_ids = sorted(set(true_by_id.keys()) | set(pred_by_id.keys()), key=str)

	field_results: list[FieldResult] = []
	for record_id in all_ids:
		t = true_by_id.get(record_id)
		p = pred_by_id.get(record_id)
		if t is None and p is None:
			continue
		if t is None:
			# Compare against an "empty" version of the pred model type.
			assert p is not None
			t = type(p).model_validate({})
		if p is None:
			assert t is not None
			p = type(t).model_validate({})

		field_results.extend(
			compare_models(
				true_model=t,
				pred_model=p,
				record_id=record_id,
				fields=fields,
				config=config,
			)
		)

	metrics = aggregate_field_metrics(field_results)
	return EvaluationReport(field_results=field_results, field_metrics=metrics, config=config)


def evaluate_indexed(
	*,
	true_by_id: dict[Hashable, BaseModel],
	pred_by_id: dict[Hashable, BaseModel],
	fields: Optional[Sequence[str]] = None,
	config: EvaluationConfig = EvaluationConfig(),
) -> EvaluationReport:
	"""Evaluate two dictionaries of models keyed by an external identifier (e.g. DOI)."""

	all_ids = sorted(set(true_by_id.keys()) | set(pred_by_id.keys()), key=str)
	field_results: list[FieldResult] = []

	for record_id in all_ids:
		t = true_by_id.get(record_id)
		p = pred_by_id.get(record_id)
		if t is None and p is None:
			continue
		if t is None:
			assert p is not None
			t = type(p).model_validate({})
		if p is None:
			assert t is not None
			p = type(t).model_validate({})

		field_results.extend(
			compare_models(
				true_model=t,
				pred_model=p,
				record_id=record_id,
				fields=fields,
				config=config,
			)
		)

	metrics = aggregate_field_metrics(field_results)
	return EvaluationReport(field_results=field_results, field_metrics=metrics, config=config)


def aggregate_field_metrics(field_results: Iterable[FieldResult]) -> dict[str, FieldMetrics]:
	"""Aggregate per-field counts and derived metrics."""

	out: dict[str, FieldMetrics] = {}
	for r in field_results:
		m = out.get(r.field)
		if m is None:
			m = FieldMetrics(field=r.field)
			out[r.field] = m
		m.tp += r.tp
		m.fp += r.fp
		m.fn += r.fn
		m.tn += r.tn
		m.n += 1
		if r.match:
			m.exact_matches += 1
	return out


def micro_average(metrics: Iterable[FieldMetrics]) -> FieldMetrics:
	"""Micro-average across fields (sums counts, then derives metrics)."""
	total = FieldMetrics(field="__micro__")
	for m in metrics:
		total.tp += m.tp
		total.fp += m.fp
		total.fn += m.fn
		total.tn += m.tn
		total.n += m.n
		total.exact_matches += m.exact_matches
	return total


def macro_f1(metrics: Iterable[FieldMetrics]) -> Optional[float]:
	"""Macro-average F1 across fields (ignores fields with undefined F1)."""
	f1s: list[float] = []
	for m in metrics:
		if m.f1 is not None:
			f1s.append(m.f1)
	return (sum(f1s) / len(f1s)) if f1s else None


# =============================================================================
# Enhanced Species Matching
# =============================================================================

import re


def _extract_species_parts(species_str: str) -> dict[str, str]:
	"""
	Extract scientific and vernacular name parts from a species string.

	Handles formats like:
	- "wood turtle (Glyptemys insculpta)" -> {"vernacular": "wood turtle", "scientific": "Glyptemys insculpta"}
	- "Glyptemys insculpta (wood turtle)" -> {"vernacular": "wood turtle", "scientific": "Glyptemys insculpta"}
	- "Rangifer tarandus" -> {"scientific": "Rangifer tarandus"}
	- "caribou" -> {"vernacular": "caribou"}

	Returns dict with keys 'vernacular' and/or 'scientific' containing normalized lowercase strings.
	"""
	if not species_str or not isinstance(species_str, str):
		return {}

	s = species_str.strip()
	parts = {}

	# Check for parentheses pattern
	paren_match = re.match(r'^([^()]+)\s*\(([^()]+)\)\s*$', s)
	if paren_match:
		before_paren = paren_match.group(1).strip()
		inside_paren = paren_match.group(2).strip()

		# Heuristic: scientific names typically have capitalized genus + lowercase species
		# and often contain 2-3 words (Genus species or Genus species subspecies)
		def looks_scientific(text: str) -> bool:
			words = text.split()
			if len(words) < 2:
				return False
			# Check if first word is capitalized and second is lowercase
			if words[0][0].isupper() and words[1][0].islower():
				return True
			return False

		if looks_scientific(before_paren):
			parts['scientific'] = before_paren.lower()
			parts['vernacular'] = inside_paren.lower()
		elif looks_scientific(inside_paren):
			parts['scientific'] = inside_paren.lower()
			parts['vernacular'] = before_paren.lower()
		else:
			# Can't determine, use both as full
			parts['full'] = s.lower()
	else:
		# No parentheses - check if it looks scientific
		words = s.split()
		if len(words) >= 2 and words[0][0].isupper() and len(words[0]) > 1:
			# Likely scientific name
			parts['scientific'] = s.lower()
		else:
			# Likely vernacular name
			parts['vernacular'] = s.lower()
		parts['full'] = s.lower()

	return parts


def _species_match_score(true_item: str, pred_item: str, threshold: int = 70) -> tuple[bool, int]:
	"""
	Check if a predicted species matches a ground truth species.

	Enhanced matching that handles:
	- Exact match (case-insensitive)
	- Vernacular name in prediction matches scientific name in ground truth
	- Scientific name in prediction matches vernacular name in ground truth
	- Fuzzy matching on individual parts

	Returns (is_match, similarity_score).
	"""
	try:
		from rapidfuzz import fuzz
	except ImportError:
		raise ImportError(
			"rapidfuzz is required for species matching; install with `pip install rapidfuzz`"
		)

	true_lower = true_item.lower().strip()
	pred_lower = pred_item.lower().strip()

	# Exact match
	if true_lower == pred_lower:
		return True, 100

	# Direct fuzzy match on full strings
	full_score = fuzz.ratio(true_lower, pred_lower)
	if full_score >= threshold:
		return True, full_score

	# Extract parts from both
	true_parts = _extract_species_parts(true_item)
	pred_parts = _extract_species_parts(pred_item)

	# Try matching ground truth against each part of prediction
	best_score = full_score

	for true_key, true_val in true_parts.items():
		for pred_key, pred_val in pred_parts.items():
			score = fuzz.ratio(true_val, pred_val)
			if score > best_score:
				best_score = score
			if score >= threshold:
				return True, score

	# Special case: ground truth might be contained in prediction
	# e.g., true="Glyptemys insculpta" in pred="wood turtle (Glyptemys insculpta)"
	if true_lower in pred_lower:
		return True, 95

	# Check if any true part is contained in full pred
	for _, true_val in true_parts.items():
		if true_val in pred_lower:
			return True, 90

	return best_score >= threshold, best_score


def _enhanced_species_match_lists(
	true_items: list[str], pred_items: list[str], threshold: int = 70
) -> tuple[set[str], set[str]]:
	"""
	Enhanced fuzzy matching for species lists with vernacular/scientific name awareness.

	Each ground truth item is matched against predictions by checking:
	1. Exact match (case-insensitive)
	2. Scientific name in pred matches vernacular in true (or vice versa)
	3. Fuzzy match on extracted parts
	4. Substring containment (e.g., "Glyptemys insculpta" in "wood turtle (Glyptemys insculpta)")

	Returns (true_normalized, pred_normalized) where matching items use the canonical (true) string.
	"""
	true_normalized = set()
	pred_normalized = set()

	# For each prediction, find best matching true value
	for pred_item in pred_items:
		if not isinstance(pred_item, str):
			pred_normalized.add(str(pred_item).lower().strip())
			continue

		pred_lower = pred_item.lower().strip()
		best_match = None
		best_score = 0

		for true_item in true_items:
			if not isinstance(true_item, str):
				continue

			is_match, score = _species_match_score(true_item, pred_item, threshold)
			if score > best_score:
				best_score = score
				if is_match:
					best_match = true_item.lower().strip()

		if best_match:
			pred_normalized.add(best_match)
		else:
			pred_normalized.add(pred_lower)

	# Add all true items (normalized)
	for true_item in true_items:
		if isinstance(true_item, str):
			true_normalized.add(true_item.lower().strip())
		else:
			true_normalized.add(str(true_item))

	return true_normalized, pred_normalized


@dataclass(frozen=True)
class EnhancedSpeciesMatchConfig:
	"""Configuration for enhanced species matching with vernacular/scientific name awareness."""

	threshold: int = 70  # Minimum similarity score (0-100)
	use_enhanced_matching: bool = True  # Use enhanced species matching logic

