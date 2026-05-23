# 后端清单

本文档描述当前 `backend/` 的真实主链，重点说明：

- 哪些模块属于运行主链
- 哪些脚本是保留的 CLI 工具
- 当前算法升级分别落在哪些文件

## 1. 运行主链

### Web 与 API

- `backend/app.py`
  - 创建 FastAPI 应用
- `backend/routes/tbm.py`
  - 提供 `/dates`、`/summary`、`/state`、`/gas`、`/geology`、`/report`、`/report_by_time`、`/agent_v2` 等接口

### 主分析编排

- `backend/services/tbm_analysis_service.py`
  - 主分析编排服务
  - 负责工况分析、地质融合、耦合分析、数字孪生状态和 LLM 摘要

### 基础施工分析

- `backend/analysis/dataprocess.py`
  - 基础工况切分
  - 停机统计
  - 常规环级停顿候选识别
- `backend/analysis/excavation_state.py`
  - 施工状态识别与效率统计
- `backend/analysis/gas_analysis.py`
  - 气体监测分析

### 地质融合与区段分析

- `backend/geology/geology_fusion_backend.py`
  - 证据库加载与 TBM 数据挂接
- `backend/geology/fusion.py`
  - 逐点地质证据融合
- `backend/geology/segment_analysis.py`
  - 固定区段聚合
- `backend/geology/geology_summary.py`
  - 地质摘要与掌子面摘要

### 区段关注与耦合分析

- `backend/analysis/geo_risk_model.py`
  - `GRS` 分量构造与动态修正
- `backend/analysis/geology_response_coupling.py`
  - `GRS / RAI / GRCI` 主版本
  - 高斯平滑
  - Isolation Forest 异常检测
  - 停顿折减后的耦合分析
- `backend/analysis/forward_risk_advisor.py`
  - 前方区段提示

### 证据解析与导入

- `backend/parsers/tsp_parser.py`
- `backend/parsers/hsp_parser.py`
- `backend/parsers/sketch_parser.py`
- `backend/services/evidence_import_service.py`

### 数字孪生、历史、缓存、存储

- `backend/services/digital_twin_state.py`
- `backend/services/history_memory_service.py`
- `backend/services/analysis_cache_service.py`
- `backend/services/sqlite_storage_service.py`

### LLM

- `backend/llm/prompt_builder.py`
  - 日报提示词
- `backend/llm/prompt_builder_timewindow.py`
  - 时段报告提示词
- `backend/llm/llm_api.py`
  - 模型调用层

### Agent

- `backend/agent/supervisor_agent.py`
- `backend/agent/tbm_tools.py`
- `backend/agent/common.py`
- `backend/agent/registry.py`

### 依赖工具与 Schema

- `backend/config.py`
- `backend/schemas/api.py`
- `backend/schemas/responses.py`
- `backend/schemas/schemas.py`
- `backend/utils/api_response.py`
- `backend/utils/chainage_utils.py`
- `backend/utils/io_utils.py`
- `backend/utils/serialization.py`
- `backend/utils/time_window_utils.py`

## 2. 保留的 CLI 工具

这些脚本不属于自动运行主链，但仍然保留为手动工具：

- `backend/scripts/build_evidence_db.py`
  - 全量重建证据库
- `backend/scripts/import_evidence_reports.py`
  - 增量导入证据 PDF
- `backend/scripts/inspect_coupling_analysis.py`
  - 查看指定日期的耦合分析输出
- `backend/scripts/test_agent_v2.py`
  - Agent 冒烟测试

## 3. 当前算法升级落点

### 3.1 GRS 平权表征

- `backend/analysis/geo_risk_model.py`
  - 负责分量归一化与平权聚合

### 3.2 高斯衰减平滑

- `backend/analysis/geology_response_coupling.py`
  - 在逐点 `GRS_base` 之后做按里程的高斯平滑
  - 再用平滑后的 `row_grs` 聚合区段 `GRS`

### 3.3 RAI Isolation Forest

- `backend/analysis/geology_response_coupling.py`
  - 逐点异常分数
  - 区段级 `RAI` 聚合

### 3.4 常规环级停顿候选折减

- `backend/analysis/dataprocess.py`
  - `annotate_routine_ring_building_stops(...)`
- `backend/services/tbm_analysis_service.py`
  - 在地质融合后调用该标记逻辑
- `backend/analysis/geology_response_coupling.py`
  - 对 `row_stop_anomaly` 做折减

### 3.5 GRCI 耦合验证

- `backend/analysis/geology_response_coupling.py`
  - 同步、滞后、变化和一致性耦合

## 4. 测试覆盖

当前与主链直接相关的测试包括：

- `backend/tests/test_geo_risk_model.py`
- `backend/tests/test_geology_response_coupling.py`
- `backend/tests/test_dataprocess.py`
- `backend/tests/test_history_memory_service.py`
- `backend/tests/test_sqlite_storage_service.py`
- `backend/tests/test_evidence_import_service.py`
- `backend/tests/test_parsers.py`
- `backend/tests/test_tbm_routes.py`

## 5. 当前结论

当前 `backend/` 已经收口为：

- 一套主分析实现
- 一套主提示词实现
- 一套主耦合分析实现
- 一套主里程工具实现
- 有明确边界的 CLI 工具与测试层

也就是说，当前后端更接近“稳定主链 + 辅助工具 + 测试”的可维护结构，而不是多版本并存的历史堆叠状态。
