# Experiments

这个目录用于承载论文实验脚本、实验配置和实验输出，不直接参与业务 API 主链。

优先阅读：

- [实验操作教程与当前进度](../docs/experiment_tutorial.md)
- [论文实验部分草稿](../docs/experiment_section_draft.md)
- [最终版方法框架](../docs/final_method_framework.md)
- [论文大纲建议](../docs/paper_outline.md)

推荐使用顺序：

1. `00_prepare_cases.py`  
   生成或整理 `case_list.csv`
2. `01_export_cst_states.py`  
   导出每个 case 的 `Construction State Twin`
3. `02_generate_reports.py`  
   生成 `Template / Direct-LLM / CST-LLM` 报告或 prompt
4. `03_evaluate_reports.py`  
   初始化并汇总主实验评分
5. `04_ablation_study.py`  
   生成消融实验计划
6. `05_traceability_check.py`  
   生成追溯表模板
7. `06_generate_ablation_reports.py`  
   生成消融报告
8. `07_prepare_ablation_evaluation.py`  
   准备消融评分表并汇总
9. `08_summarize_traceability.py`  
   汇总追溯统计
10. `09_generate_multisource_reports.py`  
    生成多源贡献实验报告
11. `10_prepare_multisource_evaluation.py`  
    准备多源实验评分表并汇总
12. `11_state_continuity_analysis.py`  
    生成轻量级状态连续性分析结果
