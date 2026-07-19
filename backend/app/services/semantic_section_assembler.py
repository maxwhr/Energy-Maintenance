from __future__ import annotations

import hashlib
from dataclasses import dataclass

from app.models import KnowledgeChunk, KnowledgeDocument


@dataclass(frozen=True, slots=True)
class AssembledSemanticSection:
    document: KnowledgeDocument
    section_id: str
    heading_path: list[str]
    title: str
    chunks: list[KnowledgeChunk]
    content: str
    page_start: int | None
    page_end: int | None
    source_locator: dict
    cross_chunk: bool
    cross_page: bool
    table_continuation: bool


class SemanticSectionAssembler:
    """Assemble only adjacent source chunks sharing one document/heading boundary."""

    @classmethod
    def assemble(
        cls,
        rows: list[tuple[KnowledgeChunk, KnowledgeDocument]],
    ) -> list[AssembledSemanticSection]:
        grouped: dict[tuple[str, str], list[tuple[KnowledgeChunk, KnowledgeDocument]]] = {}
        order: list[tuple[str, str]] = []
        for chunk, document in rows:
            title = str(chunk.section_title or chunk.chunk_index)
            key = (str(document.id), title)
            if key not in grouped:
                grouped[key] = []
                order.append(key)
            grouped[key].append((chunk, document))
        sections: list[AssembledSemanticSection] = []
        for key in order:
            group = sorted(grouped[key], key=lambda row: row[0].chunk_index)
            chunks = [row[0] for row in group]
            document = group[0][1]
            title = str(chunks[0].section_title or f"Chunk {chunks[0].chunk_index}")
            metadata = chunks[0].metadata_json or {}
            heading_path = metadata.get("heading_path") or metadata.get("section_path") or [title]
            if not isinstance(heading_path, list):
                heading_path = [str(heading_path)]
            heading_path = [str(value) for value in heading_path if str(value).strip()] or [title]
            pages = [chunk.page_number for chunk in chunks if chunk.page_number is not None]
            content = "\n".join((chunk.content or "").strip() for chunk in chunks if (chunk.content or "").strip())
            source_chunk_ids = [str(chunk.id) for chunk in chunks]
            section_key = " > ".join(heading_path)
            section_id = "sec2_" + hashlib.sha256(f"{document.id}|{section_key}|{title}".encode("utf-8")).hexdigest()[:40]
            table_continuation = len(chunks) > 1 and any(
                bool((chunk.metadata_json or {}).get("table"))
                or bool((chunk.metadata_json or {}).get("is_table"))
                or "表" in (chunk.section_title or "")
                for chunk in chunks
            )
            sections.append(AssembledSemanticSection(
                document=document,
                section_id=section_id,
                heading_path=heading_path,
                title=title,
                chunks=chunks,
                content=content,
                page_start=min(pages) if pages else None,
                page_end=max(pages) if pages else None,
                source_locator={
                    "section": title,
                    "heading_path": heading_path,
                    "page_start": min(pages) if pages else None,
                    "page_end": max(pages) if pages else None,
                    "source_chunk_ids": source_chunk_ids,
                },
                cross_chunk=len(chunks) > 1,
                cross_page=len(set(pages)) > 1,
                table_continuation=table_continuation,
            ))
        return sections
