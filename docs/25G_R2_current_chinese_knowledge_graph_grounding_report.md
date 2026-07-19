# Task 25G-R2 Current Chinese Knowledge Graph Grounding Report

## 1. Final Status

- Final result: `TASK25G_R2_CURRENT_CHINESE_GRAPH_EVIDENCE_INSUFFICIENT`.
- R1 baseline: `TASK25G_R1_CURRENT_EVIDENCE_INSUFFICIENT`.
- Fact inventory: PASS; all 68 active graph facts have stable Node/Edge identities and hashes.
- Evidence matching: PASS as an audit; the matcher produced 983 bounded candidates and classified every fact.
- Grounding applied: no. The frozen core contains 10 exact facts, but only 1 edge and 1 relation type, below the non-vacuous minimum.
- Non-vacuous context: FAILED as expected; production context remains empty and is explicitly marked vacuous.
- RAG and diagnosis: safely blocked by the current-evidence gate.
- Performance and full regression: PASS.
- Static LoongArch/Kylin preparation remains as frozen by Task 25G; no physical-machine acceptance was run.

This result is intentionally not promoted to KG production-ready. Ten exact fact matches do not satisfy the required edge and relation diversity, so applying them would create a misleading partial non-empty graph.

## 2. Frozen Baseline and Corpus Manifest

| Item | Frozen value |
|---|---:|
| active facts | 68 |
| historical evidence | 76 |
| R1 pending remediation candidates | 2 |
| current Chinese documents | 16 |
| active chunks | 1262 |
| Semantic Unit V2 | 2508 |
| corpus SHA-256 | `a3d38d58f83525eb5b6706aad1e621942104eb03a489125f71141392362d8245` |
| Alembic | `20260712_0015` |

The corpus manifest records document, chunk and semantic-unit identifiers, scope attributes, locators and hashes. It does not treat a document title, co-occurrence, vector similarity, task output or benchmark label as engineering evidence.

## 3. Active Fact Inventory

Category totals: identity=13, structural=5, diagnostic=26, action=13, safety=5, verification=0, historical-only=6, ambiguous=0.

