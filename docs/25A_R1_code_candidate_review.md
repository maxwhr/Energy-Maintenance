# Task 25A-R1 代码候选二次复核

生成时间：2026-07-10T13:39:03.515504+00:00

## 结论

- dead=24，duplicate=42，deprecated=45。
- 共 111 个候选，`safe_to_remove_now=true` 为 0；本任务删除候选数为 0。
- 静态引用、import、router、model/agent/provider registry、前端路由、package script、测试和文档引用均重新检查；动态注册仍是必须保留的风险边界。

## 分类统计

- KEEP_COMPATIBILITY: 3
- KEEP_DYNAMIC_REGISTRATION: 49
- KEEP_PRODUCTION: 10
- KEEP_TEST_ONLY: 2
- REFACTOR_DUPLICATE: 11
- REVIEW_DEPRECATION: 36

## 候选明细

| 类型 | 路径/符号 | 分类 | 静态引用 | 动态风险 | 可立即删除 |
|---|---|---|---:|---|---|
| dead | `frontend/src/api/externalApis.ts :: externalApis` | KEEP_DYNAMIC_REGISTRATION | 4 | high | false |
| dead | `frontend/src/api/recordCenter.ts :: recordCenter` | KEEP_PRODUCTION | 15 | medium | false |
| dead | `frontend/src/api/vectorSearch.ts :: vectorSearch` | KEEP_PRODUCTION | 3 | medium | false |
| dead | `frontend/src/assets/hero.png :: hero` | KEEP_PRODUCTION | 2 | medium | false |
| dead | `frontend/src/assets/p1_workbench.jpg :: p1_workbench` | KEEP_PRODUCTION | 2 | medium | false |
| dead | `frontend/src/assets/p2_knowledgeBase.jpg :: p2_knowledgeBase` | KEEP_PRODUCTION | 2 | medium | false |
| dead | `frontend/src/assets/p3_equipment.jpg :: p3_equipment` | KEEP_PRODUCTION | 2 | medium | false |
| dead | `frontend/src/assets/p4_task.jpg :: p4_task` | KEEP_PRODUCTION | 2 | medium | false |
| dead | `frontend/src/assets/vite.svg :: vite` | KEEP_PRODUCTION | 211 | medium | false |
| dead | `frontend/src/assets/vue.svg :: vue` | KEEP_DYNAMIC_REGISTRATION | 1105 | high | false |
| dead | `frontend/src/components/PageHeader.vue :: PageHeader` | KEEP_PRODUCTION | 3 | medium | false |
| dead | `frontend/src/views/agent/Workbench.vue :: Workbench` | KEEP_DYNAMIC_REGISTRATION | 39 | high | false |
| dead | `frontend/src/views/assistant/Chat.vue :: Chat` | KEEP_DYNAMIC_REGISTRATION | 124 | high | false |
| dead | `frontend/src/views/device/Alarms.vue :: Alarms` | KEEP_DYNAMIC_REGISTRATION | 20 | high | false |
| dead | `frontend/src/views/device/Inventory.vue :: Inventory` | KEEP_DYNAMIC_REGISTRATION | 40 | high | false |
| dead | `frontend/src/views/device/Models.vue :: Models` | KEEP_DYNAMIC_REGISTRATION | 39 | high | false |
| dead | `frontend/src/views/knowledge/Cases.vue :: Cases` | KEEP_DYNAMIC_REGISTRATION | 24 | high | false |
| dead | `frontend/src/views/knowledge/Contributions.vue :: Contributions` | KEEP_DYNAMIC_REGISTRATION | 51 | high | false |
| dead | `frontend/src/views/knowledge/Documents.vue :: Documents` | KEEP_DYNAMIC_REGISTRATION | 96 | high | false |
| dead | `frontend/src/views/report/Overview.vue :: Overview` | KEEP_PRODUCTION | 96 | medium | false |
| dead | `frontend/src/views/review/Corrections.vue :: Corrections` | KEEP_DYNAMIC_REGISTRATION | 53 | high | false |
| dead | `frontend/src/views/system/Users.vue :: Users` | KEEP_DYNAMIC_REGISTRATION | 72 | high | false |
| dead | `frontend/src/views/workorder/Create.vue :: Create` | KEEP_DYNAMIC_REGISTRATION | 455 | high | false |
| dead | `frontend/src/views/workorder/List.vue :: List` | KEEP_DYNAMIC_REGISTRATION | 644 | high | false |
| duplicate | `backend/app/api/routes/knowledge.py :: knowledge` | KEEP_DYNAMIC_REGISTRATION | 3218 | high | false |
| duplicate | `backend/app/repositories/agent_repository.py :: create_run` | KEEP_DYNAMIC_REGISTRATION | 39 | high | false |
| duplicate | `backend/app/repositories/agent_repository.py :: create_step` | KEEP_DYNAMIC_REGISTRATION | 33 | high | false |
| duplicate | `backend/app/repositories/agent_repository.py :: create_tool_call` | KEEP_DYNAMIC_REGISTRATION | 3 | high | false |
| duplicate | `backend/app/repositories/agent_repository.py :: create_approval` | KEEP_DYNAMIC_REGISTRATION | 19 | high | false |
| duplicate | `backend/app/repositories/correction_repository.py :: get_user` | KEEP_DYNAMIC_REGISTRATION | 33 | high | false |
| duplicate | `backend/app/repositories/device_history_repository.py :: create` | KEEP_DYNAMIC_REGISTRATION | 3464 | high | false |
| duplicate | `backend/app/repositories/device_repository.py :: create` | KEEP_DYNAMIC_REGISTRATION | 3464 | high | false |
| duplicate | `backend/app/repositories/diagnosis_repository.py :: get_by_trace_id` | REFACTOR_DUPLICATE | 9 | medium | false |
| duplicate | `backend/app/repositories/knowledge_contribution_repository.py :: create` | KEEP_DYNAMIC_REGISTRATION | 3464 | high | false |
| duplicate | `backend/app/repositories/knowledge_graph_repository.py :: create_node` | KEEP_DYNAMIC_REGISTRATION | 13 | high | false |
| duplicate | `backend/app/repositories/knowledge_graph_repository.py :: create_edge` | KEEP_DYNAMIC_REGISTRATION | 13 | high | false |
| duplicate | `backend/app/repositories/knowledge_graph_repository.py :: _count` | KEEP_DYNAMIC_REGISTRATION | 1540 | high | false |
| duplicate | `backend/app/repositories/knowledge_repository.py :: create_document` | REFACTOR_DUPLICATE | 19 | medium | false |
| duplicate | `backend/app/repositories/maintenance_task_repository.py :: create` | KEEP_DYNAMIC_REGISTRATION | 3464 | high | false |
| duplicate | `backend/app/repositories/multimodal_evidence_repository.py :: create_job` | REFACTOR_DUPLICATE | 3 | medium | false |
| duplicate | `backend/app/repositories/multimodal_evidence_repository.py :: create_ai_analysis` | REFACTOR_DUPLICATE | 7 | medium | false |
| duplicate | `backend/app/repositories/record_center_repository.py :: _user_name` | REFACTOR_DUPLICATE | 31 | medium | false |
| duplicate | `backend/app/repositories/sop_repository.py :: create_template` | KEEP_DYNAMIC_REGISTRATION | 9 | high | false |
| duplicate | `backend/app/repositories/user_repository.py :: create` | KEEP_DYNAMIC_REGISTRATION | 3464 | high | false |
| duplicate | `backend/app/repositories/vector_index_repository.py :: create_run` | KEEP_DYNAMIC_REGISTRATION | 39 | high | false |
| duplicate | `backend/app/schemas/agent.py :: strip_text` | REFACTOR_DUPLICATE | 22 | medium | false |
| duplicate | `backend/app/schemas/maintenance_task.py :: validate_media_ids` | REFACTOR_DUPLICATE | 5 | medium | false |
| duplicate | `backend/app/services/agent_approval_service.py :: __init__` | KEEP_DYNAMIC_REGISTRATION | 143 | high | false |
| duplicate | `backend/app/services/agent_artifact_conversion_service.py :: _list` | KEEP_DYNAMIC_REGISTRATION | 142 | high | false |
| duplicate | `backend/app/services/agent_orchestrators/multimodal_evidence_orchestrator.py :: __init__` | KEEP_DYNAMIC_REGISTRATION | 143 | high | false |
| duplicate | `backend/app/services/agent_orchestrators/multimodal_evidence_orchestrator.py :: _status_counts` | KEEP_DYNAMIC_REGISTRATION | 14 | high | false |
| duplicate | `backend/app/services/agent_tools/diagnosis_tools.py :: _fault_type` | KEEP_DYNAMIC_REGISTRATION | 79 | high | false |
| duplicate | `backend/app/services/auth_service.py :: __init__` | KEEP_DYNAMIC_REGISTRATION | 143 | high | false |
| duplicate | `backend/app/services/diagnosis_service.py :: _kg_context_summary` | REFACTOR_DUPLICATE | 9 | medium | false |
| duplicate | `backend/app/services/diagnosis_service.py :: _hit_count` | REFACTOR_DUPLICATE | 38 | medium | false |
| duplicate | `backend/app/services/diagnosis_service.py :: _quote` | REFACTOR_DUPLICATE | 13 | medium | false |
| duplicate | `backend/app/services/external_api_adapters/mimo_multimodal_adapter.py :: _image_content` | REFACTOR_DUPLICATE | 7 | medium | false |
| duplicate | `backend/app/services/kg_candidate_service.py :: __init__` | KEEP_DYNAMIC_REGISTRATION | 143 | high | false |
| duplicate | `backend/scripts/check_agent_artifact_conversion_flow.py :: record` | KEEP_DYNAMIC_REGISTRATION | 6228 | high | false |
| duplicate | `backend/scripts/check_agent_artifact_conversion_flow.py :: delivery_zip_snapshot` | KEEP_TEST_ONLY | 22 | medium | false |
| duplicate | `backend/scripts/check_agent_artifact_conversion_flow.py :: ensure_users` | KEEP_DYNAMIC_REGISTRATION | 20 | high | false |
| duplicate | `backend/scripts/check_agent_business_tools_flow.py :: request_json` | KEEP_DYNAMIC_REGISTRATION | 417 | high | false |
| duplicate | `backend/scripts/check_agent_business_tools_flow.py :: ensure_users` | KEEP_DYNAMIC_REGISTRATION | 20 | high | false |
| duplicate | `backend/scripts/check_cloud_model_flow.py :: assert_success` | KEEP_TEST_ONLY | 81 | medium | false |
| duplicate | `backend/scripts/check_cloud_model_flow.py :: login` | KEEP_DYNAMIC_REGISTRATION | 602 | high | false |
| duplicate | `backend/scripts/check_real_agent_provider_integration.py :: _extract_json` | KEEP_DYNAMIC_REGISTRATION | 5 | high | false |
| deprecated | `multiple_or_unresolved :: README.md` | KEEP_COMPATIBILITY | 3 | medium | false |
| deprecated | `backend/README.md :: README` | KEEP_COMPATIBILITY | 80 | medium | false |
| deprecated | `backend/scripts/check_cloud_model_flow.py :: check_cloud_model_flow` | REVIEW_DEPRECATION | 13 | medium | false |
| deprecated | `backend/scripts/check_cloud_model_online.py :: check_cloud_model_online` | REVIEW_DEPRECATION | 37 | medium | false |
| deprecated | `backend/scripts/check_contribution_flow.py :: check_contribution_flow` | REVIEW_DEPRECATION | 17 | medium | false |
| deprecated | `backend/scripts/check_global_acceptance.py :: check_global_acceptance` | KEEP_DYNAMIC_REGISTRATION | 42 | high | false |
| deprecated | `backend/scripts/check_kg_business_integration.py :: check_kg_business_integration` | REVIEW_DEPRECATION | 27 | medium | false |
| deprecated | `backend/scripts/check_knowledge_graph_flow.py :: check_knowledge_graph_flow` | REVIEW_DEPRECATION | 32 | medium | false |
| deprecated | `backend/scripts/check_local_llama_cpp_flow.py :: check_local_llama_cpp_flow` | REVIEW_DEPRECATION | 37 | medium | false |
| deprecated | `backend/scripts/check_model_enhancement_flow.py :: check_model_enhancement_flow` | REVIEW_DEPRECATION | 4 | medium | false |
| deprecated | `backend/scripts/check_model_gateway_flow.py :: check_model_gateway_flow` | REVIEW_DEPRECATION | 2 | medium | false |
| deprecated | `backend/scripts/check_ocr_flow.py :: check_ocr_flow` | REVIEW_DEPRECATION | 37 | medium | false |
| deprecated | `backend/scripts/check_real_frontend_api_integration.py :: check_real_frontend_api_integration` | REVIEW_DEPRECATION | 6 | medium | false |
| deprecated | `backend/scripts/check_review_flow.py :: check_review_flow` | REVIEW_DEPRECATION | 2 | medium | false |
| deprecated | `backend/scripts/check_task21b_remaining_real_tests.py :: check_task21b_remaining_real_tests` | REVIEW_DEPRECATION | 3 | medium | false |
| deprecated | `backend/scripts/full_smoke_check.py :: full_smoke_check` | REVIEW_DEPRECATION | 12 | medium | false |
| deprecated | `backend/frontend :: frontend` | KEEP_DYNAMIC_REGISTRATION | 1165 | high | false |
| deprecated | `docs/02_technical_stack_and_architecture.md :: 02_technical_stack_and_architecture` | REVIEW_DEPRECATION | 28 | medium | false |
| deprecated | `docs/03_database_schema_design.md :: 03_database_schema_design` | REVIEW_DEPRECATION | 30 | medium | false |
| deprecated | `docs/04_api_contract_design.md :: 04_api_contract_design` | REVIEW_DEPRECATION | 28 | medium | false |
| deprecated | `docs/05_frontend_page_and_interaction_spec.md :: 05_frontend_page_and_interaction_spec` | REVIEW_DEPRECATION | 28 | medium | false |
| deprecated | `docs/06_knowledge_base_and_document_processing_spec.md :: 06_knowledge_base_and_document_processing_spec` | REVIEW_DEPRECATION | 21 | medium | false |
| deprecated | `docs/08_deployment_and_loongarch_kylin_spec.md :: 08_deployment_and_loongarch_kylin_spec` | REVIEW_DEPRECATION | 19 | medium | false |
| deprecated | `docs/09_testing_acceptance_and_quality_spec.md :: 09_testing_acceptance_and_quality_spec` | REVIEW_DEPRECATION | 22 | medium | false |
| deprecated | `docs/10_vibe_coding_task_plan.md :: 10_vibe_coding_task_plan` | REVIEW_DEPRECATION | 14 | medium | false |
| deprecated | `docs/14A_global_gap_closure_report.md :: 14A_global_gap_closure_report` | REVIEW_DEPRECATION | 1 | medium | false |
| deprecated | `docs/16_final_hardening_report.md :: 16_final_hardening_report` | REVIEW_DEPRECATION | 1 | medium | false |
| deprecated | `docs/17_final_regression_test_report.md :: 17_final_regression_test_report` | REVIEW_DEPRECATION | 1 | medium | false |
| deprecated | `docs/18H_loongarch_kylin_acceptance_report.md :: 18H_loongarch_kylin_acceptance_report` | REVIEW_DEPRECATION | 1 | medium | false |
| deprecated | `docs/18I_global_acceptance_report.md :: 18I_global_acceptance_report` | REVIEW_DEPRECATION | 4 | medium | false |
| deprecated | `docs/19_delivery_checklist.md :: 19_delivery_checklist` | REVIEW_DEPRECATION | 6 | medium | false |
| deprecated | `docs/20C_user_acceptance_report.md :: 20C_user_acceptance_report` | REVIEW_DEPRECATION | 1 | medium | false |
| deprecated | `docs/21A_real_api_integration_audit_report.md :: 21A_real_api_integration_audit_report` | REVIEW_DEPRECATION | 1 | medium | false |
| deprecated | `docs/21B_remaining_real_test_report.md :: 21B_remaining_real_test_report` | REVIEW_DEPRECATION | 1 | medium | false |
| deprecated | `docs/21D_destructive_action_and_cleanup_report.md :: 21D_destructive_action_and_cleanup_report` | REVIEW_DEPRECATION | 1 | medium | false |
| deprecated | `docs/24A_strict_global_code_audit_report.md :: 24A_strict_global_code_audit_report` | REVIEW_DEPRECATION | 1 | medium | false |
| deprecated | `backend/frontend :: frontend` | KEEP_DYNAMIC_REGISTRATION | 1165 | high | false |
| deprecated | `backend/frontend :: frontend` | KEEP_DYNAMIC_REGISTRATION | 1165 | high | false |
| deprecated | `scripts/check_environment_windows.ps1 :: check_environment_windows` | REVIEW_DEPRECATION | 5 | medium | false |
| deprecated | `scripts/final_smoke_test.ps1 :: final_smoke_test` | KEEP_COMPATIBILITY | 139 | medium | false |
| deprecated | `scripts/final_smoke_test.sh :: final_smoke_test` | REVIEW_DEPRECATION | 139 | medium | false |
| deprecated | `scripts/health_check.ps1 :: health_check` | KEEP_DYNAMIC_REGISTRATION | 43 | high | false |
| deprecated | `scripts/health_check.sh :: health_check` | KEEP_DYNAMIC_REGISTRATION | 43 | high | false |
| deprecated | `scripts/start_postgresql.ps1 :: start_postgresql` | REVIEW_DEPRECATION | 20 | medium | false |
| deprecated | `scripts/start_postgresql_standalone.ps1 :: start_postgresql_standalone` | REVIEW_DEPRECATION | 15 | medium | false |
