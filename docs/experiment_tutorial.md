# 完整实验教程（换电脑从零开始版）

## 1. 这份教程是给谁用的

这份文档是给“在另一台电脑上从头把实验重新跑起来的人”准备的。

它解决的问题不是“方法是什么”，而是：

1. 代码拉下来后先做什么。
2. 环境怎么配。
3. 数据路径怎么接。
4. 每个实验脚本怎么跑。
5. 每一步会生成什么文件。
6. 结果应该怎么看。
7. 哪些结果已经做过，哪些还要继续补。

如果你换了一台电脑，建议直接从这份文档开始，不要先翻论文草稿。

## 2. 先理解一件事：实验输出默认不会跟着 Git 走

仓库里已经有实验脚本、实验配置和文档，但：

- `experiments/outputs/` 下的大多数运行结果默认被 `.gitignore` 忽略；
- 也就是说，你在新电脑 `git pull` 下来后，**不会自动拿到旧电脑跑出来的实验结果文件**；
- 你需要在新电脑上重新运行实验脚本，重新生成：
  - `case_list.csv`
  - `state.json`
  - 报告文本
  - 评分表
  - 汇总指标

所以这份教程的目标就是：**让你把这些结果在新电脑上重新跑出来**。

## 3. 你在新电脑上要准备什么

### 3.1 基本软件

至少准备：

- `Git`
- `Python 3.10+` 或你当前能稳定使用的 Python 版本
- `Node.js` 和 `npm`  
  只有在你还要启动前端页面时才需要

### 3.2 仓库代码

在新电脑上拉代码：

```powershell
git clone https://github.com/xiaodazhao/llmagent.git
cd llmagent
git pull
```

如果你不是新 clone，而是在已有目录更新：

```powershell
git pull origin main
```

### 3.3 真实数据目录

你当前实验依赖真实 TBM 数据和证据库。

之前用过的数据根目录是：

```text
G:\我的云端硬盘\TBM9
```

至少要保证下面这些东西在新电脑仍然能访问：

- `TBM9_2023`：日运行 CSV
- `DB`：证据库 CSV 和 SQLite
- `TSP`
- `HSP`
- `SKETCH`

如果新电脑上这个盘符或路径变了，后面要改 `.env` 配置。

### 3.4 LLM API Key

如果你要真正生成报告，需要至少有一个可用的大模型 key：

- `DeepSeek`
- 或 `Gemini`

如果只是先检查 prompt，不调用模型，那可以先不配 key。

## 4. 环境配置步骤

### 4.1 创建 Python 环境

如果你用 `conda`，可以自己起一个环境名，例如：

```powershell
conda create -n tbmexp python=3.11 -y
conda activate tbmexp
```

如果你沿用你原来那套环境名字，也可以继续用。

### 4.2 安装后端依赖

在仓库根目录执行：

```powershell
pip install -r backend/requirements.txt
```

当前核心依赖包括：

- `pandas`
- `numpy`
- `scikit-learn`
- `fastapi`
- `uvicorn`
- `python-dotenv`
- `PyMuPDF`
- `google-genai`
- `pydantic`
- `pytest`

### 4.3 前端依赖（可选）

如果你还需要启动前端页面：

```powershell
cd Frontend
npm install
cd ..
```

实验脚本本身不依赖前端。

## 5. 配置 `.env`

仓库根目录已经有：

- [.env.example](/c:/Users/22923/Desktop/my%20project/LLM_20260424/.env.example:1)

先复制一份：

```powershell
copy .env.example backend/.env
```

然后打开 `backend/.env`，至少改这些项。

### 5.1 模型配置

如果你用 DeepSeek：

```text
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=你的key
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_BASE_URL=https://api.deepseek.com
```

如果你用 Gemini：

```text
LLM_PROVIDER=google
GOOGLE_API_KEY=你的key
GOOGLE_MODEL=gemini-2.5-flash-lite
```

### 5.2 数据路径配置

最简单的是直接配 `DATA_ROOT`：

```text
DATA_ROOT=G:\我的云端硬盘\TBM9
```

如果你的新电脑上子目录结构和之前一样，通常只设 `DATA_ROOT` 就够了。

如果结构不同，也可以逐项显式写：

```text
DATA_DIR=G:\我的云端硬盘\TBM9\TBM9_2023
TSP_DIR=G:\我的云端硬盘\TBM9\TSP
HSP_DIR=G:\我的云端硬盘\TBM9\HSP
SKETCH_DIR=G:\我的云端硬盘\TBM9\SKETCH
DB_DIR=G:\我的云端硬盘\TBM9\DB
APP_DB_PATH=G:\我的云端硬盘\TBM9\DB\tbm_app.sqlite3
EVIDENCE_DB_PATH=G:\我的云端硬盘\TBM9\DB\evidence_db.csv
```

