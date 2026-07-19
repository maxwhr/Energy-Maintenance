from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_semantic_services_do_not_import_benchmark_or_expected_labels() -> None:
    representation = (ROOT / "backend/app/services/maintenance_semantic_representation_service.py").read_text(encoding="utf-8")
    query = (ROOT / "backend/app/services/semantic_query_representation_service.py").read_text(encoding="utf-8")
    assert "RetrievalEvaluationCase" not in representation
    assert "expected_chunk_ids" not in representation
    assert "RetrievalEvaluationCase" not in query
    assert "expected_chunk_ids" not in query

