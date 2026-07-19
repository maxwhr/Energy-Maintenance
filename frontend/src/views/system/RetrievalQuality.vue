<template>
  <PageFrame title="检索质量与向量索引" code="RAG / QUALITY"
    description="展示真实/测试后端边界、版本化索引、评测指标和人工审核边界；不展示密钥、Authorization、原始向量或本地路径。">
    <template #actions>
      <button class="scada-button" type="button" :disabled="loading" @click="loadAll">刷新</button>
    </template>

    <div v-if="error" class="rounded-md border border-red-400/30 bg-red-500/10 p-4 text-sm text-red-200">{{ error }}</div>

    <div class="rounded-md border border-cyan-300/30 bg-cyan-400/10 p-4 text-sm font-semibold text-cyan-100" data-testid="pilot-notice">
      {{ pilotStatus.notice || '当前为 Pilot，不影响正式默认检索。' }}
    </div>
    <div class="rounded-md border border-amber-300/30 bg-amber-400/10 p-4 text-sm text-amber-100" data-testid="u3-gate-status">
      U3：{{ u3Status.corpus_gate_status || u3Status.status || '-' }} · active {{ u3Status.active_approved_chunks || 0 }}/{{ u3Status.required_active_chunks || 300 }} Chunks · 待审 {{ u3Status.pending_official_documents || 0 }} 份 · Pilot {{ u3Status.pilot_index_allowed ? '允许' : 'blocked' }} / 索引{{ u3Status.pilot_index_executed ? '已执行' : '未执行' }}
    </div>
    <div class="grid gap-3 rounded-md border border-cyan-300/30 bg-cyan-400/10 p-4 text-sm text-cyan-100 md:grid-cols-4" data-testid="r1-scope-status">
      <span>Scope：{{ r1ScopeStatus.scope?.scope_id || '-' }}</span>
      <span>标签：{{ r1ScopeStatus.benchmark_dataset_status || '-' }}</span>
      <span>Canary：{{ r1ScopeStatus.canary_status || '-' }}</span>
      <span>质量门：{{ r1ScopeStatus.full_quality_gate_status || '-' }}</span>
      <span>v1：{{ r1ScopeStatus.v1_run?.quality_gate_status || '-' }}（保留）</span>
      <span>v2：{{ r1ScopeStatus.v2_run?.quality_gate_status || '-' }}（独立）</span>
      <span>语言：{{ r1ScopeStatus.scope?.normalized_language || '-' }}</span>
      <span>Partition：{{ r1ScopeStatus.scope?.partition_name || '-' }}</span>
    </div>
    <div class="grid gap-3 rounded-md border border-violet-300/30 bg-violet-400/10 p-4 text-sm text-violet-100 md:grid-cols-4" data-testid="r2-metric-contract-status">
      <span>v2：{{ r2Status.v2_run?.quality_gate_status || '-' }}（保留）</span>
      <span>v3：{{ r2Status.v3_dataset?.dataset_version || '-' }} / {{ r2Status.v3_dataset?.freeze_status || '-' }}</span>
      <span>raw P@5 不可达：{{ r2Status.metric_contract?.impossible_precision_at_5_cases ?? '-' }}</span>
      <span>v3 质量门：{{ r2Status.quality_gate_status || '-' }}</span>
      <span>Canary：{{ r2Status.canary?.status || '-' }}</span>
      <span>型号/告警覆盖：{{ r2Status.v3_dataset?.coverage?.model_cases ?? '-' }} / {{ r2Status.v3_dataset?.coverage?.alarm_cases ?? '-' }}</span>
      <span>Vector-heavy：{{ r2Status.v3_dataset?.coverage?.vector_heavy ?? '-' }}</span>
      <span>模式重合：{{ r2Status.mode_distinctness?.identical_case_rate ?? '-' }}</span>
      <span>Adaptive P@5 (raw/surfaced): {{ r2Status.canary?.by_mode?.adaptive?.raw_precision_at_5 ?? '-' }} / {{ r2Status.canary?.by_mode?.adaptive?.surfaced_precision ?? '-' }}</span>
      <span>Vector-heavy gain: {{ r2Status.canary?.checks?.vector_heavy_gain ? 'proven' : 'not proven' }}</span>
    </div>

    <div class="grid gap-3 rounded-md border border-rose-300/30 bg-rose-400/10 p-4 text-sm text-rose-100 md:grid-cols-4" data-testid="r3-semantic-status">
      <span>R2 preserved: {{ r3Status.r2_canary?.status || '-' }}</span>
      <span>Grounding: {{ r3Status.grounding?.summary?.GROUNDED_STRONG ?? 0 }} strong / {{ r3Status.grounding?.summary?.AMBIGUOUS_SECTION ?? 0 }} ambiguous</span>
      <span>Raw vector Top-50: {{ r3Status.raw_dashvector?.raw_top50_hit ?? '-' }} / {{ r3Status.raw_dashvector?.cases ?? '-' }}</span>
      <span>Representation: {{ r3Status.embedding?.primary_diagnosis || '-' }}</span>
      <span>pilot_r2 / semantic: {{ r3Status.semantic_index?.raw_partition || '-' }} / {{ r3Status.semantic_index?.semantic_partition || '-' }}</span>
      <span>Semantic anchors: {{ r3Status.semantic_index?.anchor_vectors ?? '-' }}</span>
      <span>Candidate Recall@50: {{ r3Status.canary?.vector_heavy?.candidate_recall_at_50 ?? '-' }}</span>
      <span>Adaptive semantic R@5: {{ r3Status.canary?.vector_heavy?.adaptive_semantic?.recall_at_5 ?? '-' }}</span>
      <span>Actual route: semantic_vector (A/B only)</span>
      <span>Canary: {{ r3Status.canary?.status || '-' }} / test_v3_1 {{ r3Status.test_v3_1?.frozen ? 'frozen' : 'not frozen' }}</span>
    </div>

    <div class="space-y-3 rounded-md border border-emerald-300/30 bg-emerald-400/10 p-4 text-sm text-emerald-50" data-testid="r4-grounded-semantic-status">
      <div class="grid gap-3 md:grid-cols-4">
        <span>History: R2 {{ r4Status.history?.r2_canary || '-' }} / R3 {{ r4Status.history?.r3_canary || '-' }}</span>
        <span>Semantic units: {{ r4Status.semantic_units?.units ?? '-' }}</span>
        <span>Grounding: {{ r4Status.grounding?.summary?.GROUNDED_STRONG ?? 0 }} strong</span>
        <span>Leakage: {{ r4Status.grounding?.lexical_leakage ?? '-' }}</span>
        <span>Partitions: {{ r4Status.semantic_index?.raw_partition || '-' }} / {{ r4Status.semantic_index?.r3_partition || '-' }} / {{ r4Status.semantic_index?.r4_partition || '-' }}</span>
        <span>Typed anchors: {{ r4Status.semantic_index?.anchor_vectors ?? '-' }}</span>
        <span>Canary: {{ r4Status.canary?.status || 'NOT_RUN' }} / iteration {{ r4Status.canary?.iteration ?? '-' }}</span>
        <span>Candidate Recall@50: {{ r4Status.canary?.vector_heavy?.candidate_recall_at_50 ?? '-' }}</span>
      </div>
      <div class="grid gap-2 lg:grid-cols-3" data-testid="r4-source-locator-examples">
        <div v-for="item in r4Status.semantic_units?.examples || []" :key="item.semantic_unit_id" class="rounded bg-black/20 p-2 text-xs">
          <div>{{ item.semantic_unit_type }} · {{ shortId(item.semantic_unit_id) }}</div>
          <div>anchors: {{ (item.anchor_types || []).join(', ') || '-' }}</div>
          <div>source: {{ item.source_locator?.section || '-' }} · page {{ item.source_locator?.page_start ?? '-' }}</div>
        </div>
      </div>
      <div class="grid gap-2 lg:grid-cols-3" data-testid="r4-typed-anchor-scores">
        <div v-for="item in r4Status.semantic_index?.score_examples || []" :key="`${item.semantic_unit_id}-${item.final_unit_score}`" class="rounded bg-black/20 p-2 text-xs">
          <div>{{ shortId(item.semantic_unit_id) }} · final {{ item.final_unit_score ?? '-' }}</div>
          <div>{{ Object.entries(item.anchor_scores || {}).map(([key, value]) => `${key}:${value}`).join(' · ') || 'scores pending' }}</div>
        </div>
      </div>
      <p class="text-xs text-emerald-100">Read-only engineering evidence. No approval, reindex, freeze, or formal-run action is available in this panel.</p>
    </div>

    <div class="space-y-3 rounded-md border border-sky-300/30 bg-sky-400/10 p-4 text-sm text-sky-50" data-testid="r5-query-aware-status">
      <div class="grid gap-3 md:grid-cols-4">
        <span>R4 历史结果：{{ r5Status.history?.r4_result || '-' }}（保留）</span>
        <span>V2 Units：{{ r5Status.semantic_unit_v2?.units ?? '-' }}</span>
        <span>类型：{{ JSON.stringify(r5Status.semantic_unit_v2?.unit_types || {}) }}</span>
        <span>Source Grounding：{{ r5Status.semantic_unit_v2?.source_grounded ? 'passed' : 'pending' }}</span>
        <span>章节审计/恢复：{{ r5Status.semantic_unit_v2?.audited_sections ?? '-' }} / {{ r5Status.semantic_unit_v2?.recovered_sections ?? '-' }}</span>
        <span>意图准确率：{{ percent(r5Status.query_understanding?.intent_accuracy) }}</span>
        <span>型号/告警幻觉：{{ r5Status.query_understanding?.hallucinated_models ?? 0 }} / {{ r5Status.query_understanding?.hallucinated_alarms ?? 0 }}</span>
        <span>追问 P/R：{{ percent(r5Status.query_understanding?.clarification_precision) }} / {{ percent(r5Status.query_understanding?.clarification_recall) }}</span>
        <span>Candidate R@50：{{ decimal(r5Status.canary?.metrics?.candidate_recall_at_50) }}</span>
        <span>Multi-query 增益：{{ decimal(r5Status.canary?.multi_query_gain) }}</span>
        <span>No-answer F1：{{ decimal(r5Status.canary?.no_answer_f1) }}</span>
        <span>Canary / Formal：{{ r5Status.canary?.status || 'NOT_RUN' }} / {{ r5Status.formal_test?.status || 'NOT_CREATED' }}</span>
        <span>Partition：{{ r5Status.semantic_index?.partition || '-' }}</span>
        <span>Vectors：{{ r5Status.semantic_index?.anchor_vectors ?? '-' }}</span>
        <span>Missing/Orphan：{{ r5Status.semantic_index?.reconciliation?.missing ?? '-' }} / {{ r5Status.semantic_index?.reconciliation?.orphan ?? '-' }}</span>
        <span>默认分区：{{ r5Status.boundaries?.default_partition_changed ? 'changed' : 'unchanged' }}</span>
      </div>
      <p class="text-xs text-sky-100">只读质量证据；本面板不提供批准、正式测试、索引切换或全量重建操作。</p>
      <div class="grid gap-2 rounded bg-black/20 p-3 text-xs md:grid-cols-4" data-testid="r5-r1-repair-status">
        <span>R5-R1 基线：{{ r5Status.r5_r1?.baseline_frozen ? 'frozen' : 'missing' }}</span>
        <span>Structured：{{ r5Status.r5_r1?.structured_output?.status || '-' }} ({{ r5Status.r5_r1?.structured_output?.success ?? 0 }}/{{ r5Status.r5_r1?.structured_output?.cases ?? 0 }})</span>
        <span>Rerank：{{ r5Status.r5_r1?.rerank?.status || '-' }} ({{ r5Status.r5_r1?.rerank?.success ?? 0 }}/{{ r5Status.r5_r1?.rerank?.cases ?? 0 }})</span>
        <span>RAW_VECTOR：{{ r5Status.r5_r1?.raw_vector?.status || '-' }} ({{ r5Status.r5_r1?.raw_vector?.raw_hits ?? 0 }}/{{ r5Status.r5_r1?.raw_vector?.post_filter_hits ?? 0 }})</span>
        <span>KG Alias：{{ r5Status.r5_r1?.kg_alias_status || '-' }}</span>
        <span>RRF channel cap：{{ r5Status.r5_r1?.rrf_channel_vote_cap ?? '-' }}</span>
        <span>Canary：{{ r5Status.r5_r1?.canary_status || '-' }}</span>
        <span>Formal：{{ r5Status.r5_r1?.formal_status || '-' }}</span>
      </div>
      <div class="grid gap-2 rounded border border-violet-300/20 bg-violet-400/10 p-3 text-xs md:grid-cols-4" data-testid="r5-r2-mm-status">
        <span>R5-R2-MM：{{ r5Status.r5_r2_mm?.final_status || 'NOT_RUN' }}</span>
        <span>MiniMax-M3：{{ r5Status.r5_r2_mm?.model_probe?.status || '-' }}</span>
        <span>Tool Calling：{{ r5Status.r5_r2_mm?.model_probe?.tool_use_received ? 'passed' : 'failed' }}</span>
        <span>Thinking：{{ r5Status.r5_r2_mm?.model_probe?.thinking_enabled ? 'enabled' : 'disabled' }}</span>
        <span>Query Understanding：{{ r5Status.r5_r2_mm?.query_understanding?.status || '-' }} / {{ percent(r5Status.r5_r2_mm?.query_understanding?.structured_success_ratio) }}</span>
        <span>Query p95：{{ decimal(r5Status.r5_r2_mm?.query_understanding?.p95_ms) }} ms</span>
        <span>确定性重排：{{ r5Status.r5_r2_mm?.deterministic_rerank?.status || '-' }} / Top1 {{ percent(r5Status.r5_r2_mm?.deterministic_rerank?.top1_accuracy) }}</span>
        <span>Deterministic p95：{{ decimal(r5Status.r5_r2_mm?.deterministic_rerank?.p95_ms) }} ms</span>
        <span>Tie-break：{{ r5Status.r5_r2_mm?.optional_tiebreak?.status || '-' }} / {{ percent(r5Status.r5_r2_mm?.optional_tiebreak?.structured_success_ratio) }}</span>
        <span>Tie-break p95：{{ decimal(r5Status.r5_r2_mm?.optional_tiebreak?.p95_ms) }} ms</span>
        <span>熔断 QU/Tie：{{ r5Status.r5_r2_mm?.circuit_breaker?.query_understanding || '-' }} / {{ r5Status.r5_r2_mm?.circuit_breaker?.tiebreak || '-' }}</span>
        <span>请求级 Provider 串联：{{ r5Status.r5_r2_mm?.provider_ab?.request_level_chaining ? 'enabled' : 'disabled' }}</span>
        <span>Canary：{{ r5Status.r5_r2_mm?.canary?.status || 'NOT_RUN' }}</span>
        <span>Formal：{{ r5Status.r5_r2_mm?.formal_test?.status || 'NOT_RUN' }}</span>
        <span>向量：{{ r5Status.r5_r2_mm?.vector_integrity?.status || '-' }} / re-upsert {{ r5Status.r5_r2_mm?.vector_integrity?.re_upserted ?? '-' }}</span>
        <span>默认分区：{{ r5Status.r5_r2_mm?.vector_integrity?.default_partition_affected ? 'changed' : 'unchanged' }}</span>
      </div>
      <div class="grid gap-2 rounded border border-amber-300/30 bg-amber-400/10 p-3 text-xs md:grid-cols-4" data-testid="r5-r3-mm-status">
        <span class="font-semibold text-amber-100">R5-R3-MM：{{ r5Status.r5_r3_mm?.final_status || 'NOT_RUN' }}</span>
        <span>Contract：{{ r5Status.r5_r3_mm?.contract_gate?.ready ? 'READY' : 'NOT READY' }}</span>
        <span>Schema v2：{{ r5Status.r5_r3_mm?.schema_probe?.passed_cases ?? 0 }}/{{ r5Status.r5_r3_mm?.schema_probe?.cases ?? 0 }}</span>
        <span>Nested queries：{{ r5Status.r5_r3_mm?.schema_probe?.nested_retrieval_queries ?? 0 }}</span>
        <span>M3 structured：{{ percent(r5Status.r5_r3_mm?.model_ab?.m3?.structured_success_ratio) }}</span>
        <span>M3 p95：{{ decimal(r5Status.r5_r3_mm?.model_ab?.m3?.p95_ms) }} ms</span>
        <span>M2.7-HS structured：{{ percent(r5Status.r5_r3_mm?.model_ab?.m27_highspeed?.structured_success_ratio) }}</span>
        <span>M2.7-HS p95：{{ decimal(r5Status.r5_r3_mm?.model_ab?.m27_highspeed?.p95_ms) }} ms</span>
        <span>运行时：{{ r5Status.r5_r3_mm?.model_ab?.selected_runtime_model || 'deterministic' }}</span>
        <span>上下文合并：{{ percent(r5Status.r5_r3_mm?.context_merge?.accuracy) }}</span>
        <span>确定性规划：{{ r5Status.r5_r3_mm?.deterministic_planner?.passed_cases ?? 0 }}/{{ r5Status.r5_r3_mm?.deterministic_planner?.cases ?? 0 }}</span>
        <span>Tie-break 默认：{{ r5Status.r5_r3_mm?.tie_break_default_enabled ? 'enabled' : 'disabled' }}</span>
        <span>Canary：{{ r5Status.r5_r3_mm?.canary?.executed_cases ?? 0 }} / {{ r5Status.r5_r3_mm?.canary?.status || 'NOT_RUN' }}</span>
        <span>Formal：{{ r5Status.r5_r3_mm?.formal_test?.status || 'NOT_CREATED' }}</span>
        <span>向量：{{ r5Status.r5_r3_mm?.vector_integrity?.status || '-' }} / read-only {{ r5Status.r5_r3_mm?.vector_integrity?.read_only ? 'yes' : 'no' }}</span>
        <span>默认分区：{{ r5Status.r5_r3_mm?.vector_integrity?.default_partition_affected ? 'changed' : 'unchanged' }}</span>
      </div>
      <div class="grid gap-2 rounded border border-emerald-300/30 bg-emerald-400/10 p-3 text-xs md:grid-cols-4" data-testid="r5-r4-mm-status">
        <span class="font-semibold text-emerald-100">R5-R4-MM：{{ r5Status.r5_r4_mm?.final_status || 'NOT_RUN' }}</span>
        <span>生产默认：{{ r5Status.r5_r4_mm?.runtime?.default || 'deterministic-first' }}</span>
        <span>MiniMax 角色：{{ r5Status.r5_r4_mm?.runtime?.minimax_role || 'optional_ambiguity_resolver' }}</span>
        <span>安全降级：{{ r5Status.r5_r4_mm?.runtime?.safe_fallback ? 'enabled' : 'pending' }}</span>
        <span>标签审计：{{ r5Status.r5_r4_mm?.labels?.status || '-' }} / 修订 {{ r5Status.r5_r4_mm?.labels?.revised ?? 0 }}</span>
        <span>确定性 Probe：{{ r5Status.r5_r4_mm?.deterministic_probe?.cases ?? 0 }} 条 / intent {{ percent(r5Status.r5_r4_mm?.deterministic_probe?.intent_accuracy) }}</span>
        <span>歧义候选：{{ percent(r5Status.r5_r4_mm?.ambiguity_probe?.correct_interpretation_coverage) }} / 最大 {{ r5Status.r5_r4_mm?.ambiguity_probe?.max_candidates ?? '-' }}</span>
        <span>MiniMax：{{ r5Status.r5_r4_mm?.minimax_probe?.real_calls ?? 0 }} 次 / structured {{ percent(r5Status.r5_r4_mm?.minimax_probe?.structured_success_ratio) }}</span>
        <span>Canary：{{ r5Status.r5_r4_mm?.canary?.status || 'NOT_RUN' }} / iteration {{ r5Status.r5_r4_mm?.canary?.iteration ?? '-' }}</span>
        <span>Checkpoint：{{ r5Status.r5_r4_mm?.canary?.checkpointed_results ?? 0 }}/{{ r5Status.r5_r4_mm?.canary?.expected_results ?? 152 }}</span>
        <span>Candidate R@50：{{ decimal(r5Status.r5_r4_mm?.canary?.deterministic?.candidate_recall_at_50) }}</span>
        <span>MRR / nDCG：{{ decimal(r5Status.r5_r4_mm?.canary?.deterministic?.mrr) }} / {{ decimal(r5Status.r5_r4_mm?.canary?.deterministic?.ndcg_at_10) }}</span>
        <span>追问 P/R：{{ percent(r5Status.r5_r4_mm?.canary?.deterministic?.clarification_precision) }} / {{ percent(r5Status.r5_r4_mm?.canary?.deterministic?.clarification_recall) }}</span>
        <span>Context merge：{{ percent(r5Status.r5_r4_mm?.canary?.deterministic?.context_merge_accuracy) }}</span>
        <span>Formal：{{ r5Status.r5_r4_mm?.formal_test?.status || 'NOT_CREATED' }}</span>
        <span>向量：{{ r5Status.r5_r4_mm?.vector_integrity?.status || '-' }} / re-upsert {{ r5Status.r5_r4_mm?.vector_integrity?.re_upserted ?? 0 }}</span>
      </div>
      <div class="grid gap-2 rounded border border-fuchsia-300/30 bg-fuchsia-400/10 p-3 text-xs md:grid-cols-4" data-testid="r5-r6-qwen-rerank-status">
        <span class="font-semibold text-fuchsia-100">R5-R6：{{ r5Status.r5_r6?.final_status || 'NOT_RUN' }}</span>
        <span>Provider / Model：{{ r5Status.r5_r6?.config?.provider || '-' }} / {{ r5Status.r5_r6?.config?.model || '-' }}</span>
        <span>配置：{{ r5Status.r5_r6?.config?.status || '-' }}</span>
        <span>Probe API success：{{ percent(r5Status.r5_r6?.qwen_probe?.api_success_rate) }}</span>
        <span>Deterministic H@1/H@3：{{ percent(r5Status.r5_r6?.deterministic_baseline?.direct_answer_hit_at_1) }} / {{ percent(r5Status.r5_r6?.deterministic_baseline?.direct_answer_hit_at_3) }}</span>
        <span>Qwen H@1/H@3：{{ percent(r5Status.r5_r6?.qwen_probe?.metrics?.direct_answer_hit_at_1) }} / {{ percent(r5Status.r5_r6?.qwen_probe?.metrics?.direct_answer_hit_at_3) }}</span>
        <span>Qwen MRR/nDCG：{{ decimal(r5Status.r5_r6?.qwen_probe?.metrics?.mrr) }} / {{ decimal(r5Status.r5_r6?.qwen_probe?.metrics?.ndcg_at_10) }}</span>
        <span>Rerank p95：{{ decimal(r5Status.r5_r6?.latency?.rerank_component_p95_ms) }} ms</span>
        <span>熔断：{{ r5Status.r5_r6?.circuit_breaker?.state || '-' }}</span>
        <span>Canary：{{ r5Status.r5_r6?.canary?.status || 'NOT_RUN' }} / iteration {{ r5Status.r5_r6?.canary?.iteration ?? 0 }}</span>
        <span>Formal：{{ r5Status.r5_r6?.formal_test?.status || 'NOT_CREATED' }}</span>
        <span>MiniMax：{{ r5Status.r5_r6?.runtime?.minimax_role || 'optional ambiguity only' }}</span>
        <span>Vector read-only：re-embed {{ r5Status.r5_r6?.vector_integrity?.re_embedded ?? 0 }} / re-upsert {{ r5Status.r5_r6?.vector_integrity?.re_upserted ?? 0 }}</span>
        <span>默认分区：{{ r5Status.r5_r6?.vector_integrity?.default_partition_affected ? 'changed' : 'unchanged' }}</span>
      </div>
      <div v-if="userStore.role === 'admin'" class="grid gap-2 rounded border border-cyan-300/30 bg-cyan-400/10 p-3 text-xs md:grid-cols-4" data-testid="rag-performance-summary">
        <span class="font-semibold text-cyan-100">RAG Performance Trace</span>
        <span>最近请求：{{ performanceSummary.trace_count ?? 0 }}</span>
        <span>p50：{{ decimal(performanceSummary.total_p50_ms) }} ms</span>
        <span>p95：{{ decimal(performanceSummary.total_p95_ms) }} ms</span>
        <span>查询原文暴露：{{ performanceSummary.query_text_exposed ? 'yes' : 'no' }}</span>
        <span>候选正文暴露：{{ performanceSummary.candidate_content_exposed ? 'yes' : 'no' }}</span>
      </div>
    </div>

    <div class="grid gap-4 lg:grid-cols-4" data-testid="pilot-status-panel">
      <DataPanel title="Base Collection"><div class="break-all text-sm font-black text-white">{{ pilotStatus.base_collection || '-' }}</div><p class="mt-2 text-xs text-slate-400">默认策略 {{ pilotStatus.default_strategy || 'keyword' }}</p></DataPanel>
      <DataPanel title="Pilot Collection"><div class="break-all text-sm font-black text-white">{{ pilotStatus.pilot_collection || '-' }}</div><p class="mt-2 text-xs text-slate-400">独立名称 {{ pilotStatus.collection_isolated_by_name ? '是' : '否' }}</p></DataPanel>
      <DataPanel title="专家审核"><div class="text-xl font-black text-amber-300">{{ benchmarkProgress.expert_verified || 0 }} / 100</div><p class="mt-2 text-xs text-slate-400">双人复核 {{ benchmarkProgress.second_reviewed || 0 }} / 20</p></DataPanel>
      <DataPanel title="正式全量重建"><div class="text-xl font-black" :class="pilotStatus.full_reindex_allowed ? 'text-red-300' : 'text-emerald-300'">{{ pilotStatus.full_reindex_allowed ? '允许' : '门禁关闭' }}</div><p class="mt-2 text-xs text-slate-400">本页面不提供全量重建按钮</p></DataPanel>
    </div>

    <DataPanel title="Benchmark Expert Review" subtitle="自动候选不等于专家结论；每次审核保留 before/after 与审计记录。" data-testid="benchmark-review-panel">
      <div class="mb-3 rounded border border-cyan-300/20 bg-cyan-400/10 p-3 text-xs text-cyan-100">
        快捷审核：A 专家接受、M 需修改、X 拒绝、N 下一条。第二审核必须由不同 expert/admin 账户执行。
      </div>
      <div class="mb-3 grid gap-3 md:grid-cols-4">
        <select v-model="caseFilters.category" class="scada-input" @change="loadPilot"><option value="">全部类别</option><option v-for="item in benchmarkCategories" :key="item" :value="item">{{ item }}</option></select>
        <select v-model="caseFilters.difficulty" class="scada-input" @change="loadPilot"><option value="">全部难度</option><option value="medium">medium</option><option value="hard">hard</option></select>
        <select v-model="caseFilters.review_status" class="scada-input" @change="loadPilot"><option value="">全部状态</option><option value="draft">draft</option><option value="engineering_verified">engineering_verified</option><option value="expert_verified">expert_verified</option><option value="needs_revision">needs_revision</option></select>
        <div class="rounded bg-white/[0.03] p-3 text-xs text-slate-300">候选 {{ benchmarkCases.total || 0 }} · vector-heavy {{ benchmarkProgress.vector_heavy || 0 }} · no-answer {{ benchmarkProgress.no_answer || 0 }}</div>
      </div>
      <div class="overflow-x-auto">
        <table class="w-full min-w-[1050px] text-left text-xs">
          <thead class="text-slate-400"><tr><th class="p-2">查询</th><th>类别</th><th>难度</th><th>来源</th><th>状态</th><th>审核历史</th><th>操作</th></tr></thead>
          <tbody><tr v-for="(item, index) in benchmarkCases.items || []" :key="item.id" class="cursor-pointer border-t border-white/10 text-slate-200" :class="activeCaseIndex === Number(index) ? 'bg-cyan-400/10' : ''" @click="activeCaseIndex = Number(index)">
            <td class="max-w-[360px] p-2">{{ item.query_text }}</td><td>{{ item.category }}<span v-if="item.vector_heavy" class="ml-1 text-cyan-300">VH</span></td><td>{{ item.difficulty }}</td>
            <td class="max-w-[260px] font-mono text-[10px]">doc {{ shortId(item.source_locator?.document_id) }}<br>chunk {{ shortId(item.source_locator?.chunk_id) }}<br>page {{ item.source_locator?.page_number || '-' }}<br><span class="font-sans text-slate-400">{{ item.source_excerpt || '' }}</span></td>
            <td>{{ item.review_status }}<br><span v-if="item.no_answer" class="text-amber-300">NO-ANSWER</span></td><td>{{ item.review_history?.length || 0 }} / second {{ item.second_reviews?.length || 0 }}<br><span class="text-[10px] text-slate-500">before/after 已审计</span></td>
            <td><div class="flex flex-wrap gap-1">
              <button v-if="canEngineeringReview" class="scada-button !min-h-7 !px-2" type="button" @click="reviewCase(item.id, 'engineering', 'approve', false)">工程通过</button>
              <button v-if="canExpertReview" class="scada-button primary !min-h-7 !px-2" type="button" @click="reviewCase(item.id, 'expert', 'approve', false)">专家通过</button>
              <button v-if="canExpertReview" class="scada-button !min-h-7 !px-2" type="button" @click="reviewCase(item.id, 'expert', 'needs_revision', false)">需修改</button>
              <button v-if="canExpertReview" class="scada-button !min-h-7 !px-2" type="button" @click="reviewCase(item.id, 'expert', 'reject', false)">拒绝</button>
              <button v-if="canExpertReview" class="scada-button !min-h-7 !px-2" type="button" @click="reviewCase(item.id, 'expert', 'approve', true)">第二审核</button>
              <button class="scada-button !min-h-7 !px-2" type="button" @click="nextCase">下一条</button>
            </div></td>
          </tr></tbody>
        </table>
      </div>
      <EmptyState v-if="!(benchmarkCases.items || []).length" text="暂无符合筛选条件的候选。" />
    </DataPanel>

    <div class="grid gap-4 lg:grid-cols-2">
      <DataPanel title="Pilot Session" subtitle="只作用于指定用户或 Task25BR2_ 查询；普通用户始终走 Base。" data-testid="pilot-session-panel">
        <dl class="space-y-2 text-sm"><div class="flex justify-between"><dt class="text-slate-400">活动 Session</dt><dd>{{ pilotStatus.active_pilot_sessions?.length || 0 }}</dd></div><div class="flex justify-between"><dt class="text-slate-400">Pilot 索引记录</dt><dd>{{ pilotStatus.pilot_index_records || 0 }}</dd></div><div class="flex justify-between"><dt class="text-slate-400">当前角色</dt><dd>{{ userStore.role || '-' }}</dd></div></dl>
        <button v-if="['admin', 'expert'].includes(userStore.role || '')" class="scada-button mt-4" type="button" @click="createSession">创建受控 Session</button>
        <p v-else class="mt-4 text-xs text-slate-400">viewer/engineer 不可切换；expert 只能提交审核或创建评估 Session。</p>
      </DataPanel>
      <DataPanel title="Freeze / Rollback" subtitle="未达到真实专家门禁时，后端拒绝冻结。" data-testid="pilot-rollback-panel">
        <p class="text-sm text-slate-300">冻结就绪：{{ benchmarkProgress.ready_to_freeze ? '是' : '否' }}</p>
        <p class="mt-2 text-xs text-amber-200">{{ (benchmarkProgress.failed_requirements || []).join('；') || '全部专家门禁已满足' }}</p>
        <button v-if="userStore.role === 'admin'" class="scada-button mt-4" type="button" :disabled="!benchmarkProgress.ready_to_freeze" @click="freezeDataset">冻结 official_pilot_test_v1</button>
      </DataPanel>
    </div>

    <div class="grid gap-4 lg:grid-cols-4">
      <DataPanel title="默认检索模式"><div class="text-xl font-black text-white">{{ strategyStatus.default_strategy || 'keyword' }}</div><p class="mt-2 text-xs text-slate-400">recommended: {{ strategyStatus.recommended_strategy || '-' }}</p></DataPanel>
      <DataPanel title="Embedding"><div class="text-xl font-black text-white">{{ vectorStatus?.embedding_model || '未配置' }}</div><p class="mt-2 text-xs text-slate-400">{{ vectorStatus?.embedding_dimension || 0 }} 维 · {{ realModeLabel }}</p></DataPanel>
      <DataPanel title="Vector Backend"><div class="text-xl font-black text-white">{{ vectorStatus?.vector_backend || '-' }}</div><p class="mt-2 break-all text-xs text-slate-400">{{ vectorStatus?.dashvector_collection || '-' }}</p></DataPanel>
      <DataPanel title="质量门禁"><div class="text-xl font-black" :class="thresholdPassed ? 'text-emerald-300' : 'text-amber-300'">{{ strategyStatus.quality_gate_status || (latestRun ? (thresholdPassed ? 'PASSED' : 'FAILED / PARTIAL') : '暂无运行') }}</div><p class="mt-2 text-xs text-slate-400">test_v2 已冻结且只允许一次正式盲测</p></DataPanel>
    </div>

    <div class="grid gap-4 xl:grid-cols-[minmax(0,1fr)_380px]">
      <DataPanel title="最新评测指标" subtitle="按模式分别展示；结果未达阈值时不会显示为通过。">
        <div v-if="metricRows.length" class="overflow-x-auto">
          <table class="w-full min-w-[900px] text-left text-xs">
            <thead class="text-slate-400"><tr><th class="p-2">模式</th><th>R@5</th><th>R@10</th><th>MRR</th><th>nDCG@10</th><th>引用有效</th><th>泄漏率</th><th>p95</th></tr></thead>
            <tbody><tr v-for="row in metricRows" :key="row.mode" class="border-t border-white/10 text-slate-200">
              <td class="p-2 font-mono text-cyan-200">{{ row.mode }}</td><td>{{ percent(row.metrics.recall_at_5) }}</td><td>{{ percent(row.metrics.recall_at_10) }}</td>
              <td>{{ decimal(row.metrics.mrr) }}</td><td>{{ decimal(row.metrics.ndcg_at_10) }}</td><td>{{ percent(row.metrics.citation_valid) }}</td><td>{{ percent(row.metrics.leakage) }}</td><td>{{ decimal(row.metrics.latency_p95_ms) }} ms</td>
            </tr></tbody>
          </table>
        </div>
        <EmptyState v-else text="暂无评测运行。" />
      </DataPanel>

      <DataPanel title="索引生命周期">
        <dl class="space-y-3 text-sm">
          <div class="flex justify-between gap-3"><dt class="text-slate-400">Collection</dt><dd class="break-all text-right text-white">{{ lifecycle.collection || vectorStatus?.dashvector_collection || '-' }}</dd></div>
          <div class="flex justify-between gap-3"><dt class="text-slate-400">Embedding version</dt><dd class="text-white">{{ lifecycle.embedding_version || '-' }}</dd></div>
          <div class="flex justify-between gap-3"><dt class="text-slate-400">Approved chunks</dt><dd class="text-white">{{ lifecycle.approved_active_chunks ?? '-' }}</dd></div>
          <div class="flex justify-between gap-3"><dt class="text-slate-400">PostgreSQL orphans</dt><dd class="text-white">{{ lifecycle.orphan_postgresql_rows ?? '-' }}</dd></div>
          <div class="flex justify-between gap-3"><dt class="text-slate-400">Full reindex</dt><dd class="text-white">{{ lifecycle.full_reindex_allowed ? '显式允许' : '门禁关闭' }}</dd></div>
        </dl>
        <p class="mt-4 rounded border border-amber-300/20 bg-amber-400/10 p-3 text-xs leading-5 text-amber-100">DashVector 是召回索引，PostgreSQL 是事实源；命中后仍执行 approved/active 二次校验。高风险检修建议必须人工确认。</p>
      </DataPanel>
    </div>

    <DataPanel title="边界与可解释性">
      <div class="grid gap-3 text-sm text-slate-300 md:grid-cols-3">
        <div class="rounded bg-white/[0.03] p-3">分数：keyword / raw vector / normalized vector / exact boost / RRF / rerank / final</div>
        <div class="rounded bg-white/[0.03] p-3">引用：候选集约束 + PostgreSQL 回查 + approved/active 状态校验</div>
        <div class="rounded bg-white/[0.03] p-3">多模态：descriptor_based_cross_modal；raw image embedding = false</div>
      </div>
    </DataPanel>

    <DataPanel title="策略路由与回退">
      <div class="grid gap-3 text-sm text-slate-300 md:grid-cols-3">
        <div class="rounded bg-white/[0.03] p-3">推荐：{{ strategyStatus.recommended_strategy || '-' }}<br>默认：{{ strategyStatus.default_strategy || '-' }}</div>
        <div class="rounded bg-white/[0.03] p-3">回退：{{ strategyStatus.fallback_strategy || '-' }}<br>原因：{{ strategyStatus.fallback_reason || '-' }}</div>
        <div class="rounded bg-white/[0.03] p-3">Reranker：{{ strategyStatus.reranker_enabled ? 'enabled' : 'disabled' }}<br>{{ strategyStatus.reranker_disabled_reason || '' }}</div>
      </div>
    </DataPanel>
  </PageFrame>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { createRetrievalPilotSessionApi, freezeRetrievalBenchmarkApi, getR5RetrievalQualitySummaryApi, getRagPerformanceSummaryApi, getRetrievalBenchmarkCasesApi, getRetrievalBenchmarkProgressApi, getRetrievalEvaluationRunApi, getRetrievalEvaluationRunsApi, getRetrievalPilotStatusApi, getRetrievalPilotU3StatusApi, getRetrievalR1ScopeStatusApi, getRetrievalR2ScopeStatusApi, getRetrievalR3ScopeStatusApi, getRetrievalR4ScopeStatusApi, getRetrievalStrategyStatusApi, getVectorLifecycleApi, getVectorSearchStatusApi, reviewRetrievalBenchmarkCaseApi } from '@/api'