### 5.3 常用分析参数

一般先保持默认即可：

```text
TOLERANCE_M=3.0
HIGH_RISK_LOOKAHEAD_M=10.0
NEXT_FORECAST_LOOKAHEAD_M=5.0
```

## 6. 先做两个最基本的连通性检查

### 6.1 检查 Python 能否运行实验脚本

在仓库根目录执行：

```powershell
python experiments/00_prepare_cases.py --help
python experiments/03_evaluate_reports.py --help
```

如果都能显示帮助信息，说明脚本层没问题。

### 6.2 检查代码能否编译

```powershell
python -m compileall experiments
python -m compileall backend
```

如果没有报致命错误，说明代码环境基本可用。

## 7. 整套实验怎么跑

推荐顺序是：

1. `00_prepare_cases.py`
2. `01_export_cst_states.py`
3. `02_generate_reports.py`
4. `03_evaluate_reports.py`
5. `05_traceability_check.py`
6. `08_summarize_traceability.py`
7. `06_generate_ablation_reports.py`
8. `07_prepare_ablation_evaluation.py`
9. `09_generate_multisource_reports.py`
10. `10_prepare_multisource_evaluation.py`
11. `11_state_continuity_analysis.py`

下面按这个顺序详细写。

## 8. Step 1：准备 case

### 8.1 运行命令

```powershell
python experiments/00_prepare_cases.py --limit 12
```

### 8.2 它会生成什么

输出目录：

```text
experiments/outputs/cases/
```

主要文件：

- `case_candidates.csv`
- `case_list.csv`

### 8.3 两个文件分别是什么

`case_candidates.csv`

- 是“候选池”
- 每一行代表一个日期
- 包含自动分类和打分

你重点看这些列：

- `date`
- `case_type`
- `selection_score`
- `GRS_top`
- `RAI_top`
- `GRCI_top`
- `gas_exceed_type_count`
- `forward_advice_level`
- `reason`

`case_list.csv`

- 是“实际实验样本清单”
- 后面所有实验都以它为输入

### 8.4 你应该怎么做

不要完全相信自动筛选。  
你应该打开 `case_list.csv`，人工确认是否保留这些案例。

当前已经用过的一套案例是：

- `C01` 2023-09-24：气体关注
- `C02` 2023-10-21：地质关注
- `C03` 2023-10-24：地质关注
- `C04` 2023-10-26：高强度地质关注
- `C05` 2023-11-01：耦合高关注
- `C06` 2023-11-18：响应异常

如果你不想重新筛，可以直接沿用这一套。

### 8.5 成功标准

成功的标志是：

- `case_candidates.csv` 正常生成
- `case_list.csv` 里有你认可的 case

## 9. Step 2：导出 CST

### 9.1 运行命令

```powershell
python experiments/01_export_cst_states.py
```

### 9.2 它会生成什么

输出目录：

```text
experiments/outputs/states/
```

主要文件：

- `C01_state.json`
- `C02_state.json`
- ...
- `state_summary.csv`

### 9.3 你要检查什么

先看 `state_summary.csv`，重点检查这些列：

- `case_id`
- `date`
- `main_state`
- `GRS`
- `RAI`
- `GRCI`
- `face_chainage`

再抽查 1-2 个 `*_state.json`，确认有这些层：

- `temporal_state`
- `spatial_state`
- `operation_state`
- `geological_state`
- `response_state`
- `attention_state`
- `provenance_state`

### 9.4 成功标准

成功的标志是：

- 所有 case 都生成了 `state.json`
- `GRS / RAI / GRCI` 不是全空
- `forward_window`、`high_attention_segments`、`evidence_list` 有合理内容

## 10. Step 3：先生成 prompt，不急着调模型

### 10.1 运行命令

```powershell
python experiments/02_generate_reports.py --mode prompt_only
```

### 10.2 它会生成什么

输出目录：

```text
experiments/outputs/reports/
```

每个 case 你会看到：

- `C01_template.txt`
- `C01_direct_llm.prompt.txt`
- `C01_cst_llm.prompt.txt`

### 10.3 你要看什么

重点比较三种输入：

#### Template

- 很短
- 很死板
- 这是正常的

#### Direct-LLM prompt

- 应该有施工摘要、地质摘要、气体摘要、前方提示
- 但没有显式 CST 组织