| # | Fact ID | Kind | Category | Stable fact label | Identity SHA-256 |
|---:|---|---|---|---|---|
| 1 | `node:025631b0-153c-4316-a27b-64cd4481a2f1` | NODE | IDENTITY_FACT | component:communication_module | `d4e679ea8e36bd31368a8a6b838892e68bd424058a46468427be2b81ead23a31` |
| 2 | `node:046b543c-25dd-4f4d-97ff-9778bfb8aa19` | NODE | DIAGNOSTIC_FACT | cause:fan_blocked | `e1940616543fce31750e67b4d3ea8b1b86f1532ea68e88c7563d962a5309b042` |
| 3 | `node:067500a7-bb1e-436b-a5d9-e02c6914c41d` | NODE | ACTION_FACT | action:clean | `16b7300b9333ad9b01767fd442aec4dd474786abbe743917e975ecd97dae8d22` |
| 4 | `node:0b97d6e6-3e1c-4aad-a31d-62209845336d` | NODE | DIAGNOSTIC_FACT | symptom:alarm | `0bc5388628a6e998307f8db7b503ce5391c19dbe50d5fdf7d25a1cf3eac49ca0` |
| 5 | `node:0bb461d2-a49b-45a1-94b6-0d20c1cc77a7` | NODE | DIAGNOSTIC_FACT | fault:mppt_abnormal | `2e4f7ec96a64a60b47e6a0fd22695951f4c6c87f8d6de34dd1afec32d1c8dfbd` |
| 6 | `node:0fc9168b-31bd-4893-b91e-b98905d21497` | NODE | DIAGNOSTIC_FACT | fault:communication_interruption | `73a29b54a9c770aa29176d1c03dee0fa018a42ac48819c598fdb1fb63af74cc4` |
| 7 | `node:1b7405d9-376c-4895-8847-0cd991d14d23` | NODE | ACTION_FACT | tool:multimeter | `84be5c168a40f66aca1aa3eea60618dca5c567832fa90e82417e5c64dec316c6` |
| 8 | `node:1d792c9f-e788-4dfe-aecf-3bc773f313fa` | NODE | IDENTITY_FACT | product_series:SUN2000 | `28bb4ca02ac96276f1da636c2456bab3b8f98b79dd4e5390ffd0230bd2db3134` |
| 9 | `node:23e170f0-e2fc-4696-be93-ce0ccec32be9` | NODE | IDENTITY_FACT | product_series:SG | `52bbd3d16e7df430458b15b69360525a0e7d6d64c4fedf58546c60dd212d6d99` |
| 10 | `node:29310b2a-0cda-45a7-9907-1236e58e0baf` | NODE | DIAGNOSTIC_FACT | cause:moisture | `13199703c947334990c1cce42402fbc353bd0df38e0dffc110809313bcc754eb` |
| 11 | `node:295de4a0-655b-4e03-84da-ac4738004e4b` | NODE | DIAGNOSTIC_FACT | cause:grounding_abnormal | `3ec5dce2b8977efbb96800134b211d314cbe3896926c944feab22b9791c8f70d` |
| 12 | `node:462e6357-e093-49d8-a6dc-57b0256a4736` | NODE | IDENTITY_FACT | device_model:SG125HX | `0c37a1feeec7850c1de4038a751a4a6b205c39017192919641d54044565ab071` |
| 13 | `node:51a917e9-c2b1-4bbd-8a49-495f6b85ea40` | NODE | IDENTITY_FACT | alarm:A-503 | `11738319e3f192f684381dfdee61a332239b8d0d8eb885b6852747e7bbfc0ab2` |
| 14 | `node:5733e1f7-105c-40df-8f1c-8054d320c2c7` | NODE | IDENTITY_FACT | device_model:SUN2000-50KTL | `7851ac1eb26dd604edddaa8d1716977d60aafc71cf2438f7df46f0fad9f5ab6a` |
| 15 | `node:5d09b7d5-72a5-44bc-81b4-7b7e3cc64c60` | NODE | IDENTITY_FACT | manufacturer:huawei | `c38806942c5e92ed086a18ee504c561e07de066b85169b01706e5b4b23ad44df` |
| 16 | `node:5e5cbdc6-f239-422f-91a8-bf55968b363d` | NODE | HISTORICAL_ONLY_FACT | knowledge_chunk:knowledge_chunk:708f8ca8-16c3-4129-8d47-cb566384e32d | `ac91b739f03998f128140d62fe72e6a8111457651cbf7c107da59b338349b120` |
| 17 | `node:63751d54-b02d-4a1f-82b7-5c3e2b4ea3a4` | NODE | IDENTITY_FACT | alarm:ALM-2001 | `6e9299c19dc48cb4eefb9bed0c7f082dd2cfa244c8c44c84b3d700e9428fd352` |
| 18 | `node:76191aea-6c38-4b5b-ac41-ed3189b7a308` | NODE | HISTORICAL_ONLY_FACT | knowledge_document:knowledge_document:37b5ed59-964f-46e1-b0da-e05f277e38a7 | `ad0e193983bce1f5c253dcac236d0221d3442b7dbe6b87ecf424dbb73c3ddd99` |
| 19 | `node:76a63edf-5f4f-4bd4-9a33-065f4c8a259d` | NODE | HISTORICAL_ONLY_FACT | knowledge_document:knowledge_document:e029dfcb-d8be-4b39-8151-c22c043d93c8 | `41b73b49992a9e34c9815aec61c9606a7ae29492c91e7af94126b990c1a02d08` |
| 20 | `node:7fea948b-ba57-4e5e-86a5-00894b859c7c` | NODE | IDENTITY_FACT | component:ac_side | `feabd407126b79c5cdb61286d22dd8277856aef057ee982c032696b3b4386a2e` |
| 21 | `node:9790b985-29dd-4c8b-bdbe-07d96c873c03` | NODE | SAFETY_FACT | safety_risk:ppe | `02fb286a4fa9343db5b568ebde9f24750a1f4f1abfa046be940b2a36da3528db` |
| 22 | `node:9c04dc4e-9a9e-4195-9d8d-4d54a973b742` | NODE | ACTION_FACT | action:power_off | `78464687312022fde7a3b3ce84b4fe151575c6e902f88facbc7f17081fae8148` |
| 23 | `node:9c209ce2-d53e-4f53-9bf4-a001e59baf75` | NODE | ACTION_FACT | tool:insulation_tester | `a2af3b28cd69a6e436768ab1afc60312d386d6146369fb263068ab27725db436` |
| 24 | `node:a6c660cd-a442-4ebd-b0d9-2c9c68a5a27a` | NODE | ACTION_FACT | action:measure | `9d16b5993a04bb6bb45baeb914bda0ce3e1d943bd47e8cbcab4618b2ac525f53` |
| 25 | `node:acbd94d7-7522-450e-b7a7-467573f900cd` | NODE | ACTION_FACT | tool:thermal_imager | `932f56b6131af97b52287b891bc9bcc27e98a643efd4c099fa1d0ddb570f3768` |
| 26 | `node:b4ede6a3-68f7-4837-9844-ae283bd6c1cc` | NODE | SAFETY_FACT | safety_risk:high_voltage | `2339d23078f098482fda0426db6888540316a063290e585a886d86cbdebfc3b9` |
| 27 | `node:b72cd493-9635-4e43-bbe5-203523c95553` | NODE | DIAGNOSTIC_FACT | fault:over_temperature | `bf7456ff911ab8f95c6c1c4b5d6f4552f4873cdd5926470c7dc2753bccfbd442` |
| 28 | `node:b73136c1-c687-400a-bd84-8345e20361e2` | NODE | IDENTITY_FACT | product_series:FusionSolar | `76312e134d4fa851ace35ceb15e1ee666c19e6978613486abf14c6cb34e41373` |
| 29 | `node:c6d3d0e2-5126-481c-b6a6-23d3d36b849c` | NODE | IDENTITY_FACT | component:fan | `43c11fbad9c5d082b742f494a0897e8a948f1cb8a620ad1e1a7234b08fea19c5` |
| 30 | `node:d3322509-fadc-4560-9636-7523ce230cd5` | NODE | IDENTITY_FACT | component:dc_side | `649c3e69d94ea83883b6a3231638b34c57f8a634df5c62ab0072208f049953d8` |
| 31 | `node:d5dc6ab6-6e85-4e88-a1f8-bafb2bf75cb7` | NODE | IDENTITY_FACT | manufacturer:sungrow | `c1b2d76f4b918d5acee53bfd7faeb88fe17497ac8fbb727028160d48de605256` |
| 32 | `node:e2c21f54-fbf2-432f-9390-5ed73df7abe3` | NODE | DIAGNOSTIC_FACT | fault:low_insulation_resistance | `e5c0079a16beb0d88770b8c87ff9c41ecc7d2458d64c5f4860667e3920b32308` |
| 33 | `node:e937246c-ac86-4fbe-8b19-a1019d63a160` | NODE | HISTORICAL_ONLY_FACT | knowledge_chunk:knowledge_chunk:fb6f389f-7fa2-47eb-8cbd-f4dc9b216e5d | `cccecf274530e2a5b05de0024f7daa9834891633348c5893746b11d54e78d1b6` |
| 34 | `node:ea2b990f-78c9-464d-81a8-c42e8ee111d9` | NODE | DIAGNOSTIC_FACT | symptom:offline | `9372178446d676ce0a86229ac77aebeac4d442699e4c11b27577fb4372f4cae5` |
| 35 | `edge:0bc46f84-c1fe-4555-99fa-b86f9e3535ad` | EDGE | STRUCTURAL_FACT | product_series:SUN2000 -BELONGS_TO-> manufacturer:huawei | `6ca48af6691a5670767e276019be30fe1414791e208bed96fc03372edb6ea670` |
| 36 | `edge:10af7af3-2fb0-411e-897b-2ad9a1cfe1db` | EDGE | SAFETY_FACT | fault:over_temperature -HAS_SAFETY_RISK-> safety_risk:ppe | `1914f42a3d2042fcd07f471595ce51631b23b7e582032d3498152693f2b94948` |
| 37 | `edge:20ffbdc9-5dc9-4ebb-8cfe-da09ca33fe81` | EDGE | DIAGNOSTIC_FACT | fault:low_insulation_resistance -CAUSED_BY-> cause:moisture | `e49869ea6f6792044729c50f49d98489af47a16e225ea2ebfaf41e3d27e0cfba` |
| 38 | `edge:224681c1-d31b-46d2-8d4a-c67ca90d2c3d` | EDGE | DIAGNOSTIC_FACT | fault:low_insulation_resistance -HAS_ALARM-> alarm:ALM-2001 | `86e7c6ac0491644f39e49c154be039cb15f69004a4b098905ce73b8ea7bf2b35` |
| 39 | `edge:2805d567-419b-412e-ae08-a62a0b0558fd` | EDGE | ACTION_FACT | fault:low_insulation_resistance -USES_TOOL-> tool:insulation_tester | `18bb7fea83a7d0ef073874486960a173366d8f35c034b99a41c97a6b79178f99` |
| 40 | `edge:2d631a44-6110-47a3-ba34-52f43cfb0bd7` | EDGE | ACTION_FACT | fault:over_temperature -RESOLVED_BY-> action:clean | `6ca0c3608ce65740a48aadbb1aa151354a27a63d7114999f790d69227288303f` |
| 41 | `edge:2e428953-43bc-440f-8e74-9224e3fff82e` | EDGE | DIAGNOSTIC_FACT | fault:over_temperature -CAUSED_BY-> cause:fan_blocked | `9f076b5fee1669051a69bb519a688e693f487c4bb2f56c1f45c9a7f407dbcbba` |
| 42 | `edge:325c0bce-588b-40fd-bd94-97779485a566` | EDGE | DIAGNOSTIC_FACT | fault:low_insulation_resistance -CHECK_BY-> component:dc_side | `fcb6a361e581e6c1fd8dda79aa7cbc5dfd81e29fb98c72f263f216030ebf22cb` |
| 43 | `edge:337dbcfb-feb5-42e5-8771-215e038ea3d0` | EDGE | DIAGNOSTIC_FACT | fault:communication_interruption -HAS_SYMPTOM-> symptom:offline | `9e5716a5919df33fc1a1ec6bcc60c05cbf84b508e5143ec05e522341969b9859` |
| 44 | `edge:35824ec3-ac5b-4b81-944f-65643bb31316` | EDGE | DIAGNOSTIC_FACT | fault:low_insulation_resistance -HAS_SYMPTOM-> symptom:alarm | `a554411ef57c69c80a436552cfd2ddaab219473034aaf233f0b7d51429536a51` |
| 45 | `edge:35c16840-c765-44a3-b1ba-1405115115c6` | EDGE | HISTORICAL_ONLY_FACT | knowledge_chunk:knowledge_chunk:708f8ca8-16c3-4129-8d47-cb566384e32d -DERIVED_FROM-> knowledge_document:knowledge_document:e029dfcb-d8be-4b39-8151-c22c043d93c8 | `6a5b7707b0c4b74a62352c8f332220b2fc3e75bc7c78b2d54dbe164b22e6e258` |
| 46 | `edge:392bb54f-1749-45a9-ab1f-dac267429e46` | EDGE | DIAGNOSTIC_FACT | fault:mppt_abnormal -CHECK_BY-> component:dc_side | `e83c8bee5685c95c27fa631baa88908315d3b63e0fa4d99b9a0d3b19338897da` |
| 47 | `edge:4808f303-0dfd-493f-86fc-b35af437e619` | EDGE | SAFETY_FACT | fault:communication_interruption -HAS_SAFETY_RISK-> safety_risk:high_voltage | `386dc23e0a483ef578bcac9cd5642855e034ed6d855d30e63f19002b60da4bff` |
| 48 | `edge:488a9334-2f27-4047-9232-b3946c6549c6` | EDGE | SAFETY_FACT | fault:low_insulation_resistance -HAS_SAFETY_RISK-> safety_risk:high_voltage | `ca9071fdb1a12fef5c1c3be3216304fa4d4be92faa886fcd522169b9827c2212` |
| 49 | `edge:5136587d-d5b8-4e75-89de-0e32ef86cfb2` | EDGE | ACTION_FACT | fault:low_insulation_resistance -RESOLVED_BY-> action:measure | `bd4d6ab35b40dad220941d2cac1fdc30ca0b56e262a58478f1e161d9e34372d4` |
| 50 | `edge:5b0daa3e-2704-4127-909b-b5407f6af405` | EDGE | DIAGNOSTIC_FACT | fault:over_temperature -HAS_SYMPTOM-> symptom:alarm | `cce95a7bc6907f77b2230d1516572543ba2e45e9e6fefc6b225153d93c7283bc` |
| 51 | `edge:5d07b52b-c7ce-460a-ab77-674dcc0800dc` | EDGE | STRUCTURAL_FACT | device_model:SG125HX -BELONGS_TO-> product_series:SG | `99af2024349f71de1ae2f52a909d7bb30c63c0048be788b98ba12426758ab213` |
| 52 | `edge:5d5e2c8d-d5ab-4994-8a79-11a1cd04ac58` | EDGE | ACTION_FACT | fault:over_temperature -USES_TOOL-> tool:thermal_imager | `7abf100c568ea27440c23652f7d5764e1ae286edd6dc2519a0bbab39d5612f2a` |
| 53 | `edge:6f25d737-e445-4adc-9670-74802ca7a3d7` | EDGE | STRUCTURAL_FACT | product_series:FusionSolar -BELONGS_TO-> manufacturer:huawei | `37bb5cbb372144f6166fab5350680af2da0114b98d1c7a2729b0a095b09d7c78` |
| 54 | `edge:79d76ee8-a772-484c-960d-403ff176ddb1` | EDGE | ACTION_FACT | fault:communication_interruption -USES_TOOL-> tool:multimeter | `9193c824a6151a55b16bb169701218d6deca64b741eaecb0994a4745179188ad` |
| 55 | `edge:7b83a49e-705b-4105-af2b-9ed7dc7fb646` | EDGE | DIAGNOSTIC_FACT | fault:low_insulation_resistance -CAUSED_BY-> cause:grounding_abnormal | `440609b7518c4423c2af07f493324e97d26b77cc52ff89c9136109112a4f66b1` |
| 56 | `edge:8903ac85-e3f1-46f1-a80a-6a9e8d11844b` | EDGE | DIAGNOSTIC_FACT | product_series:SG -HAS_FAULT-> fault:over_temperature | `28af81cb362e1be5d3e1e962024d7893051e3aa1de814272a066d4b968f68c5d` |
| 57 | `edge:967797cc-f31b-406c-b45d-77974fadcfdc` | EDGE | ACTION_FACT | fault:mppt_abnormal -USES_TOOL-> tool:multimeter | `fdd756beedbe08dc4025703c146885821e5241b832c6c00d17ac2e46d0af6f4d` |
| 58 | `edge:a186a68d-60db-4d0b-bd1e-988e412ebba1` | EDGE | DIAGNOSTIC_FACT | fault:communication_interruption -CHECK_BY-> component:communication_module | `3412d8eb21ca98d8ae24bd93447f01e4f40760c3aed41b3579c5208c082e5606` |
| 59 | `edge:a799805d-eb23-4787-ac8d-c7a31524abd7` | EDGE | DIAGNOSTIC_FACT | fault:communication_interruption -HAS_ALARM-> alarm:A-503 | `f5016715cde3beafae85163a141d0be4a04f9bda85a4c2ebc1ea3b4a0317abb4` |
| 60 | `edge:a9b9aa6d-05d8-42c6-aed8-d787ae088f55` | EDGE | DIAGNOSTIC_FACT | product_series:SG -HAS_FAULT-> fault:mppt_abnormal | `55aeeb566204811592bf63d7c797aeada1a0c9663397b8ab9ec15d0d9a32f04c` |
| 61 | `edge:b6eb2f59-b0fd-4876-9ba5-70ef73f67fb4` | EDGE | DIAGNOSTIC_FACT | fault:over_temperature -CHECK_BY-> component:fan | `61127e6ffee91f960d24496a742e20365af607959b82d3798e440b656d232fec` |
| 62 | `edge:b8091840-1eb4-41d6-88b1-e31f8849f45b` | EDGE | DIAGNOSTIC_FACT | product_series:SUN2000 -HAS_FAULT-> fault:low_insulation_resistance | `c5832a1afe86e87132762d172bc943b7f69ec4a9893b3cb6d4b0a5adbc8dcdb2` |
| 63 | `edge:d2d6a012-33e6-4190-9268-ce94677f44c8` | EDGE | STRUCTURAL_FACT | product_series:SG -BELONGS_TO-> manufacturer:sungrow | `961a0ce761b6d6e9514ab51af6eff6f16804f51c9d0dc0461afbaca7872be85e` |
| 64 | `edge:d61074b9-d0e9-4e94-87d9-cf6bf6b2cc00` | EDGE | ACTION_FACT | fault:communication_interruption -RESOLVED_BY-> action:power_off | `8ce1a933c64a41ca0e98139aba607467e91e42bb47e3c7944a3e019cf401638d` |
| 65 | `edge:d7b68bcf-6275-4f8b-9eba-e25bf521c7f7` | EDGE | HISTORICAL_ONLY_FACT | knowledge_chunk:knowledge_chunk:fb6f389f-7fa2-47eb-8cbd-f4dc9b216e5d -DERIVED_FROM-> knowledge_document:knowledge_document:37b5ed59-964f-46e1-b0da-e05f277e38a7 | `01e93b559d525227cf21e0a4936cfddb9f147375043582879a02dc601355e11e` |
| 66 | `edge:e380ca8f-74e9-493b-b3c6-4e2568be3aea` | EDGE | DIAGNOSTIC_FACT | fault:mppt_abnormal -HAS_SYMPTOM-> symptom:alarm | `0793cc22eca890fcc2b89fb9824af0b518c1d2db6e18ef3b475c2ebb94cfd11a` |
| 67 | `edge:f3b321ac-f824-4b72-888a-4fc4409f3c3a` | EDGE | STRUCTURAL_FACT | device_model:SUN2000-50KTL -BELONGS_TO-> product_series:SUN2000 | `d64f3b1150396f761b695ea9c57d4327f8239d1c8d8a47dbe08cfafac8aebbbb` |
| 68 | `edge:fc022429-1f11-4ea0-a5fa-535da0a7c3c8` | EDGE | DIAGNOSTIC_FACT | product_series:SUN2000 -HAS_FAULT-> fault:communication_interruption | `a1542151f3b2af6387053c4ed1449e338f661db85dfa324ee67be05c8fcf19b7` |

