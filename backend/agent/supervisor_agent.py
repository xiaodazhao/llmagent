from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable, Optional

from agent.common import fail, ok
from agent.registry import describe_capabilities
from agent.tbm_tools import TBMTools
from llm.llm_api import call_llm


DATE_RE = re.compile(r"\b(20\d{2}-\d{2}-\d{2})\b")


@dataclass(frozen=True)
class SupervisorStep:
    agent: str
    tools: tuple[str, ...]
    reason: str


class DomainAgent:
    """Small specialist wrapper around the shared TBM tool layer."""

    def __init__(self, name: str, description: str, tools: TBMTools):
        self.name = name
        self.description = description
        self.tools = tools

    def run(self, tool_names: list[str], date: Optional[str]) -> dict[str, Any]:
        trace = []
        for tool_name in tool_names:
            result = self._call_tool(tool_name, date)
            trace.append({
                "agent": self.name,
                "tool": tool_name,
                "result": result,
            })
            if not result.get("success"):
                return fail(
                    result.get("message", "tool failed"),
                    agent=self.name,
                    failed_tool=tool_name,
                    trace=trace,
                )

        return ok(
            {
                "agent": self.name,
                "tool_results": trace,
            },
            f"{self.name} completed.",
            agent=self.name,
            tool_count=len(trace),
        )

    def _call_tool(self, tool_name: str, date: Optional[str]) -> dict[str, Any]:
        tool_fn = getattr(self.tools, tool_name, None)
        if tool_fn is None:
            return fail(f"unknown tool: {tool_name}", agent=self.name, tool=tool_name)
        if tool_name == "list_dates":
            return tool_fn()
        if tool_name == "compare_history":
            return tool_fn(date=date)
        return tool_fn(date)


