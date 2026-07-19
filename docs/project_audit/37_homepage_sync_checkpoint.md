# Task 29A Homepage Sync Checkpoint

## Local Baseline

- Project: `D:\Work Space\Energy-Maintenance`
- Branch: `main`
- Local HEAD at task start: `5314533`
- Remote tracking state at task start: `main...origin/main [behind 5]`
- Remote: `origin -> https://github.com/maxwhr/Energy-Maintenance.git`
- Reference commit: `16815c4886af1e8f92f69a7a19f4a725d67d5904`
- Reference commit available locally: yes
- Fetch, merge, cherry-pick, checkout, or other Git write required: no

The working tree was already extensively dirty before Task 29A. Existing backend, RAG, database, frontend business, generated static, test, and report changes are user-owned and were neither reverted nor adopted as Task 29A work.

## Original Public Entry

At the checkpoint, `/login` combined a compact public introduction with authentication. It did not yet contain the reference commit's complete image-led industrial narrative, sticky story sections, interactive capability orbit, eight-step workflow, or independent `/auth/login` page.

## Protected Baseline

Before implementation, Task 29A captured SHA-256 values for protected business files and an aggregate digest for `backend/app`. The final verification matched this baseline exactly.

- `backend/app`: 325 files, aggregate SHA-256 `790bf9c59399e8e6097cb4a371afaf57cdfa47c8bf6e7b912456ee1a1e32416c`
- `frontend/src/api/retrieval.ts`: `d2451d9e405602be5cff607e1bb7c5ec4ff8e0833fd908f0765a9db0a86838fd`
- `frontend/src/views/knowledge/Search.vue`: `c39ec89dbfebbae0bbd30654d4c6a8320bf8cf63f656e9403222ef604acaccf3`
- `frontend/src/views/assistant/Chat.vue`: `ad33af6530239cc2d66d847f366f36e778556b44488e0f77809e7b3baff297a1`
- `frontend/src/views/device/Alarms.vue`: `f698a23aa7449e30655307e0b9d6c709018509b3c443babd0985907df91a9b7f`
- `frontend/src/views/device/Models.vue`: `f2c5b5aa9f7be61ac0ceba249beb3480f0777d0e0f31aa8de0dcd3210d18ae72`
- `frontend/src/views/diagnosis/index.vue`: `a1e74cce5fd84fd28a8f2b9759d50240652b872ecae1ce1c7a4d07abc640b363`

Baseline evidence is stored under `.runtime/task29a/protected_baseline.json` and is not a production artifact.

## Reference Extraction

The five reference Vue/CSS files were inspected with read-only Git commands. Six binary PNG blobs were extracted without recompression or editing, then validated by file signature and SHA-256. No GitHub URL or base64 image was introduced into the page.

## Scope Decision

Task 29A manually adapted only the public homepage, dedicated login page, account explanation page, minimal public-route declarations, six original visual assets, and these audit reports. `frontend/src/styles/global.css` did not require modification.

The formal homepage copy remains scoped to Huawei SUN2000. The `field-engineer.png` reference image may visually include Sungrow equipment and is retained with the user's explicit approval as a future-expansion visual. It is not described as current formal Sungrow support.

## Status

`COMPLETE`