Node facts and edge facts are evaluated independently. Identity is deterministic and does not depend on insertion order or display-name-only matching.

## 4. Matcher and Relation Evidence Matrix

- Matcher version: `task25g_r2_current_chinese_matcher_v1`.
- Relation matrix version: `task25g_r2_relation_evidence_matrix_v1`.
- Maximum candidates per fact: 20.
- Candidate channels: current Semantic Unit V2, source chunk, section locator and current document metadata.
- Alias use: normalization only; an alias is never evidence.
- Direct edge support requires exact subject, exact object, compatible relation, compatible product/model/alarm/component, current Chinese engineering approval, a valid locator and an explicit relation expression in the same source span.
- `FULL_SECTION` is auxiliary only and cannot establish a direct relation by itself.
- No fact-ID-specific override, LLM equivalence decision, vector-only binding or document-wide binding is used.

The matrix covers identity/structure, alarm, symptom, cause, action/procedure, safety/prerequisite, verification and communication semantic-unit types. Relation compatibility is versioned and generic.

## 5. Evidence Matching Results

| Support level | Facts |
|---|---:|
| DIRECT_EXACT_SUPPORT | 10 |
| DIRECT_MULTI_SOURCE_SUPPORT | 0 |
| PARTIAL_SUPPORT | 41 |
| ENTITY_ONLY_MATCH | 0 |
| RELATION_ONLY_MATCH | 4 |
| CONTRADICTED | 0 |
| NOT_SUPPORTED | 13 |
| review required | 58 |

