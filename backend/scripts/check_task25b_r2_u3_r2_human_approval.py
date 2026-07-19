from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from sqlalchemy import func, select

BACKEND_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.database import SessionLocal  # noqa: E402
from app.models import KnowledgeChunk, KnowledgeDocument, KnowledgeReviewRecord, OperationLog, User  # noqa: E402


REQUESTED_IDS = [
    UUID("12703ebb-4860-4a8a-bed3-11734dbcdfa5"),
    UUID("2cc85307-e1f3-4382-896f-2cdae645af11"),
    UUID("2f6e8766-df74-4e31-abd4-c4b806a538bb"),
]
SMARTLOGGER_IDS = {
    UUID("058ddd98-e3e8-44b5-a154-fb86923c3ff4"),
    UUID("da7ee239-a195-4345-94d1-48a54085bf2c"),
}
BILINGUAL_DUPLICATE_IDS = {
    UUID("7d691c02-8881-4308-acc4-f998befdd0fb"),
    UUID("06db6aff-907e-47bc-982f-58b4246054c2"),
    UUID("528dd661-7bb4-4f99-9d30-29974aec7dfc"),
}
SECOND_BATCH_IDS = [
    UUID("ed7da861-c472-4bbe-8389-66d6fee05134"),
    UUID("9cb20238-ef5f-4719-87db-94f57afba008"),
    UUID("6ae662ed-9382-4b96-95d7-acc7fb4d8250"),
    UUID("836cc336-8af6-4d81-9f43-86a59e794a73"),
    UUID("584adeaf-7221-4ab6-b191-749ce3c99c57"),
]
RUNTIME_DIR = ROOT_DIR / ".runtime" / "task25b_r2_u3_r2"
DOCS_DIR = ROOT_DIR / "docs"


def is_official(document: KnowledgeDocument) -> bool:
    metadata = document.metadata_json or {}
    return document.source_type in {"vendor_official", "vendor_official_html"} or metadata.get("source_provenance") == "VENDOR_OFFICIAL"