import DataPanel from '@/components/DataPanel.vue'
import EmptyState from '@/components/EmptyState.vue'
import PageFrame from '@/components/PageFrame.vue'
import { useUserStore } from '@/stores/user'
import type { VectorSearchStatus } from '@/types'

const userStore = useUserStore()
const vectorStatus = ref<VectorSearchStatus | null>(null)
const lifecycle = ref<Record<string, any>>({})
const latestRun = ref<Record<string, any> | null>(null)
const loading = ref(false)
const error = ref('')
const strategyStatus = ref<Record<string, any>>({})
const pilotStatus = ref<Record<string, any>>({})
const u3Status = ref<Record<string, any>>({})
const r1ScopeStatus = ref<Record<string, any>>({})
const r2Status = ref<Record<string, any>>({})
const r3Status = ref<Record<string, any>>({})
const r4Status = ref<Record<string, any>>({})
const r5Status = ref<Record<string, any>>({})
const performanceSummary = ref<Record<string, any>>({})
const benchmarkProgress = ref<Record<string, any>>({})
const benchmarkCases = ref<Record<string, any>>({ items: [], total: 0 })
const caseFilters = ref({ category: '', difficulty: '', review_status: '' })
const activeCaseIndex = ref(0)
const benchmarkCategories = ['device_model_query', 'fault_code_query', 'symptom_query', 'colloquial_symptom', 'synonym_rewrite', 'symptom_to_cause', 'symptom_to_steps', 'safety_procedure', 'tools_parts', 'manual_section', 'historical_case', 'multimodal_descriptor', 'no_answer']
const canEngineeringReview = computed(() => ['engineer', 'expert', 'admin'].includes(userStore.role || ''))
const canExpertReview = computed(() => ['expert', 'admin'].includes(userStore.role || ''))
const realModeLabel = computed(() => vectorStatus.value?.real_adapter_available ? 'real configured' : 'fake / blocked')
const latestMetrics = computed(() => (latestRun.value?.metrics_json || {}) as Record<string, any>)
const thresholdPassed = computed(() => Boolean(latestMetrics.value.quality_gate?.passed ?? latestMetrics.value.threshold_result?.passed))
const metricRows = computed(() => Object.entries(latestMetrics.value.by_mode || {}).map(([mode, metrics]) => ({ mode, metrics: metrics as Record<string, any> })))

