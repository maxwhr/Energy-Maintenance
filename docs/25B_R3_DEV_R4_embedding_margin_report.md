# Task 25B-R3-DEV-R4 Embedding Margin Report

## Diagnostic result

The first canonical-unit comparison failed with average margin -0.006862, median -0.000287, and a 50% non-positive ratio. After source-only typed anchors and the ambiguity-free Train/Dev repair, the actual typed representation improved to:

- cases: 60 vector-heavy Train/Dev cases
- average positive similarity: 0.656515
- average hard-negative similarity: 0.625111
- average positive margin: 0.031404
- median positive margin: 0.025778
- non-positive ratio: 0.400000
- gate: `MARGIN_GATE_FAILED`

The representation improvement is real but does not meet the diagnostic targets of average margin >=0.05, median >=0.04, and non-positive ratio <=10%. This diagnostic does not replace Candidate Recall@50 or Canary quality gates and is not reported as model proof.

Evidence: `.runtime/task25b_r3_dev_r4/embedding_margin.json`. Full vectors are not persisted.

