from __future__ import annotations

from services.cst_update_service import summarize_cst_for_prompt


def _summary_block(llm_summary: dict) -> str:
    """Build a compact CST-aware summary block for time-window prompts."""
    cst = llm_summary.get("CST") or llm_summary.get("Construction State Twin") or {}
    if isinstance(cst, dict) and cst:
        return summarize_cst_for_prompt(cst)

    base = llm_summary.get("基础工况统计", {})
    coupling = llm_summary.get("区段风险-施工响应耦合分析", {})
    forward = llm_summary.get("前方风险提示摘要", {})
    lines = [
        f"- Operation summary: work={base.get('work_total_min', 0)} min, stop={base.get('stop_total_min', 0)} min.",
        f"- Forward attention: level={forward.get('advice_level', 'none')}, high_risk_count={forward.get('high_risk_count', 0)}.",
        f"- Coupling summary: {coupling.get('summary_text', 'none')}",
    ]
    return "\n".join(lines)


def build_prompt_timewindow(
    start_time: str,
    end_time: str,
    seg_text: str,
    stats_text: str,
    state_text: str,
    eff_text: str,
    state_stats_text: str,
    gas_text: str,
    geo_text: str,
    llm_summary: dict,
) -> str:
    """Build the time-window TBM report prompt."""
    forward_risk_text = llm_summary.get("前方风险提示文本", "none")
    coupling_text = llm_summary.get("区段风险-施工响应耦合分析", "none")
    twin_text = llm_summary.get("数字孪生状态", "none")
    summary_block = _summary_block(llm_summary)

    return f"""
Please write a formal TBM time-window construction condition analysis report.

Window:
start_time={start_time}
end_time={end_time}

Key constraints:
1. Focus only on the specified time window.
2. Use only the provided information and keep the wording engineering-oriented.
3. Do not turn attention prompts into confirmed hazard claims.
4. Separate current observations from forward attention.
5. Do not treat routine stoppages as abnormal obstruction without clear supporting evidence.
6. If evidence coverage is limited, explicitly state that the interpretation should remain cautious.

Required sections:
1. Time-Window Overview
2. Operation State and Rhythm
3. Construction State and Efficiency
4. Stability and Local Anomalies
5. Geological Attention and Geo-Response Analysis
6. Gas Monitoring
7. Forward Attention Reminder
8. Conclusions and Recommendations

Structured CST summary:
{summary_block}

Basic operation segments:
{seg_text}

Basic statistics:
{stats_text}

Construction states:
{state_text}

Efficiency statistics:
{eff_text}

State statistics:
{state_stats_text}

Geological analysis:
{geo_text}

Geo-response coupling analysis:
{coupling_text}

Digital twin snapshot:
{twin_text}

Gas analysis:
{gas_text}

Forward risk reminder:
{forward_risk_text}
"""
