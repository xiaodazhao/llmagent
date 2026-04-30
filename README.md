# TBM 数字孪生与 LLM 施工报告生成系统

本项目面向 TBM 施工过程数据，融合 PLC 运行参数、施工状态识别、气体监测、地质多源信息、前方风险提示、数字孪生状态模型和大语言模型，自动生成 TBM 综合施工工况分析报告。

当前研究题目可表述为：

```text
数字孪生与大语言模型协同驱动的 TBM 施工报告自动化生成
```

## 核心能力

- **基础工况识别**：识别停机、启动/过渡、稳定掘进、异常扭矩等施工片段。
- **隐含施工状态识别**：基于推力、刀盘扭矩、刀盘转速、推进速度等参数聚类，识别高负载稳定推进、低负载调整等状态。
- **施工效率与稳定性分析**：统计有效掘进时长、停机占比、状态切换次数、连续掘进能力等指标。
- **地质多源融合分析**：融合 TSP、HSP、地质素描等证据信息，形成区段级地质关注结果。
- **前方风险提示**：基于当前里程向前检索风险证据，形成前方 30 m 范围内的辅助风险提示。
- **数字孪生状态模型**：将时间、位置、运行、地质、安全、前方风险、耦合状态组织为结构化状态。
- **地质风险-施工响应耦合指数**：计算区段地质风险与施工响应之间的耦合程度，用于提示哪些区段更值得关注。
- **施工历史记忆库**：保存历次日报分析摘要，并在后续报告中自动生成历史对比。
- **LLM 报告生成**：支持 Gemini 和 DeepSeek，将结构化分析结果转写为施工报告。

## 项目结构

```text
.
├── Frontend/                         # React + Vite 前端
│   ├── src/api/                      # 后端接口封装
│   ├── src/features/                 # 页面功能模块
│   ├── src/components/               # 通用组件
│   └── package.json
├── backend/                          # FastAPI 后端
│   ├── app.py                        # FastAPI 应用入口
│   ├── config.py                     # 数据目录与全局配置
│   ├── analysis/                     # 工况、状态、气体、耦合等分析
│   │   ├── coupling_analysis.py      # 地质风险-施工响应耦合指数
│   │   └── forward_risk_advisor.py   # 前方风险提示
│   ├── geology/                      # 地质融合与区段分析
│   ├── llm/                          # LLM 调用与 prompt 构建
│   ├── parsers/                      # TSP/HSP/SKETCH 资料解析
│   ├── routes/                       # API 路由
│   ├── schemas/                      # 请求模型
│   ├── services/                     # 业务编排服务
│   │   ├── tbm_analysis_service.py   # 核心分析流程
│   │   ├── digital_twin_state.py     # 数字孪生状态模型
│   │   └── history_memory_service.py # 施工历史记忆库
│   └── utils/                        # 序列化、里程格式、数据读取等工具
├── .env.example
└── README.md
```

## 数据与配置

后端会在 `backend/config.py` 中自动寻找 TBM 数据根目录：

```text
G:/我的云端硬盘/TBM9
G:/My Drive/TBM9
backend/data
```

主要目录：

```text
DATA_DIR              TBM 日 CSV 数据目录，默认 DATA_ROOT/TBM9_2023
EVIDENCE_DB_PATH      多源地质证据库，默认 DATA_ROOT/DB/evidence_db.csv
TSP_DIR               TSP PDF 目录
HSP_DIR               HSP PDF 目录
SKETCH_DIR            地质素描 PDF 目录
HISTORY_MEMORY_DIR    施工历史记忆库，默认 DATA_ROOT/analysis_history
```

TBM 日数据文件命名示例：

```text
tbm_data_20231230.csv
```

## LLM 配置

复制 `.env.example` 后填写 API Key：

```powershell
copy .env.example .env
```

使用 Gemini：

```env
LLM_PROVIDER=google
GOOGLE_API_KEY=your_google_api_key_here
GOOGLE_MODEL=gemini-2.5-flash-lite
```

使用 DeepSeek：

```env
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=your_deepseek_api_key_here
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_BASE_URL=https://api.deepseek.com
```

也可以把 `.env` 放在 `backend/.env`。

## 启动方式

### 后端

```powershell
cd backend
pip install -r requirements.txt
uvicorn app:app --reload --port 8000
```

后端地址：

```text
http://127.0.0.1:8000
```

### 前端

```powershell
cd Frontend
npm install
npm run dev
```

前端默认地址通常为：

```text
http://127.0.0.1:5173
```

