"""Tests for eval viewer note-file placement and metadata fallbacks."""

from pathlib import Path

from llm_metadata.app.app_eval_viewer import (
    _description_from_payload,
    _ensure_notes_file,
    _notes_path,
    _reasoning_effort_from_payload,
)


def test_notes_path_is_next_to_run_artifact(tmp_path):
    run_path = tmp_path / "nested" / "demo_run.json"
    expected = tmp_path / "nested" / "demo_run_notes.md"

    assert _notes_path(run_path) == expected


def test_ensure_notes_file_creates_sibling_of_run_artifact(tmp_path):
    run_path = tmp_path / "runs" / "demo_run.json"
    meta = {
        "prompt_module": "prompts.abstract",
        "model": "gpt-5-mini",
        "reasoning_effort": "medium",
        "created_at": "2026-04-01T10:00:00+00:00",
    }

    notes_path = _ensure_notes_file(run_path, meta)

    assert notes_path == run_path.with_name("demo_run_notes.md")
    assert notes_path.exists()
    assert notes_path.parent == run_path.parent

    contents = notes_path.read_text(encoding="utf-8")
    assert "# Notes" in contents
    assert "Reasoning" in contents
    assert str(run_path) in contents or run_path.name in contents
    assert "data/" not in contents


def test_metadata_helpers_fallback_when_cached_artifact_lacks_new_fields():
    class LegacyArtifact:
        pass

    meta = {"description": "Recovered from meta", "reasoning_effort": "medium"}
    artifact = LegacyArtifact()

    assert _description_from_payload(artifact, meta) == "Recovered from meta"
    assert _reasoning_effort_from_payload(artifact, meta) == "medium"
