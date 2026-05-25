from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any
from uuid import uuid4

import pandas as pd

from schemas.cst_state import normalize_cst_state
from services.sqlite_storage_service import load_previous_cst_for_context, save_cst_state
from utils.serialization import serialize_for_json


NO_DATA_TEXT = "N/A"
NO_HISTORY_TEXT = "No previous CST state is available."
STATE_VERSION = "recursive_cst_v2"
MAX_PERSISTENT_SEGMENTS = 5
MAX_PERSISTENT_HAZARDS = 8


def _safe_text(value: Any, default: str = NO_DATA_TEXT) -> str:
    """Return a compact string fallback."""
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _safe_float(value: Any, default: float | None = None) -> float | None:
    """Convert a value to float safely."""
    try:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp(value: float, low: float, high: float) -> float:
    """Clamp a float to a bounded interval."""
    return max(low, min(high, value))


def _compact_text(value: Any, max_lines: int = 8, max_chars: int = 1200) -> str:
    """Compress multiline text into a prompt-friendly summary."""
    text = _safe_text(value)
    if text == NO_DATA_TEXT:
        return text
    lines = [line.strip() for line in text.replace("\r\n", "\n").split("\n") if line.strip()]
    compact = "\n".join(lines[:max_lines])
    if len(compact) > max_chars:
        compact = compact[: max_chars - 3].rstrip() + "..."
    return compact


def _split_hazard_text(value: Any) -> list[str]:
    """Split hazard strings into normalized tags."""
    if value in (None, ""):
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    if not text:
        return []
    for separator in ["+", "、", "，", ",", ";", "；", "/", "|", "\n"]:
        text = text.replace(separator, " ")
    return [part.strip() for part in text.split() if part.strip()]


def _pick_primary_attention_segment(result: dict[str, Any], coupling_summary: dict[str, Any]) -> dict[str, Any]:
    """Select the most important high-attention segment."""
    candidates = result.get("high_attention_segments") or []
    if not candidates:
        candidates = coupling_summary.get("high_attention_segments") or []
    if not candidates:
        candidates = coupling_summary.get("top_segments") or []
    return deepcopy(candidates[0]) if candidates else {}


def _forward_window(forward_summary: dict[str, Any]) -> list[dict[str, Any]]:
    """Build forward window records from the forward risk summary."""
    if not isinstance(forward_summary, dict) or not forward_summary.get("has_forward_risk"):
        return []
    return [
        {
            "lookahead_m": forward_summary.get("lookahead_m"),
            "forward_start": forward_summary.get("forward_start"),
            "forward_end": forward_summary.get("forward_end"),
            "forward_start_dk": forward_summary.get("forward_start_dk"),
            "forward_end_dk": forward_summary.get("forward_end_dk"),
            "advice_level": forward_summary.get("advice_level"),
            "main_hazards": forward_summary.get("main_hazards", []),
            "forward_segment_count": forward_summary.get("forward_segment_count", 0),
            "high_risk_count": forward_summary.get("high_risk_count", 0),
            "multi_source_count": forward_summary.get("multi_source_count", 0),
        }
    ]


def _evidence_list(geo_record_summary: dict[str, Any]) -> list[Any]:
    """Normalize evidence list from geology record summary."""
    evidence_list = geo_record_summary.get("active_sources", [])
    return evidence_list if isinstance(evidence_list, list) else []


def _state_key(context: dict[str, Any]) -> str:
    """Build a stable state key for CST persistence."""
    mode = context.get("analysis_mode") or "daily"
    date = context.get("date") or "unknown-date"
    if mode == "time_window":
        start = context.get("time_start") or "unknown-start"
        end = context.get("time_end") or "unknown-end"
        return f"time_window:{date}:{start}->{end}"
    return f"daily:{date}"


def _lineage(previous_cst: dict[str, Any] | None) -> list[str]:
    """Build lineage ids from the previous CST."""
    if not isinstance(previous_cst, dict):
        return []
    previous_lineage = previous_cst.get("provenance_state", {}).get("lineage", [])
    lineage = [str(item) for item in previous_lineage if item]
    previous_id = previous_cst.get("cst_id")
    if previous_id:
        lineage.append(str(previous_id))
    return lineage


