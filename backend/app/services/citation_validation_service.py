from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urlparse
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import KnowledgeChunk, KnowledgeDocument
from app.repositories.retrieval_repository import RetrievalRepository
from app.schemas.retrieval_scope import RetrievalScope


@dataclass(slots=True)
class CitationValidationResult:
    citation_valid: bool
    citation_coverage: float
    invalid_reference_ids: list[str] = field(default_factory=list)
    invalid_reference_reasons: dict[str, str] = field(default_factory=dict)
    scope_mismatch_count: int = 0
    grounded_warning: str | None = None
    valid_reference_ids: list[str] = field(default_factory=list)
    citation_validity_ratio: float = 0.0
    citation_coverage_ratio: float = 0.0
    source_type_by_reference: dict[str, str] = field(default_factory=dict)


def validate_source_locator(document, chunk, locator: dict) -> tuple[bool, str, str]:
    """Validate a traceable locator without treating every non-HTML source as PDF."""
    metadata = document.metadata_json or {}
    source_url = str(metadata.get("source_url") or document.source or "")
    source_type = str(getattr(document, "source_type", "") or "").lower()
    file_ext = str(getattr(document, "file_ext", "") or metadata.get("file_ext") or "").lower().lstrip(".")
    mime_type = str(metadata.get("mime_type") or "").lower()
    source_path = urlparse(source_url).path.lower()
    is_pdf = file_ext == "pdf" or source_type.endswith("_pdf") or mime_type == "application/pdf" or source_path.endswith(".pdf")
    is_html = source_type == "vendor_official_html" or (
        source_url.lower().startswith(("http://", "https://")) and not is_pdf
    )
    if is_html:
        valid = bool(
            source_url
            and (
                locator.get("heading")
                or locator.get("heading_path")
                or locator.get("html_anchor")
                or locator.get("section")
                or chunk.section_title
            )
        )
        return valid, "HTML", "missing_html_url_or_section_locator"
    if is_pdf:
        section = locator.get("section") or locator.get("heading_path") or chunk.section_title
        title = str(getattr(document, "title", "") or "").strip()
        valid = bool(
            (locator.get("page_start") or locator.get("page_number") or chunk.page_number)
            and (section or title)
        )
        return valid, "PDF", "missing_pdf_page_or_section_locator"

    title = str(getattr(document, "title", "") or "").strip()
    chunk_index = getattr(chunk, "chunk_index", None)
    source_label = file_ext.upper() if file_ext else "DOCUMENT"
    return bool(title and chunk_index is not None), source_label, "missing_document_chunk_locator"


class CitationValidationService:
    def __init__(self, db: Session):
        self.db = db

    def validate(self, references: list, *, candidate_chunk_ids: set[UUID], scope: RetrievalScope | None = None) -> CitationValidationResult:
        reference_ids = [self._value(item, "chunk_id") for item in references]
        parsed_ids: list[UUID] = []
        invalid: list[str] = []
        reasons: dict[str, str] = {}
        valid_ids: set[UUID] = set()
        source_types: dict[str, str] = {}
        seen: set[UUID] = set()
        for raw in reference_ids:
            try:
                chunk_id = UUID(str(raw))
            except (TypeError, ValueError):
                invalid.append(str(raw or "empty"))
                reasons[str(raw or "empty")] = "invalid_chunk_id"
                continue
            if chunk_id in seen:
                continue
            if chunk_id not in candidate_chunk_ids:
                invalid.append(str(chunk_id))
                reasons[str(chunk_id)] = "not_in_final_candidates"
                continue
            seen.add(chunk_id)
            parsed_ids.append(chunk_id)
        if parsed_ids:
            statement = (
                select(KnowledgeChunk, KnowledgeDocument)
                .join(KnowledgeDocument, KnowledgeDocument.id == KnowledgeChunk.document_id)
                .where(
                    KnowledgeChunk.id.in_(parsed_ids), KnowledgeChunk.status == "active",
                    KnowledgeDocument.status == "active", KnowledgeDocument.parse_status == "parsed",
                    KnowledgeDocument.review_status == "approved",
                )
            )
            if scope is not None:
                statement = statement.where(*RetrievalRepository._scope_filters(scope))
            rows = list(self.db.execute(statement))
            for chunk, document in rows:
                locator = (chunk.metadata_json or {}).get("source_locator") or {}
                valid_locator, source_label, failure = validate_source_locator(document, chunk, locator)
                source_types[str(chunk.id)] = source_label
                if not valid_locator:
                    reasons[str(chunk.id)] = failure
                    continue
                valid_ids.add(chunk.id)
            for item in parsed_ids:
                if item not in valid_ids:
                    invalid.append(str(item)); reasons.setdefault(str(item), "scope_or_status_mismatch")
        valid_strings = [str(item) for item in parsed_ids if item in valid_ids]
        coverage = 0.0 if not references else len(valid_strings) / len(references)
        valid = bool(valid_strings)
        return CitationValidationResult(
            citation_valid=valid,
            citation_coverage=round(max(0.0, coverage), 4),
            invalid_reference_ids=list(dict.fromkeys(invalid)),
            invalid_reference_reasons=reasons,
            scope_mismatch_count=sum(reason in {"scope_or_status_mismatch", "not_in_final_candidates"} for reason in reasons.values()),
            grounded_warning=None if valid else "No definitive maintenance conclusion may be presented without valid approved sources; human confirmation is required.",
            valid_reference_ids=valid_strings,
            citation_validity_ratio=round(max(0.0, coverage), 4),
            citation_coverage_ratio=round(max(0.0, coverage), 4),
            source_type_by_reference=source_types,
        )

    @staticmethod
    def _value(item, key: str):
        return item.get(key) if isinstance(item, dict) else getattr(item, key, None)
