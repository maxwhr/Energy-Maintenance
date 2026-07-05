from __future__ import annotations

from app.core.database import SessionLocal
from app.models import KnowledgeChunk
from app.services.text_vector_service import TextVectorService


def vectorize_knowledge_chunks() -> None:
    db = SessionLocal()
    vectorizer = TextVectorService()
    updated = 0
    skipped = 0
    try:
        chunks = db.query(KnowledgeChunk).filter(KnowledgeChunk.status == "active").all()
        for chunk in chunks:
            metadata = chunk.metadata_json or {}
            if vectorizer.vector_from_metadata(metadata):
                skipped += 1
                continue
            chunk.metadata_json = vectorizer.metadata_for_text(chunk.content or "", metadata)
            chunk.embedding_status = "embedded"
            updated += 1
        db.commit()
        print(f"Knowledge chunk vectorization completed. updated={updated}, skipped={skipped}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    vectorize_knowledge_chunks()
