# 实验设计与组织方案

## 1. 文档目的

这份文档用于明确论文实验应该做什么、怎么组织、输出哪些结果，以及每个实验的目标是什么。

它服务于两个问题：

1. 如何证明 `Construction State Twin` 是必要的；
2. 如何证明 `CST + State-Aware Prompt + LLM` 比直接或弱约束生成更好。

本方案面向的是**论文实验层**，不是业务功能开发清单。

## 2. 实验总目标

实验需要回答以下五个核心问题：

1. `Construction State Twin` 到底是什么，是否能稳定表示施工状态；
2. Twin 作为中间层，是否比直接将原始数据交给 LLM 更有效；
3. Twin 中的关键模块是否真的有贡献；
4. 生成报告是否事实一致、风险表述合理、结论可追溯；
5. 这种方法是否只对个别日期有效，还是具备跨案例稳定性。

## 3. 建议的实验目录组织

建议在仓库根目录新增：

```text
experiments/
  00_prepare_cases.py
  01_export_cst_states.py
  02_generate_reports.py
  03_evaluate_reports.py
  04_ablation_study.py
  05_traceability_check.py
  configs/
    experiment_config.yaml
    baseline_prompts.yaml
  outputs/
    cases/
    states/
    reports/
    metrics/
    tables/
    figures/
```

这样可以把实验资产和业务主链分开，便于论文复现和后续导图表。

## 4. 实验数据集组织

### 4.1 先冻结一个小型实验集

第一阶段不要试图全量覆盖全部日期，建议先冻结 `10-12` 个代表性 case。

每个 case 可以是：

- 一个日期；
- 一个日期中的某个时间窗；
- 一个重点里程区段。

### 4.2 Case 类型建议

建议至少覆盖以下五类：

- `normal`：工况稳定、关注度较低；
- `geology_attention`：地质证据提示明显；
- `response_anomaly`：施工参数异常较突出；
- `coupled_attention`：`GRS` 和 `RAI` 同时高，`GRCI` 高；
- `gas_attention`：气体波动或接近阈值。

### 4.3 Case 清单输出

`00_prepare_cases.py` 的输出建议为：

```text
experiments/outputs/cases/case_list.csv
```

字段建议包括：

- `case_id`
- `date`
- `time_start`
- `time_end`
- `chainage_start`
- `chainage_end`
- `case_type`
- `reason`

## 5. 实验一：主对比实验

### 5.1 目标

证明 `CST-LLM` 相较于传统模板和直接 LLM 生成方式，能在：

- 信息完整性；
- 事实一致性；
- 风险措辞可靠性；
- 可追溯性；

等方面取得更好的表现。

### 5.2 对比方法

建议第一阶段先做 3 组：

1. `Template`
2. `Direct-LLM`
3. `CST-LLM`

如果时间和精力允许，再加入：

4. `RAG-LLM`

### 5.3 方法定义

#### Template

输入：

- 结构化统计结果
- 固定模板

作用：

- 代表传统规则报告生成基线

#### Direct-LLM

输入：

- 原始 CSV 统计摘要
- PDF 解析得到的文本片段

不提供：

- Twin 状态；
- 统一里程状态组织；
- `GRS / RAI / GRCI`；
- 强约束 prompt。

作用：

- 证明直接 LLM 容易出现混写、遗漏、表述不稳。

#### CST-LLM

输入：

- `Construction State Twin`
- `GRS / RAI / GRCI`
- 结构化证据摘要
- state-aware prompt

作用：

- 作为主方法。

#### RAG-LLM

如果后续加入，输入为：

- 检索得到的地质文本片段
- CSV 统计摘要

不提供完整 Twin 状态。  
它的作用是证明：普通检索增强仍然缺少状态组织与耦合解释。

## 6. 实验二：消融实验

### 6.1 目标

证明不是 LLM 自己在发挥，而是 Twin 中的关键模块在提供价值。

### 6.2 建议版本

