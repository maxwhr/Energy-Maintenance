from __future__ import annotations

import json
from typing import Any


class ModelPromptBuilder:
    def build_retrieval_prompt(
        self,
        *,
        question: str,
        answer: str,
        suggested_steps: list[str],
        safety_notes: list[str],
        references: list[Any],
        retrieved_chunks: list[Any] | None = None,
        media_context: list[Any] | None = None,
        kg_context: dict[str, Any] | None = None,
    ) -> str:
        return "\n".join(
            [
                "Task: Polish and structure a PV inverter maintenance QA answer.",
                "Scope: first-version Energy-Maintenance only covers Huawei and Sungrow PV inverters.",
                "Output language: Chinese.",
                "Hard rules:",
                "- Do not invent document titles, sections, page numbers, chunk IDs, sources, or references.",
                "- Do not remove or rewrite the provided references.",
                "- If references are empty, state that the current knowledge base has insufficient traceable evidence.",
                "- Keep electrical safety boundaries: isolation, power-off, voltage verification, PPE, qualified personnel, and manufacturer manuals.",
                "- Do not claim that the system has definitively determined the fault cause.",
                "- Media context contains metadata only. Do not infer image content.",
                "- Images are human-review attachments unless a real OCR result is explicitly present.",
                "- Knowledge graph context is an approved active graph summary only; do not invent graph facts outside it.",
                "- Keep knowledge graph evidence separate from document references.",
                "- Use retrieved chunk content as grounded context; do not add facts outside it.",
                "- Do not include local file paths or binary image data.",
                "",
                "Recommended output structure:",
                "1. Brief judgment",
                "2. Inspection direction",
                "3. Suggested handling steps",
                "4. Safety reminders",
                "5. Traceable basis",
                "",
                f"User question: {question}",
                "",
                "Rule-based answer:",
                answer,
                "",
                "Rule-based suggested steps:",
                self._format_list(suggested_steps),
                "",
                "Safety notes:",
                self._format_list(safety_notes),
                "",
                "Traceable references:",
                self._format_references(references),
                "",
                "Retrieved chunk content:",
                self._format_retrieved_chunks(retrieved_chunks or []),
                "",
                "Media metadata context:",
                self._format_media_context(media_context or []),
                "",
                "Approved knowledge graph context:",
                self._format_kg_context(kg_context or {}),
            ]
        )

    def build_diagnosis_prompt(
        self,
        *,
        request_summary: dict[str, Any],
        diagnosis_summary: str,
        possible_causes: list[str],
        inspection_steps: list[str],
        recommended_actions: list[str],
        safety_notes: list[str],
        references: list[Any],
        related_history: list[Any],
        media_context: list[Any] | None = None,
        kg_context: dict[str, Any] | None = None,
    ) -> str:
        return "\n".join(
            [
                "Task: Polish and structure a PV inverter fault diagnosis response.",
                "Scope: first-version Energy-Maintenance only covers Huawei and Sungrow PV inverters.",
                "Output language: Chinese.",
                "Hard rules:",
                "- Separate possible causes from inspection actions.",
                "- Do not state that one unique root cause has been confirmed.",
                "- Do not replace field engineer judgment or manufacturer safety manuals.",
                "- Do not invent references, maintenance history, alarm codes, pages, or document sources.",
                "- Keep safety notes visible and non-empty for electrical maintenance.",
                "- Media context contains metadata only. Do not infer fault causes from unparsed images.",
                "- Images are human-review attachments unless a real OCR result is explicitly present.",
                "- Knowledge graph context is approved active graph evidence only and is supplemental.",
                "- Do not treat graph context as a confirmed root cause without field verification.",
                "- Do not include local file paths or binary image data.",
                "",
                "Recommended output structure:",
                "1. Initial diagnosis summary",
                "2. Possible causes",
                "3. On-site inspection steps",
                "4. Recommended actions",
                "5. Safety boundary",
                "6. Traceable basis and related history",
                "",
                "Device and fault input:",
                self._json(request_summary),
                "",
                "Rule-based diagnosis summary:",
                diagnosis_summary,
                "",
                "Possible causes:",
                self._format_list(possible_causes),
                "",
                "Inspection steps:",
                self._format_list(inspection_steps),
                "",
                "Recommended actions:",
                self._format_list(recommended_actions),
                "",
                "Safety notes:",
                self._format_list(safety_notes),
                "",
                "Traceable references:",
                self._format_references(references),
                "",
                "Related maintenance history:",
                self._format_references(related_history),
                "",
                "Media metadata context:",
                self._format_media_context(media_context or []),
                "",
                "Approved knowledge graph context:",
                self._format_kg_context(kg_context or {}),
            ]
        )

    def build_sop_prompt(
        self,
        *,
        request_summary: dict[str, Any],
        source: str,
        title: str,
        steps: list[dict[str, Any]],
        safety_requirements: list[dict[str, Any]],
        tools_required: list[dict[str, Any]],
        materials_required: list[dict[str, Any]],
        compliance_notes: str | None,
        references: list[Any],
        media_context: list[Any] | None = None,
        kg_context: dict[str, Any] | None = None,
    ) -> str:
        return "\n".join(
            [
                "Task: Enhance the display text for a PV inverter SOP response.",
                "Scope: first-version Energy-Maintenance only covers Huawei and Sungrow PV inverters.",
                "Output language: Chinese.",
                "Hard rules:",
                "- Do not modify, delete, reorder, or fabricate database SOP steps.",
                "- Only provide supplemental explanation for this response.",
                "- Do not invent references or manufacturer instructions.",
                "- Do not weaken safety requirements.",
                "- Do not provide actions beyond manufacturer manuals, site safety rules, and qualified personnel boundaries.",
                "- Media context contains metadata only. Do not infer image content.",
                "- Images are human-review attachments unless a real OCR result is explicitly present.",
                "- Knowledge graph context is approved active graph evidence only and must not overwrite SOP templates.",
                "- Do not remove graph-derived safety risks when polishing text.",
                "- Do not include local file paths or binary image data.",
                "",
                "Recommended output structure:",
                "1. SOP applicability",
                "2. Key execution boundary",
                "3. Safety review points",
                "4. Record and archive reminders",
                "5. Traceable basis",
                "",
                "Generation input:",
                self._json(request_summary),
                "",
                f"SOP source: {source}",
                f"SOP title: {title}",
                "",
                "Original SOP steps:",
                self._json(steps),
                "",
                "Safety requirements:",
                self._json(safety_requirements),
                "",
                "Tools required:",
                self._json(tools_required),
                "",
                "Materials required:",
                self._json(materials_required),
                "",
                "Compliance notes:",
                compliance_notes or "-",
                "",
                "Traceable references:",
                self._format_references(references),
                "",
                "Media metadata context:",
                self._format_media_context(media_context or []),
                "",
                "Approved knowledge graph context:",
                self._format_kg_context(kg_context or {}),
            ]
        )

    @staticmethod
    def _format_list(items: list[str]) -> str:
        if not items:
            return "-"
        return "\n".join(f"- {item}" for item in items)

    @staticmethod
    def _format_references(items: list[Any]) -> str:
        if not items:
            return "No traceable source was provided."
        lines: list[str] = []
        for index, item in enumerate(items[:8], start=1):
            if hasattr(item, "model_dump"):
                payload = item.model_dump(mode="json")
            elif isinstance(item, dict):
                payload = item
            else:
                payload = {"value": str(item)}
            summary = {
                key: payload.get(key)
                for key in [
                    "document_id",
                    "document_title",
                    "chunk_id",
                    "chunk_index",
                    "page_number",
                    "section_title",
                    "source",
                    "score",
                    "record_id",
                    "fault_type",
                    "alarm_code",
                ]
                if payload.get(key) is not None
            }
            quote = payload.get("quote") or payload.get("fault_description") or payload.get("repair_action")
            if quote:
                summary["quote"] = str(quote)[:180]
            lines.append(f"{index}. {json.dumps(summary, ensure_ascii=False)}")
        return "\n".join(lines)

    @staticmethod
    def _format_media_context(items: list[Any]) -> str:
        if not items:
            return "No media attachment was associated."
        safe_keys = [
            "id",
            "file_name",
            "original_file_name",
            "media_type",
            "description",
            "manufacturer",
            "product_series",
            "device_type",
            "device_name",
            "fault_type",
            "alarm_code",
            "ocr_status",
            "ocr_message",
            "ocr_text",
        ]
        lines: list[str] = []
        for index, item in enumerate(items[:10], start=1):
            if hasattr(item, "model_dump"):
                payload = item.model_dump(mode="json")
            elif isinstance(item, dict):
                payload = item
            else:
                continue
            if payload.get("ocr_text"):
                payload["ocr_text"] = str(payload["ocr_text"])[:500]
            summary = {key: payload.get(key) for key in safe_keys if payload.get(key) is not None}
            lines.append(f"{index}. {json.dumps(summary, ensure_ascii=False)}")
        return "\n".join(lines) if lines else "No safe media metadata was available."

    @staticmethod
    def _format_retrieved_chunks(items: list[Any]) -> str:
        if not items:
            return "No retrieved chunk content was provided."
        lines: list[str] = []
        for index, item in enumerate(items[:6], start=1):
            if hasattr(item, "model_dump"):
                payload = item.model_dump(mode="json")
            elif isinstance(item, dict):
                payload = item
            else:
                continue
            summary = {
                key: payload.get(key)
                for key in [
                    "document_id",
                    "document_title",
                    "chunk_id",
                    "chunk_index",
                    "page_number",
                    "section_title",
                    "source",
                    "score",
                ]
                if payload.get(key) is not None
            }
            content = str(payload.get("content") or "")
            summary["content"] = content[:900]
            lines.append(f"{index}. {json.dumps(summary, ensure_ascii=False)}")
        return "\n".join(lines) if lines else "No retrieved chunk content was available."

    @staticmethod
    def _format_kg_context(context: dict[str, Any]) -> str:
        if not context or not (context.get("summary") or {}).get("matched_node_count"):
            return "No approved active knowledge graph context was matched."
        safe_keys = [
            "matched_nodes",
            "related_causes",
            "inspection_items",
            "recommended_actions",
            "safety_risks",
            "tools",
            "parts",
            "related_sop",
        ]
        compact: dict[str, Any] = {"summary": context.get("summary") or {}}
        for key in safe_keys:
            compact[key] = [
                {
                    "node_type": item.get("node_type"),
                    "display_name": item.get("display_name"),
                    "via_relation": item.get("via_relation"),
                }
                for item in (context.get(key) or [])[:5]
                if isinstance(item, dict)
            ]
        compact["evidence"] = [
            {
                "source_type": item.get("source_type"),
                "document_id": item.get("document_id"),
                "chunk_id": item.get("chunk_id"),
                "evidence_text": str(item.get("evidence_text") or "")[:180],
            }
            for item in (context.get("evidence") or [])[:5]
            if isinstance(item, dict)
        ]
        return json.dumps(compact, ensure_ascii=False, indent=2, default=str)

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, indent=2, default=str)
