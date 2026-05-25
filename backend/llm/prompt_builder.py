from __future__ import annotations

from services.cst_update_service import summarize_cst_for_prompt


def _format_list(values) -> str:
    """Format list-like values for compact Chinese prompt text."""
    if not values:
        return "无"
    if isinstance(values, str):
        text = values.strip()
        return text or "无"
    if isinstance(values, (list, tuple, set)):
        cleaned = [str(item).strip() for item in values if str(item).strip()]
        return "、".join(cleaned) if cleaned else "无"
    return str(values)


def _summary_block(llm_summary: dict) -> str:
    """Build a compact CST-first summary block."""
    cst = llm_summary.get("CST") or llm_summary.get("Construction State Twin") or {}
    if isinstance(cst, dict) and cst:
        return summarize_cst_for_prompt(cst)

    operation = (
        llm_summary.get("基础工况统计")
        or llm_summary.get("operation_summary")
        or {}
    )
    geology = (
        llm_summary.get("地质摘要_区段级")
        or llm_summary.get("geology_summary_segment")
        or {}
    )
    forward = (
        llm_summary.get("前方风险提示摘要")
        or llm_summary.get("forward_risk_summary")
        or {}
    )
    coupling = (
        llm_summary.get("区段风险-施工响应耦合分析")
        or llm_summary.get("coupling_summary")
        or {}
    )
    lines = [
        f"- 施工概况：工作 {operation.get('work_total_min', 0)} min，停机 {operation.get('stop_total_min', 0)} min，异常次数 {operation.get('abnormal_count', 0)}。",
        f"- 地质概况：高关注区段 {geology.get('high_risk_segment_count', 0)} 个，多源支撑区段 {geology.get('multi_source_segment_count', 0)} 个。",
        f"- 前方提示：等级={forward.get('advice_level', '无')}，高风险段数={forward.get('high_risk_count', 0)}，主要风险={_format_list(forward.get('main_hazards', []))}。",
        f"- 耦合摘要：{coupling.get('summary_text', '无')}",
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
    history_text = (
        llm_summary.get("施工历史记忆对比", {}).get("comparison_text")
        or llm_summary.get("history_comparison")
        or "暂无历史对比信息。"
    )
    forward_risk_text = (
        llm_summary.get("前方风险提示文本")
        or llm_summary.get("forward_risk_text")
        or "无"
    )
    summary_block = _summary_block(llm_summary)

    return f"""
你现在要撰写一份正式的《TBM综合施工工况分析报告》。

角色定位：
你是一名TBM施工分析工程师，面向项目管理和技术人员输出正式工程报告。请使用客观、简洁、审慎、工程化的中文表达。

写作约束：
1. 直接输出正式报告正文，不要写聊天式开场白。
2. 只能依据给定信息写作，不要虚构数字、现象或现场结论。
3. GRS 表示地质关注度，RAI 表示施工响应异常度，GRCI 表示地质-施工耦合关注证据，不能把它们写成已证实的灾害概率。
4. 必须严格区分“当前掌子面揭示情况”和“前方区段关注提示”。
5. 风险相关表述应使用“需关注”“提示”“表明”“显示”等审慎措辞，不能夸大成“已经发生灾害”。
6. 不能把所有停机都写成异常受阻，应结合常规停顿和施工节奏审慎判断。
7. 应保持空间连续性，除非证据非常明确，不要把相邻区段写成完全相反的结论。
8. 如果证据覆盖有限，应明确说明结论需谨慎解释。

报告标题：
TBM综合施工工况分析报告

建议章节：
1. 综合结论摘要
2. 总体施工运行概况
3. 基础工况统计分析
4. 施工状态识别与特征分析
5. 施工效率与稳定性分析
6. 当前掌子面地质情况
7. 前方区段地质关注与地质-施工耦合分析
8. 气体监测分析
9. 前方区段关注提示
10. 结论与建议

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

当前掌子面地质情况：
{face_geo_text}

前方区段地质融合分析：
{geo_text}

补充区段关注分析：
{risk_prob_text}

地质-施工耦合分析：
{coupling_text}

数字孪生快照：
{twin_text}

历史对比：
{history_text}

气体分析：
{gas_text}

前方风险提示：
{forward_risk_text}
"""
