"""Shared helpers for experiment scripts."""

from __future__ import annotations

import csv
import json
import os
import re
import sys
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from llm.prompt_builder import build_prompt  # noqa: E402
from llm.llm_api import call_llm  # noqa: E402
from services.history_memory_service import (  # noqa: E402
    build_history_comparison,
    build_history_record,
    load_history_records,
)
from services.tbm_analysis_service import analyze_tbm_data  # noqa: E402
from utils.io_utils import get_all_csv_paths, load_csv_by_date  # noqa: E402
from utils.serialization import serialize_for_json  # noqa: E402
from utils.time_window_utils import load_df_by_time  # noqa: E402


EXPERIMENTS_DIR = ROOT_DIR / "experiments"
CONFIGS_DIR = EXPERIMENTS_DIR / "configs"
OUTPUTS_DIR = EXPERIMENTS_DIR / "outputs"
CASES_DIR = OUTPUTS_DIR / "cases"
STATES_DIR = OUTPUTS_DIR / "states"
REPORTS_DIR = OUTPUTS_DIR / "reports"
METRICS_DIR = OUTPUTS_DIR / "metrics"
TABLES_DIR = OUTPUTS_DIR / "tables"
FIGURES_DIR = OUTPUTS_DIR / "figures"

CASE_COLUMNS = [
    "case_id",
    "date",
    "time_start",
    "time_end",
    "chainage_start",
    "chainage_end",
    "case_type",
    "reason",
]

DEFAULT_METHODS = ["template", "direct_llm", "cst_llm"]
FORWARD_LEVEL_SCORE = {"none": 0, "low": 1, "medium": 2, "high": 3}


@dataclass
class CaseContext:
    """Container for a single experiment case."""

    case: dict[str, Any]
    csv_path: Path
    df: pd.DataFrame
    result: dict[str, Any]


def ensure_experiment_dirs() -> None:
    """Create the standard experiment directory layout."""
    for directory in [
        CONFIGS_DIR,
        OUTPUTS_DIR,
        CASES_DIR,
        STATES_DIR,
        REPORTS_DIR,
        METRICS_DIR,
        TABLES_DIR,
        FIGURES_DIR,
    ]:
        directory.mkdir(parents=True, exist_ok=True)


def available_dates(limit: int | None = None) -> list[str]:
    """List dates inferred from available TBM CSV files."""
    dates: list[str] = []
    for path in get_all_csv_paths():
        match = re.search(r"(\d{8})", path.stem)
        if not match:
            continue
        compact = match.group(1)
        dates.append(f"{compact[:4]}-{compact[4:6]}-{compact[6:]}")
    dates = sorted(set(dates))
    return dates[:limit] if limit else dates


def draft_cases_from_dates(dates: list[str]) -> list[dict[str, Any]]:
    """Build a draft case list from available dates."""
    rows: list[dict[str, Any]] = []
    for index, date in enumerate(dates, start=1):
        rows.append(
            {
                "case_id": f"C{index:02d}",
                "date": date,
                "time_start": "",
                "time_end": "",
                "chainage_start": "",
                "chainage_end": "",
                "case_type": "unspecified",
                "reason": "draft case generated from available CSV date",
            }
        )
    return rows


