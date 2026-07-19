from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from app.services.document_parser import ParsedDocument
from app.services.text_splitter import TextChunk


@dataclass(slots=True)
class SemanticBlock:
    text: str
    block_type: str
    heading_path: list[str]
    page_number: int | None


class SemanticChunker:
    PARSER_VERSION = "structured_parser_v1"
    CHUNKER_VERSION = "semantic_chunker_v1"
    HEADING = re.compile(r"^(?:#{1,6}\s+|第[一二三四五六七八九十0-9]+[章节部分]|\d+(?:\.\d+)*[、.\s]).{1,100}$")
    MODEL = re.compile(r"\b(?:SUN2000[-\w/]+|SG\d+[A-Z0-9-]*|FusionSolar)\b", re.I)
    FAULT = re.compile(r"\b(?:[A-Z]{1,4}[-_]?)?\d{3,6}\b", re.I)

    def __init__(self, chunk_size: int = 1000, overlap: int = 120):
        self.chunk_size = max(300, chunk_size)
        self.overlap = max(0, min(overlap, 200))

    def split(self, parsed_document: ParsedDocument) -> list[TextChunk]:
        blocks = self._blocks(parsed_document)
        chunks: list[TextChunk] = []
        seen_hashes: set[str] = set()
        current: list[SemanticBlock] = []
        current_length = 0

        def flush() -> None:
            nonlocal current, current_length
            if not current:
                return
            content = "\n\n".join(item.text for item in current).strip()
            digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
            if content and digest not in seen_hashes:
                seen_hashes.add(digest)
                last = current[-1]
                models = self._unique(self.MODEL.findall(content))
                faults = self._unique(self.FAULT.findall(content))
                section_path = last.heading_path
                chunks.append(TextChunk(
                    chunk_index=len(chunks), content=content,
                    section_title=section_path[-1] if section_path else None,
                    char_count=len(content), page_number=current[0].page_number,
                    metadata={
                        "parser_version": self.PARSER_VERSION,
                        "chunker_version": self.CHUNKER_VERSION,
                        "section_path": section_path,
                        "source_locator": {"page_number": current[0].page_number, "section_path": section_path},
                        "block_types": self._unique(item.block_type for item in current),
                        "device_models": models,
                        "fault_codes": faults,
                        "content_hash": digest,
                        "duplicate": False,
                    },
                ))
            current = []
            current_length = 0

        for block in blocks:
            if len(block.text) > self.chunk_size:
                flush()
                for fragment in self._split_long_block(block):
                    current = [fragment]
                    current_length = len(fragment.text)
                    flush()
                continue
            boundary = bool(current and block.block_type == "heading")
            if boundary or (current and current_length + len(block.text) + 2 > self.chunk_size):
                flush()
            current.append(block)
            current_length += len(block.text) + (2 if len(current) > 1 else 0)
        flush()
        return chunks

    def _blocks(self, parsed_document: ParsedDocument) -> list[SemanticBlock]:
        pages = parsed_document.pages or [type("Page", (), {"page_number": None, "text": parsed_document.text})()]
        blocks: list[SemanticBlock] = []
        heading_path: list[str] = []
        for page in pages:
            text = page.text.replace("\r\n", "\n").replace("\r", "\n")
            raw_blocks = [item.strip() for item in re.split(r"\n\s*\n", text) if item.strip()]
            for raw in raw_blocks:
                cleaned = "\n".join(re.sub(r"[ \t]+", " ", line).strip() for line in raw.splitlines()).strip()
                block_type = self._block_type(cleaned)
                if block_type == "heading":
                    level, title = self._heading_level(cleaned)
                    heading_path = heading_path[: level - 1] + [title]
                blocks.append(SemanticBlock(cleaned, block_type, list(heading_path), page.page_number))
        return blocks

    def _split_long_block(self, block: SemanticBlock) -> list[SemanticBlock]:
        if block.block_type == "table":
            rows = block.text.splitlines()
            groups: list[str] = []
            current = ""
            for row in rows:
                candidate = f"{current}\n{row}".strip()
                if current and len(candidate) > self.chunk_size:
                    groups.append(current)
                    current = row
                else:
                    current = candidate
            if current:
                groups.append(current)
        else:
            sentences = [item.strip() for item in re.split(r"(?<=[。！？；.!?;])\s*", block.text) if item.strip()]
            groups = []
            current = ""
            for sentence in sentences:
                candidate = f"{current}{sentence}"
                if current and len(candidate) > self.chunk_size:
                    groups.append(current)
                    current = sentence
                else:
                    current = candidate
            if current:
                groups.append(current)
        return [SemanticBlock(text, block.block_type, block.heading_path, block.page_number) for text in groups if text.strip()]

    def _block_type(self, text: str) -> str:
        first = text.splitlines()[0]
        if self.HEADING.match(first) and len(first) <= 120:
            return "heading"
        if any("|" in line for line in text.splitlines()) or "\t" in text:
            return "table"
        if all(re.match(r"^(?:[-*•]|\d+[.)、])\s*", line) for line in text.splitlines() if line):
            return "list"
        if re.search(r"(?:警告|危险|高压|触电|必须断电)", text):
            return "safety_warning"
        if re.match(r"^\[?(?:图|Figure|Image)", first, re.I):
            return "image_placeholder"
        return "paragraph"

    @staticmethod
    def _heading_level(text: str) -> tuple[int, str]:
        first = text.splitlines()[0].strip()
        markdown = re.match(r"^(#{1,6})\s+(.+)$", first)
        if markdown:
            return len(markdown.group(1)), markdown.group(2).strip()
        numbered = re.match(r"^(\d+(?:\.\d+)*)[、.\s]+(.+)$", first)
        if numbered:
            return min(6, numbered.group(1).count(".") + 1), first
        return 1, first

    @staticmethod
    def _unique(values) -> list[str]:
        return list(dict.fromkeys(str(value) for value in values if value))
