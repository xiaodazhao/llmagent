# 实验操作教程与后续实验清单

## 1. 文档目的

这份文档不是讲论文概念，而是讲：

1. 你现在应该怎么一步一步做实验；
2. 每一步会生成什么文件；
3. 这些结果应该怎么看；
4. 第一阶段做完以后，后面还需要补哪些实验。

如果你换电脑继续做实验，优先看这份文档即可。

## 2. 实验的最小目标

第一阶段不要想着一次把所有论文实验做全。  
你现在先完成一个**最小闭环**：

1. 冻结一批 case；
2. 为每个 case 导出 `CST` 状态；
3. 用三种方法生成报告；
4. 对报告做人工评分；
5. 生成第一版指标表。

只要这五步跑通，你的论文实验就已经真正启动了。

## 3. 你要比较的三种方法

第一阶段只比较下面三种方法：

### 3.1 Template

固定模板生成。  
它代表传统规则报告基线。

### 3.2 Direct-LLM

把 CSV 摘要和 PDF 文本摘要直接给大模型，让模型自己写。  
它代表“没有 Construction State Twin 中间层”的方法。

### 3.3 CST-LLM

先构造 `Construction State Twin`，再基于 state-aware prompt 调 LLM 生成报告。  
这是论文主方法。

## 4. 换电脑前你要知道的目录

### 4.1 代码目录

实验主目录在：

`experiments/`

### 4.2 主要文档

- [最终版方法框架](final_method_framework.md)
- [实验设计与组织方案](experiment_plan.md)
- [论文大纲建议](paper_outline.md)

### 4.3 运行配置

当前后端通过 `backend/.env` 读取：

- `LLM_PROVIDER`
- `DEEPSEEK_API_KEY`
- `DEEPSEEK_MODEL`
- `DATA_ROOT`

如果换电脑，至少要确认：

1. `Python` 环境能正常使用；
2. `backend/.env` 或新的环境变量里，`DATA_ROOT` 指向真实 TBM 数据目录；
3. 证据库和 `SQLite` 路径能正常访问。

### 4.4 真实数据目录

当前实验实际使用的数据根目录是：

`G:\我的云端硬盘\TBM9`

其中：

- `TBM9_2023`：TBM 日运行 CSV
- `DB`：`evidence_db.csv` 和 `tbm_app.sqlite3`
- `TSP / HSP / SKETCH`：地质资料

如果换到另一台电脑，需要保证这些目录仍然可访问，或者在 `backend/.env` 中把 `DATA_ROOT` 改成新的绝对路径。

## 5. 第一阶段实验：一步一步怎么做

下面只讲你现在最应该做的最小闭环。

### Step 1. 生成并检查 case 清单

运行：

```powershell
& 'C:\Users\22923\anaconda3\envs\LLMenv\python.exe' experiments\00_prepare_cases.py --limit 12
```

它会生成两张表：

- `experiments/outputs/cases/case_candidates.csv`
- `experiments/outputs/cases/case_list.csv`

#### 这两张表的区别

`case_candidates.csv`：  
是全日期候选池。每一行是一日数据，并给出自动分类与分数。

`case_list.csv`：  
是自动从候选池中挑出的第一版实验样本。

#### 你要怎么看

优先看 `case_candidates.csv` 的这些列：

- `date`
- `case_type`
- `selection_score`
- `GRS_top`
- `RAI_top`
- `GRCI_top`
- `gas_exceed_type_count`
- `forward_advice_level`
- `reason`

#### 你要做什么

不要完全相信自动挑选结果，要人工修一遍 `case_list.csv`。

建议第一轮只保留 `6` 个 case：

- `normal`：1 个
- `geology_attention`：2 个
- `response_anomaly`：1 个
- `coupled_attention`：1 个
- `gas_attention`：1 个

这一步完成后，你就冻结了第一批实验集。

### Step 2. 导出 Construction State Twin

运行：

```powershell
& 'C:\Users\22923\anaconda3\envs\LLMenv\python.exe' experiments\01_export_cst_states.py
```

生成结果在：

- `experiments/outputs/states/`

每个 case 会导出：

- `C01_state.json`
- `C02_state.json`
- ...

同时还会生成：

- `state_summary.csv`

#### 你要怎么看

先重点检查 `*_state.json`：

- 日期是否正确
- 时间窗是否正确
- 主导工况是否合理
- `GRS / RAI / GRCI` 是否有值
- 前方关注是否有内容
- `evidence_list` 是否为空

这一步的目标不是评分，而是确认：

**Twin 状态已经可以稳定导出。**

### Step 3. 先生成 prompt，不急着调 LLM

运行：

```powershell
& 'C:\Users\22923\anaconda3\envs\LLMenv\python.exe' experiments\02_generate_reports.py --mode prompt_only
```

生成结果在：

- `experiments/outputs/reports/`

你会看到：

- `C01_template.txt`
- `C01_direct_llm.prompt.txt`
- `C01_cst_llm.prompt.txt`

#### 你要怎么看

重点比较：

1. `template` 是否过于死板；
2. `direct_llm.prompt` 是否只有摘要而缺少状态组织；
3. `cst_llm.prompt` 是否明显更结构化、更受约束。

这一步的目的是：

**先验证三种方法的输入设计是否合理。**

### Step 4. 真正生成三类报告

确认 prompt 没问题以后，再运行：

```powershell
& 'C:\Users\22923\anaconda3\envs\LLMenv\python.exe' experiments\02_generate_reports.py --mode call_llm --provider deepseek
```

如果你要切到 Gemini，可以改：

```powershell
--provider google
```

生成结果仍然在：