def write_case_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    """Write the case list CSV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CASE_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in CASE_COLUMNS})


def load_case_csv(path: Path) -> list[dict[str, Any]]:
    """Load experiment cases from CSV."""
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return [normalize_case_row(dict(row)) for row in reader]


def normalize_case_row(row: dict[str, Any]) -> dict[str, Any]:
    """Normalize case fields read from CSV."""
    normalized = {key: (row.get(key, "") or "").strip() for key in CASE_COLUMNS}
    for key in ["chainage_start", "chainage_end"]:
        value = normalized.get(key, "")
        if value == "":
            normalized[key] = None
        else:
            try:
                normalized[key] = float(value)
            except ValueError:
                normalized[key] = value
    return normalized


def load_case_context(case: dict[str, Any]) -> CaseContext:
    """Load dataframe and analysis result for a single case."""
    csv_path, df = load_csv_by_date(case["date"])
    if case.get("time_start") and case.get("time_end"):
        df = load_df_by_time(df, case["time_start"], case["time_end"])
    result = analyze_tbm_data(df)
    return CaseContext(case=case, csv_path=csv_path, df=df, result=result)


def build_history_comparison_text(date: str, result: dict[str, Any]) -> str:
    """Build a lightweight history comparison text when history exists."""
    current_record = build_history_record(date, result)
    history_records = load_history_records(limit=5, before_date=date)
    comparison = build_history_comparison(current_record, history_records)
    return comparison.get("comparison_text", "暂无历史分析记忆。")


def build_cst_state(case: dict[str, Any], context: CaseContext) -> dict[str, Any]:
    """Export a normalized CST state payload for experiments."""
    result = context.result
    twin = deepcopy(result.get("digital_twin_state") or {})
    llm_summary = deepcopy(result.get("llm_summary") or {})
    coupling_summary = deepcopy(result.get("coupling_summary") or {})
    geo_summary = deepcopy(result.get("geo_summary_segment") or {})
    gas_stats = deepcopy(result.get("gas_stats") or {})
    history_text = build_history_comparison_text(case["date"], result)
    state = {
        "case_id": case["case_id"],
        "date": case["date"],
        "time_window": {
            "start_time": serialize_for_json(context.df["运行时间-time"].min())
            if not context.df.empty
            else "",
            "end_time": serialize_for_json(context.df["运行时间-time"].max())
            if not context.df.empty
            else "",
            "duration_min": round(
                max(
                    0.0,
                    (
                        context.df["运行时间-time"].max() - context.df["运行时间-time"].min()
                    ).total_seconds()
                    / 60.0,
                ),
                2,
            )
            if len(context.df) >= 2
            else 0.0,
        },
        "temporal_state": {
            "sample_count": int(len(context.df)),
            "analysis_mode": "time_window"
            if case.get("time_start") and case.get("time_end")
            else "daily",
        },
        "spatial_state": {
            "chainage_start": case.get("chainage_start"),
            "chainage_end": case.get("chainage_end"),
            "face_chainage": twin.get("position_state", {}).get("current_chainage"),
            "advance_length": twin.get("position_state", {}).get("advance_length"),
            "forward_window": twin.get("forward_state", {}).get("forward_segments", []),
        },
        "operation_state": {
            "main_state": twin.get("operation_state", {}).get("dominant_operation"),
            "working_duration_min": twin.get("operation_state", {}).get("work_total_min", 0.0),
            "stoppage_duration_min": twin.get("operation_state", {}).get("stop_total_min", 0.0),
            "state_switch_count": twin.get("operation_state", {}).get("state_switch_count", 0),
            "efficiency_summary": llm_summary.get("施工状态效率分析", "无"),
        },
        "geological_state": {
            "face_condition": result.get("face_geo_text", "无"),
            "segment_grade": geo_summary.get("segment_grade"),
            "hazards": geo_summary.get("main_hazards", []),
            "evidence_count": geo_summary.get("multi_source_segment_count", 0),
            "uncertainty": geo_summary.get("uncertainty"),
        },
        "response_state": {
            "RAI": coupling_summary.get("highest_attention_segment", {}).get("RAI", 0.0),
            "anomaly_type": coupling_summary.get("highest_attention_segment", {}).get(
                "anomaly_type", ""
            ),
            "key_parameters": coupling_summary.get("highest_attention_segment", {}).get(
                "key_parameters", []
            ),
        },
        "attention_state": {
            "GRS": coupling_summary.get("highest_attention_segment", {}).get("GRS", 0.0),
            "GRCI": coupling_summary.get("highest_attention_segment", {}).get("GRCI", 0.0),
            "high_attention_segments": result.get("high_attention_segments", []),
            "forward_attention": twin.get("forward_state", {}),
        },
        "provenance_state": {
            "evidence_list": result.get("geo_summary_record", {}).get("active_sources", []),
            "state_update_sources": [
                {"type": "csv", "path": str(context.csv_path)},
                {"type": "history", "available": history_text != "暂无历史分析记忆。"},
            ],
            "previous_change_summary": history_text,
        },
        "raw_twin_state": twin,
        "llm_summary": llm_summary,
        "warnings": result.get("warnings", []),
        "gas_state": serialize_for_json(gas_stats),
    }
    return serialize_for_json(state)


def write_json(path: Path, payload: Any) -> None:
    """Write JSON with UTF-8 encoding."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def write_text(path: Path, text: str) -> None:
    """Write UTF-8 text."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def flatten_state_summary(state: dict[str, Any]) -> dict[str, Any]:
    """Build a compact CSV-friendly state summary row."""
    return {
        "case_id": state["case_id"],
        "date": state["date"],
        "analysis_mode": state["temporal_state"]["analysis_mode"],
        "sample_count": state["temporal_state"]["sample_count"],
        "face_chainage": state["spatial_state"].get("face_chainage"),
        "advance_length": state["spatial_state"].get("advance_length"),
        "main_state": state["operation_state"].get("main_state"),
        "working_duration_min": state["operation_state"].get("working_duration_min"),
        "stoppage_duration_min": state["operation_state"].get("stoppage_duration_min"),
        "RAI": state["response_state"].get("RAI"),
        "GRS": state["attention_state"].get("GRS"),
        "GRCI": state["attention_state"].get("GRCI"),
        "high_attention_segment_count": len(state["attention_state"].get("high_attention_segments", [])),
    }


def write_rows_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    """Write generic row dictionaries to CSV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_template_report(case: dict[str, Any], state: dict[str, Any]) -> str:
    """Generate a deterministic template baseline report."""
    op = state["operation_state"]
    geo = state["geological_state"]
    att = state["attention_state"]
    return (
        f"TBM施工报告（模板基线）\n\n"
        f"日期：{case['date']}\n"
        f"案例编号：{case['case_id']}\n\n"
        f"一、施工概况\n"
        f"本次分析窗口主导工况为{op.get('main_state') or '未知'}，"
        f"工作时长约{op.get('working_duration_min', 0)}分钟，"
        f"停机时长约{op.get('stoppage_duration_min', 0)}分钟。\n\n"
        f"二、地质情况\n"
        f"当前掌子面摘要：{geo.get('face_condition') or '无'}\n"
        f"主要关注标签：{', '.join(geo.get('hazards') or []) or '无'}\n\n"
        f"三、区段关注\n"
        f"GRS={att.get('GRS', 0)}，RAI={state['response_state'].get('RAI', 0)}，"
        f"GRCI={att.get('GRCI', 0)}。"
        f"高关注区段数量：{len(att.get('high_attention_segments', []))}。\n\n"
        f"四、结论与建议\n"
        f"建议结合当前施工状态、地质证据和前方关注信息，持续开展现场核查与参数跟踪。"
    )


