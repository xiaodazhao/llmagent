from __future__ import annotations

from services.cst_update_service import summarize_cst_for_prompt


def _summary_block(llm_summary: dict) -> str:
    """Build a compact CST-aware summary block for time-window prompts."""
    cst = llm_summary.get("CST") or llm_summary.get("Construction State Twin") or {}
    if isinstance(cst, dict) and cst:
        return summarize_cst_for_prompt(cst)

    operation = (
        llm_summary.get("基础工况统计")
        or llm_summary.get("operation_summary")
        or {}
    )
    coupling = (
        llm_summary.get("区段风险-施工响应耦合分析")
        or llm_summary.get("coupling_summary")
        or {}
    )
    forward = (
        llm_summary.get("前方风险提示摘要")
        or llm_summary.get("forward_risk_summary")
        or {}
    )
    lines = [
        f"- 施工概况：工作 {operation.get('work_total_min', 0)} min，停机 {operation.get('stop_total_min', 0)} min。",
        f"- 前方提示：等级={forward.get('advice_level', '无')}，高风险段数={forward.get('high_risk_count', 0)}。",
        f"- 耦合摘要：{coupling.get('summary_text', '无')}",
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
    forward_risk_text = (
        llm_summary.get("前方风险提示文本")
        or llm_summary.get("forward_risk_text")
        or "无"
    )
    coupling_text = (
        llm_summary.get("区段风险-施工响应耦合分析")
        or llm_summary.get("coupling_summary")
        or "无"
    )
    twin_text = (
        llm_summary.get("数字孪生状态")
        or llm_summary.get("digital_twin_state")
        or "无"
    )
    summary_block = _summary_block(llm_summary)

    return f"""
你现在要撰写一份正式的《TBM施工时段工况分析报告》。

分析时间窗：
开始时间：{start_time}
结束时间：{end_time}

写作约束：
1. 只围绕给定时间窗写作，不能扩展到其他日期或其他时间段。
2. 只能依据给定信息写作，语言要客观、简洁、工程化。
3. 不能把关注提示写成已发生灾害。
4. 必须区分当前揭示信息和前方区段关注信息。
5. 不能把常规停顿直接写成异常受阻，除非有明确支撑证据。
6. 如果证据覆盖有限，应明确说明结论需谨慎解释。

建议章节：
1. 时段施工概况
2. 工况状态与施工节奏
3. 施工状态与效率分析
4. 稳定性与局部异常分析
5. 地质关注与地质-施工耦合分析
6. 气体监测分析
7. 前方关注提示
8. 结论与建议

结构化 CST 摘要：
{summary_block}

基础工况分段：
{seg_text}

基础统计：
{stats_text}

施工状态：
{state_text}

效率统计：
{eff_text}

状态统计：
{state_stats_text}

地质分析：
{geo_text}

地质-施工耦合分析：
{coupling_text}

数字孪生快照：
{twin_text}

气体分析：
{gas_text}

前方风险提示：
{forward_risk_text}
"""
