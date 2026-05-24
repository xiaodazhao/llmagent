# 数字孪生和大语言模型协同驱动的 TBM 施工报告自动化生成

这是一个面向 TBM 隧道施工场景的研究型全栈系统。项目目标不是让大语言模型直接读取原始 `CSV + PDF`，而是先把 TBM 施工数据、超前地质预报和掌子面素描组织成一个统一、可解释、可约束的轻量化数字孪生状态，再由大语言模型生成日报、时段报告和问答解释。

## 文档导航

- [项目总说明](docs/research_overview.md)
- [最终版方法框架](docs/final_method_framework.md)
- [实验操作教程与后续实验清单](docs/experiment_tutorial.md)
- [实验设计与组织方案](docs/experiment_plan.md)
- [论文大纲建议](docs/paper_outline.md)
- [后端清单](docs/backend_inventory.md)
- [Agent 设计说明](docs/agent_v2.md)
- [证据导入说明](docs/evidence_import.md)

如果你希望快速理解项目主线，建议先阅读 [项目总说明](docs/research_overview.md)。

## 论文实验目录

仓库根目录新增了 [experiments](experiments/README.md) 目录，用于承载论文实验脚本、配置和输出目录骨架。它和业务主链分开维护，便于后续做：

- case 冻结
- `CST` 状态导出
- `Template / Direct-LLM / CST-LLM` 报告生成
- 人工评分表与指标汇总
- 消融计划与追溯表

## 当前主线

1. 读取 TBM 日运行 `CSV`
2. 解析 `TSP / HSP / 掌子面素描 PDF`
3. 按统一里程轴做地质-施工融合
4. 计算区段级 `GRS / RAI / GRCI`
5. 构建轻量化数字孪生状态
6. 生成日报、时段报告和 Agent 问答结果

## 当前算法版本

- `GRS`：基于多源地质证据的区段关注度表征，采用分量归一化和平权聚合
- `RAI`：基于 `Isolation Forest` 的施工响应异常度表征，并对常规环级停顿做惩罚折减
- `GRCI`：基于同步、滞后、变化与一致性的地质-施工耦合验证
- 地质侧引入高斯衰减平滑，减弱固定 `10m` 分段带来的边界切割效应

## 主要能力

- 工况分段、施工状态识别、效率分析、气体统计
- 多源地质证据解析、导入、去重、SQLite 落库
- 区段地质关注、施工响应异常、耦合验证与前方提示
- 轻量化数字孪生状态摘要
- LLM 日报、时段报告、会话式 Supervisor Agent 问答

## 项目定位

这个项目更准确的定位不是“风险识别系统”，而是：

**一个面向 TBM 施工报告自动化生成的数字孪生-大语言模型协同框架。**

其中：

- 数字孪生负责状态组织、时空对齐和事实约束
- 大语言模型负责正式报告的语言生成和篇章组织

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
