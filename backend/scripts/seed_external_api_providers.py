from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.core.database import SessionLocal
from app.services.external_api_provider_registry import ExternalApiProviderRegistry


def main() -> int:
    db = SessionLocal()
    try:
        result = ExternalApiProviderRegistry(db).seed_defaults()
        db.commit()
        print(
            "external_api_provider_seed_result "
            f"providers={result['providers']} routes={result['routes']} idempotent=true"
        )
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
