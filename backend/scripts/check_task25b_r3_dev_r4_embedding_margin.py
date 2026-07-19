from __future__ import annotations

import argparse
import hashlib
import math
import statistics

from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models import MaintenanceSemanticAnchor, RetrievalEvaluationCase
from app.services.embedding_service import EmbeddingService
from app.services.semantic_unit_retrieval_service import SemanticUnitRetrievalService
from task25b_r3_dev_r4_common import DATASET_VERSION, OUT, R4_PARTITION, now_iso, read_json, sha256_text, write_json


def cosine(left: list[float], right: list[float]) -> float:
    denominator = math.sqrt(sum(value * value for value in left)) * math.sqrt(sum(value * value for value in right))
    return sum(a * b for a, b in zip(left, right)) / denominator if denominator else 0.0


def stable_pick(items: list[dict], seed: str) -> dict:
    return sorted(items, key=lambda item: hashlib.sha256(f"{seed}|{item['semantic_unit_id']}".encode()).hexdigest())[0]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-real-api", action="store_true")
    args = parser.parse_args()
    if not args.allow_real_api:
        raise SystemExit("real text-embedding-v4 requires explicit --allow-real-api")
    settings = get_settings()
    if settings.EMBEDDING_MODEL != "text-embedding-v4" or settings.EMBEDDING_DIM != 1024:
        raise SystemExit("embedding configuration must remain text-embedding-v4/1024")
    units_payload = read_json(OUT / "semantic_units.json")
    units = units_payload.get("units") or []
    by_id = {unit["semantic_unit_id"]: unit for unit in units}
    if not units or len(by_id) != len(units):
        raise SystemExit("semantic unit artifact is missing or contains duplicate IDs")
    with SessionLocal() as db:
        cases = list(db.scalars(select(RetrievalEvaluationCase).where(
            RetrievalEvaluationCase.metadata_json["dataset_version"].as_string() == DATASET_VERSION,
            RetrievalEvaluationCase.metadata_json["is_vector_heavy"].as_boolean() == True,
            RetrievalEvaluationCase.dataset_split.in_(("train", "dev")),
        ).order_by(RetrievalEvaluationCase.name)))[:60]
        anchors = list(db.scalars(select(MaintenanceSemanticAnchor).where(
            MaintenanceSemanticAnchor.namespace == R4_PARTITION,
            MaintenanceSemanticAnchor.semantic_representation_version == "task25b_r3_dev_r4_semantic_unit_v1",
        )))
    anchor_texts = {
        (str(((anchor.semantic_fields or {}).get("semantic_unit") or {}).get("semantic_unit_id")), anchor.anchor_type): anchor.anchor_text
        for anchor in anchors
    }
    if len(cases) < 40:
        raise SystemExit(f"at least 40 vector-heavy train/dev cases are required; found {len(cases)}")

    pair_rows: list[dict] = []
    texts: dict[str, str] = {}
    for case in cases:
        metadata = case.metadata_json or {}
        expected_ids = metadata.get("expected_semantic_unit_ids") or []
        positive = by_id.get(str(expected_ids[0])) if expected_ids else None
        if positive is None:
            raise SystemExit(f"case {case.id} has no valid expected semantic unit")
        _, requested_types = SemanticUnitRetrievalService.classify_intent(case.query_text)
        positive_anchor_type = next(
            (
                anchor_type for anchor_type in requested_types
                if (positive["semantic_unit_id"], anchor_type) in anchor_texts
                and sum(key[1] == anchor_type for key in anchor_texts) > 1
            ),
            next((value for value in (positive.get("anchor_types") or []) if sum(key[1] == value for key in anchor_texts) > 1), ""),
        )
        if (positive["semantic_unit_id"], positive_anchor_type) not in anchor_texts:
            raise SystemExit(f"case {case.id} expected unit has no typed anchor")
        others = [
            unit for unit in units
            if unit["semantic_unit_id"] != positive["semantic_unit_id"]
            and (unit["semantic_unit_id"], positive_anchor_type) in anchor_texts
        ]
        same_product = [unit for unit in others if unit.get("product_family") == positive.get("product_family")]
        positive_components = set(positive.get("component_terms") or [])
        same_component = [unit for unit in others if positive_components.intersection(unit.get("component_terms") or [])]
        product_negative = stable_pick(same_product or others, f"{case.id}|product")
        component_negative = stable_pick(same_component or same_product or others, f"{case.id}|component")
        random_negative = stable_pick(others, f"{case.id}|random")
        query_key = f"q:{case.id}"
        texts[query_key] = case.query_text
        for label, unit in (("positive", positive), ("same_product", product_negative),
                            ("same_component", component_negative), ("random", random_negative)):
            texts.setdefault(
                f"u:{unit['semantic_unit_id']}:{positive_anchor_type}",
                anchor_texts[(unit["semantic_unit_id"], positive_anchor_type)],
            )
        pair_rows.append({
            "case_id": str(case.id), "query_key": query_key,
            "positive_unit_id": positive["semantic_unit_id"],
            "anchor_type": positive_anchor_type,
            "same_product_unit_id": product_negative["semantic_unit_id"],
            "same_component_unit_id": component_negative["semantic_unit_id"],
            "random_unit_id": random_negative["semantic_unit_id"],
            "query_hash": sha256_text(case.query_text),
        })

    ordered = list(texts.items())
    result = EmbeddingService(allow_real_api=True).embed_texts(
        [text for _, text in ordered], provider=settings.EMBEDDING_PROVIDER,
    )
    vectors = {key: vector for (key, _), vector in zip(ordered, result.vectors)}
    for row in pair_rows:
        query_vector = vectors[row.pop("query_key")]
        anchor_type = row["anchor_type"]
        positive = cosine(query_vector, vectors[f"u:{row['positive_unit_id']}:{anchor_type}"])
        product = cosine(query_vector, vectors[f"u:{row['same_product_unit_id']}:{anchor_type}"])
        component = cosine(query_vector, vectors[f"u:{row['same_component_unit_id']}:{anchor_type}"])
        random = cosine(query_vector, vectors[f"u:{row['random_unit_id']}:{anchor_type}"])
        hard = max(product, component, random)
        row.update({
            "positive_similarity": round(positive, 6),
            "same_product_similarity": round(product, 6),
            "same_component_similarity": round(component, 6),
            "random_negative_similarity": round(random, 6),
            "hard_negative_similarity": round(hard, 6),
            "positive_margin": round(positive - hard, 6),
        })
    positives = [row["positive_similarity"] for row in pair_rows]
    negatives = [row["hard_negative_similarity"] for row in pair_rows]
    margins = [row["positive_margin"] for row in pair_rows]
    summary = {
        "cases": len(pair_rows),
        "average_positive_similarity": round(statistics.fmean(positives), 6),
        "average_hard_negative_similarity": round(statistics.fmean(negatives), 6),
        "average_positive_margin": round(statistics.fmean(margins), 6),
        "median_positive_margin": round(statistics.median(margins), 6),
        "non_positive_count": sum(value <= 0 for value in margins),
        "non_positive_ratio": round(sum(value <= 0 for value in margins) / len(margins), 6),
    }
    checks = {
        "average_margin_at_least_0_05": summary["average_positive_margin"] >= 0.05,
        "median_margin_at_least_0_04": summary["median_positive_margin"] >= 0.04,
        "non_positive_ratio_at_most_0_10": summary["non_positive_ratio"] <= 0.10,
        "positive_above_hard_negative_on_average": summary["average_positive_similarity"] > summary["average_hard_negative_similarity"],
        "dimension_1024": result.dimension == 1024,
        "full_vectors_persisted": False,
    }
    payload = {
        "generated_at": now_iso(), "dataset": DATASET_VERSION, "split": "train+dev",
        "embedding_model": result.model, "embedding_dimension": result.dimension,
        "summary": summary, "checks": checks, "passed": all(checks.values()),
        "status": "MARGIN_GATE_PASSED" if all(checks.values()) else "MARGIN_GATE_FAILED",
        "rows": pair_rows,
    }
    write_json("embedding_margin.json", payload)
    print({"status": payload["status"], **summary})
    if not payload["passed"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