建议先做 4 组：

1. `Full CST-LLM`
2. `w/o Geo`
3. `w/o Spatial Alignment`
4. `w/o Prompt Constraints`

如果还有余力，再扩展：

5. `w/o GRS/RAI/GRCI`

### 6.3 各版本含义

#### Full CST-LLM

完整方法，包含：

- 多源输入；
- 统一里程对齐；
- Twin 状态；
- 关注/异常/耦合指标；
- 受控 prompt。

#### w/o Geo

去掉地质证据侧状态，仅保留施工运行信息。  
用于观察地质信息对报告质量的贡献。

#### w/o Spatial Alignment

不做统一里程对齐，只给摘要文本。  
用于观察“统一里程状态组织”对报告的贡献。

#### w/o Prompt Constraints

保留 Twin 状态，但去掉风险措辞和写作边界约束。  
用于观察 state-aware prompt 约束的作用。

#### w/o GRS/RAI/GRCI

保留 Twin 基础状态，但去掉三指标引导。  
用于观察重点区段排序与耦合信息对生成的贡献。

## 7. 实验三：多源数据贡献实验

### 7.1 目标

证明多源信息并不是简单叠加，而是通过 Twin 组织后共同提升报告质量。

### 7.2 建议起步版本

先做 3 组：

1. `PLC only`
2. `PLC + Geo`
3. `Full`

如果后续需要再细化，可扩展为：

4. `PLC + Geo + Face sketch`
5. `PLC + Geo + Gas`

### 7.3 关注输出

主要比较：

- 信息完整性；
- 地质描述准确性；
- 风险关注合理性；
- 结论可追溯性。

## 8. 实验四：可追溯性实验

### 8.1 目标

证明 `CST-LLM` 生成的关键结论可以追溯到结构化状态和底层证据。

### 8.2 基本做法

对每份报告提取关键结论，例如：

- 施工概况结论；
- 速度/效率异常结论；
- 地质关注结论；
- 前方提示结论；
- 气体安全结论。

然后逐条建立追溯关系表：

- 结论文本；
- 对应状态字段；
- 对应证据来源；
- 是否有明确支撑；
- 若不支持，错误类型是什么。

### 8.3 输出建议

```text
experiments/outputs/tables/traceability_<case_id>.csv
```

字段建议包括：

- `case_id`
- `method`
- `claim_id`
- `report_claim`
- `claim_type`
- `evidence_source`
- `evidence_field`
- `evidence_text`
- `is_supported`
- `error_type`

## 9. 实验五：动态状态更新实验

### 9.1 目标

证明 `CST_t` 不只是一次性快照，而是一个随施工推进动态更新的状态体。

### 9.2 需要验证的问题

1. 状态是否能从 `CST_{t-1}` 递推到 `CST_t`；
2. 前方关注、重点区段和异常趋势是否能在相邻状态中连续迁移；
3. 历史对比是否真实反映状态变化；
4. Agent 是否能围绕连续状态进行追问和解释。

### 9.3 建议验证方式

#### 状态连续性验证

对连续日期或连续时段进行状态导出，比较：

- 当前里程变化；
- 前方关注区间变化；
- 主导工况变化；
- 重点区段是否延续；
- 风险重点是否迁移。

#### 历史对比一致性验证

检查 `CST_t` 与 `CST_{t-1}` 生成的变化摘要，是否与实际结构化状态差异一致。

#### Agent 连续问答一致性验证

在连续状态上，测试用户追问：

- “今天整体怎么样？”
- “前方还需要注意什么？”
- “为什么这段要重点关注？”
- “和上次相比哪里变化最大？”

检查其回答是否仍然围绕同一状态对象展开。

## 10. 评价指标设计

建议统一采用以下五类指标。

### 10.1 Information Coverage Score, ICS

衡量报告是否覆盖应写内容。  
建议按以下六类内容打分：

- 施工概况
- 工况统计
- 施工状态与效率
- 地质情况
- 气体安全
- 前方提示

