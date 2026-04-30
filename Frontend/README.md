# TBM Frontend

这是 TBM 数字孪生与 LLM 施工报告生成系统的前端项目，基于 React + Vite。

## 启动

```powershell
npm install
npm run dev
```

默认开发地址通常为：

```text
http://127.0.0.1:5173
```

## 后端地址

如需指定后端 API 地址，可在 `Frontend/.env` 中配置：

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
```

接口封装位于：

```text
src/api/client.js
```

## 主要模块

```text
src/features/dashboard/       总览看板
src/features/summary/         基础工况统计
src/features/geology/         地质融合与区段耦合分析
src/features/state/           隐含施工状态识别
src/features/gas/             气体监测分析
src/features/risk/            风险剖面与速度剖面
src/features/report/          LLM 报告生成
```

## 常用命令

```powershell
npm run dev       # 启动开发服务器
npm run build     # 构建生产版本
npm run lint      # 代码检查
```
