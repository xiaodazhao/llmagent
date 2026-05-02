import { useEffect, useMemo, useState } from "react";

import { tbmApi } from "@/api/tbm";

const SAMPLE_QUERIES = [
  "有哪些可用日期",
  "分析瓦斯、地质风险和数字孪生状态",
  "分析施工状态、效率和停机情况",
  "分析前方30米地质风险",
  "和历史记录对比一下",
];

const HIGHLIGHT_LABELS = {
  available_date_count: "可用日期数",
  latest_date: "最新日期",
  work_total_min: "工作时长 min",
  stop_total_min: "停机时长 min",
  abnormal_count: "异常次数",
  gas_exceed_types: "气体超限",
  has_geology: "地质数据",
  geology_high_risk_segment_count: "高风险区段",
  geology_multi_source_segment_count: "多源区段",
  top_coupling_segment: "最高关注区段",
  top_coupling_label: "耦合等级",
  top_coupling_index: "耦合指数",
  forward_advice_level: "前方风险等级",
  forward_main_hazards: "前方主要风险",
  forward_high_risk_count: "前方高风险数",
  current_chainage_dk: "当前里程",
  advance_length_m: "推进长度 m",
  dominant_operation: "主导状态",
  work_ratio: "工作占比",
  has_history: "历史记录",
  history_count: "历史样本数",
  previous_date: "上一记录",
};

const HIGHLIGHT_ORDER = [
  "latest_date",
  "available_date_count",
  "current_chainage_dk",
  "advance_length_m",
  "dominant_operation",
  "work_ratio",
  "gas_exceed_types",
  "has_geology",
  "geology_high_risk_segment_count",
  "top_coupling_segment",
  "top_coupling_label",
  "top_coupling_index",
  "forward_advice_level",
  "forward_main_hazards",
  "history_count",
  "previous_date",
  "work_total_min",
  "stop_total_min",
  "abnormal_count",
];

