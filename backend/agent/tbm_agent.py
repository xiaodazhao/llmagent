from __future__ import annotations

import re
from typing import Any, Callable, Optional

from agent.common import fail, ok
from agent.registry import describe_capabilities, resolve_tool, tool_agent_name
from agent.tbm_tools import TBMTools
from llm.llm_api import call_llm


DATE_RE = re.compile(r"\b(20\d{2}-\d{2}-\d{2})\b")


class TBMAgent:
    """A lightweight rule-planned agent for TBM analysis questions.

    This is intentionally small: it gives the project an agent-oriented
    interface without forcing a LangGraph dependency or changing the existing
    analysis pipeline.
    """

    def __init__(
        self,
        analyze_tbm_data: Callable,
        build_risk_profile: Callable,
        build_speed_profile: Callable,
    ):
        self.tools = TBMTools(
            analyze_tbm_data=analyze_tbm_data,
            build_risk_profile=build_risk_profile,
            build_speed_profile=build_speed_profile,
        )

    def capabilities(self) -> dict[str, Any]:
        return describe_capabilities()

    def run(
        self,
        query: str,
        date: Optional[str] = None,
        use_llm: bool = False,
    ) -> dict[str, Any]:
        query = (query or "").strip()
        if not query:
            return fail("query is required", tool="tbm_agent")

        selected_date = date or self._extract_date(query)
        plan = self._plan(query)
        tool_results = []
        self.tools.clear_cache()

        for step in plan:
            result = self._call_tool(step, selected_date)
            agent_name = tool_agent_name(step) or "UnknownAgent"
            tool_results.append({
                "agent": agent_name,
                "tool": step,
                "result": result,
            })
            if not result.get("success"):
                return fail(
                    result.get("message", "tool failed"),
                    tool="tbm_agent",
                    failed_agent=agent_name,
                    failed_tool=step,
                    trace=tool_results,
                )

        answer = self._build_answer(query, selected_date, tool_results)
        if use_llm:
            answer = self._polish_with_llm(query, answer, tool_results)

        return ok(
            {
                "query": query,
                "date": selected_date,
                "plan": plan,
                "routed_agents": self._routed_agents(tool_results),
                "answer": answer,
                "tool_results": tool_results,
            },
            "TBM agent completed.",
            tool="tbm_agent",
            planned_steps=len(plan),
        )

    def _plan(self, query: str) -> list[str]:
        q = query.lower()
        steps: list[str] = []

        if self._has_any(q, ["date", "dates", "available", "有哪些日期", "日期列表"]):
            return ["list_dates"]

        if self._has_any(q, ["load", "csv", "data", "数据", "字段", "样本"]):
            steps.append("load_day")

        if self._has_any(q, ["gas", "ch4", "co2", "h2s", "瓦斯", "气体", "超限"]):
            steps.append("analyze_gas")

        if self._has_any(q, ["geology", "geo", "地质", "围岩", "coupling", "耦合", "cri"]):
            steps.append("analyze_geology")

        if self._has_any(q, ["forward", "lookahead", "ahead", "前方", "超前", "预测", "预警"]):
            steps.append("analyze_forward_risk")

        if self._has_any(q, ["operation", "efficiency", "stop", "work", "工况", "施工状态", "停机", "效率", "掘进"]):
            steps.append("analyze_operation")

        if self._has_any(q, ["digital", "twin", "孪生", "状态快照"]):
            steps.append("get_digital_twin_state")

        if self._has_any(q, ["history", "compare", "trend", "历史", "对比", "趋势"]):
            steps.append("compare_history")

        if self._has_any(q, ["profile", "剖面", "曲线"]):
            steps.append("risk_profile")

        if not steps:
            steps.append("analyze_day")

        return self._dedupe(steps)

    def _call_tool(self, step: str, date: Optional[str]) -> dict[str, Any]:
        tool_fn = resolve_tool(self.tools, step)
        if tool_fn is None:
            return fail(f"unknown tool: {step}", tool=step)
        if step == "list_dates":
            return tool_fn()
        if step == "compare_history":
            return tool_fn(date=date)
        return tool_fn(date)
        return fail(f"unknown tool: {step}", tool=step)

    def _build_answer(
        self,
        query: str,
        date: Optional[str],
        tool_results: list[dict[str, Any]],
    ) -> str:
        lines = []
        target = date or "latest available date"
        plan_text = " -> ".join(f"{x['agent']}.{x['tool']}" for x in tool_results)
        lines.append(f"Agent plan for {target}: {plan_text}")

        for item in tool_results:
            tool = item["tool"]
            result = item["result"]
            data = result.get("data") or {}
            if tool == "list_dates":
                dates = data.get("dates", [])
                preview = ", ".join(dates[:8])
                lines.append(f"Available dates: {preview}" + (" ..." if len(dates) > 8 else ""))
            elif tool == "load_day":
                lines.append(f"Loaded {data.get('rows', 0)} rows from {data.get('path')}.")
            elif tool == "analyze_day":
                lines.extend(self._answer_day(data))
            elif tool == "analyze_operation":
                lines.extend(self._answer_operation(data))
            elif tool == "analyze_gas":
                lines.extend(self._answer_gas(data))
            elif tool == "analyze_geology":
                lines.extend(self._answer_geology(data))
            elif tool == "analyze_forward_risk":
                lines.extend(self._answer_forward(data))
            elif tool == "get_digital_twin_state":
                lines.extend(self._answer_twin(data))
            elif tool == "compare_history":
                lines.extend(self._answer_history(data))
            elif tool == "risk_profile":
                lines.extend(self._answer_profile(data))

        return "\n".join(line for line in lines if line)

    @staticmethod
    def _answer_day(data: dict[str, Any]) -> list[str]:
        op = data.get("operation", {})
        geo = data.get("geology", {})
        fwd = data.get("forward_risk", {})
        return [
            f"Operation: work {op.get('work_total_min', 0):.1f} min, stop {op.get('stop_total_min', 0):.1f} min, abnormal count {op.get('abnormal_count', 0)}.",
            f"Geology: high-risk segments {geo.get('high_risk_segment_count', 0)}, multi-source segments {geo.get('multi_source_segment_count', 0)}.",
            f"Forward risk: level={fwd.get('advice_level')}, high-risk evidence count={fwd.get('high_risk_count', 0)}.",
        ]

    @staticmethod
    def _answer_operation(data: dict[str, Any]) -> list[str]:
        stats = data.get("stats", {})
        return [
            f"Operation states: work_count={stats.get('work_count', 0)}, stop_count={stats.get('stop_count', 0)}, abnormal_count={stats.get('abnormal_count', 0)}.",
            f"Durations: work={stats.get('work_total_min', 0):.1f} min, stop={stats.get('stop_total_min', 0):.1f} min, transition={stats.get('transition_total_min', 0):.1f} min.",
        ]

    @staticmethod
    def _answer_gas(data: dict[str, Any]) -> list[str]:
        exceed_types = data.get("exceed_types", [])
        if exceed_types:
            return [f"Gas safety: exceedance detected for {', '.join(map(str, exceed_types))}."]
        return ["Gas safety: no gas exceedance detected in the available statistics."]

    @staticmethod
    def _answer_geology(data: dict[str, Any]) -> list[str]:
        summary = data.get("segment_summary", {})
        coupling = data.get("coupling_summary", {})
        return [
            f"Geology: has_geology={summary.get('has_geology', False)}, high-risk segments={summary.get('high_risk_segment_count', 0)}, multi-source segments={summary.get('multi_source_segment_count', 0)}.",
            f"Coupling: has_coupling={coupling.get('has_coupling', False)}, {coupling.get('summary_text', '')}",
        ]

    @staticmethod
    def _answer_forward(data: dict[str, Any]) -> list[str]:
        fwd = data.get("forward_risk", {})
        text = data.get("forward_risk_text", "")
        return [
            f"Forward risk: level={fwd.get('advice_level')}, lookahead={fwd.get('lookahead_m')} m, high-risk count={fwd.get('high_risk_count', 0)}.",
            text,
        ]

    @staticmethod
    def _answer_twin(data: dict[str, Any]) -> list[str]:
        twin = data.get("digital_twin_state", {})
        pos = twin.get("position_state", {})
        op = twin.get("operation_state", {})
        return [
            f"Digital twin: current chainage={pos.get('current_chainage_dk')}, advance={pos.get('advance_length')} m.",
            f"Dominant operation={op.get('dominant_state')}, work_ratio={op.get('work_ratio')}.",
        ]

    @staticmethod
    def _answer_history(data: dict[str, Any]) -> list[str]:
        comparison = data.get("history_comparison", {})
        return [
            f"History: has_history={comparison.get('has_history', False)}, count={comparison.get('history_count', 0)}.",
            comparison.get("comparison_text", ""),
        ]

    @staticmethod
    def _answer_profile(data: dict[str, Any]) -> list[str]:
        profile = data.get("risk_profile", {})
        high_segments = profile.get("high_segments", []) if isinstance(profile, dict) else []
        return [f"Risk profile: high segment count={len(high_segments)}."]

    @staticmethod
    def _polish_with_llm(
        query: str,
        draft_answer: str,
        tool_results: list[dict[str, Any]],
    ) -> str:
        prompt = (
            "You are a TBM construction-risk analysis assistant. "
            "Rewrite the draft answer in concise Chinese, preserving all numbers and caveats.\n\n"
            f"User question:\n{query}\n\n"
            f"Draft answer:\n{draft_answer}\n"
        )
        return call_llm(prompt)

    @staticmethod
    def _extract_date(query: str) -> Optional[str]:
        match = DATE_RE.search(query or "")
        return match.group(1) if match else None

    @staticmethod
    def _has_any(text: str, keywords: list[str]) -> bool:
        return any(k.lower() in text for k in keywords)

    @staticmethod
    def _dedupe(items: list[str]) -> list[str]:
        seen = set()
        out = []
        for item in items:
            if item not in seen:
                out.append(item)
                seen.add(item)
        return out

    @staticmethod
    def _routed_agents(tool_results: list[dict[str, Any]]) -> list[str]:
        agents = []
        for item in tool_results:
            agent = item.get("agent")
            if agent and agent not in agents:
                agents.append(agent)
        return agents
