# Task 30A Multimodal Functional Acceptance

## Result

`TASK30A_REAL_MULTIMODAL_ACCEPTANCE_PASSED`

## Real Calls

- Total attempts: 8 of 16.
- Successful: 8.
- Failed: 0.
- Retries: 1, limited to the alarm-screen Vision parser correction.
- OCR calls: 3.
- Vision calls: 5.
- All calls used External API Gateway and the configured adapter.
- Complete raw provider requests and responses were not persisted.

## Four Image Classes

| Class | Real result | Human gate | Acceptance note |
| --- | --- | --- | --- |
| Nameplate/model | OCR and Vision completed | accepted/edited | Huawei/model clues were visible, but OCR quality was low and the result remains auxiliary evidence. |
| Alarm screen | OCR and Vision completed | alarm code corrected to `225` | The provider read `125`; human review corrected it to the visible `Error 225 / PV IsolationLow`. This is a verified safety-degradation case. |
| Connector/wiring | Vision completed | accepted/rejected as appropriate | The image is a technical connector illustration, not a live field photo; no energized-disassembly instruction or final fault conclusion was produced. |
| Meter/grid display | OCR and Vision completed | model/display evidence confirmed; retake available | Visible display text and values were retained as evidence; measurement location and final grid root cause remain unconfirmed. |

`requires_confirmation` is always true for provider evidence and `root_cause_determined` is always false for Vision output.

## Human Review

- Accept: exercised.
- Edit/confirm: exercised for both canonical cases; before/after values are retained in case audit events.
- Reject: exercised in Case B.
- Request retake: exercised in Case B and stored with a `request_retake` reason.
- Provider output did not enter retrieval until user-confirmed evidence was present.
- `model_output_corrections` delta is zero because Task 30A corrections are multimodal evidence audit events, not QA-answer correction submissions.

## Canonical Case A

- Case: `TASK30A-CANONICAL-ERROR225`.
- Final case status: `SOP_DRAFT_READY`.
- Diagnosis: evidence-supported possibilities only; no final root cause.
- Huawei citations: 5.
- Sungrow citations: 0.
- QA Preview delta: 0.
- QA Confirm delta: 1.
- Duplicate Confirm delta: 0.
- SOP: draft only.
- Formal maintenance task: not created.

## Canonical Case B

- Case: `TASK30A-CANONICAL-GRID-VOLTAGE`.
- Final case status: `SOP_DRAFT_READY`.
- Diagnosis: evidence-supported possibilities only; field measurement location must be verified.
- Huawei citations: 1.
- Sungrow citations: 0.
- QA Preview delta: 0.
- QA Confirm delta: 1.
- Duplicate Confirm delta: 0.
- SOP: draft only.
- Formal maintenance task: not created.

## Browser Acceptance

- Admin login and logout: passed.
- Case list and both Task 30A cases: passed.
- Upload surface, image preview, evidence review controls, citations, diagnosis boundary, SOP draft, QA controls, and audit timeline: rendered.
- Broken images: 0.
- Console blocking errors: 0.
- Observed business API failures: 0.
- Viewer: cases readable; upload, Provider run, QA Confirm, SOP draft, and Task draft controls disabled; evidence confirmation controls hidden.
- Browser logout cleared the test session.

## Database Delta

| Metric | Delta |
| --- | ---: |
| uploaded_media | +4 |
| multimodal_maintenance_cases | +2 |
| external_api_call_logs | +8 |
| qa_records | +2 |
| model_output_corrections | 0 |
| diagnosis_records | 0 |
| maintenance_tasks | 0 |
| sop_execution_records | 0 |
| vector_index_runs | 0 |
| knowledge_documents | 0 |
| knowledge_chunks | 0 |

## Known Limitations

- The real provider misread the alarm code as `125`; the human-confirmed value is `225`.
- Nameplate OCR was low quality.
- Three first-pass Vision responses used fenced/alternate JSON and were sanitized before full structure could be recovered. The generic parser was fixed, and one critical alarm-screen retry verified direct structured parsing. No additional retries were used beyond the eight-call target.
- These results validate the safety-gated workflow, not model accuracy or automatic diagnosis.
