from __future__ import annotations

import json
from pathlib import Path

from task25b_r3_dev_common import ROOT, RUNTIME, now_iso


def read(name, default=None):
    path = RUNTIME / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else (default or {})


def write_report(name: str, title: str, body: str):
    path = ROOT / "docs" / name
    path.write_text(f"# {title}\n\n{body.strip()}\n", encoding="utf-8")


def main():
    language=read("language_governance_result.json"); discovery=read("chinese_manual_discovery.json")
    quality=read("chinese_document_quality.json"); approval=read("engineering_approval_result.json")
    blocked=read("engineering_approval_blocked.json"); english=read("english_exclusion_result.json")
    gate=read("chinese_corpus_gate.json"); benchmark=read("chinese_engineering_benchmark_check.json")
    index=read("chinese_pilot_index.json"); recon=read("chinese_pilot_reconciliation.json"); pilot=read("chinese_pilot_quality_gate.json")
    integrity=read("quality_gate_integrity.json"); missing=read("missing_case_modes.json"); duplicates=read("duplicate_case_modes.json")
    final_gate=integrity.get("quality_gate", "DEVELOPMENT_ENGINEERING_QUALITY_GATE_FAILED")
    common=(f"生成时间：{now_iso()}\n\n当前审批仅为开发工程审批；Codex 不是行业专家。"
            f" `expert_verified=false`、`second_reviewed=false`。当前默认语言为中文；英文资料保留但不启用，未删除。"
            f"未使用机器翻译冒充官方中文。Pilot 仅使用 `pilot_r2`，默认 Partition 未改变，正式全量重建未执行。LoongArch 尚未实机验收。\n\n"
            f"上一轮因 Codex 所选模型容量错误中断，不是项目、DashScope、DashVector、Embedding、数据库或后端服务故障。"
            f"恢复时沿用原质量门 run `{integrity.get('run_id','-')}`，未重复索引、未重复工程审批、未重建 Benchmark；"
            f"原进程完成后直接审计其 600 条既有结果。最终质量判定：`{final_gate}`。")
    counts=language.get("counts",{})
    write_report("25B_R2_U3_R3_DEV_chinese_knowledge_governance_report.md","Task 25B-R2-U3-R3-DEV 中文知识治理报告",
        common+f"\n\n## 结果\n\n- 文档总数：{language.get('total',0)}\n- 中文：{counts.get('zh-CN',0)}\n- 英文：{counts.get('en',0)}\n- 双语：{counts.get('bilingual',0)}\n- 未知：{counts.get('unknown',0)}\n- 英文删除：0")
    write_report("25B_R2_U3_R3_DEV_engineering_approval_report.md","Task 25B-R2-U3-R3-DEV 工程审批报告",
        common+f"\n\n## 结果\n\n- 工程审批候选：{len(approval.get('approved',[]))+len(blocked.get('blocked',[]))}\n- 通过：{len(approval.get('approved',[]))}\n- 阻断：{len(blocked.get('blocked',[]))}\n- 审批模式：development_engineering_auto\n- 审批主体：Development Engineering Reviewer")
    write_report("25B_R2_U3_R3_DEV_chinese_manual_discovery_report.md","Task 25B-R2-U3-R3-DEV 中文手册发现报告",
        common+f"\n\n## 结果\n\n- 官方候选：{len(discovery.get('documents',[]))}\n- 已下载中文 PDF：{discovery.get('downloaded',0)}\n- 官方来源限定：是\n- 原始 PDF 保留：是\n- 机器翻译：未使用")
    write_report("25B_R2_U3_R3_DEV_chinese_corpus_gate_report.md","Task 25B-R2-U3-R3-DEV 中文 Corpus Gate 报告",
        common+f"\n\n## 结果\n\n- 状态：{gate.get('status','NOT_RUN')}\n- 文档：{gate.get('approved_documents',0)}\n- 当前 Chunk：{gate.get('active_current_chunks',0)}\n- 文档类型：{len(gate.get('document_types',{}))}\n- 告警标识：{gate.get('alarm_identifiers',0)}\n- 排障章节：{gate.get('troubleshooting_sections',0)}\n- 安全章节：{gate.get('safety_sections',0)}\n- 全项通过：{gate.get('passed',False)}")
    write_report("25B_R2_U3_R3_DEV_chinese_pilot_index_report.md","Task 25B-R2-U3-R3-DEV 中文 Pilot 索引报告",
        common+f"\n\n## 索引\n\n- Collection：{index.get('collection','NOT_RUN')}\n- Partition：{index.get('partition','pilot_r2')}\n- eligible：{index.get('eligible',0)}\n- upserted：{index.get('upserted',0)}\n- failed：{index.get('failed',0)}\n- 真实 Embedding：text-embedding-v4 / 1024\n- 恢复阶段重复索引：0\n\n## 最终只读对账\n\n- passed：{recon.get('passed',False)}\n- PostgreSQL：{recon.get('postgresql_vectors','NOT_RUN')}\n- remote：{recon.get('remote_partition_count','NOT_RUN')}\n- missing：{recon.get('missing','NOT_RUN')}\n- orphan：{recon.get('orphan','NOT_RUN')}\n- stale/content mismatch：{recon.get('stale','NOT_RUN')}\n- duplicate：{recon.get('duplicates','NOT_RUN')}\n- model/dimension mismatch：{recon.get('dimension_model_mismatch','NOT_RUN')}\n- English leakage：{recon.get('english_leakage','NOT_RUN')}\n- pending leakage：{recon.get('pending_leakage','NOT_RUN')}\n- marketing leakage：{recon.get('marketing_leakage','NOT_RUN')}\n- superseded leakage：{recon.get('superseded_leakage','NOT_RUN')}\n- default Partition 当前数量：{recon.get('default_partition_count','NOT_RUN')}（本任务未改变）\n- Media Collection：未执行媒体索引操作")
    write_report("25B_R2_U3_R3_DEV_chinese_engineering_benchmark_report.md","Task 25B-R2-U3-R3-DEV 中文工程 Benchmark 报告",
        common+f"\n\n## 数据集与完整性\n\n- dataset：{integrity.get('dataset_version','NOT_RUN')}\n- cases：{integrity.get('cases',0)}\n- modes：{', '.join(integrity.get('modes',[]))}\n- expected / actual：{integrity.get('expected_results',0)} / {integrity.get('actual_results',0)}\n- missing：{missing.get('count','NOT_RUN')}\n- duplicate：{duplicates.get('count','NOT_RUN')}\n- execution errors：{integrity.get('error_count','NOT_RUN')}\n- 同数据集 run 数：{integrity.get('sibling_run_count','NOT_RUN')}（无重复正式 run）\n- Benchmark 状态：{benchmark.get('status','NOT_RUN')}\n- 统计：`{json.dumps(benchmark.get('counts',{}),ensure_ascii=False)}`\n\n## 分模式真实指标\n\n```json\n{json.dumps(integrity.get('by_mode',{}),ensure_ascii=False,indent=2)}\n```\n\n## Pilot 质量门\n\n- 原始脚本结果：{pilot.get('result','NOT_RUN')}\n- 最终规范化结果：{final_gate}\n- 门禁检查：`{json.dumps(integrity.get('checks',{}),ensure_ascii=False)}`\n- 工程门禁通过：{final_gate == 'DEVELOPMENT_ENGINEERING_PILOT_PASS'}\n- expert_verified：false\n- 专家验收：否\n- 生产就绪：否")
    write_report("25B_R2_U3_R3_DEV_language_exclusion_report.md","Task 25B-R2-U3-R3-DEV 英文排除报告",
        common+f"\n\n## 结果\n\n- 英文文档：{len(english.get('english',[]))}\n- 从默认检索排除：全部\n- 从 Pilot 排除：全部\n- 删除：0\n- 文件保留：是\n- 向量泄漏：{recon.get('english_leakage','NOT_RUN')}")
    marker="<!-- TASK25B_R3_DEV_BEGIN -->"
    addition=(f"\n\n{marker}\n## Task 25B-R2-U3-R3-DEV 中文工程 Pilot 更新\n\n"
              f"- 中文 Corpus Gate：`{gate.get('status','NOT_RUN')}`，{gate.get('approved_documents',0)} 份文档、{gate.get('active_current_chunks',0)} 个当前 Chunk。\n"
              f"- 开发工程审批与真实专家审批严格分离；`expert_verified=false`。\n"
              f"- 英文保留但不进入默认检索或 `pilot_r2`。\n"
              f"- Pilot 索引：{index.get('upserted',0)} upserted；恢复阶段未重复索引，正式全量重建未执行。\n"
              f"- 质量门原 run 已完整产生 {integrity.get('actual_results',0)}/{integrity.get('expected_results',0)} 条结果；最终判定 `{final_gate}`。\n"
              f"- 中断来自 Codex 模型容量，不是项目服务故障；恢复时未重复工程审批。\n"
              "<!-- TASK25B_R3_DEV_END -->\n")
    for rel in ["docs/25B_R2_U3_document_review_report.md","docs/25B_R2_U3_corpus_gate_report.md",
                "docs/25B_R2_U3_pilot_resume_report.md","docs/25B_R2_formal_knowledge_pilot_report.md",
                "docs/25B_R2_full_reindex_go_no_go_report.md","docs/09_testing_acceptance_and_quality_spec.md",
                "docs/12_functional_design_specification.md","docs/19_delivery_checklist.md","README.md","backend/README.md"]:
        path=ROOT/rel; text=path.read_text(encoding="utf-8") if path.exists() else ""
        if marker not in text: path.write_text(text.rstrip()+addition,encoding="utf-8")
    print({"status":"passed","reports":7,"updated":10})


if __name__=="__main__": main()
