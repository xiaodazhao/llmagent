import { useEffect, useMemo, useState } from "react";

import api from "@/api/client";
import SummaryPage from "@/features/summary/SummaryPage";
import GeologyPage from "@/features/geology/GeologyPage";
import StatePage from "@/features/state/StatePage";
import GasPage from "@/features/gas/GasPage";
import ReportPage from "@/features/report/ReportPage";
import TimeWindowPage from "@/features/report/TimeWindowPage";
import RiskProfilePage from "@/features/risk/RiskProfilePage";
import AgentPage from "@/features/agent/AgentPage";

export default function Dashboard() {
  const [dates, setDates] = useState([]);
  const [currentDate, setCurrentDate] = useState("");
  const [loading, setLoading] = useState(true);
  const [agentOpen, setAgentOpen] = useState(false);

  useEffect(() => {
    const fetchDates = async () => {
      try {
        const res = await api.get("/api/tbm/dates");
        const list = res.data.dates || [];
        setDates(list);
        if (list.length > 0) setCurrentDate(list[0]);
      } catch (err) {
        console.error("日期加载失败", err);
      } finally {
        setLoading(false);
      }
    };

    fetchDates();
  }, []);

  const projectStatus = useMemo(() => {
    if (!currentDate) return "等待选择数据日期";
    return `正在查看 ${currentDate} 的掘进数据`;
  }, [currentDate]);

  if (loading) {
    return <div style={styles.loading}>正在初始化 TBM 监控驾驶舱...</div>;
  }

  return (
    <main style={styles.page}>
      <section style={styles.hero}>
        <div style={styles.heroMain}>
          <span style={styles.kicker}>隧道掘进智能分析平台</span>
          <h1 style={styles.title}>TBM 施工态势驾驶舱</h1>
          <p style={styles.subtitle}>{projectStatus}</p>
        </div>

        <div style={styles.heroPanel}>
          <label style={styles.dateLabel}>数据日期</label>
          <select
            value={currentDate}
            onChange={(e) => setCurrentDate(e.target.value)}
            style={styles.select}
          >
            {dates.map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </select>
          <div style={styles.dateHint}>已接入 {dates.length} 个可分析日期</div>
        </div>
      </section>

      <section style={styles.quickBar}>
        <QuickStat label="当前日期" value={currentDate || "--"} />
        <QuickStat label="核心模块" value="6 个" />
        <QuickStat label="分析模式" value="日报 / 时段 / 问答" />
        <QuickStat label="问答助手" value={agentOpen ? "已打开" : "待唤起"} />
      </section>

      <section style={styles.grid}>
        <Panel title="工况概览" eyebrow="施工节奏">
          <SummaryPage date={currentDate} />
        </Panel>

        <Panel title="地质融合分析" eyebrow="围岩与风险">
          <GeologyPage date={currentDate} />
        </Panel>

        <Panel title="施工状态识别" eyebrow="状态片段">
          <StatePage date={currentDate} />
        </Panel>

        <Panel title="气体监测" eyebrow="安全监测" span={3} minHeight={420}>
          <GasPage date={currentDate} />
        </Panel>

        <Panel title="空间风险剖面" eyebrow="里程关联" span={3} minHeight={420}>
          <RiskProfilePage date={currentDate} />
        </Panel>

        <Panel title="智能日报" eyebrow="AI 报告" span={3} height={700}>
          <ReportPage date={currentDate} />
        </Panel>

        <Panel title="时间段分析" eyebrow="局部复盘" span={3} height={700}>
          <TimeWindowPage date={currentDate} />
        </Panel>
      </section>

      <button
        type="button"
        onClick={() => setAgentOpen((open) => !open)}
        style={styles.agentButton}
      >
        {agentOpen ? "收起问答" : "智能问答"}
      </button>

      {agentOpen && (
        <aside style={styles.agentWindow}>
          <div style={styles.agentWindowHeader}>
            <div>
              <h2 style={styles.agentWindowTitle}>TBM 智能问答</h2>
              <p style={styles.agentWindowSubtitle}>当前日期：{currentDate || "--"}</p>
            </div>
            <button
              type="button"
              onClick={() => setAgentOpen(false)}
              style={styles.closeButton}
              aria-label="关闭问答窗口"
            >
              关闭
            </button>
          </div>
          <AgentPage date={currentDate} compact />
        </aside>
      )}
    </main>
  );
}

function Panel({ title, eyebrow, children, span = 2, minHeight = 520, height }) {
  return (
    <article
      style={{
        ...styles.panel,
        gridColumn: `span ${span}`,
        minHeight,
        ...(height ? { height } : {}),
      }}
    >
      <header style={styles.panelHeader}>
        <div>
          <div style={styles.panelEyebrow}>{eyebrow}</div>
          <h2 style={styles.panelTitle}>{title}</h2>
        </div>
      </header>
      <div style={styles.panelBody}>{children}</div>
    </article>
  );
}

function QuickStat({ label, value }) {
  return (
    <div style={styles.quickItem}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

const styles = {
  page: {
    minHeight: "100vh",
    padding: "32px",
  },
  hero: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "stretch",
    gap: 24,
    padding: 28,
    borderRadius: 18,
    background: "linear-gradient(135deg, #0f2a4a 0%, #164e63 52%, #116466 100%)",
    color: "#fff",
    boxShadow: "0 24px 60px rgba(15, 42, 74, 0.22)",
  },
  heroMain: {
    display: "flex",
    flexDirection: "column",
    justifyContent: "center",
    minWidth: 0,
  },
  kicker: {
    fontSize: 13,
    color: "#bae6fd",
    fontWeight: 700,
    marginBottom: 10,
  },
  title: {
    margin: 0,
    fontSize: 34,
    lineHeight: 1.15,
    letterSpacing: 0,
  },
  subtitle: {
    margin: "12px 0 0",
    color: "#dbeafe",
    fontSize: 15,
  },
  heroPanel: {
    width: 280,
    borderRadius: 14,
    background: "rgba(255,255,255,0.12)",
    border: "1px solid rgba(255,255,255,0.2)",
    padding: 18,
    display: "flex",
    flexDirection: "column",
    justifyContent: "center",
    gap: 10,
  },
  dateLabel: {
    color: "#dbeafe",
    fontSize: 13,
    fontWeight: 700,
  },
  select: {
    width: "100%",
    padding: "11px 12px",
    borderRadius: 10,
    border: "1px solid rgba(255,255,255,0.3)",
    background: "#fff",
    color: "#0f172a",
    fontWeight: 800,
    outline: "none",
  },
  dateHint: {
    color: "#bfdbfe",
    fontSize: 12,
  },
  quickBar: {
    display: "grid",
    gridTemplateColumns: "repeat(4, minmax(0, 1fr))",
    gap: 16,
    margin: "22px 0",
  },
  quickItem: {
    background: "rgba(255,255,255,0.78)",
    border: "1px solid rgba(203, 213, 225, 0.8)",
    borderRadius: 12,
    padding: "14px 16px",
    boxShadow: "0 10px 30px rgba(15, 23, 42, 0.06)",
    display: "flex",
    justifyContent: "space-between",
    gap: 12,
    alignItems: "center",
  },
  grid: {
    display: "grid",
    gridTemplateColumns: "repeat(6, minmax(0, 1fr))",
    gap: 20,
    alignItems: "stretch",
  },
  panel: {
    background: "rgba(255, 255, 255, 0.92)",
    border: "1px solid rgba(203, 213, 225, 0.85)",
    borderRadius: 14,
    padding: 18,
    display: "flex",
    flexDirection: "column",
    overflow: "hidden",
    boxShadow: "0 14px 40px rgba(15, 23, 42, 0.08)",
  },
  panelHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    paddingBottom: 12,
    marginBottom: 14,
    borderBottom: "1px solid #e2e8f0",
  },
  panelEyebrow: {
    color: "#0f766e",
    fontSize: 12,
    fontWeight: 800,
    marginBottom: 4,
  },
  panelTitle: {
    margin: 0,
    color: "#0f172a",
    fontSize: 18,
    lineHeight: 1.25,
  },
  panelBody: {
    flex: 1,
    minHeight: 0,
    overflow: "auto",
  },
  agentButton: {
    position: "fixed",
    right: 28,
    bottom: 28,
    zIndex: 30,
    border: "none",
    borderRadius: 999,
    background: "#0f766e",
    color: "#fff",
    boxShadow: "0 16px 34px rgba(15, 118, 110, 0.3)",
    cursor: "pointer",
    fontSize: 15,
    fontWeight: 800,
    padding: "14px 20px",
  },
  agentWindow: {
    position: "fixed",
    right: 28,
    bottom: 86,
    zIndex: 31,
    width: "min(580px, calc(100vw - 32px))",
    height: "min(740px, calc(100vh - 120px))",
    background: "#ffffff",
    border: "1px solid #cbd5e1",
    borderRadius: 14,
    boxShadow: "0 26px 80px rgba(15, 23, 42, 0.24)",
    padding: 18,
    display: "flex",
    flexDirection: "column",
    gap: 14,
  },
  agentWindowHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    borderBottom: "1px solid #e2e8f0",
    paddingBottom: 12,
    gap: 12,
  },
  agentWindowTitle: {
    margin: 0,
    color: "#0f172a",
    fontSize: 18,
  },
  agentWindowSubtitle: {
    margin: "4px 0 0",
    color: "#64748b",
    fontSize: 13,
  },
  closeButton: {
    borderRadius: 9,
    border: "1px solid #cbd5e1",
    background: "#fff",
    color: "#334155",
    cursor: "pointer",
    fontWeight: 800,
    padding: "8px 12px",
  },
  loading: {
    height: "100vh",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: 20,
    color: "#64748b",
  },
};