def _collect_gas_exceed_types(gas_state: dict[str, Any]) -> list[str]:
    """Collect gas exceed types from gas stats."""
    gas_all = gas_state.get("all", {}) if isinstance(gas_state, dict) else {}
    out: list[str] = []
    for gas, stat in gas_all.items():
        if isinstance(stat, dict) and stat.get("exceed_event_count", 0) > 0:
            out.append(str(gas))
    return out


def _normalize_segment_name(item: dict[str, Any]) -> str:
    """Return a stable segment identifier."""
    if not isinstance(item, dict):
        return ""
    for key in ("segment", "segment_name", "chainage_range", "chainage_range_dk"):
        value = item.get(key)
        if value:
            return str(value)
    start = item.get("segment_start_dk") or item.get("segment_start")
    end = item.get("segment_end_dk") or item.get("segment_end")
    if start or end:
        return f"{start or '?'}->{end or '?'}"
    return ""


def _hazard_memory(previous_cst: dict[str, Any] | None, current_hazards: list[str]) -> list[dict[str, Any]]:
    """Carry forward persistent hazards with simple streak/decay accounting."""
    previous_items = []
    if isinstance(previous_cst, dict):
        previous_items = previous_cst.get("geological_state", {}).get("persistent_hazards", []) or []

    previous_index = {}
    for item in previous_items:
        if isinstance(item, dict) and item.get("hazard"):
            previous_index[str(item["hazard"])] = item

    result = []
    current_set = {hazard for hazard in current_hazards if hazard}
    merged_keys = sorted(current_set | set(previous_index))
    for hazard in merged_keys:
        previous_item = previous_index.get(hazard, {})
        previous_streak = int(previous_item.get("streak", 0) or 0)
        previous_decay = _safe_float(previous_item.get("decay_weight"), 0.0) or 0.0
        is_active = hazard in current_set
        streak = previous_streak + 1 if is_active else max(previous_streak - 1, 0)
        decay = 1.0 if is_active else round(previous_decay * 0.65, 3)
        if streak <= 0 and decay < 0.15:
            continue
        result.append(
            {
                "hazard": hazard,
                "is_active": is_active,
                "streak": streak,
                "decay_weight": round(decay, 3),
            }
        )

    result.sort(key=lambda item: (-item["decay_weight"], -item["streak"], item["hazard"]))
    return result[:MAX_PERSISTENT_HAZARDS]