async function loadAll() {
  loading.value = true
  error.value = ''
  try {
    const [status, runs, strategy, r1Scope, r2Scope, r3Scope, r4Scope, r5Scope] = await Promise.all([getVectorSearchStatusApi(), getRetrievalEvaluationRunsApi({ page: 1, page_size: 1 }), getRetrievalStrategyStatusApi(), getRetrievalR1ScopeStatusApi(), getRetrievalR2ScopeStatusApi(), getRetrievalR3ScopeStatusApi(), getRetrievalR4ScopeStatusApi(), getR5RetrievalQualitySummaryApi()])
    vectorStatus.value = status
    strategyStatus.value = strategy
    r1ScopeStatus.value = r1Scope
    r2Status.value = r2Scope
    r3Status.value = r3Scope
    r4Status.value = r4Scope
    r5Status.value = r5Scope
    performanceSummary.value = userStore.role === 'admin' ? await getRagPerformanceSummaryApi() : {}
    const first = runs.items?.[0] as Record<string, any> | undefined
    latestRun.value = first?.id ? await getRetrievalEvaluationRunApi(String(first.id)) : null
    lifecycle.value = userStore.role === 'admin' ? await getVectorLifecycleApi() : { collection: status.dashvector_collection }
    await loadPilot()
  } catch (err) { error.value = err instanceof Error ? err.message : '检索质量数据读取失败' }
  finally { loading.value = false }
}

