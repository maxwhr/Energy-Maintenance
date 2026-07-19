from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from build_task28a_source_inventory import DEFAULT_JSON
from migrate_task28a_corpus import files_match, safe_relative_path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
CORPUS_ROOT = PROJECT_ROOT / "knowledge_assets" / "competition_corpus_v1"
KNOWLEDGE_MANIFEST = CORPUS_ROOT / "manifests" / "knowledge_import_manifest.json"
ANNOTATIONS_ROOT = CORPUS_ROOT / "annotations"


def test_inventory_contract_and_hashes_are_complete() -> None:
    inventory = json.loads(DEFAULT_JSON.read_text(encoding="utf-8"))
    assert inventory["file_count"] == 167
    assert inventory["readable_files"] == inventory["file_count"]
    assert inventory["duplicate_files"] == 3
    assert len(inventory["records"]) == inventory["file_count"]
    assert all(len(record["sha256"]) == 64 for record in inventory["records"])
    assert all(record["relative_path"] and record["absolute_source_path"] for record in inventory["records"])
    assert inventory["category_counts"] == {
        "FAULT_IMAGE": 144,
        "HUAWEI_DOCUMENT": 11,
        "OS_METADATA": 2,
        "SUNGROW_FUTURE_DOCUMENT": 10,
    }


@pytest.mark.parametrize("value", ["../escape.txt", "/absolute.txt", "C:/escape.txt", "folder/../../escape"])
def test_migration_rejects_unsafe_relative_paths(value: str) -> None:
    with pytest.raises(ValueError):
        safe_relative_path(value)


def test_migration_hash_verification_detects_changes(tmp_path: Path) -> None:
    source = tmp_path / "sample.txt"
    source.write_bytes(b"task28a verified content")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    assert files_match(source, expected_size=24, expected_sha256=digest)
    source.write_bytes(b"task28a changed content")
    assert not files_match(source, expected_size=24, expected_sha256=digest)


def test_knowledge_manifest_keeps_manufacturers_and_media_isolated() -> None:
    manifest = json.loads(KNOWLEDGE_MANIFEST.read_text(encoding="utf-8"))
    documents = manifest["documents"]
    media_assets = manifest["media_assets"]

    assert manifest["counts"] == {
        "documents": 21,
        "huawei_documents": 11,
        "sungrow_future_documents": 10,
        "media_assets": 144,
        "excluded_assets": 2,
        "preflight_failures": 0,
    }
    assert all(
        document["parse_preflight"]["status"] in {"sample_extracted", "empty_sample_review_required"}
        for document in documents
    )
    assert all(document["parse_preflight"]["error"] is None for document in documents)

    huawei_documents = [item for item in documents if item["manufacturer_normalized"] == "huawei"]
    sungrow_documents = [item for item in documents if item["manufacturer_normalized"] == "sungrow"]
    assert len(huawei_documents) == 11
    assert len(sungrow_documents) == 10
    assert all(item["scope"] == "huawei_sun2000_competition_v1" for item in huawei_documents)
    assert all(item["review_status"] == "pending_review" for item in huawei_documents)
    assert sum(item["is_formal_retrieval_candidate"] is True for item in huawei_documents) == 10
    assert all(item["scope"] == "future_sungrow_scope" for item in sungrow_documents)
    assert all(item["review_status"] == "pending_review" for item in sungrow_documents)
    assert all(item["is_formal_retrieval_candidate"] is False for item in sungrow_documents)
    assert sum(item["selected_for_test_import"] is True for item in huawei_documents) == 10
    assert sum(item["selected_for_test_import"] is True for item in sungrow_documents) == 5
    aliases = [item for item in documents if item["alias_of_relative_path"]]
    assert len(aliases) == 1
    assert aliases[0]["extension"] == ".md"
    assert aliases[0]["source_type"] == "derived_text_alias"
    assert aliases[0]["selected_for_test_import"] is False
    assert all(
        item["detected_document_version"] is None or any(char.isdigit() for char in item["detected_document_version"])
        for item in documents
    )
    assert all(item["extension"] not in {".jpg", ".jpeg", ".png", ".jp2"} for item in documents)
    assert len(media_assets) == 144


@pytest.mark.parametrize(
    ("annotation_name", "case_id", "expected_sha256"),
    [
        (
            "fault_case_01.json",
            "FAULT_CASE_01_PV_ISOLATION_LOW",
            "b53eaf6b6b24bee90955bea0a78cc1ab43a61b450196ca261ae5b378dc1d0c88",
        ),
        (
            "fault_case_02.json",
            "FAULT_CASE_02_GRID_VOLTAGE_OUT_OF_RANGE",
            "81866ff465368f376bbbf69759693096b37a080e320bc370585a51359f158572",
        ),
    ],
)
def test_fault_annotations_are_traceable_without_claiming_ocr(
    annotation_name: str,
    case_id: str,
    expected_sha256: str,
) -> None:
    annotation = json.loads((ANNOTATIONS_ROOT / annotation_name).read_text(encoding="utf-8"))
    raw_path = Path(annotation["image_project_path"])

    assert annotation["case_id"] == case_id
    assert annotation["image_sha256"] == expected_sha256
    assert hashlib.sha256(raw_path.read_bytes()).hexdigest() == expected_sha256
    assert annotation["ocr_actual_text"] is None
    assert annotation["ocr_status"] == "not_run"
    assert annotation["manual_visual_observation"]["not_an_ocr_result"] is True
    assert annotation["review_status"] == "pending_expert_review"
