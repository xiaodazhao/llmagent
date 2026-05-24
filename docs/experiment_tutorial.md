# 实验操作教程与当前进度

## 1. 这份文档的用途

这份文档是给“继续做实验的人”看的，不讲方法概念，主要讲三件事：

1. 现在已经做到了哪一步。
2. 换电脑后应该先跑什么。
3. 接下来还要补哪些实验。

## 2. 当前已经完成的实验

截至当前版本，已经完成并落地的实验包括：

- 主对比实验  
  对比 `Template / Direct-LLM / CST-LLM`
- 第一版人工评分  
  指标包括 `ICS / FCS / TS / RDR / EOR`
- 可追溯性实验  
  六个 case 的 traceability 表和汇总表已经生成
- 消融实验  
  已完成 `full / wo_geo / wo_alignment / wo_constraints`
- 多源贡献实验  
  已完成 `plc_only / plc_geo / full`
- 轻量级状态连续性分析  
  已生成 `state_continuity_summary.csv`

## 3. 当前关键结果文件

### 主实验结果

- [report_metrics.csv](../experiments/outputs/metrics/report_metrics.csv)
- [evaluation_sheet.csv](../experiments/outputs/metrics/evaluation_sheet.csv)

### 可追溯性结果

- [traceability_summary.csv](../experiments/outputs/metrics/traceability_summary.csv)
- `experiments/outputs/tables/traceability_C01.csv`
- `experiments/outputs/tables/traceability_C02.csv`
- `experiments/outputs/tables/traceability_C03.csv`
- `experiments/outputs/tables/traceability_C04.csv`
- `experiments/outputs/tables/traceability_C05.csv`
- `experiments/outputs/tables/traceability_C06.csv`

### 消融实验结果

- [ablation_metrics.csv](../experiments/outputs/metrics/ablation_metrics.csv)
- [ablation_evaluation_sheet.csv](../experiments/outputs/metrics/ablation_evaluation_sheet.csv)
- [ablation_manifest.csv](../experiments/outputs/reports_ablation/ablation_manifest.csv)

### 多源贡献实验结果

- [multisource_metrics.csv](../experiments/outputs/metrics/multisource_metrics.csv)
- [multisource_evaluation_sheet.csv](../experiments/outputs/metrics/multisource_evaluation_sheet.csv)
- [multisource_manifest.csv](../experiments/outputs/reports_multisource/multisource_manifest.csv)

### 状态连续性分析

- [state_continuity_summary.csv](../experiments/outputs/metrics/state_continuity_summary.csv)
- [state_continuity_overview.md](../experiments/outputs/tables/state_continuity_overview.md)

## 4. 当前使用的案例

当前主实验使用 6 个日尺度案例：

- `C01` 2023-09-24：气体关注
- `C02` 2023-10-21：地质关注
- `C03` 2023-10-24：地质关注
- `C04` 2023-10-26：高强度地质关注
- `C05` 2023-11-01：耦合高关注
- `C06` 2023-11-18：响应异常

案例定义文件在：

- `experiments/outputs/cases/case_list.csv`

## 5. 换电脑后怎么继续

### 5.1 先确认环境

至少确认以下内容：

1. Python 环境可用。
2. `backend/.env` 中的数据路径可访问。
3. TBM CSV、证据库和 SQLite 文件路径正确。

当前曾使用过的数据根目录是：

`G:\我的云端硬盘\TBM9`

如果换电脑后路径不同，需要修改 `backend/.env` 中对应配置。

### 5.2 实验脚本目录

实验脚本都在：

- [experiments](../experiments/README.md)

### 5.3 如果需要从头再跑主实验

建议顺序：

1. `00_prepare_cases.py`
2. `01_export_cst_states.py`
3. `02_generate_reports.py`
4. `03_evaluate_reports.py`

## 6. 还需要做的实验

当前最主要还缺这些：

### 6.1 需要优先补的

1. 补一个高质量 `normal case`  
   当前样本偏关注型和异常型，后续最好补一个稳定时间窗案例。

2. 进一步复核人工评分  
   当前 `ICS / FCS / TS / RDR / EOR` 已有首版草案，建议后续再人工复核一轮。

### 6.2 建议后续补的

3. 更完整的 `w/o indicators` 消融版本  
   当前已做 `wo_geo / wo_alignment / wo_constraints`，后续可进一步补 `wo_indicators`。

4. 更正式的动态更新实验  
   当前只有 continuity case analysis，尚未完成严格递推版 `CST_t = U(CST_{t-1}, ...)` 的定量实验。

5. 更强的人工评价  
   当前 `RDR / EOR` 已接入，但仍属于首版实验分数，后续可引入更多评审者。

## 7. 现在最推荐的工作顺序

如果当前要继续往前推进，建议顺序如下：

1. 保留现有 6 个 case 和实验结果。
2. 优先整理结果图表与案例分析材料。
3. 后续补一个 `normal case`。
4. 最后再考虑递推 CST 的增强实验。

## 8. 一句话总结

当前实验已经从“能跑通”进入“能支撑论文实验初稿”的阶段。  
接下来最重要的不是继续加系统功能，而是围绕现有结果做补强、复核和整理。