export default function AgentPage({ date, compact = false }) {
  const [query, setQuery] = useState(SAMPLE_QUERIES[1]);
  const [useLlm, setUseLlm] = useState(false);
  const [verbose, setVerbose] = useState(false);
  const [loading, setLoading] = useState(false);
  const [capabilities, setCapabilities] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    tbmApi
      .getAgentV2Capabilities()
      .then((res) => setCapabilities(res.data || null))
      .catch((err) => {
        console.error("Agent V2 capabilities load failed", err);
        setCapabilities(null);
      });
  }, []);

  useEffect(() => {
    setResult(null);
    setError("");
  }, [date]);

  const agents = useMemo(() => capabilities?.agents || [], [capabilities]);
  const supervisor = capabilities?.supervisor;
  const highlightItems = useMemo(() => buildHighlightItems(result?.highlights), [result]);

  const handleRun = async () => {
    const cleanQuery = query.trim();
    if (!cleanQuery) return;

    setLoading(true);
    setError("");
    setResult(null);

    try {
      const res = await tbmApi.runAgentV2({
        query: cleanQuery,
        date: date || null,
        use_llm: useLlm,
        verbose,
      });

      if (res.data?.success === false) {
        setError(res.data.message || "Agent V2 分析失败。");
      } else {
        setResult(res.data?.data || res.data);
      }
    } catch (err) {
      console.error("Agent V2 request failed", err);
      setError("Agent V2 请求失败，请确认后端 /api/tbm/agent_v2 已启动。");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ ...styles.wrapper, ...(compact ? styles.compactWrapper : {}) }}>
      {!compact && (
        <div style={styles.header}>
          <div>
            <h2 style={styles.title}>TBM 多智能体问答</h2>
            <p style={styles.subtitle}>当前日期：{date || "未选择，系统将尝试使用最新数据"}</p>
          </div>
          <div style={styles.modeBadge}>Supervisor V2</div>
        </div>
      )}

      <div style={styles.optionRow}>
        <Toggle checked={useLlm} onChange={setUseLlm} label="LLM 润色" />
        <Toggle checked={verbose} onChange={setVerbose} label="完整详情" />
      </div>

      <div style={styles.queryRow}>
        <textarea
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="向 TBM 多智能体提问..."
          style={styles.textarea}
        />
        <button
          type="button"
          onClick={handleRun}
          disabled={loading || !query.trim()}
          style={{
            ...styles.button,
            opacity: loading || !query.trim() ? 0.55 : 1,
          }}
        >
          {loading ? "分析中" : "运行"}
        </button>
      </div>

      <div style={styles.samples}>
        {SAMPLE_QUERIES.map((item) => (
          <button
            key={item}
            type="button"
            onClick={() => setQuery(item)}
            style={styles.sampleButton}
          >
            {item}
          </button>
        ))}
      </div>

      {error && <div style={styles.error}>{error}</div>}

      {result ? (
        <div style={styles.result}>
          <div style={styles.metaGrid}>
            <Meta label="运行模式" value={result.mode || "supervisor_v2"} />
            <Meta label="路由专家" value={(result.routed_agents || []).join(" / ") || "--"} />
            <Meta label="结果模式" value={result.verbose ? "完整详情" : "精简摘要"} />
            <Meta label="分析日期" value={result.date || date || "最新数据"} />
          </div>

          <section style={styles.block}>
            <div style={styles.blockTitle}>回答</div>
            <div style={styles.answer}>{result.answer || "暂无回答。"}</div>
          </section>

          {highlightItems.length > 0 && (
            <section style={styles.block}>
              <div style={styles.blockTitle}>关键指标</div>
              <div style={styles.highlightGrid}>
                {highlightItems.map((item) => (
                  <div key={item.key} style={styles.highlightItem}>
                    <span>{item.label}</span>
                    <strong>{item.value}</strong>
                  </div>
                ))}
              </div>
            </section>
          )}

          <section style={styles.block}>
            <div style={styles.blockTitle}>Supervisor 调度计划</div>
            <div style={styles.planList}>
              {(result.supervisor_plan || []).map((step, index) => (
                <div key={`${step.agent}-${index}`} style={styles.planItem}>
                  <div style={styles.planHead}>
                    <span style={styles.planIndex}>{index + 1}</span>
                    <strong>{step.agent}</strong>
                    <span>{(step.tools || []).join(" / ")}</span>
                  </div>
                  <p>{step.reason || "按问题意图路由。"}</p>
                </div>
              ))}
            </div>
          </section>

          <section style={styles.block}>
            <div style={styles.blockTitle}>工具执行结果</div>
            <div style={styles.trace}>
              {(result.tool_results || []).map((item, index) => (
                <ToolTrace key={`${item.agent}-${item.tool}-${index}`} item={item} />
              ))}
            </div>
          </section>

          {verbose && (
            <details style={styles.details}>
              <summary>完整 JSON 结果</summary>
              <pre style={styles.jsonBlock}>{JSON.stringify(result, null, 2)}</pre>
            </details>
          )}
        </div>
      ) : (
        !loading && (
          <div style={styles.empty}>
            选择一个问题，系统会先生成调度计划，再调用对应 TBM 专家智能体。
          </div>
        )
      )}

      {agents.length > 0 && (
        <div style={styles.capabilities}>
          <div style={styles.capabilityTitle}>
            {supervisor?.name || "TBMSupervisorAgent"}：{supervisor?.mode || "supervisor-style"}
          </div>
          <div style={styles.agentGrid}>
            {agents.map((agent) => (
              <div key={agent.name} style={styles.agentLine}>
                <strong>{agent.name}</strong>
                <span>{agent.description}</span>
                <em>{(agent.tools || []).join("，")}</em>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function Toggle({ checked, onChange, label }) {
  return (
    <label style={styles.toggleLabel}>
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
      />
      {label}
    </label>
  );
}

function Meta({ label, value }) {
  return (
    <div style={styles.metaItem}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function ToolTrace({ item }) {
  const summary = item.summary || {};
  return (
    <div style={styles.traceItem}>
      <div style={styles.traceHeader}>
        <span style={styles.traceAgent}>{item.agent}</span>
        <span style={styles.traceTool}>{item.tool}</span>
        <span style={item.success ? styles.ok : styles.fail}>
          {item.success ? "成功" : "失败"}
        </span>
      </div>
      {item.message && <div style={styles.traceMessage}>{item.message}</div>}
      {Object.keys(summary).length > 0 && (
        <div style={styles.summaryGrid}>
          {Object.entries(summary).map(([key, value]) => (
            <div key={key} style={styles.summaryItem}>
              <span>{formatKey(key)}</span>
              <strong>{formatValue(value)}</strong>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function buildHighlightItems(highlights = {}) {
  const keys = [
    ...HIGHLIGHT_ORDER,
    ...Object.keys(highlights).filter((key) => !HIGHLIGHT_ORDER.includes(key)),
  ];

  return keys
    .filter((key) => key !== "warnings" && highlights[key] !== undefined && highlights[key] !== null)
    .map((key) => ({
      key,
      label: HIGHLIGHT_LABELS[key] || formatKey(key),
      value: key === "work_ratio" ? formatPercent(highlights[key]) : formatValue(highlights[key]),
    }));
}

function formatKey(key) {
  return String(key).replaceAll("_", " ");
}

function formatPercent(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "--";
  return `${(number * 100).toFixed(1)}%`;
}

function formatValue(value) {
  if (Array.isArray(value)) {
    return value.length ? value.join("，") : "--";
  }
  if (typeof value === "boolean") {
    return value ? "有" : "无";
  }
  if (typeof value === "number") {
    return Number.isInteger(value) ? String(value) : value.toFixed(3);
  }
  if (value && typeof value === "object") {
    return JSON.stringify(value);
  }
  return value === "" || value === undefined || value === null ? "--" : String(value);
}

const styles = {
  wrapper: {
    height: "100%",
    display: "flex",
    flexDirection: "column",
    gap: 12,
    minHeight: 0,
  },
  compactWrapper: {
    overflow: "hidden",
  },
  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    gap: 12,
  },
  title: {
    margin: 0,
    fontSize: 18,
    color: "#0f172a",
  },
  subtitle: {
    margin: "4px 0 0",
    fontSize: 13,
    color: "#64748b",
  },
  modeBadge: {
    border: "1px solid #99f6e4",
    borderRadius: 999,
    padding: "6px 10px",
    background: "#f0fdfa",
    color: "#0f766e",
    fontSize: 12,
    fontWeight: 800,
    whiteSpace: "nowrap",
  },
  optionRow: {
    display: "flex",
    justifyContent: "flex-end",
    gap: 14,
    flexWrap: "wrap",
  },
  toggleLabel: {
    display: "flex",
    alignItems: "center",
    gap: 7,
    color: "#475569",
    fontSize: 13,
    whiteSpace: "nowrap",
  },
  queryRow: {
    display: "grid",
    gridTemplateColumns: "1fr 84px",
    gap: 10,
    alignItems: "stretch",
  },
  textarea: {
    minHeight: 78,
    resize: "vertical",
    border: "1px solid #cbd5e1",
    borderRadius: 8,
    padding: "10px 12px",
    fontSize: 14,
    lineHeight: 1.5,
    outline: "none",
  },
  button: {
    border: "none",
    borderRadius: 8,
    background: "#0f766e",
    color: "#fff",
    fontWeight: 900,
    cursor: "pointer",
  },
  samples: {
    display: "flex",
    flexWrap: "wrap",
    gap: 8,
  },
  sampleButton: {
    border: "1px solid #cbd5e1",
    borderRadius: 8,
    background: "#fff",
    color: "#334155",
    padding: "6px 10px",
    fontSize: 12,
    cursor: "pointer",
  },
  error: {
    color: "#b91c1c",
    background: "#fef2f2",
    border: "1px solid #fecaca",
    borderRadius: 8,
    padding: 10,
    fontSize: 13,
  },
  result: {
    minHeight: 0,
    display: "flex",
    flexDirection: "column",
    gap: 12,
    overflow: "auto",
    paddingRight: 2,
  },
  metaGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(4, minmax(0, 1fr))",
    gap: 8,
  },
  metaItem: {
    border: "1px solid #e2e8f0",
    borderRadius: 8,
    padding: 9,
    background: "#f8fafc",
    display: "flex",
    flexDirection: "column",
    gap: 4,
    minWidth: 0,
    fontSize: 12,
  },
  block: {
    display: "flex",
    flexDirection: "column",
    gap: 8,
  },
  blockTitle: {
    fontSize: 13,
    fontWeight: 900,
    color: "#0f172a",
  },
  answer: {
    minHeight: 116,
    maxHeight: 230,
    overflow: "auto",
    padding: 13,
    border: "1px solid #e2e8f0",
    borderRadius: 8,
    background: "#f8fafc",
    color: "#1e293b",
    whiteSpace: "pre-wrap",
    wordBreak: "break-word",
    fontSize: 14,
    lineHeight: 1.7,
  },
  highlightGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
    gap: 8,
  },
  highlightItem: {
    border: "1px solid #e2e8f0",
    borderRadius: 8,
    background: "#ffffff",
    padding: 9,
    display: "flex",
    flexDirection: "column",
    gap: 4,
    minWidth: 0,
  },
  planList: {
    display: "flex",
    flexDirection: "column",
    gap: 8,
  },
  planItem: {
    border: "1px solid #dbeafe",
    borderRadius: 8,
    background: "#eff6ff",
    padding: 9,
  },
  planHead: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    flexWrap: "wrap",
    color: "#1e3a8a",
    fontSize: 13,
  },
  planIndex: {
    width: 22,
    height: 22,
    borderRadius: 999,
    background: "#2563eb",
    color: "#fff",
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    fontWeight: 900,
  },
  trace: {
    display: "flex",
    flexDirection: "column",
    gap: 8,
  },
  traceItem: {
    border: "1px solid #e2e8f0",
    borderRadius: 8,
    padding: 9,
    background: "#fff",
  },
  traceHeader: {
    display: "grid",
    gridTemplateColumns: "120px 1fr 52px",
    gap: 8,
    alignItems: "center",
    fontSize: 12,
  },
  traceAgent: {
    color: "#0f172a",
    fontWeight: 900,
  },
  traceTool: {
    color: "#475569",
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
  },
  traceMessage: {
    marginTop: 6,
    color: "#64748b",
    fontSize: 12,
  },
  summaryGrid: {
    marginTop: 8,
    display: "grid",
    gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
    gap: 6,
  },
  summaryItem: {
    display: "flex",
    justifyContent: "space-between",
    gap: 8,
    color: "#64748b",
    fontSize: 12,
    minWidth: 0,
  },
  ok: {
    color: "#15803d",
    textAlign: "right",
    fontWeight: 900,
  },
  fail: {
    color: "#b91c1c",
    textAlign: "right",
    fontWeight: 900,
  },
  details: {
    border: "1px solid #e2e8f0",
    borderRadius: 8,
    padding: 10,
    background: "#fff",
  },
  jsonBlock: {
    maxHeight: 280,
    overflow: "auto",
    margin: "10px 0 0",
    padding: 10,
    background: "#0f172a",
    color: "#e2e8f0",
    borderRadius: 8,
    fontSize: 12,
  },
  empty: {
    color: "#94a3b8",
    textAlign: "center",
    padding: "32px 10px",
    border: "1px dashed #cbd5e1",
    borderRadius: 8,
  },
  capabilities: {
    borderTop: "1px solid #e2e8f0",
    paddingTop: 10,
    display: "flex",
    flexDirection: "column",
    gap: 8,
    fontSize: 12,
    color: "#64748b",
  },
  capabilityTitle: {
    color: "#0f172a",
    fontWeight: 900,
  },
  agentGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
    gap: 8,
  },
  agentLine: {
    border: "1px solid #e2e8f0",
    borderRadius: 8,
    padding: 8,
    display: "flex",
    flexDirection: "column",
    gap: 3,
    minWidth: 0,
    background: "#fff",
  },
};