def _segment_memory(previous_cst: dict[str, Any] | None, current_segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Carry forward high-attention segments with streak/decay accounting."""
    previous_items = []
    if isinstance(previous_cst, dict):
        previous_items = previous_cst.get("attention_state", {}).get("persistent_attention_segments", []) or []

    previous_index = {}
    for item in previous_items:
        name = _normalize_segment_name(item)
        if name:
            previous_index[name] = item

    current_index = {}
    for item in current_segments or []:
        name = _normalize_segment_name(item)
        if name:
            current_index[name] = item

    result = []
    merged_names = sorted(set(previous_index) | set(current_index))
    for name in merged_names:
        previous_item = previous_index.get(name, {})
        current_item = current_index.get(name)
        previous_streak = int(previous_item.get("streak", 0) or 0)
        previous_carry = _safe_float(previous_item.get("carryover_score"), 0.0) or 0.0
        is_active = current_item is not None
        streak = previous_streak + 1 if is_active else max(previous_streak - 1, 0)
        carry = 1.0 if is_active else round(previous_carry * 0.6, 3)
        if streak <= 0 and carry < 0.15:
            continue
        base = deepcopy(current_item) if current_item is not None else {"segment": name}
        base["segment_name"] = name
        base["is_active"] = is_active
        base["streak"] = streak
        base["carryover_score"] = round(carry, 3)
        result.append(base)

    result.sort(
        key=lambda item: (
            -(_safe_float(item.get("GRCI"), 0.0) or 0.0),
            -(item.get("carryover_score", 0.0) or 0.0),
            -int(item.get("streak", 0) or 0),
        )
    )
    return result[:MAX_PERSISTENT_SEGMENTS]


def _changed_fields(previous_cst: dict[str, Any] | None, current_cst: dict[str, Any]) -> list[str]:
    """Describe the main CST field groups that changed."""
    if not isinstance(previous_cst, dict):
        return ["initial_state"]

    changed: list[str] = []

    prev_main = previous_cst.get("operation_state", {}).get("main_state")
    cur_main = current_cst.get("operation_state", {}).get("main_state")
    if prev_main != cur_main:
        changed.append("operation_state.main_state")

    for label in ("GRS", "GRCI"):
        prev_value = _safe_float(previous_cst.get("attention_state", {}).get(label), 0.0) or 0.0
        cur_value = _safe_float(current_cst.get("attention_state", {}).get(label), 0.0) or 0.0
        if abs(cur_value - prev_value) >= 0.05:
            changed.append(f"attention_state.{label}")

    prev_rai = _safe_float(previous_cst.get("response_state", {}).get("RAI"), 0.0) or 0.0
    cur_rai = _safe_float(current_cst.get("response_state", {}).get("RAI"), 0.0) or 0.0
    if abs(cur_rai - prev_rai) >= 0.05:
        changed.append("response_state.RAI")

    prev_hazards = set(_split_hazard_text(previous_cst.get("geological_state", {}).get("hazards")))
    cur_hazards = set(_split_hazard_text(current_cst.get("geological_state", {}).get("hazards")))
    if prev_hazards != cur_hazards:
        changed.append("geological_state.hazards")

    prev_gas = set(_collect_gas_exceed_types(previous_cst.get("gas_state", {})))
    cur_gas = set(_collect_gas_exceed_types(current_cst.get("gas_state", {})))
    if prev_gas != cur_gas:
        changed.append("gas_state.exceed_types")

    prev_forward = previous_cst.get("attention_state", {}).get("forward_attention", {})
    cur_forward = current_cst.get("attention_state", {}).get("forward_attention", {})
    if isinstance(prev_forward, dict) and isinstance(cur_forward, dict):
        if prev_forward.get("advice_level") != cur_forward.get("advice_level"):
            changed.append("attention_state.forward_attention")

    return changed


def _state_confidence(snapshot: dict[str, Any]) -> float:
    """Estimate a CST confidence score from coverage and evidence support."""
    temporal = snapshot.get("temporal_state", {})
    geo = snapshot.get("geological_state", {})
    attention = snapshot.get("attention_state", {})
    gas_state = snapshot.get("gas_state", {})

    sample_count = _safe_float(temporal.get("sample_count"), 0.0) or 0.0
    evidence_count = _safe_float(geo.get("evidence_count"), 0.0) or 0.0
    segment_count = len(attention.get("high_attention_segments", []) or [])
    gas_cov = len((gas_state.get("all") or {})) if isinstance(gas_state, dict) else 0

    sample_score = _clamp(sample_count / 1000.0, 0.0, 1.0)
    evidence_score = _clamp(evidence_count / 3.0, 0.0, 1.0)
    segment_score = _clamp(segment_count / 3.0, 0.0, 1.0)
    gas_score = 0.5 if gas_cov else 0.0
    confidence = 0.45 * sample_score + 0.30 * evidence_score + 0.15 * segment_score + 0.10 * gas_score
    return round(_clamp(confidence, 0.0, 1.0), 3)


def _state_stability(previous_cst: dict[str, Any] | None, current_cst: dict[str, Any]) -> float:
    """Estimate CST stability from inter-state changes."""
    if not isinstance(previous_cst, dict):
        return 1.0

    prev_att = previous_cst.get("attention_state", {})
    cur_att = current_cst.get("attention_state", {})
    prev_resp = previous_cst.get("response_state", {})
    cur_resp = current_cst.get("response_state", {})
    prev_op = previous_cst.get("operation_state", {})
    cur_op = current_cst.get("operation_state", {})

    deltas = [
        abs((_safe_float(cur_att.get("GRS"), 0.0) or 0.0) - (_safe_float(prev_att.get("GRS"), 0.0) or 0.0)),
        abs((_safe_float(cur_att.get("GRCI"), 0.0) or 0.0) - (_safe_float(prev_att.get("GRCI"), 0.0) or 0.0)),
        abs((_safe_float(cur_resp.get("RAI"), 0.0) or 0.0) - (_safe_float(prev_resp.get("RAI"), 0.0) or 0.0)),
    ]
    mean_delta = sum(deltas) / len(deltas)
    state_switch_penalty = 0.15 if prev_op.get("main_state") != cur_op.get("main_state") else 0.0
    stability = 1.0 - mean_delta - state_switch_penalty
    return round(_clamp(stability, 0.0, 1.0), 3)


def _trend_label(previous_cst: dict[str, Any] | None, current_cst: dict[str, Any]) -> str:
    """Label the current attention trend."""
    if not isinstance(previous_cst, dict):
        return "initialized"
    grs_delta = (_safe_float(current_cst.get("attention_state", {}).get("GRS_delta"), 0.0) or 0.0)
    rai_delta = (_safe_float(current_cst.get("response_state", {}).get("RAI_delta"), 0.0) or 0.0)
    combined = grs_delta + rai_delta
    if combined > 0.12:
        return "strengthening"
    if combined < -0.12:
        return "weakening"
    return "stable"


def build_cst_snapshot(
    analysis_result: dict[str, Any],
    *,
    case_id: str | None = None,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the current-step CST snapshot from one analysis result."""
    context = context or {}
    twin = deepcopy(analysis_result.get("digital_twin_state") or {})
    llm_summary = deepcopy(analysis_result.get("llm_summary") or {})
    coupling_summary = deepcopy(analysis_result.get("coupling_summary") or {})
    geo_summary = deepcopy(analysis_result.get("geo_summary_segment") or {})
    geo_record_summary = deepcopy(analysis_result.get("geo_summary_record") or {})
    gas_stats = deepcopy(analysis_result.get("gas_stats") or {})
    forward_summary = deepcopy(analysis_result.get("forward_risk_summary") or {})

    position_state = twin.get("position_state", {}) if isinstance(twin, dict) else {}
    operation_state = twin.get("operation_state", {}) if isinstance(twin, dict) else {}
    twin_geo_state = twin.get("geology_state", {}) if isinstance(twin, dict) else {}
    primary_segment = _pick_primary_attention_segment(analysis_result, coupling_summary)
    hazard_list = (
        geo_summary.get("main_hazards")
        or _split_hazard_text(twin_geo_state.get("current_hazard"))
        or _split_hazard_text(analysis_result.get("face_geo_text"))
    )

    snapshot = normalize_cst_state(
        {
            "version": STATE_VERSION,
            "case_id": case_id,
            "date": context.get("date"),
            "time_window": {
                "start_time": context.get("time_start") or twin.get("time_state", {}).get("start_time"),
                "end_time": context.get("time_end") or twin.get("time_state", {}).get("end_time"),
                "duration_min": twin.get("time_state", {}).get("duration_min", 0.0),
            },
            "temporal_state": {
                "sample_count": twin.get("time_state", {}).get("sample_count", 0),
                "analysis_mode": context.get("analysis_mode") or "daily",
                "source_name": context.get("source_name"),
            },
            "spatial_state": {
                "chainage_start": context.get("chainage_start") or position_state.get("start_chainage"),
                "chainage_end": context.get("chainage_end") or position_state.get("end_chainage"),
                "face_chainage": position_state.get("current_chainage"),
                "advance_length": position_state.get("advance_length"),
                "forward_window": _forward_window(forward_summary),
                "forward_focus_level": forward_summary.get("advice_level"),
            },
            "operation_state": {
                "main_state": operation_state.get("dominant_state"),
                "working_duration_min": operation_state.get("work_total_min", 0.0),
                "stoppage_duration_min": operation_state.get("stop_total_min", 0.0),
                "state_switch_count": operation_state.get("state_switch_count", 0),
                "efficiency_summary": _compact_text(
                    llm_summary.get("施工状态效率分析") or llm_summary.get("efficiency_summary"),
                    NO_DATA_TEXT,
                ),
                "work_ratio": operation_state.get("work_ratio"),
                "stop_ratio": operation_state.get("stop_ratio"),
            },
            "geological_state": {
                "face_condition": analysis_result.get("face_geo_text", NO_DATA_TEXT),
                "segment_grade": twin_geo_state.get("current_grade") or geo_summary.get("segment_grade"),
                "hazards": hazard_list,
                "evidence_count": twin_geo_state.get("current_active_source_count")
                or geo_summary.get("multi_source_segment_count", 0),
                "uncertainty": geo_summary.get("uncertainty") or geo_record_summary.get("uncertainty"),
            },
            "response_state": {
                "RAI": primary_segment.get("RAI", 0.0),
                "anomaly_type": primary_segment.get("anomaly_type", ""),
                "key_parameters": primary_segment.get("key_parameters", []),
            },
            "attention_state": {
                "GRS": primary_segment.get("GRS", 0.0),
                "GRCI": primary_segment.get("GRCI", 0.0),
                "high_attention_segments": analysis_result.get("high_attention_segments", []),
                "forward_attention": serialize_for_json(twin.get("forward_risk_state", {}) or forward_summary),
            },
            "provenance_state": {
                "evidence_list": _evidence_list(geo_record_summary),
                "state_update_sources": [
                    {"type": "csv", "path": context.get("source_name") or context.get("source_path")},
                    {"type": "geo_evidence", "available": bool(geo_summary.get("has_geology", False))},
                ],
                "update_strategy": "snapshot_then_recursive_merge",
            },
            "raw_twin_state": twin,
            "llm_summary": llm_summary,
            "warnings": analysis_result.get("warnings", []),
            "gas_state": serialize_for_json(gas_stats),
        }
    )
    snapshot["provenance_state"]["state_confidence"] = _state_confidence(snapshot)
    return serialize_for_json(snapshot)


def summarize_cst_delta(previous_cst: dict[str, Any] | None, current_cst: dict[str, Any]) -> str:
    """Generate a lightweight state-to-state delta summary."""
    if not isinstance(previous_cst, dict):
        return NO_HISTORY_TEXT

    prev_op = previous_cst.get("operation_state", {})
    cur_op = current_cst.get("operation_state", {})
    prev_resp = previous_cst.get("response_state", {})
    cur_resp = current_cst.get("response_state", {})
    prev_att = previous_cst.get("attention_state", {})
    cur_att = current_cst.get("attention_state", {})
    prev_geo = previous_cst.get("geological_state", {})
    cur_geo = current_cst.get("geological_state", {})

    lines = [f"Previous state date: {previous_cst.get('date') or 'unknown'}"]
    prev_main = _safe_text(prev_op.get("main_state"), "unknown")
    cur_main = _safe_text(cur_op.get("main_state"), "unknown")
    if prev_main == cur_main:
        lines.append(f"Main operation state remained {cur_main}.")
    else:
        lines.append(f"Main operation state changed from {prev_main} to {cur_main}.")

    prev_rai = _safe_float(prev_resp.get("RAI"), 0.0) or 0.0
    cur_rai = _safe_float(cur_resp.get("RAI"), 0.0) or 0.0
    prev_grs = _safe_float(prev_att.get("GRS"), 0.0) or 0.0
    cur_grs = _safe_float(cur_att.get("GRS"), 0.0) or 0.0
    prev_grci = _safe_float(prev_att.get("GRCI"), 0.0) or 0.0
    cur_grci = _safe_float(cur_att.get("GRCI"), 0.0) or 0.0
    lines.append(f"RAI delta: {cur_rai - prev_rai:+.2f}.")
    lines.append(f"GRS delta: {cur_grs - prev_grs:+.2f}.")
    lines.append(f"GRCI delta: {cur_grci - prev_grci:+.2f}.")

    previous_hazards = set(_split_hazard_text(prev_geo.get("hazards")))
    current_hazards = set(_split_hazard_text(cur_geo.get("hazards")))
    new_hazards = sorted(current_hazards - previous_hazards)
    if new_hazards:
        lines.append(f"New geological attention tags: {', '.join(new_hazards)}.")
    elif current_hazards:
        lines.append(f"Geological attention persisted as: {', '.join(sorted(current_hazards))}.")

    changed_fields = current_cst.get("provenance_state", {}).get("changed_fields", [])
    if changed_fields:
        lines.append(f"Changed field groups: {', '.join(changed_fields)}.")

    return " ".join(lines)


def summarize_cst_for_prompt(cst_state: dict[str, Any] | None) -> str:
    """Build a compact CST-only summary block for prompts and reports."""
    if not isinstance(cst_state, dict) or not cst_state:
        return "- CST unavailable."

    temporal = cst_state.get("temporal_state", {})
    spatial = cst_state.get("spatial_state", {})
    operation = cst_state.get("operation_state", {})
    geo = cst_state.get("geological_state", {})
    response = cst_state.get("response_state", {})
    attention = cst_state.get("attention_state", {})
    provenance = cst_state.get("provenance_state", {})

    forward_attention = attention.get("forward_attention", {})
    if not isinstance(forward_attention, dict):
        forward_attention = {}
    forward_hazards = forward_attention.get("main_hazards", []) or []

    lines = [
        f"- Analysis mode: {temporal.get('analysis_mode', 'daily')}, samples={temporal.get('sample_count', 0)}.",
        f"- Spatial state: face_chainage={spatial.get('face_chainage')}, advance_length={spatial.get('advance_length')}, forward_level={spatial.get('forward_focus_level') or forward_attention.get('advice_level', 'none')}.",
        f"- Operation state: main_state={operation.get('main_state', 'N/A')}, work={operation.get('working_duration_min', 0)} min, stop={operation.get('stoppage_duration_min', 0)} min.",
        f"- Geological state: grade={geo.get('segment_grade')}, hazards={', '.join(_split_hazard_text(geo.get('hazards'))) or 'none'}, evidence_count={geo.get('evidence_count', 0)}.",
        f"- Response state: RAI={float(response.get('RAI') or 0.0):.2f}, anomaly_type={response.get('anomaly_type') or 'none'}, key_parameters={', '.join(response.get('key_parameters', []) or []) or 'none'}.",
        f"- Attention state: GRS={float(attention.get('GRS') or 0.0):.2f}, GRCI={float(attention.get('GRCI') or 0.0):.2f}, trend={attention.get('trend_label', 'stable')}, forward_hazards={', '.join(forward_hazards) or 'none'}.",
        f"- Provenance: confidence={float(provenance.get('state_confidence') or 0.0):.2f}, stability={float(temporal.get('state_stability') or 0.0):.2f}, changed_fields={', '.join(provenance.get('changed_fields', []) or []) or 'none'}.",
    ]
    previous_change_summary = provenance.get("previous_change_summary")
    if previous_change_summary:
        lines.append(f"- Previous-state delta: {previous_change_summary}")
    return "\n".join(lines)


def update_cst(
    previous_cst: dict[str, Any] | None,
    snapshot: dict[str, Any],
    *,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Update the canonical CST by combining the current snapshot with the previous CST."""
    context = context or {}
    snapshot = normalize_cst_state(snapshot)
    current = normalize_cst_state(snapshot)

    previous_id = previous_cst.get("cst_id") if isinstance(previous_cst, dict) else None
    current["cst_id"] = str(uuid4())
    current["state_key"] = _state_key(context)
    current["previous_cst_id"] = previous_id
    current["version"] = STATE_VERSION
    current["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    current["provenance_state"]["lineage"] = _lineage(previous_cst)

    if isinstance(previous_cst, dict):
        prev_spatial = previous_cst.get("spatial_state", {})
        prev_operation = previous_cst.get("operation_state", {})
        prev_geo = previous_cst.get("geological_state", {})
        prev_response = previous_cst.get("response_state", {})
        prev_attention = previous_cst.get("attention_state", {})
        prev_temporal = previous_cst.get("temporal_state", {})

        current["spatial_state"]["chainage_delta_from_previous"] = (
            (_safe_float(current["spatial_state"].get("face_chainage"), 0.0) or 0.0)
            - (_safe_float(prev_spatial.get("face_chainage"), 0.0) or 0.0)
        )
        current["operation_state"]["previous_main_state"] = prev_operation.get("main_state")
        current["operation_state"]["work_duration_delta"] = (
            (_safe_float(current["operation_state"].get("working_duration_min"), 0.0) or 0.0)
            - (_safe_float(prev_operation.get("working_duration_min"), 0.0) or 0.0)
        )
        current["operation_state"]["stop_duration_delta"] = (
            (_safe_float(current["operation_state"].get("stoppage_duration_min"), 0.0) or 0.0)
            - (_safe_float(prev_operation.get("stoppage_duration_min"), 0.0) or 0.0)
        )
        current["response_state"]["RAI_delta"] = (
            (_safe_float(current["response_state"].get("RAI"), 0.0) or 0.0)
            - (_safe_float(prev_response.get("RAI"), 0.0) or 0.0)
        )
        current["attention_state"]["GRS_delta"] = (
            (_safe_float(current["attention_state"].get("GRS"), 0.0) or 0.0)
            - (_safe_float(prev_attention.get("GRS"), 0.0) or 0.0)
        )
        current["attention_state"]["GRCI_delta"] = (
            (_safe_float(current["attention_state"].get("GRCI"), 0.0) or 0.0)
            - (_safe_float(prev_attention.get("GRCI"), 0.0) or 0.0)
        )
        current["temporal_state"]["previous_date"] = previous_cst.get("date")

        prev_sample_date = previous_cst.get("date")
        cur_sample_date = current.get("date")
        if prev_sample_date and cur_sample_date:
            try:
                prev_dt = datetime.strptime(prev_sample_date, "%Y-%m-%d")
                cur_dt = datetime.strptime(cur_sample_date, "%Y-%m-%d")
                current["temporal_state"]["continuity_gap_days"] = (cur_dt - prev_dt).days
            except ValueError:
                current["temporal_state"]["continuity_gap_days"] = None

        current["geological_state"]["persistent_hazards"] = _hazard_memory(
            previous_cst,
            _split_hazard_text(current["geological_state"].get("hazards")),
        )
        current["attention_state"]["persistent_attention_segments"] = _segment_memory(
            previous_cst,
            current["attention_state"].get("high_attention_segments", []),
        )
    else:
        current["geological_state"]["persistent_hazards"] = _hazard_memory(None, _split_hazard_text(current["geological_state"].get("hazards")))
        current["attention_state"]["persistent_attention_segments"] = _segment_memory(None, current["attention_state"].get("high_attention_segments", []))

    current["temporal_state"]["state_stability"] = _state_stability(previous_cst, current)
    current["attention_state"]["trend_label"] = _trend_label(previous_cst, current)
    current["provenance_state"]["state_confidence"] = _state_confidence(current)
    current["provenance_state"]["changed_fields"] = _changed_fields(previous_cst, current)
    current["provenance_state"]["previous_change_summary"] = summarize_cst_delta(previous_cst, current)

    return serialize_for_json(current)


def build_or_update_cst(
    analysis_result: dict[str, Any],
    *,
    case_id: str | None = None,
    context: dict[str, Any] | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    """Create the current CST snapshot and update it against the previous state."""
    context = context or {}
    previous_cst = load_previous_cst_for_context(
        date=context.get("date"),
        analysis_mode=context.get("analysis_mode") or "daily",
        end_time=context.get("time_end"),
    )
    snapshot = build_cst_snapshot(analysis_result, case_id=case_id, context=context)
    cst_state = update_cst(previous_cst, snapshot, context=context)
    if persist and cst_state.get("state_key"):
        save_cst_state(cst_state)
    return cst_state
