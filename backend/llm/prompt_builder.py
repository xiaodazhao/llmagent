from __future__ import annotations

from services.cst_update_service import summarize_cst_for_prompt


def _safe_text(value, default: str = "无") -> str:
    """Return compact prompt text."""
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _format_list(values) -> str:
    """Format list-like values into compact Chinese text."""
    if not values:
        return "无"
    if isinstance(values, str):
        text = values.strip()
        return text or "无"
    if isinstance(values, (list, tuple, set)):
        cleaned = [str(item).strip() for item in values if str(item).strip()]
        return "、".join(cleaned) if cleaned else "无"
    return str(values)


def _pick(summary: dict, *keys, default="无"):
    """Return the first non-empty field from a summary dict."""
    for key in keys:
        value = summary.get(key)
        if value not in (None, "", {}, []):
            return value
    return default


def _summary_block(llm_summary: dict) -> str:
    """Build a compact CST-first summary block."""
    cst = llm_summary.get("CST") or llm_summary.get("Construction State Twin") or {}
    if isinstance(cst, dict) and cst:
        return summarize_cst_for_prompt(cst)

    operation = _pick(llm_summary, "基础工况统计", "operation_summary", default={})
    geology = _pick(llm_summary, "地质摘要_区段级", "geology_summary_segment", default={})
    forward = _pick(llm_summary, "前方风险提示摘要", "forward_risk_summary", default={})
    coupling = _pick(llm_summary, "区段地质-施工耦合分析", "coupling_summary", default={})

    if not isinstance(operation, dict):
        operation = {}
    if not isinstance(geology, dict):
        geology = {}
    if not isinstance(forward, dict):
        forward = {}
    if not isinstance(coupling, dict):
        coupling = {}

    return "\n".join(
        [
            f"- 运行状态：工作 {operation.get('work_total_min', 0)} min，停机 {operation.get('stop_total_min', 0)} min，异常段 {operation.get('abnormal_count', 0)} 个。",
            f"- 地质状态：高关注区段 {geology.get('high_risk_segment_count', 0)} 个，多源支撑区段 {geology.get('multi_source_segment_count', 0)} 个。",
            f"- 前方提示：等级 {forward.get('advice_level', '无')}，高风险段 {forward.get('high_risk_count', 0)} 个，主要风险 {_format_list(forward.get('main_hazards', []))}。",
            f"- 耦合状态：{coupling.get('summary_text', '无')}",
        ]
    )


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
    coupling_text = _pick(llm_summary, "区段地质-施工耦合分析", "coupling_summary")
    twin_text = _pick(llm_summary, "数字孪生状态", "digital_twin_state")
    history_text = (
        llm_summary.get("施工历史记忆对比", {}).get("comparison_text")
        or llm_summary.get("history_comparison")
        or "暂无历史对比信息。"
    )
    forward_risk_text = _pick(llm_summary, "前方风险提示文本", "forward_risk_text")
    summary_block = _summary_block(llm_summary)

    return f"""
你现在要撰写一份正式的《TBM综合施工工况分析报告》。

角色定位：你是一名TBM施工分析工程师，面向项目管理人员、施工技术人员和安全管理人员输出正式工程报告。

核心任务：
请优先依据“结构化 CST 摘要”组织报告，再使用补充状态文本完善细节。报告必须体现以下状态逻辑：
1. 时间状态：本次分析对应的日期与分析时段。
2. 空间状态：今日从哪一里程推进到哪一里程、累计推进多少米、当前掌子面在哪、前方关注范围在哪。
3. 运行状态：工作/停机比例、主导工况、状态切换、效率与稳定性。
4. 地质状态：邻近掌子面的现场素描/揭示、已开挖区段回顾性耦合复核、前方区段关注提示。
5. 响应状态：施工参数异常、停机影响、RAI 相关表现。
6. 关注状态：GRS、GRCI、高关注区段、前方提示、历史变化。

写作约束：
1. 直接输出正式报告正文，不要写聊天式开场白。
2. 只能依据给定信息写作，不要虚构数字、现象或现场结论。
3. 开篇必须明确写出：今日/本时段 TBM 从哪一里程推进到哪一里程，累计推进多少米。
4. GRS 表示地质关注度，RAI 表示施工响应异常度，GRCI 表示地质-施工耦合关注证据，不能把它们写成已证实的灾害概率。
5. 必须严格区分“当前掌子面揭示情况”和“前方区段关注提示”：
   - 第6节只写与当前掌子面邻近的现场素描/揭示信息，必须写清信息来源是“现场素描点揭示”还是“与掌子面邻近的揭示记录”。
   - 如果当前掌子面缺少与当前里程匹配的现场揭示资料，必须明确说明“当前掌子面直接揭示资料不足”，不能用超前预报、远离掌子面的素描或前方预测替代当前掌子面描述。
   - 除非输入明确表明素描点与当前掌子面里程一致，否则不要写“基于现场观察”“资料充分”“当前掌子面已直接揭示”等确定性表述；如果输入中出现“距当前掌子面最近的现场素描点揭示”或“与当前掌子面邻近的揭示记录”，报告中必须保留这种限定说法，不能自行改写成“当前掌子面揭示”。
   - 第7节写已开挖区段的回顾性地质-施工耦合复核，不能写成“潜在风险段”或“尚未开挖区段风险”。
   - 第9节只写前方区段提示，不要与当前掌子面混写。
6. 风险相关表述应使用“需关注”“提示”“显示”“表明”“建议核查”等审慎措辞，不得夸大为“已发生灾害”。
7. 不要把所有停机都写成异常受阻，应结合常规停顿和施工节奏审慎判断。
8. 相邻区段表述应保持空间连续性，除非证据非常明确，不要写成截然相反的结论。
9. 如果地质-施工耦合证据不足，应明确写出“需谨慎解释”。
10. 如果证据覆盖有限，应明确说明结论存在局限。
11. 不要输出程序字段名，不要写“根据提示词”“根据模型分析”等元叙述。
12. 不要在报告中出现“状态0、状态1、状态2、状态3”等内部编号，只能使用对应的语义名称，如“高负载稳定推进状态”“低负载调整状态”“高推力低速受阻状态”等。

建议章节：
1. 综合结论摘要
2. 总体施工运行概况
3. 基础工况统计分析
4. 施工状态识别与特征分析
5. 施工效率与稳定性分析
6. 当前掌子面地质情况
7. 已开挖区段地质关注与地质-施工耦合复核
8. 气体监测分析
9. 前方区段关注提示
10. 结论与建议

补充要求：
- 第1节必须概括运行、地质、气体、前方提示和历史变化，并明确写出今日推进范围。
- 第2节必须明确写出从哪一里程推进到哪一里程、累计推进多少米。
- 第6节如果没有当前掌子面现场揭示，就明确说资料不足；如果有的只是邻近掌子面的现场素描点，也必须说明“该描述来自邻近点位素描/揭示”，不要写成对当前掌子面的实时直接观察。
- 第7节重点解释已开挖区段中哪些区段呈现较高 GRS / RAI / GRCI；这些关注信息主要来自既有超前地质预报、现场素描或历史地质资料，本次施工过程中哪些现象形成了印证（如停机增多、参数波动、局部出水/掉块），哪些尚未形成充分印证，都要分别写清楚；不要把已经挖过的区段写成“潜在风险区段”。
- 第8节重点写超阈值气体、持续时间、主要风险和安全建议。
- 第9节要写清楚：前方范围、风险提示段数量、高风险段数量、主要风险类型，以及既有超前资料在各里程段提示了什么；如果前方风险本身已经来自超前预报/物探资料，就不要再泛泛重复“建议做超前预报”，除非是建议补充验证或加密核查。
- 第10节建议分“主要结论”和“建议”两部分。

结构化 CST 摘要：
{summary_block}

基础工况分段：
{_safe_text(seg_text)}

基础统计：
{_safe_text(stats_text)}

施工状态：
{_safe_text(state_text)}

效率统计：
{_safe_text(eff_text)}

状态统计：
{_safe_text(state_stats_text)}

当前掌子面地质情况：
{_safe_text(face_geo_text)}

前方区段地质融合分析：
{_safe_text(geo_text)}

补充区段关注分析：
{_safe_text(risk_prob_text)}

地质-施工耦合分析：
{_safe_text(coupling_text)}

数字孪生快照：
{_safe_text(twin_text)}

历史对比：
{_safe_text(history_text)}

气体分析：
{_safe_text(gas_text)}

前方风险提示：
{_safe_text(forward_risk_text)}
"""
