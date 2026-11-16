"""Tests for the Claude adapter with a mocked Anthropic client (no network, no cost)."""

from __future__ import annotations

import pytest
from joblib import Memory
from pydantic import BaseModel
from types import SimpleNamespace
from unittest.mock import MagicMock

from llm_metadata import anthropic_extract as ax
from llm_metadata.extraction import ExtractionConfig, estimate_run_cost, run_manifest_extraction, validation_stats
from llm_metadata.prompt_eval import CostLimitExceeded, run_eval
from llm_metadata.schemas.data_paper import DataPaperManifest, DataPaperRecord, ExtractionMode


class Tiny(BaseModel):
    relevance: str
    notes: str | None = None


GOOD = '{"relevance": "high", "notes": null}'


def _response(text: str, *, inp=100, out=50, write=0, read=0, stop="end_turn"):
    usage = SimpleNamespace(
        model_dump=lambda: {
            "input_tokens": inp,
            "output_tokens": out,
            "cache_creation_input_tokens": write,
            "cache_read_input_tokens": read,
        }
    )
    return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)], usage=usage, stop_reason=stop)


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(ax, "memory", Memory(str(tmp_path / "cache"), verbose=0))
    mock = MagicMock()
    mock.messages.create.return_value = _response(GOOD)
    mock.messages.count_tokens.return_value = SimpleNamespace(input_tokens=1000)
    monkeypatch.setattr(ax, "get_anthropic_client", lambda *a, **k: mock)
    return mock


@pytest.fixture
def pdf(tmp_path):
    import pymupdf

    path = tmp_path / "paper.pdf"
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "Fish survey in Quebec lakes 2010-2012")
    doc.save(str(path))
    return path


