# Task 25B-R3-DEV-R4 Grounded Benchmark Report

## Result

The Train/Dev engineering dataset `task25b_r3_dev_r4_grounded_train_dev_v1` contains 100 cases (67 train, 33 dev), including 60 vector-heavy cases and 10 each for model, alarm, safety, and no-answer coverage.

The first generic source-concept formulation was found insufficiently discriminative before Canary. Its case IDs, query hashes, and expected mappings were frozen in `grounded_train_dev_pre_ambiguity_repair.json`. The in-place Train/Dev repair uses a source-present partial topic discriminator that is unique within the product family, while continuing to prohibit full model IDs, full alarm codes, full section titles, semantic-unit IDs, expected IDs, and benchmark text in anchors.

The dual engineering audit now reports:

- total: 100
- GROUNDED_STRONG: 100
- weak: 0
- ambiguous: 0
- vector-heavy: 60
- lexical leakage: 0
- engineering grounded: 100
- human/expert verified: 0

No test dataset was read or created. Evidence: `.runtime/task25b_r3_dev_r4/grounding_audit.json` and `.csv`.

