from __future__ import annotations

from app.services.citation_validation_service import CitationValidationResult


class CitationBatchBuilderService:
    """Builds citation validity from request-hydrated, scope-filtered candidates."""

    def validate_candidates(self, candidates: list, *, scope) -> CitationValidationResult:
        valid_ids: list[str] = []
        invalid_ids: list[str] = []
        reasons: dict[str, str] = {}
        source_types: dict[str, str] = {}
        for item in candidates:
            chunk = item.chunk
            document = item.document
            chunk_id = str(item.chunk_id)
            metadata = document.metadata_json or {}
            if hasattr(chunk, "content") and not str(chunk.content or "").strip():
                invalid_ids.append(chunk_id)
                reasons[chunk_id] = "empty_chunk_content"
                continue
            in_scope = (
                bool(item.scope_validation_passed)
                and document.id in scope.allowed_document_ids
                and document.review_status == scope.required_document_status
                and chunk.status == scope.required_chunk_status
                and document.status == "active"
                and document.parse_status == "parsed"
                and (not scope.normalized_language or metadata.get("normalized_language") == scope.normalized_language)
                and (not scope.approved_for_pilot or (
                    metadata.get("approved_for_pilot") is True
                    and metadata.get("engineering_approved_for_pilot") is True
                ))
                and (scope.include_alternate_language or metadata.get("is_alternate_language") is not True)
                and (scope.include_test_fixture or metadata.get("is_test_fixture") is not True)
                and (scope.include_marketing or (
                    metadata.get("marketing_only") is not True
                    and metadata.get("quality_status") != "MARKETING_ONLY"
                ))
            )
            if not in_scope:
                invalid_ids.append(chunk_id)
                reasons[chunk_id] = "scope_or_status_mismatch"
                continue
            locator = item.source_locator or (chunk.metadata_json or {}).get("source_locator") or {}
            source_url = str(metadata.get("source_url") or document.source or "")
            is_html = document.source_type == "vendor_official_html" or (
                source_url.lower().startswith(("http://", "https://")) and not source_url.lower().endswith(".pdf")
            )
            if is_html:
                valid_locator = bool(source_url and (
                    locator.get("heading") or locator.get("heading_path") or locator.get("html_anchor")
                    or locator.get("section") or chunk.section_title
                ))
                source_types[chunk_id] = "HTML"
                failure = "missing_html_url_or_section_locator"
            else:
                section_locator = (
                    locator.get("section")
                    or locator.get("heading_path")
                    or chunk.section_title
                )
                # Some vendor PDFs have reliable page extraction but no recoverable
                # heading path. The parent title and page form a traceable locator
                # without inventing a section or weakening scope/status checks.
                document_title_fallback = str(getattr(document, "title", "") or "").strip()
                valid_locator = bool(
                    (locator.get("page_start") or locator.get("page_number") or chunk.page_number)
                    and (section_locator or document_title_fallback)
                )
                source_types[chunk_id] = "PDF"
                failure = "missing_pdf_page_or_section_locator"
            if valid_locator:
                valid_ids.append(chunk_id)
            else:
                invalid_ids.append(chunk_id)
                reasons[chunk_id] = failure
        coverage = len(valid_ids) / len(candidates) if candidates else 0.0
        return CitationValidationResult(
            citation_valid=bool(valid_ids),
            citation_coverage=round(coverage, 4),
            invalid_reference_ids=list(dict.fromkeys(invalid_ids)),
            invalid_reference_reasons=reasons,
            scope_mismatch_count=sum(value == "scope_or_status_mismatch" for value in reasons.values()),
            grounded_warning=None if valid_ids else "No definitive maintenance conclusion may be presented without valid approved sources; human confirmation is required.",
            valid_reference_ids=valid_ids,
            citation_validity_ratio=round(coverage, 4),
            citation_coverage_ratio=round(coverage, 4),
            source_type_by_reference=source_types,
        )
