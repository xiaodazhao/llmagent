# 数字孪生与大语言模型协同驱动的 TBM 施工报告自动化生成

这是一个面向 TBM 隧道施工数据的后端分析服务 + 前端可视化系统。它把每日 TBM 运行 CSV、TSP/HSP/洞身素描 PDF 超前地质预报、历史分析记录和 LLM 报告生成串在一起，用于做施工状态识别、地质风险融合、风险-施工响应耦合分析、历史对比和日报生成。

项目当前不是一个单纯的网页 Demo，而是一套完整的数据处理链路：

```text
TBM 日运行 CSV
    -> 工况分段、施工状态识别、气体统计、速度/风险剖面

TSP / HSP / 洞身素描 PDF
    -> PDF 解析
    -> evidence_db.csv 地质证据库
    -> 按里程融合到 TBM 数据
    -> 区段级地质风险 GRS

TBM 响应 + 地质风险
    -> RAI 施工响应异常指数
    -> GRCI 地质-施工响应耦合指数
    -> 高关注区段、数字孪生状态、前方风险提示

分析结果
    -> FastAPI 接口
    -> React 前端看板
    -> LLM 日报 / 时间窗报告
    -> analysis_history 历史记忆
```

## 1. 系统功能总览

### 1.1 施工运行分析

系统读取每日 `tbm_data_YYYYMMDD.csv`，按时间排序后识别 TBM 运行状态：

- 停机
- 启动/过渡
- 稳定掘进
- 异常扭矩

基础统计包括：

- 各类工况段数量
- 各类工况累计时长
- 最长停机、最长掘进、最长过渡、最长异常段
- 短时停机、短时掘进、短时过渡统计
- 状态切换频率

核心代码：

- `backend/analysis/dataprocess.py`
- `backend/services/tbm_analysis_service.py`

### 1.2 隐含施工状态识别

系统会在有效样本足够时，基于 TBM 参数做施工状态聚类与状态解释。

当前使用的状态特征：

```text
推力
刀盘扭矩
刀盘实际转速
推进速度
```

处理逻辑：

1. 统计有效样本数。
2. 根据样本量自适应选择聚类参数。
3. 使用 `detect_excavation_state()` 生成 `state_id`。
4. 使用 `explain_excavation_states()` 把状态编号解释为工程语义标签。
5. 生成状态分段、状态效率表和状态切换统计。

核心代码：

- `backend/analysis/excavation_state.py`
- `backend/services/tbm_analysis_service.py`

### 1.3 气体安全分析

系统支持以下气体字段：

```text
CO2检测
H2S检测
SO2检测
NO2检测
NO检测
CH4检测
```

当前默认阈值在 `backend/analysis/gas_analysis.py` 中：

| 字段 | 阈值 | 备注 |
| --- | ---: | --- |
| CO2检测 | 0.5 | 按百分比处理 |
| H2S检测 | 10 | 按 ppm 处理 |
| SO2检测 | 2 | 按 ppm 处理 |
| NO2检测 | 5 | 占位阈值，需要结合现场标准确认 |
| NO检测 | 20 | 按 ppm 处理 |
| CH4检测 | 0.5 | 按百分比处理 |

输出内容：

- 全天统计
- 掘进期统计
- 停机期统计
- 如果施工状态识别成功，还会输出状态级气体统计
- 每类气体的均值、最大值、最小值、超阈值事件数和超阈值时间段

注意：如果现场 CSV 中这些字段不是浓度值，而是 0/1 报警量，则气体逻辑需要改成报警事件分析。

### 1.4 地质证据库与多源融合

系统把 TSP、HSP、洞身素描等超前地质预报解析为统一的 `EvidenceRecord`，写入 `evidence_db.csv`。

地质证据库用途：

- 把地质预报按里程挂到 TBM 每条运行记录上
- 汇总每 10m 区段内的地质风险
- 形成地质风险评分 GRS
- 给前方风险提示和 LLM 报告提供证据

核心代码：

- `backend/parsers/tsp_parser.py`
- `backend/parsers/hsp_parser.py`
- `backend/parsers/sketch_parser.py`
- `backend/scripts/build_evidence_db.py`
- `backend/services/evidence_import_service.py`
- `backend/geology/geology_fusion_backend.py`