如需指定后端地址，可在 `Frontend/.env` 中配置：

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
```

## 主要 API

| 接口 | 方法 | 说明 |
| --- | --- | --- |
| `/api/tbm/dates` | GET | 获取可用日期 |
| `/api/tbm/summary?date=YYYY-MM-DD` | GET | 获取基础工况统计 |
| `/api/tbm/state?date=YYYY-MM-DD` | GET | 获取隐含施工状态识别结果 |
| `/api/tbm/gas?date=YYYY-MM-DD` | GET | 获取气体监测分析 |
| `/api/tbm/geology?date=YYYY-MM-DD` | GET | 获取地质融合、区段耦合、数字孪生状态摘要 |
| `/api/tbm/digital_twin_state?date=YYYY-MM-DD` | GET | 获取数字孪生状态模型与耦合摘要 |
| `/api/tbm/history_memory?date=YYYY-MM-DD` | GET | 获取本次分析历史记忆对比 |
| `/api/tbm/risk_profile?date=YYYY-MM-DD` | GET | 获取里程风险剖面与速度剖面 |
| `/api/tbm/report` | POST | 生成单日 TBM 综合施工工况分析报告 |
| `/api/tbm/report_by_time` | POST | 生成指定时间窗口报告 |

## 核心分析流程

核心入口位于：

```text
backend/services/tbm_analysis_service.py
```

整体流程：

```text
TBM 日 CSV 数据
    -> 数据清洗与工况分段
    -> 地质证据融合 evidence_db.csv
    -> 区段级地质分析
    -> 地质风险-施工响应耦合指数计算
    -> 隐含施工状态识别
    -> 状态效率与稳定性统计
    -> 气体监测分析
    -> 前方 30 m 风险提示
    -> 数字孪生状态模型构建
    -> 施工历史记忆对比
    -> LLM 生成综合施工报告
```

## 数字孪生状态模型

`backend/services/digital_twin_state.py` 将施工现场状态压缩为结构化对象，主要包含：

- `time_state`：时间范围、样本数、持续时长。
- `position_state`：起止里程、当前里程、进尺长度，并统一提供 `DKxxxx+xxx` 格式。
- `operation_state`：主导工况、停机次数、掘进次数、有效掘进占比、停机占比。
- `geology_state`：当前地质关注、区段高风险数量、多源关注数量。
- `safety_state`：气体超阈值类型。
- `forward_risk_state`：前方风险提示结果。
- `coupling_state`：区段风险-施工响应耦合状态。

## 地质风险-施工响应耦合指数

`backend/analysis/coupling_analysis.py` 计算区段级耦合指数，综合考虑：

- 地质风险强度
- 多源证据关注程度
- 推力/扭矩负载响应
- 推进速度衰减

该指标用于辅助判断“地质风险是否在施工响应中有所体现”。它是补充性、解释性指标，不等同于实时灾害预测结论。

## 施工历史记忆库

`backend/services/history_memory_service.py` 会在生成日报时保存本次分析摘要，并在下一次报告生成时读取历史记录进行对比。

默认保存位置：

```text
DATA_ROOT/analysis_history/YYYY-MM-DD.json
```

历史记忆记录包含：

- 当前里程与 DK 格式里程
- 有效掘进占比、停机占比、状态切换次数
- 前方高风险提示段数量和主要风险类型
- 平均耦合指数、最大耦合指数、主导耦合等级
- 气体超阈值类型

报告生成时，LLM 会收到类似如下对比信息：

```text
有效掘进占比较上一记录升高 5.2 个百分点。
停机占比较上一记录降低 4.8 个百分点。
前方高风险提示段数量较上一记录增加 2 个。
```

## 里程格式约定

项目统一使用 `DKxxxx+xxx` 格式。工具函数位于：

```text
backend/utils/chainage_utils.py
```

支持两类输入：

```text
1014616  -> DK1014+616
1014.616 -> DK1014+616
```

## 注意事项

- CH4 阈值和单位暂不在代码中强行修正，需等待现场确认。
- 前方风险提示、区段综合风险评估和耦合指数均属于辅助决策信息，不应写成已发生灾害。
- 低耦合不代表无风险，只代表当前地质风险与施工响应的关联程度较低。
- 后续新增业务逻辑优先放入 `services/` 或 `analysis/`，避免继续堆到 `app.py`。

## 地质证据库构建

如需从 PDF 资料重建地质证据库：

```powershell
cd backend
python scripts/build_evidence_db.py
```

输入目录来自：

```text
TSP_DIR
HSP_DIR
SKETCH_DIR
```

输出：

```text
DB/evidence_db.csv
```
