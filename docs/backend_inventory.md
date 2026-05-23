# 后端脚本清单

这份清单描述当前 `backend/` 的真实状态，重点回答三个问题：

- 哪些脚本属于运行主链
- 哪些脚本是手动使用的 CLI 工具
- 哪些历史重复实现已经被收口

## 1. 当前运行主链

### Web 入口与 API

- `backend/app.py`
  作用：创建 FastAPI 应用并注册 TBM 路由。
- `backend/routes/tbm.py`
  作用：统一提供 `/dates`、`/summary`、`/state`、`/gas`、`/geology`、`/report`、`/report_by_time`、`/agent_v2` 等接口。

### 主分析编排

- `backend/services/tbm_analysis_service.py`
  作用：主分析编排服务，负责施工分析、地质融合、区段耦合、数字孪生状态和 LLM 摘要准备。
- `backend/services/analysis_cache_service.py`
  作用：按 CSV 文件做分析缓存。
- `backend/services/sqlite_storage_service.py`
  作用：统一负责 SQLite 持久化，包括证据库、历史记录、Agent 会话和缓存。

### 施工分析

- `backend/analysis/dataprocess.py`
  作用：基础工况切分与工况统计。
- `backend/analysis/excavation_state.py`
  作用：施工状态识别、状态片段汇总和效率统计。
- `backend/analysis/gas_analysis.py`
  作用：气体监测统计和超限分析。

### 地质融合与区段分析

- `backend/geology/geology_fusion_backend.py`
  作用：加载证据库并挂接到 TBM DataFrame。
- `backend/geology/fusion.py`
  作用：逐里程命中证据并做事实层融合。
- `backend/geology/segment_analysis.py`
  作用：把逐点数据聚合为固定区段特征。
- `backend/geology/geology_summary.py`
  作用：输出记录级、区段级和掌子面摘要。

### 区段关注、耦合与前方提示

- `backend/analysis/geo_risk_model.py`
  作用：地质关注度相关计算。
- `backend/analysis/geology_response_coupling.py`
  作用：当前唯一保留的耦合分析主版本，负责 `GRS / RAI / GRCI`、区段分类、高关注区段和耦合摘要。
- `backend/analysis/forward_risk_advisor.py`
  作用：生成前视区段关注提示。

### 证据解析与导入

- `backend/parsers/tsp_parser.py`
  作用：解析 TSP PDF。
- `backend/parsers/hsp_parser.py`
  作用：解析 HSP PDF。
- `backend/parsers/sketch_parser.py`
  作用：解析掌子面/洞身素描 PDF。
- `backend/services/evidence_import_service.py`
  作用：统一负责证据 PDF 的增量导入、清洗、去重和写库。

### 数字孪生、历史、LLM

- `backend/services/digital_twin_state.py`
  作用：构建轻量化数字孪生状态快照。
- `backend/services/history_memory_service.py`
  作用：生成历史记录和历史对比摘要。
- `backend/llm/prompt_builder.py`
  作用：生成日报 Prompt。
- `backend/llm/prompt_builder_timewindow.py`
  作用：生成时段报告 Prompt。
- `backend/llm/llm_api.py`
  作用：调用 DeepSeek / Gemini 输出报告文本。

### Agent 问答链

- `backend/agent/supervisor_agent.py`
  作用：当前唯一在用的会话式 Supervisor Agent。
- `backend/agent/tbm_tools.py`
  作用：把主分析能力封装为 Agent 工具层。
- `backend/agent/common.py`
  作用：统一工具输出结构。
- `backend/agent/registry.py`
  作用：描述 Agent 能力和工具映射。

### 主链依赖的配置、Schema 和工具

- `backend/config.py`
- `backend/schemas/api.py`
- `backend/schemas/responses.py`
- `backend/schemas/schemas.py`
- `backend/utils/api_response.py`
- `backend/utils/chainage_utils.py`
- `backend/utils/io_utils.py`
- `backend/utils/serialization.py`
- `backend/utils/time_window_utils.py`

这些文件都属于当前系统真实依赖的一部分。

## 2. CLI 工具

这些脚本不会被页面或 API 自动调用，但仍然保留为明确的手动工具。

- `backend/scripts/build_evidence_db.py`
  作用：全量扫描 `TSP_DIR / HSP_DIR / SKETCH_DIR` 并重建证据库。
- `backend/scripts/import_evidence_reports.py`
  作用：增量导入指定 PDF 或目录。
- `backend/scripts/inspect_coupling_analysis.py`
  作用：查看指定日期的耦合分析结果。
- `backend/scripts/test_agent_v2.py`
  作用：对 `agent_v2` 做接口级冒烟检查。

## 3. 测试脚本

`backend/tests/` 下所有文件都属于测试层，不进运行主链，但都仍然有效：

- `conftest.py`
- `test_evidence_import_service.py`
- `test_geo_risk_model.py`
- `test_geology_response_coupling.py`
- `test_history_memory_service.py`
- `test_parsers.py`
- `test_sqlite_storage_service.py`
- `test_tbm_routes.py`

## 4. 已经完成的收口

### 4.1 耦合分析统一为单一版本

此前后端同时存在：

- `backend/analysis/geology_response_coupling.py`
- `backend/analysis/coupling_analysis.py`

现在已经统一为单一版本：

- 保留 `backend/analysis/geology_response_coupling.py`
- 删除 `backend/analysis/coupling_analysis.py`
- `backend/services/tbm_analysis_service.py` 不再维护旧版 fallback 分支

### 4.2 里程工具统一为单一模块

此前里程相关函数分散在：

- `backend/utils/utils.py`
- `backend/utils/chainage_utils.py`

现在已经统一为：

- 保留 `backend/utils/chainage_utils.py`

并将以下能力集中到该模块：

- `mileage_to_num`
- `num_to_mileage`
- `format_chainage_dk`
- `format_chainage_range_dk`
- `safe_float`
- `compact_text`

原来的 `backend/utils/utils.py` 已删除。

### 4.3 证据建库与导入共用一套清洗逻辑

此前全量建库和增量导入各自维护一套清洗/转表逻辑。

现在已经统一为：

- `backend/services/evidence_import_service.py`
  - `records_to_dataframe`
  - `clean_evidence_dataframe`

因此：

- `backend/scripts/build_evidence_db.py` 已复用 service 层实现
- `backend/scripts/db.py` 已删除

## 5. 已移除的遗留脚本

以下边缘或历史实验脚本已经从仓库中清理：

- `backend/check_and_install.py`
- `backend/debug_runner.py`
- `backend/train_risk_probability_model_b.py`
- `backend/parsers/drill_parser.py`
- `backend/脚本提取.py`

这样做的目的，是让当前仓库只保留：

- 正在运行的主链代码
- 仍然有明确用途的 CLI 工具
- 测试代码

## 6. 当前结论

当前后端已经收口成更干净的结构：

- 耦合分析只有一套主实现
- 里程工具只有一个主模块
- 证据建库和增量导入共享一套清洗逻辑
- 明显的遗留脚本已经移除

现在的 `backend/` 更接近“可交付版本”，而不是“主链 + 历史实验 + 个人调试脚本混放”的状态。