def test_text_request_shape_and_return_contract(client):
    result = ax.extract_from_text("An abstract.", text_format=Tiny, model="claude-haiku-5-5", reasoning={"effort": "medium"})
    kwargs = client.messages.create.call_args.kwargs
    assert kwargs["max_tokens"] == 16000
    assert kwargs["output_config"] == {"effort": "medium"}
    assert kwargs["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert "JSON schema" in kwargs["system"][0]["text"]
    assert kwargs["messages"] == [{"role": "user", "content": "An abstract."}]
    assert result["output"] == Tiny(relevance="high")
    assert result["usage_cost"]["validation_retries"] == 0
    assert {"prompt", "text", "model", "response", "output", "usage_cost", "temperature", "reasoning"} <= set(result)


def test_pdf_native_sends_document_block_before_instruction(client, pdf):
    result = ax.extract_from_pdf_file(pdf, text_format=Tiny)
    content = client.messages.create.call_args.kwargs["messages"][0]["content"]
    assert content[0]["type"] == "document"
    assert content[0]["source"]["type"] == "base64"
    assert content[0]["source"]["media_type"] == "application/pdf"
    assert content[1]["type"] == "text"
    assert result["extraction_method"] == "pdf_native"
    assert result["pdf_path"] == str(pdf)


def test_pdf_text_uses_pymupdf_text_then_text_path(client, pdf):
    result = ax.extract_from_pdf_text(pdf, text_format=Tiny)
    user = client.messages.create.call_args.kwargs["messages"][0]["content"]
    assert "Fish survey in Quebec lakes" in user
    assert result["extraction_method"] == "pdf_text"


def test_cost_counts_cache_write_and_read_separately():
    # input_tokens excludes cached tokens. Haiku: 0.10 in, 0.50 out.
    cost = ax._usage_cost(
        {"input_tokens": 1_000_000, "cache_creation_input_tokens": 1_000_000,
         "cache_read_input_tokens": 1_000_000, "output_tokens": 1_000_000},
        "claude-haiku-5-5", joblib_cache_hit=False,
    )
    assert cost["input_cost"] == pytest.approx(0.10)
    assert cost["cache_write_cost"] == pytest.approx(0.125)
    assert cost["cache_cost"] == pytest.approx(0.01)
    assert cost["output_cost"] == pytest.approx(0.50)
    assert cost["total_cost"] == pytest.approx(0.735)
    assert cost["input_tokens"] == 3_000_000


def test_joblib_cache_hit_is_free_and_skips_the_api(client):
    ax.extract_from_text("same", text_format=Tiny)
    second = ax.extract_from_text("same", text_format=Tiny)
    assert client.messages.create.call_count == 1
    assert second["usage_cost"]["joblib_cache_hit"] is True
    assert second["usage_cost"]["total_cost"] == 0.0


def test_repair_retry_sends_validation_error_and_records_it(client):
    client.messages.create.side_effect = [_response('{"relevance": 3}', inp=100, out=10), _response(GOOD, inp=200, out=20)]
    result = ax.extract_from_text("x", text_format=Tiny)
    assert client.messages.create.call_count == 2
    retry_messages = client.messages.create.call_args.kwargs["messages"]
    assert retry_messages[1]["role"] == "assistant"
    assert "failed schema validation" in retry_messages[2]["content"]
    assert result["usage_cost"]["validation_retries"] == 1
    assert result["usage_cost"]["validation_failed"] is False
    assert result["usage_cost"]["uncached_input_tokens"] == 300  # both calls are billed


def test_second_validation_failure_raises_with_cost(client):
    client.messages.create.return_value = _response("not json")
    with pytest.raises(ax.ClaudeValidationError) as exc:
        ax.extract_from_text("x", text_format=Tiny)
    assert client.messages.create.call_count == 2
    assert exc.value.usage_cost["validation_failed"] is True
    assert exc.value.usage_cost["total_cost"] > 0


def test_max_tokens_stop_raises(client):
    client.messages.create.return_value = _response("{", stop="max_tokens")
    with pytest.raises(RuntimeError, match="max_tokens"):
        ax.extract_from_text("x", text_format=Tiny)


def test_structured_output_option_sends_json_schema_format(client):
    ax.extract_from_text("x", text_format=Tiny, structured_output=True, reasoning={"effort": "low"})
    kwargs = client.messages.create.call_args.kwargs
    assert kwargs["output_config"]["effort"] == "low"
    assert kwargs["output_config"]["format"]["type"] == "json_schema"
    assert "properties" in kwargs["output_config"]["format"]["schema"]
    assert "JSON schema" not in kwargs["system"][0]["text"]


def _manifest(pdf=None, n=3):
    return DataPaperManifest(
        records=[
            DataPaperRecord(gt_record_id=i, source="dryad", title=f"t{i}", abstract=f"abstract number {i}",
                            source_doi=f"10.1/{i}", pdf_local_path=str(pdf) if pdf else None)
            for i in range(1, n + 1)
        ]
    )


def test_run_manifest_extraction_routes_claude_and_reports_failure_rate(client, pdf):
    client.messages.create.side_effect = [
        _response(GOOD), _response("bad"), _response("bad"),  # record 1 ok, record 2 fails after retry
    ]
    for mode in (ExtractionMode.ABSTRACT,):
        artifact = run_manifest_extraction(
            _manifest(n=2), mode=mode, config=ExtractionConfig(model="claude-haiku-5-5", text_format=Tiny),
            skip_cache=True,
        )
    statuses = [r.status for r in artifact.records]
    assert statuses == ["success", "error"]
    stats = validation_stats(artifact.records)
    assert stats["failed"] == 1 and stats["records_with_usage"] == 2 and stats["failure_rate"] == 0.5
    assert artifact.records[1].usage_cost["validation_failed"] is True


@pytest.mark.parametrize("mode,method", [(ExtractionMode.PDF_NATIVE, "pdf_native"), (ExtractionMode.PDF_TEXT, "pdf_text")])
def test_pdf_modes_route_to_claude(client, pdf, mode, method):
    artifact = run_manifest_extraction(
        _manifest(pdf, n=1), mode=mode, config=ExtractionConfig(model="claude-haiku-5-5", text_format=Tiny),
        skip_cache=True,
    )
    assert artifact.records[0].status == "success"
    assert artifact.records[0].extraction_method == method


def test_estimate_skips_cached_records_and_prices_tokens(client):
    config = ExtractionConfig(model="claude-haiku-5-5", text_format=Tiny)
    manifest = _manifest(n=3)
    run_manifest_extraction(DataPaperManifest(records=manifest.records[:1]), mode="abstract", config=config)
    est = estimate_run_cost(manifest, mode="abstract", config=config, assumed_output_tokens=1000)
    assert est["already_cached"] == 1 and est["to_call"] == 2
    assert est["input_tokens"] == 2000  # count_tokens mocked at 1000 per record
    # 2000 * 0.10/M + 2000 output * 0.50/M
    assert est["estimated_cost_usd"] == pytest.approx(0.0012)


def test_max_cost_aborts_before_any_extraction_call(client, tmp_path):
    client.messages.count_tokens.return_value = SimpleNamespace(input_tokens=1_000_000)
    manifest = _manifest(n=2).records
    gt = [{"gt_record_id": 1}, {"gt_record_id": 2}]
    with pytest.raises(CostLimitExceeded):
        run_eval(
            mode="abstract", manifest=manifest, gt=gt, model="claude-haiku-5-5", text_format=Tiny,
            max_cost_usd=0.01, output_path=tmp_path / "run.json",
        )
    client.messages.create.assert_not_called()


def test_estimate_only_returns_without_calls(client, tmp_path):
    result = run_eval(
        mode="abstract", manifest=_manifest(n=2).records, gt=[{"gt_record_id": 1}], model="claude-haiku-5-5",
        text_format=Tiny, estimate_only=True, output_path=tmp_path / "run.json",
    )
    assert result is None
    client.messages.create.assert_not_called()
