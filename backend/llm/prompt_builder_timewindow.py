from __future__ import annotations

from services.cst_update_service import summarize_cst_for_prompt


def _safe_text(value, default: str = "无") -> str:
    """Return compact prompt text."""
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _pick(summary: dict, *keys, default="无"):
    """Return the first non-empty field from a summary dict."""
    for key in keys:
        value = summary.get(key)
        if value not in (None, "", {}, []):
            return value
    return default


def _summary_block(llm_summary: dict) -> str:
    """Build a compact CST-aware summary block for time-window prompts."""
    cst = llm_summary.get("CST") or llm_summary.get("Construction State Twin") or {}
    if isinstance(cst, dict) and cst:
        return summarize_cst_for_prompt(cst)

    operation = _pick(llm_summary, "基础工况统计", "operation_summary", default={})
    coupling = _pick(llm_summary, "区段地质-施工耦合分析", "coupling_summary", default={})
    forward = _pick(llm_summary, "前方风险提示摘要", "forward_risk_summary", default={})

    if not isinstance(operation, dict):
        operation = {}
    if not isinstance(coupling, dict):
        coupling = {}
    if not isinstance(forward, dict):
        forward = {}

    return "\n".join(
        [
            f"- 运行状态：工作 {operation.get('work_total_min', 0)} min，停机 {operation.get('stop_total_min', 0)} min。",
            f"- 前方提示：等级 {forward.get('advice_level', '无')}，高风险段 {forward.get('high_risk_count', 0)} 个。",
            f"- 耦合状态：{coupling.get('summary_text', '无')}",
        ]
    )


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
    forward_risk_text = _pick(llm_summary, "前方风险提示文本", "forward_risk_text")
    coupling_text = _pick(llm_summary, "区段地质-施工耦合分析", "coupling_summary")
    twin_text = _pick(llm_summary, "数字孪生状态", "digital_twin_state")
    summary_block = _summary_block(llm_summary)

    return f"""
你现在要撰写一份正式的《TBM施工时段工况分析报告》。

分析时间窗：
开始时间：{start_time}
结束时间：{end_time}

角色定位：你是一名TBM施工分析工程师，面向施工技术与管理人员输出正式的时段复盘报告。

核心任务：
请基于 CST 状态组织这段时间窗内的施工概况、局部异常、地质关注、耦合分析和安全提示，重点回答“这一时段发生了什么、为什么值得关注、后续应注意什么”。

写作约束：
1. 只围绕给定时间窗写作，不得扩展到其他日期或其他时段。
2. 只能依据给定信息写作，语言要客观、简洁、工程化。
3. 开篇必须说明该时段内 TBM 从哪一里程推进到哪一里程，累计推进多少米。
4. GRS 表示地质关注度，RAI 表示施工响应异常度，GRCI 表示地质-施工耦合关注证据，不能把它们写成已证实的灾害概率。
5. 必须区分当前揭示和前方提示，不能混写。
6. 若当前掌子面缺少与当前时段匹配的现场揭示资料，应明确说明资料不足；若仅有邻近掌子面的素描点记录，也必须说明其来源，不能直接写成当前掌子面实时直接观察，更不能拿超前预报替代。
7. 已开挖区段的耦合分析属于回顾性复核，不要写成“潜在风险段”；要说明这些关注信息主要来自既有超前资料，而本时段施工是否形成了印证。
8. 不要把常规停顿直接写成异常受阻，除非有明确支撑证据。
9. 如耦合证据不足，应明确写出“需谨慎解释”。
10. 不要输出程序字段名，不要写“根据提示词”“根据模型分析”等元叙述。
11. 不要在报告中出现“状态0、状态1、状态2、状态3”等内部编号，只能使用对应的语义名称。

建议章节：
1. 时段施工概况
2. 工况状态与施工节奏
3. 施工状态与效率分析
4. 稳定性与局部异常分析
5. 已开挖区段地质关注与地质-施工耦合复核
6. 气体监测分析
7. 前方区段关注提示
8. 结论与建议

补充要求：
- 第1节应明确写出该时段的推进范围与推进长度。
- 第5节重点写已开挖区段的回顾性复核，不要写“潜在风险”；要说明既有资料提示了什么，而本时段施工对这些提示形成了哪些印证或尚未形成哪些充分印证。
- 第7节重点写前方范围、风险类型、建议重点监测参数和支护/排水/补充验证措施；如果风险本身已经来自超前资料，不要泛泛重复“建议做超前预报”。
- 第8节建议分“主要结论”和“建议”两部分。

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

地质分析：
{_safe_text(geo_text)}

地质-施工耦合分析：
{_safe_text(coupling_text)}

数字孪生快照：
{_safe_text(twin_text)}

气体分析：
{_safe_text(gas_text)}

前方风险提示：
{_safe_text(forward_risk_text)}
"""