Direct support is limited to 9 nodes and 1 edge. The only exact edge relation type is `HAS_SYMPTOM`. No SG fact borrowed Huawei evidence; incompatible product-family evidence remains partial or unsupported.

### Direct Support Audit

| Fact ID | Kind | Category | Support | Document | Chunk | Locator |
|---|---|---|---|---|---|---|
| `edge:35824ec3-ac5b-4b81-944f-65643bb31316` | EDGE | DIAGNOSTIC_FACT | DIRECT_EXACT_SUPPORT | `c50295a3-1f71-40a6-b621-5f1ab3a4b554` | `091cba74-d885-43a7-8b29-e58f3281ed7e` | page 88; semantic_unit=su2_7a20de3ccf13cfa1fba7c014286d535b853fc298466dd9f5 |
| `node:0b97d6e6-3e1c-4aad-a31d-62209845336d` | NODE | DIAGNOSTIC_FACT | DIRECT_EXACT_SUPPORT | `c50295a3-1f71-40a6-b621-5f1ab3a4b554` | `0915a612-97ec-4f93-944f-d5e49b652a1c` | page 71; semantic_unit=su2_3c11eafaaef98b85af27e3972c7a34e6598c88bc050177f8 |
| `node:1b7405d9-376c-4895-8847-0cd991d14d23` | NODE | ACTION_FACT | DIRECT_EXACT_SUPPORT | `2ee5665d-5a65-48dc-9e1e-1aaecd73a121` | `86170d02-b1eb-4d34-8b16-d95a9ca36a56` | page 51; semantic_unit=su2_172159ca959c85e422109cc320ac622a72c2e67baf278ecc |
| `node:1d792c9f-e788-4dfe-aecf-3bc773f313fa` | NODE | IDENTITY_FACT | DIRECT_EXACT_SUPPORT | `1666856f-bcb6-43a4-b434-1ff057b67cbc` | `af8b1c7c-d62a-4df5-9c3d-c451d9e6b009` | page 68; semantic_unit=su2_fc127f89ed8ec731bd0b6d28c456a0db327d7e427984b8db |
| `node:5d09b7d5-72a5-44bc-81b4-7b7e3cc64c60` | NODE | IDENTITY_FACT | DIRECT_EXACT_SUPPORT | `1666856f-bcb6-43a4-b434-1ff057b67cbc` | `7070f107-5852-4442-b2e3-9c01a950abbb` | page 287; semantic_unit=su2_e1fd85389249803d15f7cf12fadd0e8cec37cef484de6494 |
| `node:a6c660cd-a442-4ebd-b0d9-2c9c68a5a27a` | NODE | ACTION_FACT | DIRECT_EXACT_SUPPORT | `c50295a3-1f71-40a6-b621-5f1ab3a4b554` | `652fb052-f438-47dd-8a05-348bc9159cc4` | page 53; semantic_unit=su2_b0afceb9aaacc908407d56b13e9a42837291e66e2674a6a5 |
| `node:b73136c1-c687-400a-bd84-8345e20361e2` | NODE | IDENTITY_FACT | DIRECT_EXACT_SUPPORT | `fbb02382-88d0-4f5a-a8fb-56404a8b7cf2` | `f9a19e18-7b63-4391-9f9c-71d86a3bff86` | page 62; semantic_unit=su2_f275a4ffc7a3b8f1ca6e23048fd1c8c18396ba35c1fa8cc5 |
| `node:d3322509-fadc-4560-9636-7523ce230cd5` | NODE | IDENTITY_FACT | DIRECT_EXACT_SUPPORT | `c50295a3-1f71-40a6-b621-5f1ab3a4b554` | `652fb052-f438-47dd-8a05-348bc9159cc4` | page 53; semantic_unit=su2_bede3ddd4f66c9ccf4e8bcbdcc02759922cb6c462819d459 |
| `node:e2c21f54-fbf2-432f-9390-5ed73df7abe3` | NODE | DIAGNOSTIC_FACT | DIRECT_EXACT_SUPPORT | `c50295a3-1f71-40a6-b621-5f1ab3a4b554` | `98f6ef8c-18dd-4052-aaa8-09e358bfaf06` | page 87; semantic_unit=su2_5ff52d646058d17510d5aeb36e4090ecd47472b0d3ba09d0 |
| `node:ea2b990f-78c9-464d-81a8-c42e8ee111d9` | NODE | DIAGNOSTIC_FACT | DIRECT_EXACT_SUPPORT | `2ee5665d-5a65-48dc-9e1e-1aaecd73a121` | `cc589525-4bec-48a3-af13-220925b18eaa` | page 39; semantic_unit=su2_54b1c133e19533321600e908e571dd3943570732f3bf8f65 |

