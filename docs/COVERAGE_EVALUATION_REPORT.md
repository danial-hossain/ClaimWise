# Coverage Evaluation Report

- Cases: 7/7 passed (100.0%)
- Retrieval recall: 100.0%
- Overall: PASS

## Stage Summary

| Stage | Passed | Checks | Pass rate |
| --- | ---: | ---: | ---: |
| extraction | 2 | 2 | 100.0% |
| retrieval | 5 | 5 | 100.0% |
| evidence_context | 5 | 5 | 100.0% |
| evaluation | 4 | 4 | 100.0% |
| verification | 4 | 4 | 100.0% |

## Cases

| Case | Result | Failure stage |
| --- | --- | --- |
| bordered-vector-table | PASS | - |
| unbordered-visual-table | PASS | - |
| multi-event-camera-and-accommodation | PASS | - |
| emergency-room-copayment | PASS | - |
| camera-limit-and-depreciation | PASS | - |
| cosmetic-rhinoplasty-exclusion | PASS | - |
| additional-accommodation-limit | PASS | - |

## Recorded Stage-2 event evaluation

Offline recorded model output; this does not measure live LLM reasoning.

| Metric | Accuracy |
| --- | ---: |
| extraction_accuracy | 100.0% |
| retrieval_recall | 100.0% |
| selection_recall | 100.0% |
| status_accuracy | 100.0% |
| amount_accuracy | 100.0% |
| citation_accuracy | 100.0% |

| Event | Error stage |
| --- | --- |
| global-exclusion | pass |
| optional-condition | pass |
| limit-and-depreciation | pass |
| section-scoped-condition | pass |
| cross-reference | pass |
| table-detector-miss | pass |