每类：

- `0`：未覆盖
- `1`：部分覆盖
- `2`：完整覆盖

最终：

`ICS = 实际得分 / 最高得分`

### 10.2 Factual Consistency Score, FCS

衡量报告关键事实是否与结构化状态一致。

错误类型包括：

- 数值错误；
- 时间错误；
- 空间错误；
- 证据错误；
- 状态错误。

建议：

`FCS = 1 - 事实错误数 / 关键事实总数`

### 10.3 Risk Description Reliability, RDR

衡量风险相关表述是否谨慎、准确、不过度。

重点看：

- 是否夸大风险；
- 是否把“关注”写成“已发生”；
- 是否混淆当前揭示和前方预测；
- 是否忽略证据边界。

### 10.4 Traceability Score, TS

定义为：

`TS = 有证据支撑的关键结论数 / 关键结论总数`

这是最能体现 Twin 价值的指标之一，建议优先纳入主实验。

### 10.5 Expert Overall Rating, EOR

建议邀请 `2-3` 位 domain-aware reviewer 打分。  
评分维度包括：

- 工程语言规范性；
- 报告完整性；
- 风险表述合理性；
- 可读性；
- 是否可用于实际汇报。

如果前期很难组织专家评分，第一阶段可先完成 `ICS / FCS / TS`，后续再补 `RDR / EOR`。

## 11. 推荐的实验脚本职责

### 11.1 `00_prepare_cases.py`

职责：

- 选择实验 case；
- 生成标准 case 清单。

输出：

- `case_list.csv`

### 11.2 `01_export_cst_states.py`

职责：

- 调用现有服务或 API；
- 导出每个 case 的 `Construction State Twin`。

输出：

- `state.json`
- 必要时再导出 `state.csv`

### 11.3 `02_generate_reports.py`

职责：

- 用不同方法生成报告；
- 保存 prompt 和生成结果。

输出：

- `template`
- `direct_llm`
- `cst_llm`
- 可选 `rag_llm`

### 11.4 `03_evaluate_reports.py`

职责：

- 汇总人工或半自动评分；
- 输出指标表。

输出：

- `report_metrics.csv`

### 11.5 `04_ablation_study.py`

职责：

- 跑消融版本；
- 导出对应报告。

### 11.6 `05_traceability_check.py`

职责：

- 建立报告关键结论与状态/证据的映射表。

## 12. 图表建议

### 图

建议至少准备：

1. 总体框架图  
   `Multi-source Data -> CST -> State-Aware Prompt -> LLM Report`

2. Construction State Twin 分层图  
   `Temporal / Spatial / Operation / Geological / Response / Attention / Provenance`

3. 时间-里程对齐图  
   展示 PLC、地质证据、掌子面和 `GRS/RAI/GRCI` 在统一里程轴上的关系。

4. 主实验对比柱状图  
   比较 `Template / Direct-LLM / CST-LLM`

5. 消融实验对比图  
   比较 `Full / w-o modules`

### 表

建议至少准备：

1. 数据集描述表
2. 指标定义表
3. 主实验结果表
4. 典型案例追溯表

## 13. 推荐执行顺序

### 第一阶段：最小可运行实验集

1. 冻结 `10-12` 个 case；
2. 导出 `CST` 状态；
3. 生成 `Template / Direct-LLM / CST-LLM` 三组报告；
4. 完成 `ICS / FCS / TS` 评分。

### 第二阶段：方法说服力增强

1. 做消融；
2. 做 3 个强案例；
3. 做追溯表。

### 第三阶段：进一步补强

1. 引入 `RAG-LLM`；
2. 细化多源贡献实验；
3. 补 `RDR / EOR`。

## 14. 一句话总结

实验层的核心不是再加功能，而是证明：

**Construction State Twin 作为中间状态层，确实比直接或弱约束的 LLM 生成方式更完整、更一致、更可控，也更可追溯。**