当前融合规则的重要点：

- `segment` 级证据参与区间融合。
- `point` 级证据也会参与融合，用于处理素描、局部掉块、局部出水等点状事实。
- `overview` 级概述信息不直接进入逐里程风险融合，避免把整份报告的泛化描述扩散到所有里程。
- 融合采用里程容差，默认 `TOLERANCE_M = 3.0`。
- 前方高风险提示默认关注掌子面前方 `HIGH_RISK_LOOKAHEAD_M = 10.0` 和 `NEXT_FORECAST_LOOKAHEAD_M = 5.0` 等配置。

### 1.5 GRS 地质风险评分

GRS 是 Geology Risk Score，表示区段级地质风险强度，范围为 0 到 1。

当前基础模型为工程先验加权模型：

```text
GRS_base =
    0.30 * grade_score
  + 0.25 * hazard_score
  + 0.20 * water_score
  + 0.15 * collapse_score
  + 0.10 * source_confidence
```

组件含义：

- `grade_score`：围岩等级风险，I 到 V 级逐步升高。
- `hazard_score`：破碎、裂隙、断层、弱风化、岩溶等关键词或结构风险。
- `water_score`：出水、涌水、突水、富水、渗水等风险。
- `collapse_score`：掉块、塌方、坍塌、冒落等风险。
- `source_confidence`：多源证据和证据置信度。

随后会进行动态修正：

```text
correction = 0.5 * RAI + 0.5 * stop_ratio
GRS_corrected = GRS_base * (1 + lambda * correction)
lambda = 0.40
```

再经过空间平滑、最小值下限和 0 到 1 裁剪，得到最终：

```text
GRS_final
GRS
geo_risk_score
geo_risk_norm
```

核心代码：

- `backend/analysis/geo_risk_model.py`
- `backend/analysis/geology_response_coupling.py`

### 1.6 RAI 施工响应异常指数

RAI 是 Response Anomaly Index。项目当前把它定义为“施工行为异常指数”，不是单纯的设备参数异常指数。

当前实现公式：

```text
RAI =
    0.50 * stop_anomaly
  + 0.30 * efficiency_anomaly
  + 0.20 * param_anomaly
```

全部结果会裁剪到 0 到 1。

三个子项来源：

| 子项 | 优先字段 | fallback |
| --- | --- | --- |
| `stop_anomaly` | `stop_ratio`, `stop_duration_ratio`, `stop_time_ratio`, `stop_total_ratio`, `stoppage_ratio` | `1 - working_ratio` / `1 - work_ratio` / `stop_state_ratio` / `speed_zero_ratio` / 缺失则 0 并 warning |
| `efficiency_anomaly` | `1 - working_ratio`, `1 - work_ratio`, `1 - effective_digging_ratio` 等 | `stop_anomaly` / `1 - efficiency` / `speed_drop_score` / 相对速度下降 / 缺失则 0 并 warning |
| `param_anomaly` | 推进速度、推力、刀盘扭矩、转速、贯入度、CV、波动率等 Robust Z-score 结果 | 没有可用参数时为 0 并 warning |

`param_anomaly` 内部组合：

```text
param_anomaly =
    0.60 * top_mean
  + 0.25 * mean_all
  + 0.15 * response_consistency
```

其中：

- `top_mean`：参数异常评分中最高若干项均值。
- `mean_all`：所有参数异常评分均值。
- `response_consistency`：多个参数组同时异常的比例。

异常类型识别：

| 条件 | `anomaly_type` |
| --- | --- |
| `stop_anomaly` 最高且 `>= 0.50` | 停机主导型 |
| `efficiency_anomaly` 最高且 `>= 0.40` | 效率下降型 |
| 推力/扭矩等负载异常最高且 `>= 0.35` | 高负载型 |
| CV/波动类异常最高且 `>= 0.35` | 波动型 |
| 速度下降最高且 `>= 0.35` | 速度下降型 |
| 最高分 `>= 0.35` 但不属于以上 | 综合异常型 |
| 其他 | 轻微异常型 |

保留和输出字段：

