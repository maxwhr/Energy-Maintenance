from app.services.document_parser import ParsedDocument, ParsedPage
from app.services.semantic_chunker import SemanticChunker


def test_semantic_chunker_preserves_heading_page_table_model_and_fault():
    document = ParsedDocument(text="", pages=[ParsedPage(3, "# 告警处理\n\nSUN2000-100KTL 告警 2064。\n\n代码 | 措施\n2064 | 断电验电后检查绝缘")])
    chunks = SemanticChunker(chunk_size=350).split(document)
    assert chunks and chunks[0].page_number == 3
    merged = " ".join(chunk.content for chunk in chunks)
    assert "SUN2000-100KTL" in merged and "2064" in merged
    assert all(chunk.metadata["chunker_version"] == "semantic_chunker_v1" for chunk in chunks)


def test_semantic_chunker_rejects_duplicate_content():
    document = ParsedDocument(text="same\n\nsame")
    chunks = SemanticChunker().split(document)
    assert len({chunk.metadata["content_hash"] for chunk in chunks}) == len(chunks)
