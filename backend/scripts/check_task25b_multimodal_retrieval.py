from __future__ import annotations

import argparse
from sqlalchemy import select

from task25b_common import write_result
from app.core.database import SessionLocal
from app.models import UploadedMedia
from app.services.multimodal_retrieval_service import MultimodalRetrievalService, MultimodalRetrievalServiceError


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--media-id")
    parser.add_argument("--allow-real-api", action="store_true")
    args = parser.parse_args()
    with SessionLocal() as db:
        media = db.get(UploadedMedia, args.media_id) if args.media_id else db.scalar(select(UploadedMedia).where(UploadedMedia.status == "active").order_by(UploadedMedia.created_at.desc()))
        if not media:
            result = {"status": "BLOCKED_DATA", "reason": "no active media available", "raw_image_embedding": False}
        else:
            try:
                service = MultimodalRetrievalService(db, allow_real_api=args.allow_real_api)
                if args.allow_real_api:
                    peers = list(db.scalars(select(UploadedMedia).where(
                        UploadedMedia.status == "active", UploadedMedia.id != media.id,
                        UploadedMedia.original_file_name.startswith("Task25B_")
                    ).limit(3)))
                    for peer in peers:
                        service.retrieve(peer.id, top_k=2)
                response = service.retrieve(media.id)
                result = {"status": "PASSED", **response.model_dump(mode="json")}
            except MultimodalRetrievalServiceError as exc:
                result = {"status": "BLOCKED_DATA", "reason": str(exc), "raw_image_embedding": False}
    write_result("multimodal_retrieval.json", result)
    return 0 if result["status"] == "PASSED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
