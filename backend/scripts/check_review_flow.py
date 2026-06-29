from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import KnowledgeDocument, KnowledgeReviewRecord


@dataclass(frozen=True)
class Account:
    username: str
    password: str


class ReviewFlowError(RuntimeError):
    pass


def request_json(
    method: str,
    url: str,
    *,
    token: str | None = None,
    payload: dict | None = None,
) -> tuple[int, dict]:
    body = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8")
            return response.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            parsed = {"message": raw}
        return exc.code, parsed


def upload_markdown(
    base_url: str,
    *,
    token: str,
    title: str,
    content: str,
    manufacturer: str,
    product_series: str,
) -> dict:
    boundary = f"----Task11ABoundary{int(time.time() * 1000)}"
    fields = {
        "manufacturer": manufacturer,
        "product_series": product_series,
        "device_type": "pv_inverter",
        "document_type": "manual",
        "title": title,
        "description": "Task 11A disposable review verification document",
        "source": "Task11A disposable verification",
    }
    parts: list[bytes] = []
    for name, value in fields.items():
        parts.append(f"--{boundary}\r\n".encode("ascii"))
        parts.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"))
        parts.append(str(value).encode("utf-8"))
        parts.append(b"\r\n")
    parts.append(f"--{boundary}\r\n".encode("ascii"))
    filename = f"{title}.md"
    parts.append(
        (
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            "Content-Type: text/markdown; charset=utf-8\r\n\r\n"
        ).encode("utf-8")
    )
    parts.append(content.encode("utf-8"))
    parts.append(b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode("ascii"))
    body = b"".join(parts)
    request = urllib.request.Request(
        f"{base_url}/knowledge/upload",
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise ReviewFlowError(f"Upload failed for {title}: HTTP {exc.code} {raw}") from exc


def login(base_url: str, account: Account) -> str:
    status, response = request_json(
        "POST",
        f"{base_url}/auth/login",
        payload={"username": account.username, "password": account.password},
    )
    if status != 200 or response.get("code") not in {0, 200} or not response.get("data"):
        raise ReviewFlowError(f"Login failed for {account.username}: HTTP {status} {response}")
    return response["data"]["access_token"]


def assert_success(label: str, status: int, response: dict) -> dict:
    if status != 200 or response.get("code") not in {0, 200}:
        raise ReviewFlowError(f"{label} failed: HTTP {status} {response}")
    return response.get("data") or {}


def assert_forbidden(label: str, status: int, response: dict) -> None:
    if status != 403:
        raise ReviewFlowError(f"{label} should be forbidden, got HTTP {status} {response}")


def query_document_state(document_id: str) -> dict:
    db = SessionLocal()
    try:
        document = db.get(KnowledgeDocument, UUID(document_id))
        if not document:
            raise ReviewFlowError(f"Document not found in database: {document_id}")
        records = list(
            db.scalars(
                select(KnowledgeReviewRecord)
                .where(KnowledgeReviewRecord.document_id == document.id)
                .order_by(KnowledgeReviewRecord.reviewed_at.desc())
            )
        )
        return {
            "document_id": str(document.id),
            "title": document.title,
            "review_status": document.review_status,
            "status": document.status,
            "reviewed_by": str(document.reviewed_by) if document.reviewed_by else None,
            "reviewed_at": document.reviewed_at.isoformat() if document.reviewed_at else None,
            "review_comment": document.review_comment,
            "review_record_count": len(records),
            "latest_review_record": {
                "review_action": records[0].review_action,
                "review_comment": records[0].review_comment,
                "before_status": records[0].before_status,
                "after_status": records[0].after_status,
                "reviewer_id": str(records[0].reviewer_id) if records[0].reviewer_id else None,
                "reviewed_at": records[0].reviewed_at.isoformat() if records[0].reviewed_at else None,
                "created_at": records[0].created_at.isoformat() if records[0].created_at else None,
            }
            if records
            else None,
        }
    finally:
        db.close()


def run(base_url: str) -> dict:
    admin = Account(os.getenv("TASK11A_ADMIN_USERNAME", "admin"), os.getenv("TASK11A_ADMIN_PASSWORD", "admin123456"))
    viewer = Account(os.getenv("TASK11A_VIEWER_USERNAME", "viewer_task10"), os.getenv("TASK11A_VIEWER_PASSWORD", "viewer123456"))
    engineer = Account(
        os.getenv("TASK11A_ENGINEER_USERNAME", "engineer_task10"),
        os.getenv("TASK11A_ENGINEER_PASSWORD", "engineer123456"),
    )

    admin_token = login(base_url, admin)
    viewer_token = login(base_url, viewer)
    engineer_token = login(base_url, engineer)

    suffix = time.strftime("%Y%m%d%H%M%S")
    docs = {
        "approve": {
            "title": f"Task11A_Disposable_Approve_Test_{suffix}",
            "manufacturer": "huawei",
            "product_series": "SUN2000",
            "content": (
                "华为 SUN2000 绝缘阻抗低审核测试文档。\n"
                "本文件仅用于 Task 11A 知识审核 approve 接口验收。\n"
                "该文档为一次性测试数据，不作为正式知识库资料。\n"
            ),
            "comment": "Task11A approve verification passed",
            "expected_status": "approved",
            "endpoint": "approve",
        },
        "reject": {
            "title": f"Task11A_Disposable_Reject_Test_{suffix}",
            "manufacturer": "sungrow",
            "product_series": "SG",
            "content": (
                "阳光电源 SG 系列过温审核测试文档。\n"
                "本文件仅用于 Task 11A 知识审核 reject 接口验收。\n"
                "该文档为一次性测试数据，不作为正式知识库资料。\n"
            ),
            "comment": "Task11A reject verification passed",
            "expected_status": "rejected",
            "endpoint": "reject",
        },
        "archive": {
            "title": f"Task11A_Disposable_Archive_Test_{suffix}",
            "manufacturer": "huawei",
            "product_series": "FusionSolar",
            "content": (
                "华为 FusionSolar 通信中断审核测试文档。\n"
                "本文件仅用于 Task 11A 知识审核 archive 接口验收。\n"
                "该文档为一次性测试数据，不作为正式知识库资料。\n"
            ),
            "comment": "Task11A archive verification passed",
            "expected_status": "archived",
            "endpoint": "archive",
        },
    }

    results: dict = {
        "base_url": base_url,
        "accounts": {
            "admin": admin.username,
            "viewer": viewer.username,
            "engineer": engineer.username,
        },
        "documents": {},
        "permission_checks": [],
        "review_list": {},
        "review_details": {},
    }

    for key, doc in docs.items():
        upload_response = upload_markdown(
            base_url,
            token=admin_token,
            title=doc["title"],
            content=doc["content"],
            manufacturer=doc["manufacturer"],
            product_series=doc["product_series"],
        )
        data = assert_success(f"upload {key}", 200, upload_response)
        document_id = data["document_id"]
        results["documents"][key] = {
            "title": doc["title"],
            "document_id": document_id,
            "upload_parse_status": data.get("parse_status"),
            "upload_review_status": data.get("review_status"),
            "chunk_count": data.get("chunk_count"),
        }

    status, list_response = request_json(
        "GET",
        f"{base_url}/review/knowledge?{urllib.parse.urlencode({'keyword': 'Task11A_Disposable', 'page': 1, 'page_size': 20})}",
        token=admin_token,
    )
    list_data = assert_success("review list", status, list_response)
    results["review_list"] = {
        "total": list_data.get("total"),
        "matched_titles": [item["title"] for item in list_data.get("items", []) if "Task11A_Disposable" in item["title"]],
    }

    for role, token in [("viewer", viewer_token), ("engineer", engineer_token)]:
        first_document_id = results["documents"]["approve"]["document_id"]
        status, response = request_json("GET", f"{base_url}/review/knowledge?page=1&page_size=1", token=token)
        assert_success(f"{role} list", status, response)
        status, response = request_json("GET", f"{base_url}/review/knowledge/{first_document_id}", token=token)
        assert_success(f"{role} detail", status, response)
        for action in ("approve", "reject", "archive"):
            status, response = request_json(
                "POST",
                f"{base_url}/review/knowledge/{first_document_id}/{action}",
                token=token,
                payload={"comment": f"Task11A {role} blocked {action}"},
            )
            assert_forbidden(f"{role} {action}", status, response)
            results["permission_checks"].append({"role": role, "action": action, "status": status})

    for key, doc in docs.items():
        document_id = results["documents"][key]["document_id"]
        status, detail_response = request_json("GET", f"{base_url}/review/knowledge/{document_id}", token=admin_token)
        detail_data = assert_success(f"admin detail before {key}", status, detail_response)
        results["review_details"][f"{key}_before"] = {
            "chunk_preview_count": len(detail_data.get("chunk_preview", [])),
            "review_records": len(detail_data.get("review_records", [])),
        }

        payload = {"comment": doc["comment"]}
        if key == "archive" and os.getenv("TASK11A_ARCHIVE_EMPTY_BODY") == "1":
            payload = None
        status, review_response = request_json(
            "POST",
            f"{base_url}/review/knowledge/{document_id}/{doc['endpoint']}",
            token=admin_token,
            payload=payload,
        )
        review_data = assert_success(f"admin {doc['endpoint']}", status, review_response)
        results["documents"][key]["api_review_status"] = review_data["document"].get("review_status")
        results["documents"][key]["api_status"] = review_data["document"].get("status")

        state = query_document_state(document_id)
        if state["review_status"] != doc["expected_status"]:
            raise ReviewFlowError(f"{key} review_status mismatch: {state}")
        if key == "archive" and state["status"] != "archived":
            raise ReviewFlowError(f"archive status mismatch: {state}")
        if not state["reviewed_by"] or not state["reviewed_at"] or state["review_comment"] != doc["comment"]:
            raise ReviewFlowError(f"{key} reviewed_by/reviewed_at/comment mismatch: {state}")
        if state["review_record_count"] < 1 or not state["latest_review_record"]:
            raise ReviewFlowError(f"{key} review record missing: {state}")
        latest = state["latest_review_record"]
        if latest["review_action"] != doc["endpoint"] or latest["after_status"] != doc["expected_status"]:
            raise ReviewFlowError(f"{key} review record state mismatch: {state}")
        if latest["review_comment"] != doc["comment"]:
            raise ReviewFlowError(f"{key} review record comment mismatch: {state}")
        results["documents"][key]["database_state"] = state

        status, detail_response = request_json("GET", f"{base_url}/review/knowledge/{document_id}", token=admin_token)
        detail_data = assert_success(f"admin detail after {key}", status, detail_response)
        results["review_details"][f"{key}_after"] = {
            "review_status": detail_data["document"].get("review_status"),
            "status": detail_data["document"].get("status"),
            "review_records": len(detail_data.get("review_records", [])),
        }

    results["status"] = "passed"
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Task 11A knowledge review flow verification.")
    parser.add_argument("--base-url", default=os.getenv("TASK11A_BASE_URL", "http://127.0.0.1:8000/api"))
    args = parser.parse_args()
    try:
        result = run(args.base_url.rstrip("/"))
    except Exception as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