- `experiments/outputs/reports/`

这时会新增：

- `C01_direct_llm.txt`
- `C01_cst_llm.txt`

模板报告已经在第 3 步生成。

#### 你要怎么看

先不要打分，先直接通读：

- 哪个更完整
- 哪个更容易把地质和前方写混
- 哪个更像正式报告
- 哪个更容易出现 unsupported claim

这一步是在做第一轮“肉眼对比”。

### Step 5. 初始化人工评分表

运行：

```powershell
& 'C:\Users\22923\anaconda3\envs\LLMenv\python.exe' experiments\03_evaluate_reports.py --init-only
```

生成结果：

- `experiments/outputs/metrics/evaluation_sheet.csv`

#### 你要做什么

打开这个 CSV，开始手工填分。

第一阶段先只填这些字段：

- `ICS_operation`
- `ICS_geology`
- `ICS_gas`
- `ICS_forward`
- `factual_errors_count`
- `key_facts_count`
- `unsupported_claims_count`
- `key_claims_count`

#### 这些字段怎么算

##### ICS

每个内容块按下面打：

- `0`：没写
- `1`：写了一部分
- `2`：写得比较完整

这里先只看四块：

- operation
- geology
- gas
- forward

##### FCS

你自己数：

- 这篇报告有多少个关键事实点：`key_facts_count`
- 其中有多少条写错了：`factual_errors_count`

##### TS

你自己数：

- 这篇报告有多少条关键结论：`key_claims_count`
- 其中多少条找不到证据支撑：`unsupported_claims_count`

### Step 6. 汇总指标

评分表填完以后，运行：

```powershell
& 'C:\Users\22923\anaconda3\envs\LLMenv\python.exe' experiments\03_evaluate_reports.py
```

生成：

- `experiments/outputs/metrics/report_metrics.csv`

#### 你要怎么看

这个表会先给出三种方法的平均表现：

- `ICS_mean`
- `FCS_mean`
- `TS_mean`

这就是你第一版主实验结果表。

## 6. 可追溯性实验怎么做

在你已经生成报告文本之后，运行：

```powershell
& 'C:\Users\22923\anaconda3\envs\LLMenv\python.exe' experiments\05_traceability_check.py
```

生成：

- `experiments/outputs/tables/traceability_C01.csv`
- `experiments/outputs/tables/traceability_C02.csv`
- ...

#### 这个表怎么用

每一行是一条候选结论句。  
你需要手工补：

- `claim_type`
- `evidence_source`
- `evidence_field`
- `evidence_text`
- `is_supported`
- `error_type`

#### 这个实验的目标

不是自动判定，而是建立：

**报告结论 -> Twin 状态 -> 底层证据**

这条追溯链。

## 7. 消融实验怎么做

先运行：

```powershell
& 'C:\Users\22923\anaconda3\envs\LLMenv\python.exe' experiments\04_ablation_study.py
```

生成：

- `experiments/outputs/metrics/ablation_plan.csv`

这一步目前只是生成计划，不会自动跑完消融。

### 你现在怎么用它

先把它当成实验待办表。  
第一阶段不用马上全做。

建议先准备 4 个版本：

- `full`
- `wo_geo`
- `wo_alignment`
- `wo_constraints`

等主对比实验跑顺以后，再正式扩展脚本去生成这些版本。

## 8. 你现在最应该做的实验顺序

### 第一阶段：先把最小闭环跑通

1. 修 `case_list.csv`
2. 跑 `01_export_cst_states.py`
3. 跑 `02_generate_reports.py --mode prompt_only`
4. 跑 `02_generate_reports.py --mode call_llm`
5. 填 `evaluation_sheet.csv`
6. 生成 `report_metrics.csv`

### 第二阶段：补强说服力

1. 跑 `05_traceability_check.py`
2. 完成 3 个强案例的追溯表
3. 做第一版 case study 图表

### 第三阶段：再做增强实验

1. 消融实验
2. 多源贡献实验
3. 动态更新 case study
4. `RDR / EOR`

## 9. 现在还没做、但后面要做的实验

### 9.1 主对比实验

要正式跑完：

- `Template`
- `Direct-LLM`
- `CST-LLM`

并产出：

- `ICS`
- `FCS`
- `TS`

### 9.2 消融实验

要回答：

- 没有地质信息时会怎样
- 没有空间对齐时会怎样
- 没有 prompt 约束时会怎样
- 没有 `GRS / RAI / GRCI` 时会怎样

### 9.3 多源贡献实验

建议后面做 3 组起步：

- `PLC only`
- `PLC + Geo`
- `Full`

### 9.4 动态状态更新案例分析

先不要一上来做最重主实验，而是先做：

- 连续日期状态变化
- 历史对比一致性
- Agent 连续追问一致性

### 9.5 风险措辞与专家评分

后面再补：

- `RDR`
- `EOR`

## 10. 你回家换电脑后，最先做什么

换电脑后，不要马上想着重新开发。  
先做下面 4 件事：

1. 把项目拉下来
2. 配好 Python 环境
3. 确认 `backend/.env` 的 `DATA_ROOT` 指向真实数据目录
4. 先跑：

```powershell
python experiments\00_prepare_cases.py --help
python experiments\01_export_cst_states.py --help
python experiments\02_generate_reports.py --help
```

确认脚本都能跑，再继续正式实验。

## 11. 一句话总结

你现在做实验，不需要先懂整套论文理论。  
你只需要按这个顺序推进：

**选 case -> 导出 CST -> 生成三类报告 -> 人工评分 -> 做追溯表**

这五步跑通，实验就真正开始了。
