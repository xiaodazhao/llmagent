# 面向TBM施工报告自动化生成的数字孪生与大语言模型协同方法研究

这是一个面向 TBM 隧道施工场景的研究型全栈系统。项目目标不是让大语言模型直接读取原始 `CSV + PDF`，而是先把 TBM 施工数据、超前地质预报和掌子面素描组织成一个轻量化数字孪生状态，再由大语言模型生成日报、时段报告和问答解释。

## 文档导航

- [项目总说明](docs/research_overview.md)
- [后端清单](docs/backend_inventory.md)
- [Agent 设计说明](docs/agent_v2.md)
- [证据导入说明](docs/evidence_import.md)

## 当前主线

1. 读取 TBM 日运行 `CSV`
2. 解析 `TSP / HSP / 掌子面素描 PDF`
3. 按统一里程轴做地质-施工融合
4. 计算区段级 `GRS / RAI / GRCI`
5. 构建轻量化数字孪生状态
6. 生成日报、时段报告和 Agent 问答结果

## 当前算法版本

- `GRS`：分量归一化后平权聚合，不再使用主观工程权重
- `RAI`：基于 `Isolation Forest` 的多参数施工响应异常表征
- `GRCI`：保留同步、滞后、变化和一致性的耦合验证逻辑
- 地质侧新增高斯衰减平滑，减弱固定 `10m` 分段的边界切割效应
- 施工侧新增常规环级停顿候选折减，降低正常停顿对 `RAI` 的误报

## 主要能力

- 工况分段、施工状态识别、效率分析、气体统计
- 多源地质证据解析、导入、去重、SQLite 落库
- 区段地质关注、施工响应异常、耦合验证与前方提示
- 轻量化数字孪生状态摘要
- LLM 日报、时段报告、会话式 Supervisor Agent 问答

## 技术栈

- 前端：React、Vite、Recharts、Axios
- 后端：FastAPI、Pydantic、Pandas、scikit-learn
- 数据：CSV、PDF、SQLite
- 测试：pytest

## 快速启动

### 1. 配置环境变量

```powershell
copy .env.example .env
```

### 2. 启动后端

```powershell
cd backend
pip install -r requirements.txt
uvicorn app:app --reload --port 8000
```

后端地址：

```text
http://127.0.0.1:8000
http://127.0.0.1:8000/docs
```

### 3. 启动前端

```powershell
cd Frontend
npm install
npm.cmd run dev
```

前端地址：

```text
http://127.0.0.1:5173
```

## 常用接口

- `GET /api/tbm/dates`
- `GET /api/tbm/summary`
- `GET /api/tbm/state`
- `GET /api/tbm/gas`
- `GET /api/tbm/geology`
- `GET /api/tbm/risk_profile`
- `GET /api/tbm/digital_twin_state`
- `GET /api/tbm/history_memory`
- `POST /api/tbm/report`
- `POST /api/tbm/report_by_time`
- `POST /api/tbm/agent_v2`
- `GET /api/tbm/agent_v2/session`
- `POST /api/tbm/evidence/import`

## 验证

后端测试：

```powershell
cd backend
python -m pytest tests
```

前端构建：

```powershell
cd Frontend
npm.cmd run build
```