The table intentionally excludes source text. Full candidate evidence remains in the runtime JSON/CSV with canonical hashes and auditable locators.

## 6. Production Core Manifest and Gate

- Manifest version: `task25g_r2_production_core_fact_manifest_v1`.
- Manifest SHA-256: `285edbc36f2a899355717da495281bc684f2af28b2293ab58014dd65ab397879`.
- Eligible exact facts: 10.
- Eligible nodes: 9.
- Eligible edges: 1.
- Relation types: 1 (`HAS_SYMPTOM`).
- Current evidence candidates: 10.
- Categories: 3 (ACTION_FACT, DIAGNOSTIC_FACT, IDENTITY_FACT).
- Gate: FAILED because edges must be >=5 and relation types must be >=2.

The manifest was frozen before any potential apply and was reused unchanged by subsequent regression runs.

## 7. Grounding Plan, Dry Run and Governance

- Plan status: `TASK25G_R2_GROUNDING_PLAN_REJECTED`.
- `CREATE_CURRENT_EVIDENCE_LINK`: 10 planned operations.
- `REUSE_CURRENT_EVIDENCE_LINK`: 0 planned operations.
- `MARK_HISTORICAL_EVIDENCE_NON_PRODUCTION`: 76 checks/operations.
- `CREATE_MANUAL_REVIEW_CANDIDATE`: 58 planned operations.
- Dry-run result: `DRY_RUN_GATE_BLOCKED`.
- Transaction committed: false.
- Database writes/current evidence links: 0/0.
- Historical evidence preserved: 76.
- Manual review candidates: 58; created on the final idempotency run=0, reused=58.
- Candidate auto-approval: 0.
- Fact auto-publication: 0.
- Expert auto-write: false.