def build_direct_llm_prompt(case: dict[str, Any], context: CaseContext) -> str:
    """Build a weaker baseline prompt without explicit CST alignment."""
    result = context.result
    return f"""
请根据以下 TBM 施工摘要信息，直接生成一份正式的《TBM综合施工工况分析报告》。

要求：
1. 使用正式工程报告语体；
2. 尽量覆盖施工概况、工况统计、施工状态、地质情况、气体安全和前方提示；
3. 不要虚构未提供的信息；
4. 不需要显式输出指标解释；
5. 不提供统一里程状态组织，请仅依据以下摘要进行综合写作。

案例编号：{case["case_id"]}
日期：{case["date"]}

【基础工况分段】
{result.get("seg_text", "无")}

【基础统计】
{result.get("stats_text", "无")}

【施工状态】
{result.get("state_text", "无")}

【效率统计】
{result.get("eff_text", "无")}

【状态统计】
{result.get("state_stats_text", "无")}

【地质分析】
{result.get("geo_text", "无")}

【当前掌子面】
{result.get("face_geo_text", "无")}

【气体分析】
{result.get("gas_text", "无")}

【前方提示】
{result.get("forward_risk_text", "无")}
""".strip()


def build_cst_llm_prompt(context: CaseContext) -> str:
    """Build the main CST-LLM prompt by reusing backend prompt builder."""
    result = context.result
    llm_summary = deepcopy(result.get("llm_summary") or {})
    llm_summary["施工历史记忆对比"] = {
        "comparison_text": build_history_comparison_text(context.case["date"], result)
    }
    return build_prompt(
        seg_text=result.get("seg_text", "无"),
        stats_text=result.get("stats_text", "无"),
        state_text=result.get("state_text", "无"),
        eff_text=result.get("eff_text", "无"),
        state_stats_text=result.get("state_stats_text", "无"),
        gas_text=result.get("gas_text", "无"),
        geo_text=result.get("geo_text", "无"),
        face_geo_text=result.get("face_geo_text", "无"),
        llm_summary=llm_summary,
        risk_prob_text=result.get("risk_prob_text", "无"),
    )