```text
RAI
response_anomaly_index
stop_anomaly
efficiency_anomaly
param_anomaly
anomaly_type
anomaly_type_score
```

核心代码：

- `backend/analysis/geology_response_coupling.py`

### 1.7 GRCI 地质-施工响应耦合指数

GRCI 是 Geology Response Coupling Index，范围为 0 到 1，用于判断“地质风险”和“施工响应异常”是否同步、滞后或变化耦合。

当前实现包括：

```text
sync_coupling =
    0.50 * min(GRS, RAI)
  + 0.30 * sqrt(GRS * RAI)
  + 0.20 * balance * mean(GRS, RAI)

lag_coupling =
    max(
      min(previous_GRS, RAI),
      min(GRS, response_rise * 1.5),
      min(risk_entry * 1.5, RAI)
    )

response_change_coupling =
    max(
      min(GRS, response_rise * 1.8),
      sqrt(risk_entry * response_rise),
      min(abs(delta_GRS) * 1.2, RAI)
    )

GRCI =
    (
      0.40 * sync_coupling
    + 0.25 * lag_coupling
    + 0.25 * response_change_coupling
    + 0.10 * multi_param_response
    ) * confidence
```

输出字段包括：

```text
GRCI
coupling_index
risk_response_coupling_index
sync_coupling
lag_coupling
lag_response
response_change_coupling
delta_RAI
delta_GRS
grci_class_code
grci_class_label
coupling_class
coupling_type
coupling_interpretation
```

典型分类：

- A 类：地质响应耦合型高风险
- B 类：地质预警型潜在风险
- C 类：施工响应主导型异常
- D 类：低耦合或低关注

### 1.8 前方风险提示

系统会基于当前掌子面里程和地质证据库，提取前方一定距离内的风险证据，生成：

- 是否存在前方风险
- 前方风险证据数量
- 高风险段数量
- 多源证据段数量
- 主要风险类型
- 供 LLM 报告使用的结构化摘要和文字描述

核心代码：

- `backend/analysis/forward_risk_advisor.py`

### 1.9 数字孪生状态

数字孪生状态是一个结构化对象，用于把当天 TBM 的关键状态压缩成“当前态”：

- `position_state`：当前里程、起止里程、推进长度
- `operation_state`：停机、掘进、过渡、异常等运行状态
- `geology_state`：是否有地质证据、高风险段数量、多源证据段数量
- `forward_risk_state`：前方风险提示
- `coupling_state`：耦合强度、主导风险等级
- `safety_state`：气体超限情况

核心代码：

- `backend/services/digital_twin_state.py`

### 1.10 历史记忆

历史记忆用于让 LLM 日报能写出“与上一记录相比”的内容。

存储目录：

```text
DATA_ROOT/analysis_history/
```

每个日期一个 JSON：

```text
2023-12-28.json
2023-12-30.json
```

历史记录包含：

- 日期和生成时间
- 当前里程、起止里程、推进长度
- 总时长、有效掘进时长、停机时长
- 有效掘进占比、停机占比
- 掘进段数、停机段数、异常段数
- 状态切换次数
- 高风险地质段数量、多源证据段数量
- 前方风险数量和主要风险类型
- GRCI 均值、最大值、最高关注区段
- 气体超限类型

重要运行逻辑：

- `POST /api/tbm/report` 会分析当天数据、读取历史、生成历史对比、保存当前日期记录。
- `GET /api/tbm/history_memory` 会构造当前记录并返回对比结果，但不保存当前记录。
- `load_history_records(limit=10, before_date=date)` 只读取早于当前日期的历史 JSON。
- 对比时默认使用读取到的最后一条历史记录作为上一记录。

核心代码：

- `backend/services/history_memory_service.py`
- `backend/routes/tbm.py`

### 1.11 LLM 报告与 Agent

系统支持两类报告：

- 日报：`POST /api/tbm/report`
- 时间窗报告：`POST /api/tbm/report_by_time`

LLM 默认 provider：

```text
LLM_PROVIDER=deepseek
DEEPSEEK_MODEL=deepseek-chat
```

也支持：

```text
LLM_PROVIDER=google
GOOGLE_MODEL=gemini-2.5-flash-lite
```

