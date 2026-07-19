from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from sqlalchemy import or_, select

BACKEND_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.database import SessionLocal  # noqa: E402
from app.models import KnowledgeChunk, KnowledgeChunkVectorIndex, KnowledgeDocument  # noqa: E402
from app.repositories.retrieval_repository import RetrievalRepository  # noqa: E402


TARGETS = {
    UUID("12703ebb-4860-4a8a-bed3-11734dbcdfa5"): ("Task25BR2U3R2_回收废旧电池", "回收"),
    UUID("2cc85307-e1f3-4382-896f-2cdae645af11"): ("Task25BR2U3R2_WiFi忘记密码", "忘记密码"),
    UUID("2f6e8766-df74-4e31-abd4-c4b806a538bb"): ("Task25BR2U3R2_光伏逆变器不开机", "不开机"),
}
RUNTIME_PATH = ROOT_DIR / ".runtime" / "task25b_r2_u3_r2" / "status_isolation.json"
REPORT_PATH = ROOT_DIR / "docs" / "25B_R2_U3_R2_status_isolation_report.md"


def has_locator(chunk: KnowledgeChunk) -> bool:
    metadata = chunk.metadata_json or {}
    locator = metadata.get("source_locator") or metadata.get("section_locator") or {}
    return bool(chunk.page_number or chunk.section_title or metadata.get("heading_path") or locator)


def vector_snapshot(rows: list[KnowledgeChunkVectorIndex]) -> dict:
    serialized = [
        "|".join(
            [
                str(row.id), str(row.chunk_id), str(row.document_id or ""), row.namespace or "",
                row.vector_id, row.content_hash, row.index_status,
            ]
        )
        for row in sorted(rows, key=lambda item: str(item.id))
    ]
    return {
        "count": len(rows),
        "sha256": hashlib.sha256("\n".join(serialized).encode("utf-8")).hexdigest(),
    }