class TBMSupervisorAgent:
    """Supervisor-style multi-agent coordinator for TBM analysis.

    This keeps the existing analysis pipeline intact while changing the agent
    shape from one rule-planned agent into a supervisor plus domain agents.
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
        self.domain_agents = {
            "DataAgent": DomainAgent(
                "DataAgent",
                "Find available dates, load CSV files, and run compact daily analysis.",
                self.tools,
            ),
            "OperationAgent": DomainAgent(
                "OperationAgent",
                "Analyze work, stop, transition, abnormal states, and efficiency.",
                self.tools,
            ),
            "SafetyAgent": DomainAgent(
                "SafetyAgent",
                "Analyze gas statistics and exceedance events.",
                self.tools,
            ),
            "GeologyAgent": DomainAgent(
                "GeologyAgent",
                "Analyze geology fusion, forward risk, coupling, risk and speed profiles.",
                self.tools,
            ),
            "TwinAgent": DomainAgent(
                "TwinAgent",
                "Build the compact digital-twin state snapshot.",
                self.tools,
            ),
            "MemoryAgent": DomainAgent(
                "MemoryAgent",
                "Compare the selected analysis with saved history memory.",
                self.tools,
            ),
        }

    def capabilities(self) -> dict[str, Any]:
        capabilities = describe_capabilities()
        capabilities["supervisor"] = {
            "name": "TBMSupervisorAgent",
            "description": "Routes user requests to specialist TBM domain agents.",
            "active_agents": list(self.domain_agents.keys()),
            "mode": "supervisor-style",
        }
        return capabilities

    def run(
        self,
        query: str,
        date: Optional[str] = None,
        use_llm: bool = False,
        verbose: bool = False,
    ) -> dict[str, Any]:
        query = (query or "").strip()
        if not query:
            return fail("query is required", tool="tbm_supervisor_agent")

        selected_date = date or self._extract_date(query)
        supervisor_plan = self._plan(query)
        self.tools.clear_cache()

        agent_results = []
        flat_tool_results = []
        for step in supervisor_plan:
            agent = self.domain_agents.get(step.agent)
            if agent is None:
                return fail(
                    f"unknown agent: {step.agent}",
                    tool="tbm_supervisor_agent",
                    failed_agent=step.agent,
                )

            result = agent.run(list(step.tools), selected_date)
            agent_results.append({
                "agent": step.agent,
                "reason": step.reason,
                "tools": list(step.tools),
                "result": result,
            })
            flat_tool_results.extend((result.get("data") or {}).get("tool_results", []))

            if not result.get("success"):
                return fail(
                    result.get("message", "agent failed"),
                    tool="tbm_supervisor_agent",
                    failed_agent=step.agent,
                    trace=agent_results,
                )

        answer = self._build_answer(query, selected_date, supervisor_plan, flat_tool_results)
        if use_llm:
            answer = self._polish_with_llm(query, answer)

        payload = {
            "query": query,
            "date": selected_date,
            "mode": "supervisor_v2",
            "verbose": verbose,
            "supervisor_plan": [
                {
                    "agent": step.agent,
                    "tools": list(step.tools),
                    "reason": step.reason,
                }
                for step in supervisor_plan
            ],
            "routed_agents": [step.agent for step in supervisor_plan],
            "answer": answer,
            "highlights": self._build_highlights(flat_tool_results),
            "agent_results": self._compact_agent_results(agent_results),
            "tool_results": self._compact_tool_results(flat_tool_results),
        }
        if verbose:
            payload["agent_results"] = agent_results
            payload["tool_results"] = flat_tool_results

        return ok(
            payload,
            "TBM supervisor completed.",
            tool="tbm_supervisor_agent",
            routed_agents=len(supervisor_plan),
            tool_calls=len(flat_tool_results),
        )

    def _plan(self, query: str) -> list[SupervisorStep]:
        q = query.lower()
        steps: list[SupervisorStep] = []

        if self._has_any(q, ["date", "dates", "available", "日期", "有哪些数据"]):
            return [
                SupervisorStep(
                    agent="DataAgent",
                    tools=("list_dates",),
                    reason="用户询问可用数据日期。",
                )
            ]

        if self._has_any(q, ["load", "csv", "data", "加载", "读取", "数据文件"]):
            steps.append(SupervisorStep(
                agent="DataAgent",
                tools=("load_day",),
                reason="请求需要读取数据文件并返回基础元信息。",
            ))

        if self._has_any(q, ["summary", "daily", "overview", "report", "总览", "概况", "日报", "总结"]):
            steps.append(SupervisorStep(
                agent="DataAgent",
                tools=("analyze_day",),
                reason="用户需要当天综合分析摘要。",
            ))

        if self._has_any(q, ["operation", "efficiency", "stop", "work", "state", "工况", "效率", "停机", "工作", "施工状态"]):
            steps.append(SupervisorStep(
                agent="OperationAgent",
                tools=("analyze_operation",),
                reason="请求涉及施工状态、工作停机或效率分析。",
            ))

        if self._has_any(q, ["gas", "ch4", "co2", "h2s", "瓦斯", "甲烷", "气体", "超限"]):
            steps.append(SupervisorStep(
                agent="SafetyAgent",
                tools=("analyze_gas",),
                reason="请求涉及瓦斯或气体安全分析。",
            ))

        geology_tools = []
        if self._has_any(q, ["geology", "geo", "coupling", "cri", "地质", "围岩", "耦合"]):
            geology_tools.append("analyze_geology")
        if self._has_any(q, ["forward", "lookahead", "ahead", "前方", "超前", "预测"]):
            geology_tools.append("analyze_forward_risk")
        if self._has_any(q, ["profile", "risk profile", "speed profile", "风险剖面", "速度剖面", "沿程"]):
            geology_tools.append("risk_profile")
        if geology_tools:
            steps.append(SupervisorStep(
                agent="GeologyAgent",
                tools=tuple(self._dedupe(geology_tools)),
                reason="请求涉及地质、前方风险、耦合或沿程剖面分析。",
            ))

        if self._has_any(q, ["digital", "twin", "数字孪生", "孪生", "状态快照"]):
            steps.append(SupervisorStep(
                agent="TwinAgent",
                tools=("get_digital_twin_state",),
                reason="请求需要数字孪生状态快照。",
            ))

        if self._has_any(q, ["history", "compare", "trend", "历史", "对比", "趋势"]):
            steps.append(SupervisorStep(
                agent="MemoryAgent",
                tools=("compare_history",),
                reason="请求需要历史记忆对比。",
            ))

        if not steps:
            steps.append(SupervisorStep(
                agent="DataAgent",
                tools=("analyze_day",),
                reason="未识别到更具体的专业意图，执行当天综合分析。",
            ))

        return self._merge_agent_steps(steps)

    def _build_answer(
        self,
        query: str,
        date: Optional[str],
        supervisor_plan: list[SupervisorStep],
        tool_results: list[dict[str, Any]],
    ) -> str:
        target = date or "最新可用日期"
        lines = [
            f"Supervisor 调度计划（{target}）："
            + " -> ".join(f"{step.agent}({', '.join(step.tools)})" for step in supervisor_plan)
        ]

        for item in tool_results:
            agent = item.get("agent", "")
            tool = item.get("tool", "")
            result = item.get("result", {})
            data = result.get("data") or {}

            if tool == "list_dates":
                dates = data.get("dates", [])
                preview = ", ".join(dates[:8])
                lines.append(f"{agent}: 共找到 {len(dates)} 个可用日期，最近包括：{preview}" + (" ..." if len(dates) > 8 else ""))
            elif tool == "load_day":
                lines.append(f"{agent}: 已加载 {data.get('rows', 0)} 行数据，文件：{data.get('path')}。")
            elif tool == "analyze_day":
                lines.extend(self._answer_day(agent, data))
            elif tool == "analyze_operation":
                lines.extend(self._answer_operation(agent, data))
            elif tool == "analyze_gas":
                lines.extend(self._answer_gas(agent, data))
            elif tool == "analyze_geology":
                lines.extend(self._answer_geology(agent, data))
            elif tool == "analyze_forward_risk":
                lines.extend(self._answer_forward(agent, data))
            elif tool == "risk_profile":
                lines.extend(self._answer_profile(agent, data))
            elif tool == "get_digital_twin_state":
                lines.extend(self._answer_twin(agent, data))
            elif tool == "compare_history":
                lines.extend(self._answer_history(agent, data))

        return "\n".join(line for line in lines if line)

    @staticmethod
    def _answer_day(agent: str, data: dict[str, Any]) -> list[str]:
        op = data.get("operation", {})
        geo = data.get("geology", {})
        fwd = data.get("forward_risk", {})
        return [
            f"{agent}: 工作 {op.get('work_total_min', 0):.1f} min，停机 {op.get('stop_total_min', 0):.1f} min，异常次数 {op.get('abnormal_count', 0)}。",
            f"{agent}: 地质高风险区段 {geo.get('high_risk_segment_count', 0)} 个，多源证据区段 {geo.get('multi_source_segment_count', 0)} 个。",
            f"{agent}: 前方风险等级={fwd.get('advice_level')}，高风险证据数量={fwd.get('high_risk_count', 0)}。",
        ]

    @staticmethod
    def _answer_operation(agent: str, data: dict[str, Any]) -> list[str]:
        stats = data.get("stats", {})
        return [
            f"{agent}: 工作次数={stats.get('work_count', 0)}，停机次数={stats.get('stop_count', 0)}，异常次数={stats.get('abnormal_count', 0)}。",
            f"{agent}: 工作={stats.get('work_total_min', 0):.1f} min，停机={stats.get('stop_total_min', 0):.1f} min，过渡={stats.get('transition_total_min', 0):.1f} min。",
        ]

    @staticmethod
    def _answer_gas(agent: str, data: dict[str, Any]) -> list[str]:
        exceed_types = data.get("exceed_types", [])
        if exceed_types:
            return [f"{agent}: 检测到气体超限类型：{', '.join(map(str, exceed_types))}。"]
        return [f"{agent}: 当前统计中未检测到气体超限。"]

    @staticmethod
    def _answer_geology(agent: str, data: dict[str, Any]) -> list[str]:
        summary = data.get("segment_summary", {})
        coupling = data.get("coupling_summary", {})
        return [
            f"{agent}: 地质匹配={summary.get('has_geology', False)}，高风险区段={summary.get('high_risk_segment_count', 0)}，多源证据区段={summary.get('multi_source_segment_count', 0)}。",
            f"{agent}: 耦合分析={coupling.get('has_coupling', False)}，{coupling.get('summary_text', '')}",
        ]

    @staticmethod
    def _answer_forward(agent: str, data: dict[str, Any]) -> list[str]:
        fwd = data.get("forward_risk", {})
        return [
            f"{agent}: 前方风险等级={fwd.get('advice_level')}，前探距离={fwd.get('lookahead_m')} m，高风险数量={fwd.get('high_risk_count', 0)}。",
            data.get("forward_risk_text", ""),
        ]

    @staticmethod
    def _answer_profile(agent: str, data: dict[str, Any]) -> list[str]:
        profile = data.get("risk_profile", {})
        high_segments = profile.get("high_segments", []) if isinstance(profile, dict) else []
        speed_profile = data.get("speed_profile", [])
        return [
            f"{agent}: 风险高关注区段={len(high_segments)} 个，速度剖面点数={len(speed_profile)}。"
        ]

    @staticmethod
    def _answer_twin(agent: str, data: dict[str, Any]) -> list[str]:
        twin = data.get("digital_twin_state", {})
        pos = twin.get("position_state", {})
        op = twin.get("operation_state", {})
        return [
            f"{agent}: 当前里程={pos.get('current_chainage_dk')}，推进长度={pos.get('advance_length')} m。",
            f"{agent}: 主导工况={op.get('dominant_state')}，工作占比={op.get('work_ratio')}。",
        ]

    @staticmethod
    def _answer_history(agent: str, data: dict[str, Any]) -> list[str]:
        comparison = data.get("history_comparison", {})
        return [
            f"{agent}: 有历史记录={comparison.get('has_history', False)}，对比记录数={comparison.get('history_count', 0)}。",
            comparison.get("comparison_text", ""),
        ]

    @classmethod
    def _compact_agent_results(cls, agent_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        compact = []
        for item in agent_results:
            result = item.get("result", {})
            tool_results = (result.get("data") or {}).get("tool_results", [])
            compact.append({
                "agent": item.get("agent"),
                "reason": item.get("reason"),
                "tools": item.get("tools", []),
                "success": bool(result.get("success")),
                "message": result.get("message", ""),
                "tool_count": len(tool_results),
            })
        return compact

    @classmethod
    def _compact_tool_results(cls, tool_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        compact = []
        for item in tool_results:
            result = item.get("result", {})
            compact.append({
                "agent": item.get("agent"),
                "tool": item.get("tool"),
                "success": bool(result.get("success")),
                "message": result.get("message", ""),
                "summary": cls._tool_summary(item.get("tool", ""), result.get("data") or {}),
            })
        return compact

    @classmethod
    def _tool_summary(cls, tool: str, data: dict[str, Any]) -> dict[str, Any]:
        if tool == "list_dates":
            dates = data.get("dates", [])
            return {
                "date_count": len(dates),
                "preview_dates": dates[:8],
            }
        if tool == "load_day":
            return {
                "date": data.get("date"),
                "rows": data.get("rows", 0),
                "column_count": len(data.get("columns", []) or []),
                "path": data.get("path"),
            }
        if tool == "analyze_day":
            return {
                "date": data.get("date"),
                "operation": data.get("operation", {}),
                "geology": data.get("geology", {}),
                "forward_risk": data.get("forward_risk", {}),
                "coupling": data.get("coupling", {}),
            }
        if tool == "analyze_operation":
            stats = data.get("stats", {})
            return {
                "date": data.get("date"),
                "work_count": stats.get("work_count", 0),
                "stop_count": stats.get("stop_count", 0),
                "abnormal_count": stats.get("abnormal_count", 0),
                "work_total_min": stats.get("work_total_min", 0),
                "stop_total_min": stats.get("stop_total_min", 0),
            }
        if tool == "analyze_gas":
            gas_stats = data.get("gas_stats", {})
            gas_all = gas_stats.get("all", {}) if isinstance(gas_stats, dict) else {}
            exceed_types = data.get("exceed_types", [])
            return {
                "date": data.get("date"),
                "exceed_types": exceed_types,
                "exceed_type_count": len(exceed_types),
                "gas_count": len(gas_all),
            }
        if tool == "analyze_geology":
            coupling = data.get("coupling_summary", {})
            top_segments = coupling.get("top_segments", []) if isinstance(coupling, dict) else []
            top = top_segments[0] if top_segments else {}
            return {
                "date": data.get("date"),
                "record_has_geology": (data.get("record_summary") or {}).get("has_geology", False),
                "segment_count": data.get("segment_count", 0),
                "high_risk_segment_count": (data.get("segment_summary") or {}).get("high_risk_segment_count", 0),
                "multi_source_segment_count": (data.get("segment_summary") or {}).get("multi_source_segment_count", 0),
                "top_coupling_segment": top.get("segment"),
                "top_coupling_index": top.get("risk_response_coupling_index"),
                "top_coupling_label": top.get("coupling_label"),
            }
        if tool == "analyze_forward_risk":
            fwd = data.get("forward_risk", {})
            return {
                "date": data.get("date"),
                "has_forward_risk": fwd.get("has_forward_risk", False),
                "advice_level": fwd.get("advice_level"),
                "lookahead_m": fwd.get("lookahead_m"),
                "high_risk_count": fwd.get("high_risk_count", 0),
                "main_hazards": fwd.get("main_hazards", []),
            }
        if tool == "risk_profile":
            profile = data.get("risk_profile", {})
            high_segments = profile.get("high_segments", []) if isinstance(profile, dict) else []
            return {
                "date": data.get("date"),
                "high_segment_count": len(high_segments),
                "profile_count": len(profile.get("profile", []) if isinstance(profile, dict) else []),
                "speed_profile_count": len(data.get("speed_profile", []) or []),
            }
        if tool == "get_digital_twin_state":
            twin = data.get("digital_twin_state", {})
            return {
                "date": data.get("date"),
                "position_state": twin.get("position_state", {}),
                "operation_state": twin.get("operation_state", {}),
                "safety_state": twin.get("safety_state", {}),
                "forward_risk_state": twin.get("forward_risk_state", {}),
                "coupling_state": twin.get("coupling_state", {}),
            }
        if tool == "compare_history":
            comparison = data.get("history_comparison", {})
            return {
                "date": data.get("date"),
                "has_history": comparison.get("has_history", False),
                "history_count": comparison.get("history_count", 0),
                "previous_date": comparison.get("previous_date"),
            }
        return {}

    @classmethod
    def _build_highlights(cls, tool_results: list[dict[str, Any]]) -> dict[str, Any]:
        highlights: dict[str, Any] = {
            "warnings": [],
        }
        for item in tool_results:
            tool = item.get("tool", "")
            result = item.get("result", {})
            data = result.get("data") or {}

            if not result.get("success"):
                highlights["warnings"].append({
                    "agent": item.get("agent"),
                    "tool": tool,
                    "message": result.get("message", ""),
                })
                continue

            if tool == "list_dates":
                dates = data.get("dates", [])
                highlights["available_date_count"] = len(dates)
                highlights["latest_date"] = dates[0] if dates else None
            elif tool == "analyze_day":
                op = data.get("operation", {})
                geo = data.get("geology", {})
                fwd = data.get("forward_risk", {})
                coupling = data.get("coupling", {})
                highlights["work_total_min"] = op.get("work_total_min", 0)
                highlights["stop_total_min"] = op.get("stop_total_min", 0)
                highlights["abnormal_count"] = op.get("abnormal_count", 0)
                highlights["has_geology"] = geo.get("has_geology", False)
                highlights["geology_high_risk_segment_count"] = geo.get("high_risk_segment_count", 0)
                highlights["geology_multi_source_segment_count"] = geo.get("multi_source_segment_count", 0)
                highlights["forward_advice_level"] = fwd.get("advice_level")
                highlights["forward_high_risk_count"] = fwd.get("high_risk_count", 0)
                highlights["forward_main_hazards"] = fwd.get("main_hazards", [])
                highlights["has_coupling"] = coupling.get("has_coupling", False)
            elif tool == "analyze_gas":
                highlights["gas_exceed_types"] = data.get("exceed_types", [])
            elif tool == "analyze_geology":
                segment_summary = data.get("segment_summary", {})
                coupling = data.get("coupling_summary", {})
                top_segments = coupling.get("top_segments", []) if isinstance(coupling, dict) else []
                top = top_segments[0] if top_segments else {}
                highlights["has_geology"] = segment_summary.get("has_geology", False)
                highlights["geology_high_risk_segment_count"] = segment_summary.get("high_risk_segment_count", 0)
                highlights["geology_multi_source_segment_count"] = segment_summary.get("multi_source_segment_count", 0)
                highlights["top_coupling_segment"] = top.get("segment")
                highlights["top_coupling_label"] = top.get("coupling_label")
                highlights["top_coupling_index"] = top.get("risk_response_coupling_index")
            elif tool == "analyze_forward_risk":
                fwd = data.get("forward_risk", {})
                highlights["forward_advice_level"] = fwd.get("advice_level")
                highlights["forward_main_hazards"] = fwd.get("main_hazards", [])
                highlights["forward_high_risk_count"] = fwd.get("high_risk_count", 0)
            elif tool == "get_digital_twin_state":
                twin = data.get("digital_twin_state", {})
                pos = twin.get("position_state", {})
                op = twin.get("operation_state", {})
                safety = twin.get("safety_state", {})
                fwd = twin.get("forward_risk_state", {})
                highlights["current_chainage_dk"] = pos.get("current_chainage_dk")
                highlights["advance_length_m"] = pos.get("advance_length")
                highlights["dominant_operation"] = op.get("dominant_state")
                highlights["work_ratio"] = op.get("work_ratio")
                highlights.setdefault("gas_exceed_types", safety.get("gas_exceed_types", []))
                highlights.setdefault("forward_advice_level", fwd.get("advice_level"))
                highlights.setdefault("forward_main_hazards", fwd.get("main_hazards", []))
            elif tool == "compare_history":
                comparison = data.get("history_comparison", {})
                highlights["has_history"] = comparison.get("has_history", False)
                highlights["history_count"] = comparison.get("history_count", 0)
                highlights["previous_date"] = comparison.get("previous_date")

        if not highlights["warnings"]:
            highlights.pop("warnings")
        return highlights

    @staticmethod
    def _polish_with_llm(query: str, draft_answer: str) -> str:
        prompt = (
            "You are a TBM multi-agent supervisor. Rewrite the draft answer in concise Chinese, "
            "preserving all numbers, agent routing, and caveats.\n\n"
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
    def _merge_agent_steps(steps: list[SupervisorStep]) -> list[SupervisorStep]:
        merged: dict[str, list[str]] = {}
        reasons: dict[str, list[str]] = {}
        order: list[str] = []

        for step in steps:
            if step.agent not in merged:
                merged[step.agent] = []
                reasons[step.agent] = []
                order.append(step.agent)
            for tool_name in step.tools:
                if tool_name not in merged[step.agent]:
                    merged[step.agent].append(tool_name)
            reasons[step.agent].append(step.reason)

        return [
            SupervisorStep(
                agent=agent,
                tools=tuple(merged[agent]),
                reason=" ".join(reasons[agent]),
            )
            for agent in order
        ]
