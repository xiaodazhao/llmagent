import { useEffect, useMemo, useState } from "react";

import { tbmApi } from "@/api/tbm";

const SAMPLE_QUERIES = [
  "分析今天的瓦斯风险和前方地质风险。",
  "总结这一天的工况、停机和掘进效率。",
  "和历史记录相比，今天的风险水平有什么变化？",
  "给我当前数字孪生状态快照。",
];

export default function AgentPage({ date, compact = false }) {
  const [query, setQuery] = useState(SAMPLE_QUERIES[0]);
  const [useLlm, setUseLlm] = useState(false);
  const [loading, setLoading] = useState(false);
  const [capabilities, setCapabilities] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    tbmApi
      .getAgentCapabilities()
      .then((res) => setCapabilities(res.data || null))
      .catch((err) => {
        console.error("Agent 能力加载失败", err);
        setCapabilities(null);
      });
  }, []);

  useEffect(() => {
    setResult(null);
    setError("");
  }, [date]);

  const agents = useMemo(() => capabilities?.agents || [], [capabilities]);

  const handleRun = async () => {
    if (!query.trim() || !date) return;
    setLoading(true);
    setError("");
    setResult(null);

    try {
      const res = await tbmApi.runAgent({
        query,
        date,
        use_llm: useLlm,
      });

      if (res.data?.success === false) {
        setError(res.data.message || "Agent 分析失败。");
      } else {
        setResult(res.data?.data || res.data);
      }
    } catch (err) {
      console.error("Agent 请求失败", err);
      setError("Agent 请求失败，请确认 /api/tbm/agent 接口已启动。");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ ...styles.wrapper, ...(compact ? styles.compactWrapper : {}) }}>
      {!compact && (
        <div style={styles.header}>
          <div>
            <h2 style={styles.title}>TBM 智能问答</h2>
            <p style={styles.subtitle}>当前日期：{date || "--"}</p>
          </div>
          <LlmToggle checked={useLlm} onChange={setUseLlm} />
        </div>
      )}

      {compact && (
        <div style={styles.compactOptions}>
          <LlmToggle checked={useLlm} onChange={setUseLlm} />
        </div>
      )}

      <div style={styles.queryRow}>
        <textarea
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="向 TBM Agent 提问..."
          style={styles.textarea}
        />
        <button
          type="button"
          onClick={handleRun}
          disabled={loading || !date || !query.trim()}
          style={{
            ...styles.button,
            opacity: loading || !date || !query.trim() ? 0.55 : 1,
          }}
        >
          {loading ? "分析中" : "提问"}
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
            <Meta label="执行计划" value={(result.plan || []).join(" -> ") || "--"} />
            <Meta label="路由专家" value={(result.routed_agents || []).join(" / ") || "--"} />
          </div>

          <pre style={styles.answer}>{result.answer || "暂无回答。"}</pre>

          <div style={styles.trace}>
            {(result.tool_results || []).map((item, index) => (
              <div key={`${item.tool}-${index}`} style={styles.traceItem}>
                <span style={styles.traceAgent}>{item.agent}</span>
                <span style={styles.traceTool}>{item.tool}</span>
                <span style={item.result?.success ? styles.ok : styles.fail}>
                  {item.result?.success ? "成功" : "失败"}
                </span>
              </div>
            ))}
          </div>
        </div>
      ) : (
        !loading && (
          <div style={styles.empty}>
            可以询问瓦斯、地质、工况、数字孪生或历史对比。
          </div>
        )
      )}

      {agents.length > 0 && (
        <div style={styles.capabilities}>
          {agents.map((agent) => (
            <div key={agent.name} style={styles.agentLine}>
              <strong>{agent.name}</strong>
              <span>{(agent.tools || []).join("，")}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function LlmToggle({ checked, onChange }) {
  return (
    <label style={styles.toggleLabel}>
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
      />
      使用 LLM 润色
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

const styles = {
  wrapper: {
    height: "100%",
    display: "flex",
    flexDirection: "column",
    gap: 14,
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
  compactOptions: {
    display: "flex",
    justifyContent: "flex-end",
  },
  toggleLabel: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    color: "#475569",
    fontSize: 13,
    whiteSpace: "nowrap",
  },
  queryRow: {
    display: "grid",
    gridTemplateColumns: "1fr 82px",
    gap: 10,
    alignItems: "stretch",
  },
  textarea: {
    minHeight: 78,
    resize: "vertical",
    border: "1px solid #cbd5e1",
    borderRadius: 10,
    padding: "10px 12px",
    fontSize: 14,
    lineHeight: 1.5,
    outline: "none",
  },
  button: {
    border: "none",
    borderRadius: 10,
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
    borderRadius: 999,
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
    borderRadius: 10,
    padding: 10,
    fontSize: 13,
  },
  result: {
    minHeight: 0,
    display: "flex",
    flexDirection: "column",
    gap: 12,
    overflow: "hidden",
  },
  metaGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
    gap: 10,
  },
  metaItem: {
    border: "1px solid #e2e8f0",
    borderRadius: 10,
    padding: 10,
    background: "#f8fafc",
    display: "flex",
    flexDirection: "column",
    gap: 4,
    minWidth: 0,
    fontSize: 12,
  },
  answer: {
    flex: 1,
    minHeight: 170,
    overflow: "auto",
    margin: 0,
    padding: 14,
    border: "1px solid #e2e8f0",
    borderRadius: 10,
    background: "#f8fafc",
    color: "#1e293b",
    whiteSpace: "pre-wrap",
    wordBreak: "break-word",
    fontFamily: "inherit",
    fontSize: 14,
    lineHeight: 1.7,
  },
  trace: {
    display: "flex",
    flexDirection: "column",
    gap: 6,
    maxHeight: 108,
    overflow: "auto",
  },
  traceItem: {
    display: "grid",
    gridTemplateColumns: "120px 1fr 52px",
    gap: 8,
    alignItems: "center",
    fontSize: 12,
  },
  traceAgent: {
    color: "#0f172a",
    fontWeight: 800,
  },
  traceTool: {
    color: "#475569",
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
  },
  ok: {
    color: "#15803d",
    textAlign: "right",
    fontWeight: 800,
  },
  fail: {
    color: "#b91c1c",
    textAlign: "right",
    fontWeight: 800,
  },
  empty: {
    color: "#94a3b8",
    textAlign: "center",
    padding: "32px 10px",
    border: "1px dashed #cbd5e1",
    borderRadius: 10,
  },
  capabilities: {
    borderTop: "1px solid #e2e8f0",
    paddingTop: 10,
    display: "grid",
    gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
    gap: 8,
    fontSize: 12,
    color: "#64748b",
    overflow: "auto",
  },
  agentLine: {
    display: "flex",
    flexDirection: "column",
    gap: 2,
    minWidth: 0,
  },
};