配置文件参考：

```text
.env.example
```

Agent 分两版：

- `TBMAgent`：较简单的意图分流和工具调用。
- `TBMSupervisorAgent`：V2 Supervisor，按问题类型调度不同分析工具，支持更详细的 `verbose` 输出。

文档：

- `docs/agent_v2.md`

## 2. 项目结构

```text
LLM_20260424/
├── backend/
│   ├── app.py
│   ├── config.py
│   ├── routes/
│   │   └── tbm.py
│   ├── schemas/
│   │   ├── api.py
│   │   └── schemas.py
│   ├── services/
│   │   ├── tbm_analysis_service.py
│   │   ├── history_memory_service.py
│   │   ├── digital_twin_state.py
│   │   └── evidence_import_service.py
│   ├── analysis/
│   │   ├── dataprocess.py
│   │   ├── excavation_state.py
│   │   ├── gas_analysis.py
│   │   ├── geo_risk_model.py
│   │   ├── geology_response_coupling.py
│   │   ├── forward_risk_advisor.py
│   │   └── coupling_analysis.py
│   ├── geology/
│   │   ├── geology_fusion_backend.py
│   │   ├── geology_summary.py
│   │   ├── segment_analysis.py
│   │   └── fusion.py
│   ├── parsers/
│   │   ├── tsp_parser.py
│   │   ├── hsp_parser.py
│   │   ├── sketch_parser.py
│   │   └── drill_parser.py
│   ├── llm/
│   │   ├── llm_api.py
│   │   ├── prompt_builder.py
│   │   └── prompt_builder_timewindow.py
│   ├── agent/
│   │   ├── tbm_agent.py
│   │   ├── supervisor_agent.py
│   │   ├── tbm_tools.py
│   │   └── registry.py
│   ├── scripts/
│   │   ├── build_evidence_db.py
│   │   ├── import_evidence_reports.py
│   │   ├── inspect_coupling_analysis.py
│   │   └── test_agent_v2.py
│   └── requirements.txt
├── Frontend/
│   ├── src/
│   │   ├── api/
│   │   ├── components/
│   │   ├── features/
│   │   │   ├── dashboard/
│   │   │   ├── summary/
│   │   │   ├── state/
│   │   │   ├── geology/
│   │   │   ├── gas/
│   │   │   ├── risk/
│   │   │   ├── report/
│   │   │   ├── agent/
│   │   │   ├── settings/
│   │   │   └── evidence/
│   │   └── utils/
│   ├── package.json
│   └── README.md
├── docs/
│   ├── agent_v2.md
│   └── evidence_import.md
├── .env.example
└── README.md
```

## 3. 数据目录和配置

数据根目录由 `backend/config.py` 自动识别。

Windows 优先尝试：

```text
G:/我的云端硬盘/TBM9
G:/My Drive/TBM9
```

macOS 优先尝试：

```text
~/Library/CloudStorage/GoogleDrive*/我的云端硬盘/TBM9
~/Library/CloudStorage/GoogleDrive*/My Drive/TBM9
```

如果都找不到，则 fallback 到：

```text
backend/data
```

主要目录：

| 配置名 | 默认含义 |
| --- | --- |
| `DATA_ROOT` | TBM9 根目录 |
| `DATA_DIR` | 每日 TBM CSV，默认 `TBM9_2023` |
| `TSP_DIR` | TSP PDF 超前地质预报 |
| `HSP_DIR` | HSP / sonic PDF 超前地质预报 |
| `SKETCH_DIR` | 洞身素描 PDF |
| `DB_DIR` | 地质证据库目录 |
| `EVIDENCE_DB_PATH` | `DB/evidence_db.csv` |
| `RESULT_DIR` | 分析输出目录 |
| `HISTORY_MEMORY_DIR` | 历史分析记忆 JSON 目录 |

### 3.1 TBM CSV 命名

日期接口默认按以下文件名查找：

```text
tbm_data_YYYYMMDD.csv
```

例如：

```text
tbm_data_20231230.csv
```

`GET /api/tbm/dates` 会扫描 `DATA_DIR` 下所有符合命名的 CSV，并返回可选日期。

