from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.core.database import SessionLocal
from app.services.agent_tool_registry import AgentToolRegistryService
from app.services.external_api_provider_registry import ExternalApiProviderRegistry


def main() -> int:
    db = SessionLocal()
    try:
        result = AgentToolRegistryService(db).seed_defaults()
        external_api_result = ExternalApiProviderRegistry(db).seed_defaults()
        db.commit()
        print(
            "agent_runtime_seed_result "
            f"definitions={result['definitions']} tools={result['tools']} "
            f"external_api_providers={external_api_result['providers']} "
            f"external_api_routes={external_api_result['routes']} "
            "idempotent=true"
        )
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
