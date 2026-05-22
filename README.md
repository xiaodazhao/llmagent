# TBM 智能分析平台

这是一个面向 TBM 隧道施工场景的全栈项目。系统把 `TBM 日运行 CSV`、`TSP/HSP/洞身素描 PDF`、历史分析记录和 LLM 报告串成一条完整链路，用来做施工状态识别、地质风险融合、风险-响应耦合分析、历史对比和日报生成。

## 项目亮点

- `FastAPI + React` 的完整前后端闭环
- `TSP / HSP / 素描` 多源证据解析与里程融合
- `GRS / RAI / GRCI` 地质风险与施工响应分析
- `SQLite + 内存缓存` 的分析缓存与历史记录持久化
- `日报 / 时间窗报告 / Agent 问答` 三类分析入口
- 已接入 `pytest` 自动化测试

## 系统结构

```text
TBM CSV
  -> 工况分段
  -> 施工状态识别
  -> 气体统计
  -> 风险/速度剖面

TSP / HSP / 素描 PDF
  -> 解析为 EvidenceRecord
  -> evidence_db.csv / SQLite
  -> 按里程融合到 TBM 数据

融合分析
  -> GRS 地质风险评分
  -> RAI 施工响应异常指数
  -> GRCI 风险-响应耦合指数
  -> 前方风险提示 / 数字孪生状态 / 历史对比

输出
  -> FastAPI 接口
  -> React 看板
  -> LLM 日报 / 时间窗报告 / Agent
```

## 目录说明

```text
backend/
  app.py                     FastAPI 入口
  config.py                  环境与路径配置
  routes/tbm.py              主要 API 路由
  services/                  分析编排、缓存、历史、导入、SQLite
  analysis/                  工况、状态、气体、GRS/RAI/GRCI
  parsers/                   TSP / HSP / 素描 PDF 解析
  geology/                   地质融合与区段汇总
  tests/                     后端自动化测试

Frontend/
  src/features/              各业务页面
  src/api/                   前端接口封装
  vite.config.js             构建与拆包配置

docs/
  agent_v2.md                Agent 说明
  evidence_import.md         证据导入说明
```

## 快速开始

### 1. 后端

```powershell
cd backend
pip install -r requirements.txt
uvicorn app:app --reload --port 8000
```

默认地址：

```text
http://127.0.0.1:8000
http://127.0.0.1:8000/docs
```

### 2. 前端

```powershell
cd Frontend
npm install
npm.cmd run dev
```

默认地址：

```text
http://127.0.0.1:5173
```

### 3. 环境变量

先复制示例配置：

```powershell
copy .env.example .env
```

关键配置：

```env
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=your_key_here

DATA_ROOT=
DATA_DIR=
TSP_DIR=
HSP_DIR=
SKETCH_DIR=
APP_DB_PATH=
EVIDENCE_DB_PATH=
```

如果这些路径留空，系统会继续使用当前的自动探测逻辑。

## 核心接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/api/tbm/dates` | 可用数据日期 |
| `GET` | `/api/tbm/summary` | 工况概览 |
| `GET` | `/api/tbm/state` | 施工状态识别 |
| `GET` | `/api/tbm/gas` | 气体统计 |
| `GET` | `/api/tbm/geology` | 地质融合与耦合分析 |
| `GET` | `/api/tbm/risk_profile` | 风险/速度剖面 |
| `GET` | `/api/tbm/digital_twin_state` | 数字孪生状态 |
| `GET` | `/api/tbm/history_memory` | 历史分析对比 |
| `POST` | `/api/tbm/report` | 日报生成 |
| `POST` | `/api/tbm/report_by_time` | 时间窗报告 |
| `POST` | `/api/tbm/agent` | Agent 问答 |
| `POST` | `/api/tbm/agent_v2` | Supervisor Agent |
| `POST` | `/api/tbm/evidence/import` | 增量导入证据 PDF |

## 测试与构建

后端测试：

```powershell
cd backend
python -m pytest tests
```

前端生产构建：

```powershell
cd Frontend
npm.cmd run build
```

## 证据库工作流

首次全量建库：

```powershell
cd backend
python scripts/build_evidence_db.py
```

后续增量导入：

```powershell
cd backend
python scripts/import_evidence_reports.py "你的PDF或目录" --source-type sketch --dry-run
python scripts/import_evidence_reports.py "你的PDF或目录" --source-type sketch
```

更详细说明见 `docs/evidence_import.md`。

## 当前工程状态

已经完成：

- 统一 API 返回结构
- 分析缓存与 SQLite 落库
- `.env` 配置化路径
- 核心 GRS / 耦合分析 / 历史 / 导入 / 路由测试
- 前端懒加载与构建拆包

接下来最值得继续做的是：

- 清理少量历史乱码文案
- 给 LLM 报告链路补更多测试
- 补 Docker / 部署文档 / 健康检查
- 收紧 CORS 与导入接口安全边界
