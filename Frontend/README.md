# TBM Frontend

这是 TBM 施工-地质-安全多源融合智能分析系统的前端项目，基于 React + Vite。

前端负责把后端分析结果组织成可操作的工程看板，包括日期选择、施工统计、状态识别、气体监测、地质融合、风险剖面、LLM 报告、Agent 问答和地质证据库增量导入。

## 启动

```powershell
npm install
npm.cmd run dev
```

默认开发地址：

```text
http://127.0.0.1:5173
```

如果你的 PowerShell 禁止执行 `npm.ps1`，请使用 `npm.cmd`，例如：

```powershell
npm.cmd run build
npx.cmd eslint src/features/evidence/EvidenceImportPage.jsx
```

## 后端地址

可在 `Frontend/.env` 中配置：

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
```

接口封装：

```text
src/api/client.js
src/api/tbm.js
```

## 页面模块

```text
src/features/dashboard/       总览看板、日期选择、模块入口
src/features/summary/         基础工况统计
src/features/state/           隐含施工状态识别、状态效率、岩性带展示
src/features/geology/         地质融合、GRS/RAI/GRCI、典型区段
src/features/gas/             气体监测统计和超阈值事件
src/features/risk/            风险剖面与速度剖面
src/features/report/          LLM 日报和时间窗报告
src/features/agent/           TBM Agent 问答
src/features/evidence/        地质证据库控制台、新超报增量导入
src/features/settings/        设置页
```

## 证据库导入页

`src/features/evidence/EvidenceImportPage.jsx` 对应后端：

```text
POST /api/tbm/evidence/import
```

支持：

- 输入一个或多个 PDF 文件路径或目录路径
- 选择 `tsp` / `hsp` / `sonic` / `sketch`
- `dry_run` 预检查
- `replace_existing` 替换同 ID 旧记录
- `recursive` 递归扫描目录
- 展示解析记录数、插入数、跳过重复数、错误列表和备份路径

这个页面的目标是让新增超前地质预报可以直接增量入库，不需要每次重跑全量 `build_evidence_db.py`。

## 常用命令

```powershell
npm.cmd run dev       # 启动开发服务器
npm.cmd run build     # 构建生产版本
npm.cmd run lint      # 全量 lint
npm.cmd run preview   # 预览构建产物
```

注意：当前全量 `npm run lint` 可能会暴露项目历史遗留 lint 问题；新增证据导入页可单独用 `npx.cmd eslint src/features/evidence/EvidenceImportPage.jsx` 检查。