The explicit `--apply-approved-engineering-grounding` path was not run because the core gate failed. Unsupported facts were not deleted or rewritten; they remain excluded from production and represented by pending manual-governance candidates.

## 8. Non-Vacuous Context and Scope

| Gate | Result |
|---|---:|
| production facts | 0 |
| production nodes | 0 |
| production edges | 0 |
| current evidence | 0 |
| citations | 0 |
| current-valid coverage | 0.00 |
| locator coverage | 0.00 |
| empty context | true |
| vacuous metric | true |
| safe empty-context degradation | true |

Leakage: archived=0, English=0, pending=0, marketing=0, superseded=0, approval=0, unsupported=0, scope=0.

Citation preservation is **not** reported as 1.00: there were zero returned graph facts and zero citation observations, so the metric is explicitly vacuous.

## 9. RAG, Diagnosis, Workflow and Alias Boundaries

- RAG queries: 20; status=`BLOCKED_BY_CURRENT_EVIDENCE_GATE`.
- KG RAG context non-empty: false.
- Citation observations/preservation: 0/0.00; vacuous=true.
- Unsupported facts/wrong model-or-alarm/scope changes: 0/0/0.
- KG_ALIAS duplicate RRF voting: 0.
- Diagnosis probes: 3; status=`BLOCKED_BY_CURRENT_EVIDENCE_GATE`.
- Diagnosis grounded facts/citations: 0/0.
- Workflow automatic graph writes: 0.
- Correction review boundary: true.
- Automatic diagnosis confirmation: false.
- Safe degradation: RAG=true, diagnosis=true.
- Alias policy retained: both incompatible collisions remain non-resolvable without context; unsafe automatic resolution remains zero.

