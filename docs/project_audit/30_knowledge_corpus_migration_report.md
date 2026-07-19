# Task 28A Knowledge Corpus Migration Report

## Boundary And Method

- Allowed source root: `E:\大学\竞赛\软件杯\知识库文档`
- Allowed project root: `D:\Work Space\Energy-Maintenance`
- Target: `D:\Work Space\Energy-Maintenance\knowledge_assets\competition_corpus_v1\raw`
- Outside allowed roots modified: **no**
- Source root deleted: **no**

Every file followed this sequence: source SHA-256 verification, copy to a project-local staging name, target size verification, target SHA-256 verification, atomic rename, durable journal write, final verification, then source-file deletion. No directory was recursively moved or deleted.

## Result

| Item | Count |
|---|---:|
| Scanned files | 167 |
| Readable files | 167 |
| Migration dry-run ready | 167 |
| Successfully moved | 167 |
| Failed | 0 |
| Byte-identical duplicates | 3 |
| Excluded from knowledge-document upload | 146 |
| Huawei document candidates | 11 |
| Sungrow future-scope document candidates | 10 |

Total verified size: **263715057 bytes**. Independent post-migration verification found 167 target files and zero size/hash mismatches. The source root remains present with its three empty subdirectories and zero files.

## Duplicate Handling

Three duplicate image files were migrated and retained under their original relative paths. `source_inventory.json` records their authoritative first-seen aliases by SHA-256. No duplicate source was discarded before verified migration, and duplicate images are not knowledge-document upload candidates.

## Evidence

- Source inventory: `knowledge_assets/competition_corpus_v1/manifests/source_inventory.json`
- CSV inventory: `knowledge_assets/competition_corpus_v1/manifests/source_inventory.csv`
- Durable move journal: `knowledge_assets/competition_corpus_v1/import_reports/file_migration_journal.jsonl`
- Migration result: `knowledge_assets/competition_corpus_v1/import_reports/file_migration_result.json`

The inventory holds the source SHA-256 for every relative path; the move journal/result holds the verified target SHA-256. Their values are identical for all 167 files.

## Safety Tests

Path and migration tests: **12 passed**. Coverage includes valid source/project paths, `..` escape, cross-drive escape, similar-prefix escape, NTFS Junction escape, unsafe manifest paths, inventory completeness, duplicate accounting, and changed-file hash rejection.