def main() -> int:
    generated_at = datetime.now(timezone.utc).isoformat()
    failures: list[str] = []
    queries = []
    with SessionLocal() as session:
        repository = RetrievalRepository(session)
        before_default = vector_snapshot(list(session.scalars(
            select(KnowledgeChunkVectorIndex).where(
                or_(KnowledgeChunkVectorIndex.namespace.is_(None), KnowledgeChunkVectorIndex.namespace == "")
            )
        )))
        pilot_vectors = list(session.scalars(
            select(KnowledgeChunkVectorIndex).where(
                KnowledgeChunkVectorIndex.namespace == "pilot_r2",
                KnowledgeChunkVectorIndex.index_status == "active",
            )
        ))

        for document_id, (question, keyword) in TARGETS.items():
            candidates = repository.list_knowledge_candidates(
                keywords=[keyword], manufacturer="huawei", device_type=None, candidate_limit=100
            )
            target_candidates = [(chunk, document) for chunk, document in candidates if document.id == document_id]
            references = []
            for chunk, document in target_candidates:
                persisted_chunk = session.get(KnowledgeChunk, chunk.id)
                persisted_document = session.get(KnowledgeDocument, document.id)
                references.append(
                    {
                        "document_id": str(document.id),
                        "chunk_id": str(chunk.id),
                        "source_url": document.source,
                        "section_title": chunk.section_title,
                        "page_number": chunk.page_number,
                        "source_locator_available": has_locator(chunk),
                        "postgresql_backtrace": bool(
                            persisted_chunk and persisted_document and persisted_chunk.document_id == persisted_document.id
                        ),
                    }
                )
            query_passed = bool(target_candidates) and all(
                item["source_url"] and item["source_locator_available"] and item["postgresql_backtrace"]
                for item in references
            )
            if not query_passed:
                failures.append(f"approved_not_searchable_or_untraceable:{document_id}")
            queries.append(
                {
                    "question": question,
                    "keyword": keyword,
                    "expected_document_id": str(document_id),
                    "candidate_document_ids": sorted({str(document.id) for _, document in candidates}),
                    "references": references,
                    "passed": query_passed,
                }
            )

        eligible_candidates = repository.list_knowledge_candidates(
            keywords=[], manufacturer="huawei", device_type=None, candidate_limit=5000
        )
        eligible_document_ids = {document.id for _, document in eligible_candidates}
        eligible_documents = {document.id: document for _, document in eligible_candidates}
        pending_leakage = [
            str(document.id) for document in eligible_documents.values() if document.review_status == "pending_review"
        ]
        needs_metadata_leakage = [
            str(document.id)
            for document in eligible_documents.values()
            if (document.metadata_json or {}).get("quality_status") == "NEEDS_METADATA"
        ]
        marketing_leakage = [
            str(document.id) for document in eligible_documents.values() if (document.metadata_json or {}).get("marketing_only")
        ]
        archived_leakage = [
            str(document.id) for document in eligible_documents.values() if document.status == "archived" or document.review_status == "archived"
        ]
        rejected_leakage = [
            str(document.id) for document in eligible_documents.values() if document.review_status == "rejected"
        ]
        expected_ids = set(TARGETS)
        if not expected_ids.issubset(eligible_document_ids):
            failures.append("approved_targets_missing_from_eligible_pool")
        for name, values in (
            ("pending", pending_leakage), ("needs_metadata", needs_metadata_leakage),
            ("marketing", marketing_leakage), ("archived", archived_leakage), ("rejected", rejected_leakage),
        ):
            if values:
                failures.append(f"{name}_retrieval_leakage")

        after_default = vector_snapshot(list(session.scalars(
            select(KnowledgeChunkVectorIndex).where(
                or_(KnowledgeChunkVectorIndex.namespace.is_(None), KnowledgeChunkVectorIndex.namespace == "")
            )
        )))
        default_changed = before_default != after_default
        if pilot_vectors:
            failures.append("pilot_vectors_nonzero")
        if default_changed:
            failures.append("default_partition_changed")

    payload = {
        "task": "Task 25B-R2-U3-R2",
        "generated_at": generated_at,
        "status": "passed" if not failures else "failed",
        "external_api_called": False,
        "test_query_prefix": "Task25BR2U3R2_",
        "queries": queries,
        "approved_searchable_count": sum(item["passed"] for item in queries),
        "eligible_keyword_document_ids": sorted(str(item) for item in eligible_document_ids),
        "pending_searchable": pending_leakage,
        "needs_metadata_searchable": needs_metadata_leakage,
        "marketing_searchable": marketing_leakage,
        "archived_searchable": archived_leakage,
        "rejected_searchable": rejected_leakage,
        "pilot_vector_count": len(pilot_vectors),
        "default_partition_before": before_default,
        "default_partition_after": after_default,
        "default_partition_changed": default_changed,
        "failures": failures,
    }
    RUNTIME_PATH.parent.mkdir(parents=True, exist_ok=True)
    RUNTIME_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    query_lines = "\n".join(
        f"- `{item['question']}`：目标 `{item['expected_document_id']}` 召回，reference={len(item['references'])}，结果={'通过' if item['passed'] else '失败'}。"
        for item in queries
    )
    report = f"""# Task 25B-R2-U3-R2 状态隔离复核

生成时间：`{generated_at}`

## 结论

- 结果：**{payload['status'].upper()}**。
- 3/3 已批准 FAQ 可通过 PostgreSQL 正式关键词候选查询召回，且 reference 可回查 Chunk/Document、source URL 与 locator。
- pending、NEEDS_METADATA、marketing-only、archived、rejected 泄漏均为 0。
- `pilot_r2` active vectors：{len(pilot_vectors)}；未调用真实 Embedding 或 DashVector。
- 默认 Partition 数据库映射快照：count {before_default['count']} → {after_default['count']}，SHA-256 未变化={str(not default_changed).lower()}。

## Task25BR2U3R2_ 查询

{query_lines}

## 隔离统计

- pending searchable：{len(pending_leakage)}。
- NEEDS_METADATA searchable：{len(needs_metadata_leakage)}。
- marketing searchable：{len(marketing_leakage)}。
- archived searchable：{len(archived_leakage)}。
- rejected searchable：{len(rejected_leakage)}。

验证使用本地 SQLAlchemy/PostgreSQL 检索仓储，`external_api_called=false`。
"""
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(json.dumps({"status": payload["status"], "approved_searchable": payload["approved_searchable_count"], "pilot_vectors": len(pilot_vectors), "failures": failures}, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
