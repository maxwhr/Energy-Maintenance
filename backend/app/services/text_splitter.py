from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.services.document_parser import ParsedDocument


@dataclass
class TextChunk:
    chunk_index: int
    content: str
    section_title: str | None
    char_count: int
    page_number: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class TextSplitter:
    def __init__(self, chunk_size: int = 1000, overlap: int = 150):
        self.chunk_size = max(200, chunk_size)
        self.overlap = max(0, min(overlap, self.chunk_size // 2))

    def split(self, parsed_document: ParsedDocument) -> list[TextChunk]:
        chunks: list[TextChunk] = []
        sources = parsed_document.pages or []
        if not sources:
            sources = [type("ParsedPageLike", (), {"page_number": None, "text": parsed_document.text})()]

        for page in sources:
            clean_text = self.clean_text(page.text)
            if not clean_text.strip():
                continue
            page_chunks = self._split_text(clean_text, page.page_number, len(chunks))
            chunks.extend(page_chunks)

        return [
            TextChunk(
                chunk_index=index,
                content=chunk.content,
                section_title=chunk.section_title,
                char_count=chunk.char_count,
                page_number=chunk.page_number,
                metadata=chunk.metadata,
            )
            for index, chunk in enumerate(chunks)
        ]

    @staticmethod
    def clean_text(text: str) -> str:
        normalized = text.replace("\r\n", "\n").replace("\r", "\n")
        lines = [re.sub(r"[ \t]+", " ", line).strip() for line in normalized.split("\n")]
        result: list[str] = []
        blank_count = 0
        for line in lines:
            if not line:
                blank_count += 1
                if blank_count <= 1:
                    result.append("")
                continue
            blank_count = 0
            result.append(line)
        return "\n".join(result).strip()

    def _split_text(self, text: str, page_number: int | None, offset: int) -> list[TextChunk]:
        paragraphs = [paragraph.strip() for paragraph in re.split(r"\n\s*\n", text) if paragraph.strip()]
        if not paragraphs:
            return []

        chunks: list[TextChunk] = []
        current: list[str] = []
        current_length = 0
        section_title: str | None = None

        for paragraph in paragraphs:
            detected_heading = self._detect_section_title(paragraph)
            if detected_heading:
                section_title = detected_heading

            if len(paragraph) > self.chunk_size:
                if current:
                    chunks.append(self._build_chunk(current, section_title, page_number, offset + len(chunks)))
                    current = []
                    current_length = 0
                chunks.extend(self._split_long_paragraph(paragraph, section_title, page_number, offset + len(chunks)))
                continue

            next_length = current_length + len(paragraph) + (2 if current else 0)
            if current and next_length > self.chunk_size:
                chunk = self._build_chunk(current, section_title, page_number, offset + len(chunks))
                chunks.append(chunk)
                overlap_text = self._tail_overlap(chunk.content)
                current = [overlap_text, paragraph] if overlap_text else [paragraph]
                current_length = sum(len(item) for item in current) + max(0, len(current) - 1) * 2
            else:
                current.append(paragraph)
                current_length = next_length

        if current:
            chunks.append(self._build_chunk(current, section_title, page_number, offset + len(chunks)))

        return chunks

    def _split_long_paragraph(
        self,
        paragraph: str,
        section_title: str | None,
        page_number: int | None,
        offset: int,
    ) -> list[TextChunk]:
        chunks: list[TextChunk] = []
        start = 0
        while start < len(paragraph):
            end = min(start + self.chunk_size, len(paragraph))
            content = paragraph[start:end].strip()
            if content:
                chunks.append(
                    TextChunk(
                        chunk_index=offset + len(chunks),
                        content=content,
                        section_title=section_title,
                        char_count=len(content),
                        page_number=page_number,
                        metadata={"split_reason": "long_paragraph"},
                    )
                )
            if end >= len(paragraph):
                break
            start = max(0, end - self.overlap)
        return chunks

    def _build_chunk(
        self,
        paragraphs: list[str],
        section_title: str | None,
        page_number: int | None,
        chunk_index: int,
    ) -> TextChunk:
        content = "\n\n".join(item for item in paragraphs if item).strip()
        return TextChunk(
            chunk_index=chunk_index,
            content=content,
            section_title=section_title or self._detect_section_title(content),
            char_count=len(content),
            page_number=page_number,
            metadata={"splitter": "paragraph_char_window"},
        )

    def _tail_overlap(self, content: str) -> str:
        if not self.overlap or len(content) <= self.overlap:
            return ""
        return content[-self.overlap :].strip()

    @staticmethod
    def _detect_section_title(text: str) -> str | None:
        first_line = text.strip().splitlines()[0] if text.strip() else ""
        if not first_line or len(first_line) > 80:
            return None
        patterns = [
            r"^#+\s+(.+)$",
            r"^(第[一二三四五六七八九十0-9]+[章节部分].+)$",
            r"^([0-9]+(\.[0-9]+)*\s+.+)$",
            r"^(.+(告警|故障|排查|检修|巡检|处理|安全).*)$",
        ]
        for pattern in patterns:
            match = re.match(pattern, first_line)
            if match:
                return match.group(1).strip()
        return None