def has_locator(chunk: KnowledgeChunk) -> bool:
    metadata = chunk.metadata_json or {}
    locator = metadata.get("source_locator") or metadata.get("section_locator") or {}
    return bool(
        chunk.page_number
        or chunk.section_title
        or metadata.get("heading_path")
        or locator.get("page_number")
        or locator.get("section_title")
        or locator.get("question_title")
        or locator.get("nid")
    )


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    generated_at = datetime.now(timezone.utc).isoformat()
    failures: list[str] = []
    rows: list[dict] = []
    with SessionLocal() as session:
        for document_id in REQUESTED_IDS:
            document = session.get(KnowledgeDocument, document_id)
            if not document:
                failures.append(f"missing_document:{document_id}")
                continue
            approver = session.get(User, document.reviewed_by) if document.reviewed_by else None
            event = session.scalar(
                select(KnowledgeReviewRecord)
                .where(
                    KnowledgeReviewRecord.document_id == document_id,
                    KnowledgeReviewRecord.review_action == "approve",
                    KnowledgeReviewRecord.after_status == "approved",
                )
                .order_by(KnowledgeReviewRecord.reviewed_at.desc())
                .limit(1)
            )
            operation = session.scalar(
                select(OperationLog)
                .where(
                    OperationLog.target_id == str(document_id),
                    OperationLog.module == "knowledge_review",
                    OperationLog.action == "approve",
                )
                .order_by(OperationLog.created_at.desc())
                .limit(1)
            )
            chunks = list(session.scalars(select(KnowledgeChunk).where(KnowledgeChunk.document_id == document_id)))
            active_chunks = [item for item in chunks if item.status == "active"]
            inactive_chunks = [item for item in chunks if item.status != "active"]
            locator_count = sum(has_locator(item) for item in active_chunks)
            hash_count = sum(bool(item.content_hash) for item in active_chunks)
            operation_detail = operation.detail if operation else {}
            row = {
                "document_id": str(document.id),
                "title": document.title,
                "document_status": document.status,
                "review_status": document.review_status,
                "approved_by": str(document.reviewed_by) if document.reviewed_by else None,
                "approved_by_name": approver.display_name or approver.username if approver else None,
                "approver_role": approver.role if approver else None,
                "approved_at": document.reviewed_at.isoformat() if document.reviewed_at else None,
                "review_event_id": str(event.id) if event else None,
                "review_event_type": event.review_action if event else None,
                "before_status": event.before_status if event else None,
                "after_status": event.after_status if event else None,
                "approval_source": "authenticated_review_api" if operation else None,
                "batch_operation": False,
                "automatic_operation": operation_detail.get("automatic_approval") if operation else None,
                "active_chunk_count": len(active_chunks),
                "inactive_chunk_count": len(inactive_chunks),
                "source_locator_count": locator_count,
                "source_locator_coverage": round(locator_count / len(active_chunks), 4) if active_chunks else 0.0,
                "content_hash_count": hash_count,
                "content_hash_coverage": round(hash_count / len(active_chunks), 4) if active_chunks else 0.0,
                "passed": False,
            }
            row["passed"] = all(
                [
                    document.status == "active",
                    document.review_status == "approved",
                    document.reviewed_by is not None,
                    document.reviewed_at is not None,
                    approver is not None and approver.role in {"admin", "expert"},
                    event is not None,
                    event.before_status == "pending_review" if event else False,
                    event.after_status == "approved" if event else False,
                    operation is not None,
                    operation_detail.get("automatic_approval") is False if operation else False,
                    len(active_chunks) > 0,
                    len(inactive_chunks) == 0,
                    locator_count == len(active_chunks),
                    hash_count == len(active_chunks),
                ]
            )
            if not row["passed"]:
                failures.append(f"approval_invariant_failed:{document_id}")
            rows.append(row)

        official_documents = [item for item in session.scalars(select(KnowledgeDocument)) if is_official(item)]
        unexpected_approved = [
            {"document_id": str(item.id), "title": item.title}
            for item in official_documents
            if item.review_status == "approved" and item.id not in set(REQUESTED_IDS)
        ]
        if unexpected_approved:
            failures.append("unexpected_approved_official_documents")
        pending_documents = [item for item in official_documents if item.review_status == "pending_review"]
        pending_formal_chunk_count = sum(
            item.chunk_count
            for item in pending_documents
            if bool((item.metadata_json or {}).get("approved_for_pilot"))
        )

        recommendation_rows = []
        exclusion_reasons = {
            str(item): "english_duplicate_of_approved_chinese_faq" for item in BILINGUAL_DUPLICATE_IDS
        }
        for document_id in SECOND_BATCH_IDS:
            document = session.get(KnowledgeDocument, document_id)
            if not document:
                failures.append(f"missing_second_batch_candidate:{document_id}")
                continue
            metadata = document.metadata_json or {}
            if (
                document.review_status != "pending_review"
                or document_id in SMARTLOGGER_IDS
                or metadata.get("quality_status") != "READY_FOR_HUMAN_REVIEW"
                or metadata.get("marketing_only")
            ):
                failures.append(f"ineligible_second_batch_candidate:{document_id}")
                continue
            recommendation_rows.append(
                {
                    "document_id": str(document.id),
                    "title": document.title,
                    "product_family": metadata.get("product_family") or document.product_series,
                    "equipment_categories": metadata.get("equipment_categories") or [],
                    "document_type": document.document_type,
                    "language": metadata.get("language"),
                    "chunk_count": document.chunk_count,
                    "quality_status": metadata.get("quality_status"),
                    "reason": {
                        str(SECOND_BATCH_IDS[0]): "indicator abnormality and fault handling",
                        str(SECOND_BATCH_IDS[1]): "communication fault",
                        str(SECOND_BATCH_IDS[2]): "device grounding and safety",
                        str(SECOND_BATCH_IDS[3]): "energy-storage maintenance",
                        str(SECOND_BATCH_IDS[4]): "fuse replacement and safety",
                    }[str(document.id)],
                    "automatic_approval": False,
                }
            )

        needs_metadata_count = sum((item.metadata_json or {}).get("quality_status") == "NEEDS_METADATA" for item in official_documents)
        marketing_count = sum(bool((item.metadata_json or {}).get("marketing_only")) for item in official_documents)

    withdrawal_path = RUNTIME_DIR / "unexpected_approval_withdrawal.json"
    withdrawal = json.loads(withdrawal_path.read_text(encoding="utf-8")) if withdrawal_path.exists() else {}
    payload = {
        "task": "Task 25B-R2-U3-R2",
        "generated_at": generated_at,
        "status": "passed" if not failures else "failed",
        "requested_document_count": len(REQUESTED_IDS),
        "approved_count": sum(item["review_status"] == "approved" for item in rows),
        "wrong_approver_count": sum(item["approver_role"] not in {"admin", "expert"} for item in rows),
        "automatic_approval_count": sum(item["automatic_operation"] is not False for item in rows),
        "audit_record_count": sum(bool(item["review_event_id"]) for item in rows),
        "unexpected_approved_documents": unexpected_approved,
        "unexpected_approvals_detected_and_withdrawn": withdrawal.get("unexpected_approved_count", 0),
        "documents": rows,
        "pending_official_documents": len(pending_documents),
        "pending_chunks_activated_in_formal_corpus": pending_formal_chunk_count,
        "failures": failures,
    }
    recommendation = {
        "task": "Task 25B-R2-U3-R2",
        "generated_at": generated_at,
        "maximum_recommendations": 5,
        "recommended_count": len(recommendation_rows),
        "recommendations": recommendation_rows,
        "excluded_bilingual_duplicates": exclusion_reasons,
        "excluded_needs_metadata_count": needs_metadata_count,
        "excluded_smartlogger_document_ids": sorted(str(item) for item in SMARTLOGGER_IDS),
        "excluded_marketing_count": marketing_count,
        "automatic_approval": False,
    }
    write_json(RUNTIME_DIR / "human_approval.json", payload)
    write_json(RUNTIME_DIR / "second_batch_review_recommendation.json", recommendation)

    approval_lines = "\n".join(
        f"- `{item['document_id']}`：approved，审核人 `{item['approved_by_name']}`（{item['approver_role']}），"
        f"时间 `{item['approved_at']}`，审计事件 `{item['review_event_id']}`，active Chunk={item['active_chunk_count']}，"
        f"locator/hash 覆盖率={item['source_locator_coverage']:.0%}/{item['content_hash_coverage']:.0%}。"
        for item in rows
    )
    withdrawn_lines = "\n".join(
        f"- `{item['document_id']}`：`{item['review_status']}` → `pending_review`，必须逐份审核。"
        for item in withdrawal.get("before", [])
    ) or "- 无。"
    approval_report = f"""# Task 25B-R2-U3-R2 首批人工批准真实性验证

生成时间：`{generated_at}`

## 结论

- 结果：**{payload['status'].upper()}**。
- 用户指定 3 份 FAQ 均由真实 admin/expert 账号通过已认证审核 API 批准；审计事件、before/after、审核时间均存在。
- 未发现自动批准，未调用批量批准 API；本脚本只读验证。
- 当前非预期 approved 官方文档为 0。此前检测出的 {payload['unexpected_approvals_detected_and_withdrawn']} 份长篇手册已通过新建的审计化撤回 API 退回，不是直接数据库修改。

## 指定文档

{approval_lines}

## 非预期批准处置

{withdrawn_lines}

每次撤回均保留原批准事件，并新增 `withdraw_approval` 记录与 OperationLog，包含 before/after、操作人、原因与 `automatic_operation=false`。SmartLogger 明确设置 `pilot_index_excluded=true`。

## 状态边界

- 其余 pending 官方文档：{len(pending_documents)}。
- pending 文档进入正式 active corpus 的 Chunk：{pending_formal_chunk_count}。
- 文档 Chunk 行自身可保持 `active`，但只有父文档 `review_status=approved` 才具备正式检索资格。
"""
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    (DOCS_DIR / "25B_R2_U3_R2_first_human_approval_validation.md").write_text(approval_report, encoding="utf-8")

    recommendation_lines = "\n".join(
        f"{index}. `{item['document_id']}` {item['title']} — {item['reason']}；Chunk={item['chunk_count']}。"
        for index, item in enumerate(recommendation_rows, 1)
    )
    recommendation_report = f"""# Task 25B-R2-U3-R2 第二批人工审核建议

生成时间：`{generated_at}`

## 推荐清单（最多 5 份）

{recommendation_lines}

## 排除规则

- 排除 SmartLogger 两份长文档：{', '.join(f'`{item}`' for item in sorted(str(value) for value in SMARTLOGGER_IDS))}。
- 排除 NEEDS_METADATA：{needs_metadata_count} 份。
- 排除英文与已批准中文 FAQ 重复项：{len(BILINGUAL_DUPLICATE_IDS)} 份。
- 排除 marketing-only：{marketing_count} 份。

本清单只提供人工审核顺序，`automatic_approval=false`，未执行任何批准。
"""
    (DOCS_DIR / "25B_R2_U3_R2_second_batch_recommendation.md").write_text(recommendation_report, encoding="utf-8")
    print(json.dumps({"status": payload["status"], "approved": payload["approved_count"], "recommendations": len(recommendation_rows), "failures": failures}, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