def maybe_call_llm(prompt: str, mode: str, provider: str | None = None) -> str:
    """Optionally call the configured LLM provider."""
    if mode == "prompt_only":
        return ""
    return call_llm(prompt, provider=provider)


def evaluation_sheet_rows(cases: list[dict[str, Any]], methods: list[str]) -> list[dict[str, Any]]:
    """Create blank evaluation sheet rows."""
    rows: list[dict[str, Any]] = []
    for case in cases:
        for method in methods:
            rows.append(
                {
                    "case_id": case["case_id"],
                    "method": method,
                    "reviewer_id": "",
                    "ICS_operation": "",
                    "ICS_geology": "",
                    "ICS_gas": "",
                    "ICS_forward": "",
                    "factual_errors_count": "",
                    "key_facts_count": "",
                    "unsupported_claims_count": "",
                    "key_claims_count": "",
                    "risk_overstatement_count": "",
                    "RDR_score": "",
                    "EOR_score": "",
                    "comments": "",
                }
            )
    return rows


def summarize_case_metrics(case: dict[str, Any], context: CaseContext, state: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build compact metrics for case selection and experiment bookkeeping."""
    result = context.result
    state = state or build_cst_state(case, context)
    coupling = result.get("coupling_summary") or {}
    forward = result.get("forward_risk_summary") or {}
    geo = result.get("geo_summary_segment") or {}
    twin = result.get("digital_twin_state") or {}
    safety_state = twin.get("safety_state", {}) if isinstance(twin, dict) else {}
    top_segment = (coupling.get("high_attention_segments") or [{}])[0]
    return {
        "case_id": case["case_id"],
        "date": case["date"],
        "sample_count": state["temporal_state"]["sample_count"],
        "analysis_mode": state["temporal_state"]["analysis_mode"],
        "work_min": state["operation_state"].get("working_duration_min", 0.0),
        "stop_min": state["operation_state"].get("stoppage_duration_min", 0.0),
        "GRS_top": top_segment.get("GRS", coupling.get("GRS_max", 0.0)),
        "RAI_top": top_segment.get("RAI", coupling.get("RAI_max", 0.0)),
        "GRCI_top": top_segment.get("GRCI", coupling.get("GRCI_max", 0.0)),
        "high_attention_segment_count": len(result.get("high_attention_segments", [])),
        "high_risk_segment_count": geo.get("high_risk_segment_count", 0),
        "multi_source_segment_count": geo.get("multi_source_segment_count", 0),
        "forward_advice_level": forward.get("advice_level", "none"),
        "forward_high_risk_count": forward.get("high_risk_count", 0),
        "gas_exceed_type_count": safety_state.get("gas_exceed_type_count", 0),
        "gas_exceed_types": ",".join(safety_state.get("gas_exceed_types", [])),
        "top_segment": top_segment.get("segment", ""),
        "top_segment_class": top_segment.get("grci_class_label", ""),
    }


def classify_case_type(metrics: dict[str, Any]) -> tuple[str, str, float]:
    """Assign a candidate case type using simple heuristic rules."""
    grs = float(metrics.get("GRS_top") or 0.0)
    rai = float(metrics.get("RAI_top") or 0.0)
    grci = float(metrics.get("GRCI_top") or 0.0)
    gas_count = int(metrics.get("gas_exceed_type_count") or 0)
    high_risk_count = int(metrics.get("high_risk_segment_count") or 0)
    forward_level = str(metrics.get("forward_advice_level") or "none").lower()
    forward_score = FORWARD_LEVEL_SCORE.get(forward_level, 0)

    if gas_count > 0:
        return (
            "gas_attention",
            f"gas exceed types={metrics.get('gas_exceed_types') or gas_count}",
            max(gas_count, 1),
        )
    if grs >= 0.55 and rai >= 0.55 and grci >= 0.55:
        return (
            "coupled_attention",
            f"GRS={grs:.2f}, RAI={rai:.2f}, GRCI={grci:.2f}",
            grci,
        )
    if rai >= 0.60 and grci < 0.55:
        return (
            "response_anomaly",
            f"RAI={rai:.2f}, GRCI={grci:.2f}",
            rai,
        )
    if grs >= 0.60 or high_risk_count > 0 or forward_score >= 2:
        return (
            "geology_attention",
            f"GRS={grs:.2f}, high_risk_segments={high_risk_count}, forward={forward_level}",
            max(grs, forward_score / 3.0),
        )
    if grs < 0.35 and rai < 0.35 and grci < 0.35 and gas_count == 0:
        stability = 1.0 - max(grs, rai, grci)
        return (
            "normal",
            f"GRS={grs:.2f}, RAI={rai:.2f}, GRCI={grci:.2f}",
            stability,
        )

    # Fallback: choose the strongest signal.
    if grci >= max(grs, rai):
        return ("coupled_attention", f"fallback by GRCI={grci:.2f}", grci)
    if rai >= grs:
        return ("response_anomaly", f"fallback by RAI={rai:.2f}", rai)
    return ("geology_attention", f"fallback by GRS={grs:.2f}", grs)


def pick_balanced_cases(candidate_rows: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    """Pick a balanced subset of candidates across target case types."""
    target_order = [
        "normal",
        "geology_attention",
        "response_anomaly",
        "coupled_attention",
        "gas_attention",
    ]
    grouped: dict[str, list[dict[str, Any]]] = {key: [] for key in target_order}
    for row in candidate_rows:
        grouped.setdefault(str(row.get("case_type")), []).append(row)
    for values in grouped.values():
        values.sort(key=lambda item: float(item.get("selection_score") or 0), reverse=True)

    selected: list[dict[str, Any]] = []
    seen_dates: set[str] = set()

    # First pass: at most one per type.
    for case_type in target_order:
        for row in grouped.get(case_type, []):
            if row["date"] in seen_dates:
                continue
            selected.append(row)
            seen_dates.add(row["date"])
            break

    # Second pass: fill remaining slots by score.
    remaining = []
    for rows in grouped.values():
        for row in rows:
            if row["date"] in seen_dates:
                continue
            remaining.append(row)
    remaining.sort(key=lambda item: float(item.get("selection_score") or 0), reverse=True)
    for row in remaining:
        if len(selected) >= limit:
            break
        selected.append(row)
        seen_dates.add(row["date"])

    selected = sorted(selected[:limit], key=lambda item: item["date"])
    for index, row in enumerate(selected, start=1):
        row["case_id"] = f"C{index:02d}"
    return selected


def safe_float(value: Any) -> float | None:
    """Convert a cell value to float when possible."""
    if value in ("", None):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def aggregate_metrics(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Aggregate manual evaluation rows into method-level metrics."""
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(row["method"], []).append(row)
    output: list[dict[str, Any]] = []
    for method, items in grouped.items():
        ics_values = []
        fcs_values = []
        ts_values = []
        for item in items:
            ics_parts = [
                safe_float(item.get("ICS_operation")),
                safe_float(item.get("ICS_geology")),
                safe_float(item.get("ICS_gas")),
                safe_float(item.get("ICS_forward")),
            ]
            valid_ics = [part for part in ics_parts if part is not None]
            if valid_ics:
                ics_values.append(sum(valid_ics) / (2.0 * len(valid_ics)))
            factual_errors = safe_float(item.get("factual_errors_count"))
            key_facts = safe_float(item.get("key_facts_count"))
            unsupported_claims = safe_float(item.get("unsupported_claims_count"))
            key_claims = safe_float(item.get("key_claims_count"))
            if factual_errors is not None and key_facts and key_facts > 0:
                fcs_values.append(1.0 - factual_errors / key_facts)
            if unsupported_claims is not None and key_claims and key_claims > 0:
                ts_values.append(1.0 - unsupported_claims / key_claims)
        output.append(
            {
                "method": method,
                "ICS_mean": round(sum(ics_values) / len(ics_values), 4) if ics_values else "",
                "FCS_mean": round(sum(fcs_values) / len(fcs_values), 4) if fcs_values else "",
                "TS_mean": round(sum(ts_values) / len(ts_values), 4) if ts_values else "",
                "n_rows": len(items),
            }
        )
    return output


def extract_claim_candidates(report_text: str) -> list[str]:
    """Split report text into lightweight claim candidates for traceability review."""
    normalized = re.sub(r"\s+", " ", report_text).strip()
    if not normalized:
        return []
    parts = re.split(r"[。！？；;\n]+", normalized)
    claims = []
    for part in parts:
        cleaned = part.strip("  \t-")
        if len(cleaned) >= 8:
            claims.append(cleaned)
    return claims