#### CST-LLM prompt

- 应该更结构化
- 明确区分当前掌子面与前方预测
- 有状态摘要和约束
- 不应该出现原始 Python dict dump

### 10.4 成功标准

成功的标志是：

- `direct_llm.prompt` 可读
- `cst_llm.prompt` 比 direct_llm 更结构化
- 不出现明显脏内容，比如 `Timestamp(...)`、原始 dict 串

## 11. Step 4：正式生成三组报告

### 11.1 运行命令

如果用 DeepSeek：

```powershell
python experiments/02_generate_reports.py --mode call_llm --provider deepseek
```

如果用 Gemini：

```powershell
python experiments/02_generate_reports.py --mode call_llm --provider google
```

### 11.2 它会生成什么

同样在：

```text
experiments/outputs/reports/
```

你会看到真正的报告文本：

- `C01_direct_llm.txt`
- `C01_cst_llm.txt`
- 以及已有的 `C01_template.txt`

### 11.3 你要看什么

先不用打分，先肉眼比较：

- 哪个更完整
- 哪个更像正式工程报告
- 哪个更容易夸大风险
- 哪个更容易混写当前掌子面和前方预测

### 11.4 成功标准

成功的标志是：

- 三组方法都能生成文本
- `CST-LLM` 在结构上明显更稳
- `Direct-LLM` 保持 baseline 的“无状态组织”特征

## 12. Step 5：初始化人工评分表

### 12.1 运行命令

```powershell
python experiments/03_evaluate_reports.py --init-only
```

### 12.2 它会生成什么

输出目录：

```text
experiments/outputs/metrics/
```

主要文件：

- `evaluation_sheet.csv`

### 12.3 这个表怎么填

每一行是：

- 一个 `case`
- 一种 `method`

例如：

- `C01 + template`
- `C01 + direct_llm`
- `C01 + cst_llm`

当前已经有首版草案分数，但如果你在新电脑重跑，可能要重新填或复核。

### 12.4 五类评分字段

#### 用来算 `ICS`

- `ICS_operation`
- `ICS_geology`
- `ICS_gas`
- `ICS_forward`

打分规则：

- `0` = 没覆盖
- `1` = 部分覆盖
- `2` = 完整覆盖

#### 用来算 `FCS`

- `factual_errors_count`
- `key_facts_count`

#### 用来算 `TS`

- `unsupported_claims_count`
- `key_claims_count`

#### 用来算 `RDR`

- `RDR_score`

建议 `1-5`：

- `1` 很差
- `3` 基本合理
- `5` 风险措辞很稳

#### 用来算 `EOR`

- `EOR_score`

建议 `1-5`：

- `1` 基本不可用
- `3` 可用但一般
- `5` 很成熟

## 13. Step 6：汇总主实验结果

### 13.1 运行命令

```powershell
python experiments/03_evaluate_reports.py
```

### 13.2 它会生成什么

- `report_metrics.csv`

### 13.3 你怎么看

重点看：

- `ICS_mean`
- `FCS_mean`
- `TS_mean`
- `RDR_mean`
- `EOR_mean`

当前已有的一版结果是：

- `Template`：`ICS=0.25, FCS=1.0, TS=1.0, RDR=4.0, EOR=2.0`
- `Direct-LLM`：`ICS=1.0, FCS=0.9167, TS=0.8, RDR=2.6667, EOR=3.5`
- `CST-LLM`：`ICS=1.0, FCS=1.0, TS=1.0, RDR=4.8333, EOR=4.6667`

如果你新电脑重跑后差很多，优先检查：

- 数据目录是否一致
- 模型 provider 是否变了
- case 是否仍是同一批

## 14. Step 7：可追溯性实验

### 14.1 先生成追溯表模板

```powershell
python experiments/05_traceability_check.py
```

### 14.2 再汇总追溯结果

```powershell
python experiments/08_summarize_traceability.py
```

### 14.3 会生成什么

输出目录：

```text
experiments/outputs/tables/
experiments/outputs/metrics/
```

主要文件：

- `traceability_C01.csv`
- ...
- `traceability_C06.csv`
- `traceability_summary.csv`

### 14.4 你怎么看

每个 `traceability_Cxx.csv` 里每一行代表一条关键结论，常见字段包括：

- `report_claim`
- `claim_type`
- `evidence_source`
- `evidence_field`
- `evidence_text`
- `is_supported`

而 `traceability_summary.csv` 会汇总：

- 一共审核了多少结论
- 支持了多少
- 不支持多少
- 支持率是多少