## 10. Performance Preservation

| Operation | p50 | p95 | Gate | Result |
|---|---:|---:|---:|---|
| node search | 1.082 ms | 1.732 ms | 500 ms | PASS |
| alias | 0.930 ms | 1.542 ms | 300 ms | PASS |
| one-hop | 0.873 ms | 1.966 ms | 800 ms | PASS |
| two-hop | 0.871 ms | 2.180 ms | 1500 ms | PASS |
| RAG context | 17.287 ms | 69.476 ms | 1200 ms | PASS |

- Maximum SQL: 4.
- Serializer SQL: 0.
- N+1: false.

## 11. Full Regression

| Group | Result |
|---|---|
| compileall | PASS |
| Alembic heads/current | PASS (`20260712_0015`) |
| pytest | PASS (482 passed, 3 skipped) |
| security | PASS |
| RBAC | PASS |
| RAG | PASS |
| agents | PASS |
| Knowledge Curator | PASS |
| Task 25D | PASS |
| Task 25E | PASS |
| Task 25F-R1 | PASS |
| Task 25G | PASS |
| Task 25G-R1 | PASS |
| R2 matching | PASS |
| R2 grounding | EXPECTED_BLOCKER |
| R2 performance | PASS |
| R2 reconciliation | PASS |
| final smoke | PASS |

