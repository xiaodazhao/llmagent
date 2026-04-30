# TBM Frontend

这是 TBM 智能监控与日报分析系统的前端部分，基于 React + Vite 构建。

## 启动

```powershell
npm install
npm run dev
```

默认请求后端：

```text
http://127.0.0.1:8000
```

配置位置：

```text
src/api/client.js
```

## 主要页面

```text
src/features/dashboard/       主驾驶舱
src/features/summary/         工况概览
src/features/geology/         地质融合分析
src/features/state/           施工状态分析
src/features/gas/             气体监测
src/features/risk/            空间风险剖面
src/features/report/          智能日报与时间窗口报告
```

## 常用命令

```powershell
npm run dev       # 开发服务
npm run build     # 生产构建
npm run lint      # 代码检查
```

