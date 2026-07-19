from __future__ import annotations

import math


def dcg(grades: list[int], k: int) -> float:
    return sum((2 ** grade - 1) / math.log2(index + 2) for index, grade in enumerate(grades[:k]))


def ndcg(grades: list[int], k: int) -> float:
    ideal = dcg(sorted(grades, reverse=True), k)
    return 0.0 if ideal == 0 else dcg(grades, k) / ideal


def graded_mrr(grades: list[int]) -> float:
    return next((grade / (3.0 * rank) for rank, grade in enumerate(grades, start=1) if grade > 0), 0.0)


def direct_answer_hit(grades: list[int], k: int) -> float:
    return 1.0 if 3 in grades[:k] else 0.0


def requested_information_coverage_at_k(support: list[set[str]], requested: set[str], k: int = 3) -> float:
    if not requested:
        return 1.0
    covered = set().union(*support[:k]) if support[:k] else set()
    return len(covered & requested) / len(requested)
