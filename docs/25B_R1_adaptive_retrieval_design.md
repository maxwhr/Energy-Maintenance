# Task 25B-R1 Adaptive Retrieval Design

`AdaptiveRetrievalStrategy` routes exact model, exact fault-code and safety queries keyword-first; semantic symptoms use calibrated hybrid; visual/OCR descriptors use vector-enhanced hybrid. Vector candidates below 0.761434 do not participate in fusion. Weighted RRF uses K=60 and dev-selected lexical protection. Strong keyword evidence triggers `strong_keyword_evidence_protected`; vector timeout triggers keyword fallback. Unknown or unsupported exact evidence returns `insufficient_evidence=true`.

The production default remains `keyword`; the controlled blind result permits adaptive pilot use but does not automatically enable it globally. Reranker remains available for diagnostics but is disabled because dev gain was zero.