## 12. Integrity, Reconciliation and Deployment Boundaries

- Task 25G original report/runtime unchanged: true/true.
- Task 25G-R1 report unchanged: true.
- Task 25G-R1 immutable runtime unchanged: true.
- Disclosed R1 volatile audit refresh: `kg_performance_preservation.json`. One historical performance JSON was refreshed before child-process isolation; no R1 report or immutable evidence artifact changed.
- `backend/.env`, current corpus, active facts, historical evidence, Alembic and ZIP inventory: unchanged.
- Vector namespaces: default=80, pilot_r2=1262, task25b_r1_canary=192; vector writes=0, embedding writes=0.
- pilot_r2 changed: no. pilot_r3_semantic changed: no. pilot_r4_grounded changed: no. pilot_r5_query_aware changed: no.
- Document/chunk/Semantic Unit updates: 0/0/0.
- Approval updates/expert auto-write: 0/false.
- Full reindex: false; `TASK25B_ALLOW_FULL_REINDEX=false` remained enforced.
- Package/ZIP generated: no. Git add/commit/reset/clean/restore: not executed; staged files remained zero.
- Task 25C remains `MULTIMODAL_BENCHMARK_INSUFFICIENT`.
- R6 remains `DEFERRED_QWEN3_RERANK_CONFIG`.
- Static LoongArch/Kylin preparation: retained from Task 25G.
- Physical LoongArch/Kylin acceptance: not executed and not claimed.

## 13. Final Judgment

- KG production ready: **no**.
- KG deployment ready for production RAG/diagnosis: **no**.
- Static deployment preparation: retained/pass from Task 25G, real machine pending.
- Human graph review required: **yes**, for 58 pending candidates and for expanding exact edge/relation coverage.
- Remaining blockers: exact grounded edges must increase from 1 to at least 5; exact grounded relation types must increase from 1 to at least 2; only then may the frozen/apply workflow be rerun and the non-vacuous RAG/diagnosis gates evaluated.
- No return to Task 25C or R6 is required to resolve this graph-evidence blocker.
