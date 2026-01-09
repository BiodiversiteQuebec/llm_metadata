"""llm_metadata.schemas.evaluation

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
class EvaluationConfig:
	"""Configuration for how values are normalized and compared."""

	casefold_strings: bool = True
	strip_strings: bool = True
	collapse_whitespace: bool = True
	treat_lists_as_sets: bool = True
	fuzzy_match_fields: dict[str, FuzzyMatchConfig] = field(default_factory=dict)


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

	if fields is None:
		# Compare common fields only to avoid accidental mismatch across schemas.
		fields = sorted(set(true_data.keys()) & set(pred_data.keys()))

	results: list[FieldResult] = []
	for field in fields:
		true_raw = true_data.get(field)
		pred_raw = pred_data.get(field)

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

