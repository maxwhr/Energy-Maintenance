from __future__ import annotations

import argparse
import json
import math
from collections import Counter

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import KnowledgeChunk, KnowledgeDocument, RetrievalEvaluationCase
from app.schemas.retrieval_scope import CHINESE_ENGINEERING_PILOT_SCOPE_ID
from app.services.embedding_service import EmbeddingService
from app.services.retrieval_scope_service import RetrievalScopeService
from task25b_r3_dev_r3_common import SEMANTIC_VERSION, jaccard, normalized, now_iso, terms, text_hash, write_json


DATASET = "task25b_r3_dev_r3_grounded_train_dev_v1"


def cosine(left: list[float], right: list[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    return round(numerator / (left_norm * right_norm), 6) if left_norm and right_norm else 0.0


def semantic_text(chunk: KnowledgeChunk, document: KnowledgeDocument, evidence: dict) -> str:
    metadata = chunk.metadata_json or {}
    source_excerpt = " ".join((chunk.content or "").split())[:360]
    return "\n".join((
        f"产品族：{document.product_series or ''}", f"设备类别：{document.device_type or ''}",
        f"章节：{chunk.section_title or ''}", f"部件：{'、'.join(evidence.get('components') or [])}",
        f"处理动作：{'、'.join(evidence.get('actions') or [])}", f"故障主题：{'、'.join(evidence.get('themes') or [])}",
        f"安全要求：{'是' if 'safety' in (evidence.get('themes') or []) else ''}",
        f"原文摘要：{source_excerpt}", f"定位：页{chunk.page_number or ''}",
        f"版本：{SEMANTIC_VERSION}", f"来源哈希：{text_hash(chunk.content)}",
    ))


def section_summary(chunk: KnowledgeChunk, document: KnowledgeDocument) -> str:
    return "\n".join((
        f"产品族：{document.product_series or ''}", f"文档类型：{document.document_type or ''}",
        f"章节：{chunk.section_title or ''}", f"页码：{chunk.page_number or ''}",
    ))


def _choose_negatives(
    *, case: RetrievalEvaluationCase, expected: KnowledgeChunk, document: KnowledgeDocument,
    scoped: list[tuple[KnowledgeChunk, KnowledgeDocument]],
) -> dict[str, KnowledgeChunk]:
    expected_id = str(expected.id)
    others = [(chunk, doc) for chunk, doc in scoped if str(chunk.id) != expected_id]
    same_device = [item for item in others if item[1].product_series == document.product_series]
    themes = ((case.metadata_json or {}).get("grounding_evidence") or {}).get("themes") or []
    theme_terms = {"communication": ("通信", "rs485", "modbus", "网络"), "safety": ("警告", "危险", "防护", "接地"), "fault": ("告警", "故障", "异常")}
    family = [item for item in others if any(term.lower() in item[0].content.lower() for theme in themes for term in theme_terms.get(theme, ()))]
    query_terms = terms(case.query_text)
    keyword_overlap = sorted(others, key=lambda item: jaccard(query_terms, terms(item[0].content)), reverse=True)
    def pick(values: list[tuple[KnowledgeChunk, KnowledgeDocument]], salt: str) -> KnowledgeChunk:
        values = values or others
        return min(values, key=lambda item: text_hash(f"{case.id}:{salt}:{item[0].id}"))[0]
    return {
        "same_device": pick(same_device, "same_device"),
        "same_fault_family": pick(family, "same_fault"),
        "random": pick(others, "random"),
        "keyword_overlap": keyword_overlap[0][0] if keyword_overlap else pick(others, "keyword"),
    }


def classify(averages: dict[str, float]) -> tuple[str, float]:
    semantic_delta = float(averages["query_to_semantic_text_similarity"]) - float(averages["query_to_raw_chunk_similarity"])
    raw_margin = float(averages["positive_margin_raw"])
    semantic_margin = float(averages["positive_margin_semantic"])
    if float(averages["query_to_semantic_text_similarity"]) < 0.30 and float(averages["query_to_raw_chunk_similarity"]) < 0.30:
        return "GROUNDING_OR_LABEL_FAILURE", semantic_delta
    # This is a diagnostic threshold, not a quality gate: a reproducible 0.04 semantic lift
    # and a 0.04 positive-margin lift indicate raw long-chunk dilution.
    if semantic_delta >= 0.04 and semantic_margin >= raw_margin + 0.04:
        return "RAW_CHUNK_REPRESENTATION_DILUTION", semantic_delta
    if semantic_margin < 0.05:
        return "EMBEDDING_SEPARABILITY_WEAK", semantic_delta
    return "EMBEDDING_PAIR_SEPARABLE", semantic_delta


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-real-api", action="store_true")
    parser.add_argument("--limit", type=int, default=40)
    parser.add_argument("--reuse-existing", action="store_true")
    args = parser.parse_args()
    if args.reuse_existing:
        path = __import__("pathlib").Path(__file__).resolve().parents[2] / ".runtime" / "task25b_r3_dev_r3" / "embedding_pair_diagnostics.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        diagnosis, delta = classify(payload["averages"])
        payload["primary_diagnosis"] = diagnosis
        payload["semantic_minus_raw"] = round(delta, 6)
        payload["reclassified_at"] = now_iso()
        payload["reclassification_used_no_external_api"] = True
        write_json("embedding_pair_diagnostics.json", payload)
        print({"status": "PASSED_REUSED", "pairs": payload["pairs"], "primary_diagnosis": diagnosis})
        return
    if not args.allow_real_api or args.limit < 40:
        raise SystemExit("requires --allow-real-api and at least 40 grounded train/dev pairs")
    with SessionLocal() as db:
        scope = RetrievalScopeService(db).resolve(CHINESE_ENGINEERING_PILOT_SCOPE_ID, pilot_required=True)
        cases = list(db.scalars(select(RetrievalEvaluationCase).where(
            RetrievalEvaluationCase.metadata_json["dataset_version"].as_string() == DATASET,
            RetrievalEvaluationCase.dataset_split.in_(("train", "dev")),
            RetrievalEvaluationCase.metadata_json["is_vector_heavy"].as_boolean().is_(True),
        ).order_by(RetrievalEvaluationCase.dataset_split, RetrievalEvaluationCase.name).limit(args.limit)))
        if len(cases) < 40:
            raise SystemExit(f"only {len(cases)} grounded candidates available")
        expected_ids = {str(case.expected_chunk_ids[0]) for case in cases}
        chunks = {str(chunk.id): chunk for chunk in db.scalars(select(KnowledgeChunk).where(KnowledgeChunk.id.in_(expected_ids)))}
        doc_ids = {chunk.document_id for chunk in chunks.values()}
        documents = {doc.id: doc for doc in db.scalars(select(KnowledgeDocument).where(KnowledgeDocument.id.in_(doc_ids)))}
        scoped = list(db.execute(select(KnowledgeChunk, KnowledgeDocument).join(KnowledgeDocument).where(
            KnowledgeDocument.id.in_(scope.allowed_document_ids), KnowledgeChunk.status == "active",
        )))
        pairs = []
        text_pool: dict[str, str] = {}
        for case in cases:
            expected = chunks[str(case.expected_chunk_ids[0])]
            document = documents[expected.document_id]
            evidence = (case.metadata_json or {}).get("grounding_evidence") or {}
            negatives = _choose_negatives(case=case, expected=expected, document=document, scoped=scoped)
            texts = {
                "query": case.query_text, "raw": expected.content, "section": section_summary(expected, document),
                "semantic": semantic_text(expected, document, evidence),
                **{f"negative_{name}": chunk.content for name, chunk in negatives.items()},
            }
            hashes = {name: text_hash(value) for name, value in texts.items()}
            text_pool.update({digest: texts[name] for name, digest in hashes.items()})
            pairs.append({"case": case, "expected": expected, "document": document, "evidence": evidence, "negatives": negatives, "hashes": hashes})
    embedding = EmbeddingService(allow_real_api=True)
    status = embedding.status()
    if status["status"] != "available" or status["embedding_model"] != "text-embedding-v4" or status["embedding_dimension"] != 1024:
        raise SystemExit({"embedding_status": status, "reason": "real text-embedding-v4 is required"})
    ordered_hashes = sorted(text_pool)
    embedded = embedding.embed_texts([text_pool[digest] for digest in ordered_hashes])
    vectors = dict(zip(ordered_hashes, embedded.vectors))
    rows = []
    for pair in pairs:
        hashes = pair["hashes"]
        query_vector = vectors[hashes["query"]]
        scores = {name: cosine(query_vector, vectors[digest]) for name, digest in hashes.items() if name != "query"}
        negatives = [scores[name] for name in scores if name.startswith("negative_")]
        hard_negative = max(scores["negative_same_device"], scores["negative_same_fault_family"])
        rows.append({
            "case_id": str(pair["case"].id), "query_text_hash": hashes["query"], "source_chunk_id": str(pair["expected"].id),
            "source_chunk_hash": hashes["raw"], "section_hash": hashes["section"], "semantic_text_hash": hashes["semantic"],
            "query_to_raw_chunk_similarity": scores["raw"], "query_to_section_similarity": scores["section"],
            "query_to_semantic_text_similarity": scores["semantic"], "query_to_hard_negative_similarity": hard_negative,
            "query_to_random_negative_similarity": scores["negative_random"], "query_to_keyword_overlap_negative_similarity": scores["negative_keyword_overlap"],
            "positive_margin_raw": round(scores["raw"] - hard_negative, 6),
            "positive_margin_section": round(scores["section"] - hard_negative, 6),
            "positive_margin_semantic": round(scores["semantic"] - hard_negative, 6),
            "model": embedded.model, "dimension": embedded.dimension, "vectors_exported": False,
        })
    avg = lambda field: round(sum(float(row[field]) for row in rows) / len(rows), 6)
    averages = {field: avg(field) for field in (
        "query_to_raw_chunk_similarity", "query_to_section_similarity", "query_to_semantic_text_similarity",
        "query_to_hard_negative_similarity", "query_to_random_negative_similarity", "positive_margin_raw",
        "positive_margin_section", "positive_margin_semantic",
    )}
    diagnosis, semantic_delta = classify(averages)
    payload = {
        "generated_at": now_iso(), "dataset": DATASET, "split": "train+dev", "test_v3_used": False,
        "pairs": len(rows), "embedding_model": embedded.model, "embedding_dimension": embedded.dimension,
        "averages": averages, "semantic_minus_raw": round(semantic_delta, 6), "primary_diagnosis": diagnosis,
        "rows": rows, "vectors_exported": False,
    }
    write_json("embedding_pair_diagnostics.json", payload)
    write_json("embedding_score_distributions.json", {
        "generated_at": now_iso(), "pairs": len(rows), "primary_diagnosis": diagnosis,
        "distributions": {field: sorted(float(row[field]) for row in rows) for field in (
            "query_to_raw_chunk_similarity", "query_to_section_similarity", "query_to_semantic_text_similarity",
            "query_to_hard_negative_similarity", "positive_margin_raw", "positive_margin_semantic",
        )}, "vectors_exported": False,
    })
    print({"status": "PASSED", "pairs": len(rows), "primary_diagnosis": diagnosis, "averages": payload["averages"]})


if __name__ == "__main__":
    main()