当前已有结果里：

- `CST-LLM` 的已审核结论支持率最高
- `Direct-LLM` 在 `C05` 和 `C06` 上有 unsupported claims

## 15. Step 8：消融实验

### 15.1 先生成计划

```powershell
python experiments/04_ablation_study.py
```

### 15.2 生成消融报告

```powershell
python experiments/06_generate_ablation_reports.py --mode call_llm --provider deepseek
```

### 15.3 准备并汇总消融评分

```powershell
python experiments/07_prepare_ablation_evaluation.py
```

### 15.4 输出文件

- `ablation_plan.csv`
- `ablation_manifest.csv`
- `ablation_evaluation_sheet.csv`
- `ablation_metrics.csv`

### 15.5 当前已做的版本

- `full`
- `wo_geo`
- `wo_alignment`
- `wo_constraints`

### 15.6 你怎么看结果

当前已有草案结果：

- `full`: `ICS=1.0, FCS=1.0, TS=1.0, RDR=5.0, EOR=5.0`
- `wo_geo`: `ICS=0.5, FCS=1.0, TS=0.8, RDR=4.0, EOR=3.0`
- `wo_alignment`: `ICS=1.0, FCS=1.0, TS=0.8, RDR=4.0, EOR=4.0`
- `wo_constraints`: `ICS=1.0, FCS=1.0, TS=0.8, RDR=3.0, EOR=4.0`

这说明：

- 去掉地质信息会明显伤害覆盖度
- 去掉空间对齐会伤害追溯性
- 去掉约束会伤害风险表述可靠性

## 16. Step 9：多源贡献实验

### 16.1 生成多源版本报告

```powershell
python experiments/09_generate_multisource_reports.py --mode call_llm --provider deepseek
```

### 16.2 准备并汇总评分

```powershell
python experiments/10_prepare_multisource_evaluation.py
```

### 16.3 输出文件

- `multisource_manifest.csv`
- `multisource_evaluation_sheet.csv`
- `multisource_metrics.csv`

### 16.4 当前已做的版本

- `plc_only`
- `plc_geo`
- `full`

### 16.5 当前已有草案结果

- `plc_only`: `ICS=0.5, FCS=1.0, TS=0.8, RDR=3.0, EOR=3.0`
- `plc_geo`: `ICS=0.75, FCS=1.0, TS=1.0, RDR=4.0, EOR=4.0`
- `full`: `ICS=1.0, FCS=1.0, TS=1.0, RDR=5.0, EOR=5.0`

这说明多源输入越完整，报告整体质量越高。

## 17. Step 10：轻量级状态连续性分析

### 17.1 运行命令

```powershell
python experiments/11_state_continuity_analysis.py
```

### 17.2 输出文件

- `state_continuity_summary.csv`
- `state_continuity_overview.md`

### 17.3 它是什么

它不是严格递推版 `CST_t = U(CST_{t-1}, ...)` 的定量实验。  
它更像一个轻量级 continuity case study，用于看：

- 相邻 case 的 `GRS / RAI / GRCI` 如何变化
- 主导工况如何变化
- 前方关注等级如何变化
- 共同 hazard 如何变化

## 18. 常见问题与排查

### 18.1 没有生成 case

优先检查：

- `DATA_ROOT` / `DATA_DIR` 是否指向真实 CSV
- 新电脑是否能访问 `G:` 盘

### 18.2 没有生成 state.json

优先检查：

- `case_list.csv` 是否为空
- 地质证据库是否可访问
- 某个 case 是否缺少可用里程字段

### 18.3 prompt 正常，但 call_llm 失败

优先检查：

- `DEEPSEEK_API_KEY` 或 `GOOGLE_API_KEY`
- `LLM_PROVIDER`
- 网络连通性

### 18.4 输出结果和旧电脑不一致

优先检查：

- 数据路径是否一致
- case 是否相同
- 模型提供方是否一致
- 评分表是否重新初始化过

## 19. 当前还没完全补齐的实验

现在最主要还缺：

1. 一个更好的 `normal case`
2. `w/o indicators` 消融
3. 更正式的人工复核
4. 严格递推版 `CST_t = U(CST_{t-1}, ...)` 定量实验

## 20. 最后一句话

如果你换到一台新电脑上继续做，最推荐的做法是：

1. 先配 `.env`
2. 跑 `00 -> 01 -> 02 -> 03`
3. 再跑 `05/08 -> 06/07 -> 09/10 -> 11`

也就是说，**先恢复主实验，再恢复增强实验。**
