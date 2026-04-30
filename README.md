# TBM 智能监控与日报分析系统

这是一个面向 TBM 隧道掘进数据的前后端分离项目。系统读取每日 TBM/PLC 数据，结合 TSP、HSP、素描等地质资料形成的证据库，完成工况识别、施工状态分析、气体监测、地质风险融合、空间风险剖面展示，并支持调用大模型生成工程日报。

项目当前更接近科研/原型系统：功能链路已经比较完整，但部分文件和中文编码仍有整理空间。

## 项目结构

```text
.
├── Frontend/                 # React + Vite 前端驾驶舱
│   ├── src/
│   │   ├── api/              # 后端接口封装
│   │   ├── features/         # 各业务页面：概览、地质、气体、报告等
│   │   ├── components/       # 通用组件与布局组件
│   │   └── utils/            # 前端工具函数
│   └── package.json
│
├── backend/                  # FastAPI 后端分析服务
│   ├── app.py                # API 入口与主分析流程
│   ├── config.py             # 数据路径配置
│   ├── analysis/             # 工况、气体、施工状态、前方风险分析
│   ├── geology/              # 地质证据融合与区段分析
│   ├── llm/                  # Prompt 构建与 Gemini 调用
│   ├── parsers/              # TSP/HSP/SKETCH 等 PDF 解析
│   ├── routes/               # FastAPI 路由
│   ├── scripts/              # 证据库构建脚本
│   ├── schemas/              # 结构化证据数据模型
│   ├── services/             # TBM 分析编排服务
│   ├── utils/                # 数据读取、时间窗口、JSON 序列化等工具函数
│   └── requirements.txt
│
└── .gitignore
```

## 主要功能

- **工况概览**：识别停机、过渡、稳定掘进、异常扭矩等工况段，并统计时长和次数。
- **施工状态分析**：基于推力、刀盘扭矩、刀盘转速、推进速度等字段进行聚类，生成施工状态标签。
- **气体监测**：统计 CO2、H2S、SO2、NO2、NO、CH4 等气体指标，并识别超阈值事件。
- **地质融合分析**：将 TBM 里程与地质证据库按里程匹配，融合风险、围岩等级、出水、掉块、变形等信息。
- **空间风险剖面**：按里程展示风险强度、关注区段和推进速度变化。
- **智能日报**：将结构化分析结果拼接成 Prompt，调用 Gemini 生成工程日报。
- **时间窗口分析**：支持选择某一时间段生成局部分析报告。

## 数据要求

后端默认从 `backend/config.py` 中配置的数据目录读取数据。

默认数据根目录优先级：

```text
G:/某个 Google Drive 目录/TBM9
G:/My Drive/TBM9
backend/data
```

关键数据路径：

```text
DATA_DIR            TBM 每日 CSV 数据目录，默认 DATA_ROOT/TBM9_2023
EVIDENCE_DB_PATH    地质证据库，默认 DATA_ROOT/DB/evidence_db.csv
TSP_DIR             TSP PDF 目录
HSP_DIR             HSP PDF 目录
SKETCH_DIR          素描 PDF 目录
```

每日 TBM 数据文件名需要类似：

```text
tbm_data_20230424.csv
```

后端会根据日期请求自动寻找对应文件。

## 环境变量

如果需要生成 AI 日报，需要在后端运行环境中配置：

```env
GOOGLE_API_KEY=你的 Gemini API Key
```

项目提供了 `.env.example` 作为模板。可以参考它创建本地 `.env` 文件：

```powershell
copy .env.example .env
```

如果缺少该变量，后端仍可启动，概览、气体、地质等非 LLM 功能仍可使用；生成 AI 日报时会返回明确的配置提示。

## 启动方式

### 1. 启动后端

```powershell
cd backend
pip install -r requirements.txt
uvicorn app:app --reload --port 8000
```

后端默认地址：

```text
http://127.0.0.1:8000
```

### 2. 启动前端

另开一个终端：

```powershell
cd Frontend
npm install
npm run dev
```

前端会请求：

```text
http://127.0.0.1:8000
```

该地址配置在：

```text
Frontend/src/api/client.js
```

## 主要后端接口

| 接口 | 方法 | 作用 |
| --- | --- | --- |
| `/api/tbm/dates` | GET | 获取可用数据日期 |
| `/api/tbm/summary?date=YYYY-MM-DD` | GET | 获取工况与地质概览 |
| `/api/tbm/state?date=YYYY-MM-DD` | GET | 获取施工状态分析 |
| `/api/tbm/gas?date=YYYY-MM-DD` | GET | 获取气体统计 |
| `/api/tbm/geology?date=YYYY-MM-DD` | GET | 获取地质融合分析 |
| `/api/tbm/risk_profile?date=YYYY-MM-DD` | GET | 获取空间风险剖面 |
| `/api/tbm/report` | POST | 生成单日智能日报 |
| `/api/tbm/report_by_time` | POST | 生成时间窗口报告 |

## 核心分析流程

后端主入口在 `backend/app.py`，其中最核心的函数是：

```python
analyze_tbm_data(df)
```

大致流程如下：

```text
每日 CSV 数据
    ↓
读取并清洗时间列
    ↓
挂接地质证据库 evidence_db.csv
    ↓
工况识别：停机 / 过渡 / 稳定掘进 / 异常
    ↓
施工状态聚类：高负载、受阻、低负载等
    ↓
气体监测统计
    ↓
里程区段地质风险融合
    ↓
前方 30m 风险提示
    ↓
生成结构化结果或交给 LLM 生成日报
```

## 证据库构建

如果需要从 PDF 重新生成 `evidence_db.csv`，可以运行：

```powershell
cd backend
python scripts/build_evidence_db.py
```

该脚本会读取：

```text
TSP_DIR
HSP_DIR
SKETCH_DIR
```

并输出：

```text
DB/evidence_db.csv
```

## 当前需要注意的问题

- 部分中文注释或字符串存在乱码，可能来自历史编码问题，需要后续统一为 UTF-8。
- `backend/app.py` 已精简为 FastAPI 启动入口；核心分析编排位于 `backend/services/tbm_analysis_service.py`。
- 前端目前主要是单页驾驶舱，后续如果页面继续变多，可以再引入正式路由结构。

## 建议的整理顺序

1. 先保证 README、数据路径和启动命令清楚。
2. 统一源码编码，修复乱码文案。
3. 再优化前端布局、样式和组件复用。
