from __future__ import annotations

from services.cst_update_service import summarize_cst_for_prompt


def _format_list(values) -> str:
    """Format list-like values for compact prompt text."""
    if not values:
        return "none"
    if isinstance(values, str):
        text = values.strip()
        return text or "none"
    if isinstance(values, (list, tuple, set)):
        cleaned = [str(item).strip() for item in values if str(item).strip()]
        return ", ".join(cleaned) if cleaned else "none"
    return str(values)


def _summary_block(llm_summary: dict) -> str:
    """Build a compact CST-first summary block."""
    cst = llm_summary.get("CST") or llm_summary.get("Construction State Twin") or {}
    if isinstance(cst, dict) and cst:
        return summarize_cst_for_prompt(cst)

    base = llm_summary.get("基础工况统计", {})
    geo = llm_summary.get("地质摘要_区段级", {})
    forward = llm_summary.get("前方风险提示摘要", {})
    coupling = llm_summary.get("区段风险-施工响应耦合分析", {})
    lines = [
        f"- Operation summary: work={base.get('work_total_min', 0)} min, stop={base.get('stop_total_min', 0)} min, abnormal_count={base.get('abnormal_count', 0)}.",
        f"- Geological summary: high_risk_segments={geo.get('high_risk_segment_count', 0)}, multi_source_segments={geo.get('multi_source_segment_count', 0)}.",
        f"- Forward attention: level={forward.get('advice_level', 'none')}, high_risk_count={forward.get('high_risk_count', 0)}, hazards={_format_list(forward.get('main_hazards', []))}.",
        f"- Coupling summary: {coupling.get('summary_text', 'none')}",
    ]
    return "\n".join(lines)


def build_prompt(
    seg_text: str,
    stats_text: str,
    state_text: str,
    eff_text: str,
    state_stats_text: str,
    gas_text: str,
    geo_text: str,
    face_geo_text: str,
    llm_summary: dict,
    risk_prob_text: str,
) -> str:
    """Build the daily TBM report prompt."""
    coupling_text = llm_summary.get("区段风险-施工响应耦合分析", "none")
    twin_text = llm_summary.get("数字孪生状态", "none")
    history_text = llm_summary.get("施工历史记忆对比", {}).get("comparison_text", "No history comparison is available.")
    forward_risk_text = llm_summary.get("前方风险提示文本", "none")
    summary_block = _summary_block(llm_summary)

    return f"""
You are writing a formal TBM comprehensive construction condition analysis report.

Role:
You are a TBM construction analysis engineer preparing a formal engineering report for project managers and technical staff. Use objective, concise, engineering-oriented language.

Key constraints:
1. Output the report directly. Do not add conversational introductions.
2. Use only the provided information. Do not invent unsupported numbers or field observations.
3. Treat GRS as geological attention, RAI as response anomaly, and GRCI as geo-response coupling evidence. Do not describe them as confirmed hazard probabilities.
4. Strictly separate current face observations from forward geological attention.
5. Use cautious wording such as "requires attention", "suggests", or "indicates" for risk-related statements.
6. Do not treat every stoppage as abnormal obstruction. Consider routine pauses and regular construction rhythm.
7. Preserve spatial continuity. Avoid describing adjacent segments as abruptly contradictory unless the evidence clearly supports that.
8. If evidence coverage is limited, state that interpretation should remain cautious.

Title:
TBM Comprehensive Construction Condition Analysis Report

Required sections:
1. Executive Summary
2. Overall Operation Overview
3. Basic Operation Statistics
4. Construction State Identification
5. Construction Efficiency Analysis
6. Construction Stability Analysis
7. Current Face Geological Condition
8. Forward Geological Attention and Geo-Response Coupling Analysis
9. Gas Monitoring Analysis
10. Forward Section Attention Reminder
11. Conclusions and Recommendations

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

Current face geological condition:
{face_geo_text}

Forward geological fusion analysis:
{geo_text}

Additional section-level attention analysis:
{risk_prob_text}

Geo-response coupling analysis:
{coupling_text}

Digital twin snapshot:
{twin_text}

History comparison:
{history_text}

Gas analysis:
{gas_text}

Forward risk reminder:
{forward_risk_text}
"""
