# Experiments

这个目录用于承载论文实验资产，不直接参与业务接口主链。

建议的使用顺序：

1. `00_prepare_cases.py`
   生成或整理实验 `case_list.csv`，并可输出 `case_candidates.csv` 候选打分表
2. `01_export_cst_states.py`
   导出每个 case 的 `Construction State Twin`
3. `02_generate_reports.py`
   生成 `Template / Direct-LLM / CST-LLM` 报告或 prompt
4. `03_evaluate_reports.py`
   初始化人工评分表并汇总 `ICS / FCS / TS`
5. `04_ablation_study.py`
   生成消融实验计划
6. `05_traceability_check.py`
   生成报告结论追溯表模板

推荐先阅读：

- [最终版方法框架](../docs/final_method_framework.md)
- [实验设计与组织方案](../docs/experiment_plan.md)
- [论文大纲建议](../docs/paper_outline.md)
