# 18F Local llama.cpp / GGUF Integration Report

## Scope

Task 18F prepares optional local llama.cpp / GGUF model access through the existing Model Gateway.

The task does not install llama.cpp, download models, commit GGUF files, add an Alembic migration, introduce Docker, introduce SQLite, introduce pgvector/embedding, or enable OCR.

## Local Provider Configuration

Supported local settings:

```env
LOCAL_LLM_ENABLED=false
LOCAL_LLM_BASE_URL=http://127.0.0.1:8080
LOCAL_LLM_MODEL=local-gguf-model
LOCAL_LLM_API_TYPE=openai_compatible
LOCAL_LLM_TIMEOUT_SECONDS=60
LOCAL_LLM_MAX_TOKENS=1024
LOCAL_LLM_TEMPERATURE=0.2
LOCAL_LLM_HEALTH_PATH=/health
LOCAL_LLM_NATIVE_COMPLETION_PATH=/completion
LOCAL_LLM_OPENAI_CHAT_PATH=/v1/chat/completions
```

Supported API types:

- `openai_compatible`: llama.cpp `POST /v1/chat/completions`.
- `llama_cpp_native`: llama.cpp `POST /completion`.

## Backend Implementation

- `local_llama_cpp` supports OpenAI-compatible chat completions.
- `local_llama_cpp` supports native llama.cpp completion.
- Health checks try `/health`, `/`, and `/props`.
- Disabled or unavailable local model service does not block backend startup.
- Local model errors are summarized as disabled, not configured, unavailable, endpoint mismatch, invalid response, or empty response where applicable.
- Full local model file paths are not returned as `model_name` and are sanitized from error summaries.
- Model Gateway logs provider, model label, latency, success/error, fallback status, and safe provider metadata.

## Frontend Implementation

The Model Service page can display the `local_llama_cpp` provider card with:

- enabled/configured state.
- API type.
- base URL configured state.
- model label.
- availability status.
- health path.
- latency.
- error summary.

The page already supports selecting `local_llama_cpp` for test/chat calls.

## Scripts

Added:

- `backend/scripts/check_local_llama_cpp_flow.py`
- `scripts/start_llama_cpp_server_example.ps1`
- `scripts/start_llama_cpp_server_example.sh`

The startup scripts are examples only. They do not install llama.cpp and do not provide a model file.

## LoongArch / Kylin Preparation

The deployment documentation now describes:

- native toolchain checks.
- llama.cpp source build preparation.
- GGUF model placement outside the repository.
- llama-server startup example.
- Energy-Maintenance `LOCAL_LLM_*` configuration.
- validation with `check_local_llama_cpp_flow.py`.

This task was performed on Windows. It does not claim that llama.cpp was compiled or executed on real LoongArch/Kylin hardware.

## Result Modes

- `passed`: real local llama.cpp calls succeeded.
- `blocked`: local llama.cpp is disabled or unreachable; rule-based fallback is verified.
- `failed`: local llama.cpp configuration exists but call, logging, or safety checks failed.

## Current Local Status

At the time of this report, no local llama.cpp server is assumed to be running. The expected validation mode is `blocked` unless the user starts a real local llama.cpp service and configures `LOCAL_LLM_*`.

## Verification Run

Executed in the local Windows environment:

- `uv run python -m compileall app scripts`: passed.
- `uv run python -m alembic -c alembic.ini current`: passed, current revision `20260601_0003 (head)`.
- `npm.cmd install`: passed, with one existing high-severity npm audit warning.
- `npm.cmd run build`: passed.
- `powershell -ExecutionPolicy Bypass -File .\scripts\build_and_install_frontend.ps1`: passed.
- `powershell -ExecutionPolicy Bypass -File .\scripts\final_smoke_test.ps1`: passed, 23 total and 0 failed.
- `uv run python scripts\check_local_llama_cpp_flow.py`: blocked mode completed successfully.

Blocked-mode evidence:

- `local_llama_cpp` status: disabled.
- `model-gateway/test` with `allow_fallback=false`: returned a clear local provider failure.
- `model-gateway/chat` with `allow_fallback=false`: returned a clear local provider failure.
- `model-gateway/test`: used `rule_based` fallback.
- `model-gateway/chat`: used `rule_based` fallback.
- retrieval model enhancement: used `rule_based` fallback.
- model log list/detail path and Authorization safety checks: passed.

## Deferred

- downloading GGUF models.
- installing or compiling llama.cpp.
- systemd service creation for llama.cpp.
- LoongArch/Kylin real-hardware inference benchmark.
- GPU acceleration or hardware-specific optimization.