async function loadPilot() {
  const params = Object.fromEntries(Object.entries({ ...caseFilters.value, page: 1, page_size: 20 }).filter(([, value]) => value !== ''))
  const [status, u3, progress, cases] = await Promise.all([getRetrievalPilotStatusApi(), getRetrievalPilotU3StatusApi(), getRetrievalBenchmarkProgressApi(), getRetrievalBenchmarkCasesApi(params)])
  pilotStatus.value = status
  u3Status.value = u3
  benchmarkProgress.value = progress
  benchmarkCases.value = cases
}

async function reviewCase(caseId: string, kind: 'engineering' | 'expert', decision: 'approve' | 'needs_revision' | 'reject', secondReview: boolean) {
  error.value = ''
  try {
    await reviewRetrievalBenchmarkCaseApi(caseId, kind, { decision, query_valid: true, expected_reference_valid: true, difficulty_valid: true, category_valid: true, notes: '', second_review: secondReview })
    await loadPilot()
  } catch (err) { error.value = err instanceof Error ? err.message : '审核提交失败' }
}

function nextCase() {
  const length = (benchmarkCases.value.items || []).length
  if (length) activeCaseIndex.value = Math.min(activeCaseIndex.value + 1, length - 1)
}

function keyboardReview(event: KeyboardEvent) {
  if (['INPUT', 'SELECT', 'TEXTAREA'].includes((event.target as HTMLElement)?.tagName)) return
  const item = (benchmarkCases.value.items || [])[activeCaseIndex.value]
  if (!item) return
  const key = event.key.toLowerCase()
  if (key === 'n') return nextCase()
  if (!canExpertReview.value) return
  if (key === 'a') void reviewCase(item.id, 'expert', 'approve', false)
  if (key === 'm') void reviewCase(item.id, 'expert', 'needs_revision', false)
  if (key === 'x') void reviewCase(item.id, 'expert', 'reject', false)
}

async function freezeDataset() {
  try { await freezeRetrievalBenchmarkApi(); await loadPilot() }
  catch (err) { error.value = err instanceof Error ? err.message : '冻结失败' }
}

async function createSession() {
  try {
    await createRetrievalPilotSessionApi({ name: 'Task25B-R2 UI Pilot Session', scope_user_ids: [], query_prefix: 'Task25BR2_', retrieval_strategy: 'adaptive' })
    await loadPilot()
  } catch (err) { error.value = err instanceof Error ? err.message : 'Pilot Session 创建失败' }
}

function shortId(value: unknown) { return typeof value === 'string' ? value.slice(0, 8) : '-' }

function decimal(value: unknown) { return typeof value === 'number' ? value.toFixed(3) : '-' }
function percent(value: unknown) { return typeof value === 'number' ? `${(value * 100).toFixed(1)}%` : '-' }
onMounted(() => { window.addEventListener('keydown', keyboardReview); void loadAll() })
onBeforeUnmount(() => window.removeEventListener('keydown', keyboardReview))
</script>