### 3.2 TBM CSV 关键字段

必须字段：

| 字段 | 类型 | 用途 |
| --- | --- | --- |
| `运行时间-time` | datetime 字符串 | 时间排序、工况分段、时间窗过滤 |

常用施工字段：

| 字段 | 类型 | 用途 |
| --- | --- | --- |
| `掘进状态` | 数值 | 优先用于判断停机/掘进 |
| `推进速度` | 数值 | 工况判断、RAI、效率、速度剖面 |
| `推力` | 数值 | 工况判断、状态聚类、负载异常 |
| `刀盘扭矩` | 数值 | 工况判断、状态聚类、负载异常 |
| `刀盘实际转速` | 数值 | 状态聚类、转速异常 |
| `推进给定速度` | 数值 | 状态效率统计 |
| `贯入度` | 数值 | 掘进/停机 fallback、参数异常 |

常用里程字段：

| 字段 | 类型 | 用途 |
| --- | --- | --- |
| `chainage` | 数值 | 标准化后的里程 |
| `导向盾首里程` | 数值或 DK 字符串 | 可用于里程转换 |
| `开累进尺` | 数值 | 可用于里程推算 |

气体字段：

```text
CO2检测
H2S检测
SO2检测
NO2检测
NO检测
CH4检测
```

字段缺失原则：

- 必须字段缺失时直接报错，例如缺少 `运行时间-time`。
- 可选字段缺失时对应分析会降级，不让整体接口崩掉。
- 地质、气体、状态识别、耦合分析各自有 try/except 隔离。

### 3.3 地质证据库字段

`EvidenceRecord` 统一结构位于 `backend/schemas/schemas.py`：

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `evidence_id` | str | 唯一证据 ID，用于去重 |
| `source_type` | str | `tsp` / `sonic` / `sketch` 等 |
| `source_level` | str | `segment` / `point` / `overview` |
| `report_id` | str | 报告 ID |
| `report_date` | str/null | 报告日期 |
| `issue_date` | str/null | 发布日期 |
| `tunnel_name` | str/null | 隧道或线路名称 |
| `start_num` | float | 起始里程，数值米 |
| `end_num` | float | 结束里程，数值米 |
| `face_num` | float/null | 掌子面里程 |
| `next_forecast_num` | float/null | 下次预报里程 |
| `confidence` | str | 证据置信度 |
| `attrs_json` | str | 结构化属性 JSON |
| `raw_text` | str/null | 原始文本片段 |

`attrs_json` 可能包含：

- 围岩等级
- 出水标记
- 掉块标记
- 破碎、裂隙、断层、岩溶等关键词
- HSP/TSP 异常类型
- 素描中的观测事实
- 解析器保留的其他结构化字段

## 4. 后端 API

所有 TBM 接口都挂在：

```text
/api/tbm
```

| 方法 | 路径 | 功能 |
| --- | --- | --- |
| GET | `/dates` | 返回可用 CSV 日期 |
| GET | `/summary?date=YYYY-MM-DD` | 基础工况统计摘要 |
| GET | `/state?date=YYYY-MM-DD` | 施工状态分段、状态效率、状态统计 |
| GET | `/gas?date=YYYY-MM-DD` | 气体统计和超阈值事件 |
| GET | `/geology?date=YYYY-MM-DD` | 地质融合、GRS/RAI/GRCI、典型区段 |
| GET | `/digital_twin_state?date=YYYY-MM-DD` | 数字孪生当前状态 |
| GET | `/risk_profile?date=YYYY-MM-DD` | 风险剖面和速度剖面 |
| GET | `/history_memory?date=YYYY-MM-DD&limit=10` | 历史记忆对比，不保存记录 |
| POST | `/report` | 生成日报，读取历史并保存当前历史记录 |
| POST | `/report_by_time` | 生成指定时间窗报告 |
| POST | `/agent` | V1 Agent 问答 |
| POST | `/agent_v2` | Supervisor Agent 问答 |
| GET | `/agent/capabilities` | V1 Agent 能力说明 |
| GET | `/agent_v2/capabilities` | V2 Agent 能力说明 |
| POST | `/evidence/import` | 增量导入新的 TSP/HSP/素描 PDF |

