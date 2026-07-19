# Task 25A-R1 重构前基线 Manifest

冻结时间：2026-07-10T13:51:23.007378+00:00

## 基线身份

- branch: `main`
- HEAD: `53145339c66b6efed489156ea68cf55d24161ab8`
- Git status entries: 160
- Python: 3.12.6；Node: v24.15.0；npm: 11.12.1。
- PostgreSQL: PostgreSQL 16.14, compiled by Visual C++ build 1944, 64-bit；tables=42；Alembic current=20260601_0008。
- OpenAPI paths=150；operations=174；reachable=True。

## 代码与契约哈希

- backend_production_source: files=189, sha256=`7463434aecb8fde236189a68cca30796022c435a90463891d8ec674061948b8b`
- frontend_production_source: files=102, sha256=`d0cc70d67073d34fe662405f6d802e0db10c106f5ca37ac1910758d8eefdbb5e`
- migrations: files=8, sha256=`efbd7453f11a77163c143a86ea2ee68674b1bfdb2da05aace415043511ba1cdd`
- package_manifests: files=2, sha256=`e793d32478bdf2daf86d0b573e37c3b5d1882c2bfd9c9928f352d68b380c8b50`
- lockfiles: files=2, sha256=`77e6f96033cead0b5aa98cbcb1974920d66e248da633dfa05503cf618588942d`
- critical_docs: files=9, sha256=`f686223690d9a9d521556be9814cc81b05da86eab3d7f7cff2947f4cf8e99830`
- test_scripts: files=58, sha256=`fc4c2f4ecb2b28cc57778c44d617420ec85ffb754a6067c91addc41dc1c18aae`

## 构建产物

- frontend/dist: files=59, bytes=593596, sha256=`4a43f67f11fabd60f6e4179d045e28b4d15c19a9a3f22e7a5cf0d1e53653f3e8`
- backend/static/frontend: files=59, bytes=593596, sha256=`f0be28f6b7eb54b14a8850180477cf06d9923ba68189739fb0090a7c3f273c7a`

## 环境与证据状态

- `.env` 仅记录 exists/key_count/configured_count/placeholder_count；未记录任何值。
- backend/.env: exists=True, keys=59, configured=0, placeholders=59
- frontend/.env: exists=False, keys=0, configured=0, placeholders=0
- .env: exists=False, keys=0, configured=0, placeholders=0
- current test registry entries: 73（passed=71）
- browser evidence: {"discovered": 7, "executed": 7, "passed": 7, "failed": 0, "blocked": 0, "skipped": 0, "console_errors": 0, "page_errors": 0, "network_failures": 0, "unexpected_http_failures": 0, "viewer_rbac": "PASSED", "admin_flows": "PASSED", "real_external_api_used": false}
- performance evidence: {"endpoint_count": 13, "total_samples": 2176, "read_samples": 2050, "write_samples": 126, "failure_count": 0, "timeout_count": 0, "error_rate": 0.0, "timeout_rate": 0.0, "classifications": {"PASS": 11, "NEEDS_OPTIMIZATION": 2}, "overall": "NEEDS_OPTIMIZATION", "slowest_endpoints": [{"endpoint_id": "record_center", "p95_ms": 11635.603}, {"endpoint_id": "kg_business_context", "p95_ms": 1911.709}, {"endpoint_id": "agent_runs", "p95_ms": 451.643}, {"endpoint_id": "retrieval_references", "p95_ms": 410.129}, {"endpoint_id": "sop_templates", "p95_ms": 322.135}]}

## 约束

本 Manifest 排除了 secret、用户 storage 内容、node_modules、.venv、.git、delivery 包和图片/大二进制正文。它冻结当前证据状态，不代表 LoongArch 实机或真实 provider 已验证。