### 4.1 请求体

日报：

```json
{
  "date": "2023-12-30"
}
```

时间窗报告：

```json
{
  "start_time": "2023-12-30T08:00:00",
  "end_time": "2023-12-30T10:00:00"
}
```

Agent：

```json
{
  "query": "分析 2023-12-30 的地质风险和施工响应",
  "date": "2023-12-30",
  "use_llm": false,
  "verbose": true
}
```

增量导入超报：

```json
{
  "paths": [
    "G:/我的云端硬盘/TBM9/SKETCH/example.pdf"
  ],
  "source_type": "sketch",
  "dry_run": true,
  "replace_existing": false,
  "recursive": false
}
```

## 5. 地质证据库生成与增量导入

### 5.1 首次全量生成

当你第一次建立地质证据库，或希望全量重建时运行：

```powershell
cd backend
python scripts/build_evidence_db.py
```

它会扫描：

```text
TSP_DIR
HSP_DIR
SKETCH_DIR
```

然后生成：

```text
DATA_ROOT/DB/evidence_db.csv
```

### 5.2 后续新增超报的增量导入

如果后面来了新的超前地质预报，不需要每次重新生成整张表。可以只把新 PDF 增量导入。

命令行方式：

```powershell
cd backend
python scripts/import_evidence_reports.py "G:/我的云端硬盘/TBM9/SKETCH/new_report.pdf" --source-type sketch --dry-run
python scripts/import_evidence_reports.py "G:/我的云端硬盘/TBM9/SKETCH/new_report.pdf" --source-type sketch
```

目录导入：

```powershell
cd backend
python scripts/import_evidence_reports.py "G:/我的云端硬盘/TBM9/SKETCH/new_folder" --source-type sketch --recursive
```

API 方式：

```http
POST /api/tbm/evidence/import
```

重要参数：

| 参数 | 含义 |
| --- | --- |
| `paths` | PDF 文件或目录列表 |
| `source_type` | `tsp` / `hsp` / `sonic` / `sketch`，为空时按路径和文件名推断 |
| `dry_run` | 只解析和检查，不写入 |
| `replace_existing` | 已有 `evidence_id` 时是否替换 |
| `recursive` | 目录导入时是否递归扫描 |

写入保护：

- 默认跳过已存在的 `evidence_id`。
- `replace_existing=true` 时会替换同 ID 旧记录。
- 真正写入前会自动备份旧的 `evidence_db.csv`。
- 增量导入也会做里程合法性、重复 ID、超长区段过滤。

更详细说明见：

- `docs/evidence_import.md`

## 6. 前端结构

前端使用 React + Vite。

主要模块：

| 目录 | 功能 |
| --- | --- |
| `src/features/dashboard` | 总览看板、日期选择、模块入口 |
| `src/features/summary` | 基础工况统计 |
| `src/features/state` | 施工状态识别与岩性带展示 |
| `src/features/geology` | 地质融合、区段表、耦合分析 |
| `src/features/gas` | 气体监测统计 |
| `src/features/risk` | 风险剖面、速度剖面 |
| `src/features/report` | 日报和时间窗报告生成 |
| `src/features/agent` | Agent 问答 |
| `src/features/evidence` | 地质证据库控制台，支持新增超报导入 |
| `src/features/settings` | 设置页 |

接口封装：

```text
Frontend/src/api/client.js
Frontend/src/api/tbm.js
```

## 7. 启动方式

### 7.1 后端

```powershell
cd backend
pip install -r requirements.txt
uvicorn app:app --reload --port 8000
```

默认后端地址：

```text
http://127.0.0.1:8000
```

FastAPI 文档：

```text
http://127.0.0.1:8000/docs
```

### 7.2 前端

```powershell
cd Frontend
npm install
npm.cmd run dev
```

默认前端地址：

```text
http://127.0.0.1:5173
```

如果 PowerShell 禁止运行 `npm.ps1`，Windows 下使用 `npm.cmd`。

### 7.3 前端 API 地址

可在 `Frontend/.env` 中设置：

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
```

## 8. LLM 配置

复制 `.env.example` 为 `.env`：

```powershell
copy .env.example .env
```

默认 DeepSeek：

```env
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=your_deepseek_api_key_here
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_BASE_URL=https://api.deepseek.com
```

切换 Gemini：

```env
LLM_PROVIDER=google
GOOGLE_API_KEY=your_google_api_key_here
GOOGLE_MODEL=gemini-2.5-flash-lite
```

如果没有配置 API Key，普通数据接口仍能运行；只有报告生成或 LLM 问答会返回配置错误提示。

## 9. 常用调试命令

检查耦合分析：

```powershell
cd backend
python scripts/inspect_coupling_analysis.py --date 2023-12-30 --limit 5 --json
```

测试 Agent V2：

```powershell
cd backend
python scripts/test_agent_v2.py
```

前端构建：

```powershell
cd Frontend
npm.cmd run build
```

前端单页 lint 示例：

```powershell
cd Frontend
npx.cmd eslint src/features/evidence/EvidenceImportPage.jsx
```

## 10. 当前实现注意事项

1. 地质风险是“多源信息综合关注程度”，不等同于现场灾害已经发生。
2. TSP/HSP/素描 PDF 解析依赖当前固定模板；模板变化时需要同步更新 parser。
3. 增量导入不会自动刷新已经存在的旧记录，除非使用 `replace_existing=true`。
4. 如果 parser 逻辑调整过，旧的 `evidence_db.csv` 中已有记录不会自动重算；需要全量重建或按文件替换导入。
5. 气体阈值目前按浓度处理，字段单位必须和现场数据确认。
6. 历史记忆只有生成过日报或手动保存过 JSON 的日期才存在，不是自动拥有所有 CSV 日期。
7. 前端全量 `npm run lint` 当前可能会暴露历史遗留的 Hook/Node 全局变量问题；新证据导入页已单独通过 lint 检查。

## 11. 推荐工作流

日常分析：

```text
1. 放入当天 TBM CSV
2. 确认 /api/tbm/dates 能看到日期
3. 前端选择日期查看 summary/state/gas/geology/risk
4. 需要日报时调用 /api/tbm/report
5. 日报生成后自动写入 analysis_history
```

来了新超报：

```text
1. 把 PDF 放入 TSP/HSP/SKETCH 目录
2. 使用前端“地质证据库控制台”或 /api/tbm/evidence/import 做 dry_run
3. 确认解析记录数、重复记录数和错误列表
4. 正式导入
5. 重新查看 geology 或运行 inspect_coupling_analysis.py
```

需要重新建库：

```text
1. 备份旧 DB/evidence_db.csv
2. 运行 backend/scripts/build_evidence_db.py
3. 抽查 evidence_db.csv 字段和记录数
4. 运行指定日期的 coupling inspection
```

## 12. 关键文件速查

| 目标 | 文件 |
| --- | --- |
| FastAPI 入口 | `backend/app.py` |
| API 路由 | `backend/routes/tbm.py` |
| 总分析流程 | `backend/services/tbm_analysis_service.py` |
| 工况分段 | `backend/analysis/dataprocess.py` |
| 施工状态识别 | `backend/analysis/excavation_state.py` |
| 气体分析 | `backend/analysis/gas_analysis.py` |
| 地质融合 | `backend/geology/geology_fusion_backend.py` |
| 地质证据 schema | `backend/schemas/schemas.py` |
| GRS 模型 | `backend/analysis/geo_risk_model.py` |
| RAI/GRCI 模型 | `backend/analysis/geology_response_coupling.py` |
| 历史记忆 | `backend/services/history_memory_service.py` |
| 增量导入服务 | `backend/services/evidence_import_service.py` |
| 增量导入 CLI | `backend/scripts/import_evidence_reports.py` |
| 全量建库 CLI | `backend/scripts/build_evidence_db.py` |
| LLM 调用 | `backend/llm/llm_api.py` |
| LLM 日报 Prompt | `backend/llm/prompt_builder.py` |
| 前端接口封装 | `Frontend/src/api/tbm.js` |
| 前端总览页 | `Frontend/src/features/dashboard/Dashboard.jsx` |
| 前端证据导入页 | `Frontend/src/features/evidence/EvidenceImportPage.jsx` |
