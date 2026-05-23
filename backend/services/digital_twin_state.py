import pandas as pd

from utils.chainage_utils import format_chainage_dk


def _safe_float(value):
    """Safely convert a value to float."""
    try:
        if pd.isna(value):
            return None
        return float(value)
    except Exception:
        return None


def _safe_timestamp(value):
    """Safely format a timestamp value."""
    try:
        if pd.isna(value):
            return None
        return pd.to_datetime(value).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return None


def _collect_gas_exceed_types(gas_stats: dict) -> list[str]:
    """Collect gas exceed types."""
    gas_all = gas_stats.get("all", {}) if isinstance(gas_stats, dict) else {}
    out = []
    for gas, stat in gas_all.items():
        if isinstance(stat, dict) and stat.get("exceed_event_count", 0) > 0:
            out.append(gas)
    return out


def _dominant_operation_state(stats: dict) -> str:
    """Internal helper for dominant operation state."""
    candidates = {
        "稳定掘进": stats.get("work_total_min", 0),
        "停机": stats.get("stop_total_min", 0),
        "启动/过渡": stats.get("transition_total_min", 0),
        "异常扭矩": stats.get("abnormal_total_min", 0),
    }
    return max(candidates, key=candidates.get) if candidates else "未知"


def build_digital_twin_state(
    df_geo: pd.DataFrame,
    stats: dict,
    state_stats: dict,
    gas_stats: dict,
    geo_summary_segment: dict,
    forward_risk_summary: dict,
    coupling_summary: dict,
) -> dict:
    """
    Build a compact TBM construction digital-twin state.

    This state is a data/status/risk twin rather than a 3D visualization twin.
    It provides a stable interface for report generation and paper experiments.
    """
    df = df_geo.copy() if df_geo is not None else pd.DataFrame()

    time_col = "运行时间-time"
    if time_col in df.columns:
        time_values = pd.to_datetime(df[time_col], errors="coerce").dropna()
    else:
        time_values = pd.Series(dtype="datetime64[ns]")

    if "chainage" in df.columns:
        chainage = pd.to_numeric(df["chainage"], errors="coerce").dropna()
    else:
        chainage = pd.Series(dtype=float)
    start_chainage = _safe_float(chainage.min()) if not chainage.empty else None
    end_chainage = _safe_float(chainage.max()) if not chainage.empty else None
    current_chainage = _safe_float(chainage.iloc[-1]) if not chainage.empty else None

    total_min = (
        stats.get("stop_total_min", 0)
        + stats.get("transition_total_min", 0)
        + stats.get("work_total_min", 0)
        + stats.get("abnormal_total_min", 0)
    )
    work_ratio = stats.get("work_total_min", 0) / total_min if total_min else 0
    stop_ratio = stats.get("stop_total_min", 0) / total_min if total_min else 0

    current_rows = df.tail(1)
    current_grade = None
    current_hazard = None
    current_sources = None
    if not current_rows.empty:
        row = current_rows.iloc[0]
        current_grade = row.get("fused_grade")
        current_hazard = row.get("hazard")
        current_sources = row.get("active_source_count")

    gas_exceed_types = _collect_gas_exceed_types(gas_stats)

    return {
        "time_state": {
            "start_time": _safe_timestamp(time_values.min()) if not time_values.empty else None,
            "end_time": _safe_timestamp(time_values.max()) if not time_values.empty else None,
            "duration_min": _safe_float((time_values.max() - time_values.min()).total_seconds() / 60)
            if len(time_values) >= 2 else 0,
            "sample_count": int(len(df)),
        },
        "position_state": {
            "start_chainage": start_chainage,
            "start_chainage_dk": format_chainage_dk(start_chainage),
            "end_chainage": end_chainage,
            "end_chainage_dk": format_chainage_dk(end_chainage),
            "current_chainage": current_chainage,
            "current_chainage_dk": format_chainage_dk(current_chainage),
            "advance_length": _safe_float(chainage.max() - chainage.min()) if len(chainage) >= 2 else 0,
        },
        "operation_state": {
            "dominant_state": _dominant_operation_state(stats),
            "work_count": int(stats.get("work_count", 0)),
            "stop_count": int(stats.get("stop_count", 0)),
            "abnormal_count": int(stats.get("abnormal_count", 0)),
            "work_total_min": _safe_float(stats.get("work_total_min", 0)),
            "stop_total_min": _safe_float(stats.get("stop_total_min", 0)),
            "work_ratio": _safe_float(work_ratio),
            "stop_ratio": _safe_float(stop_ratio),
            "state_switch_count": int(state_stats.get("状态切换次数", 0)) if isinstance(state_stats, dict) else 0,
        },
        "geology_state": {
            "current_grade": None if pd.isna(current_grade) else current_grade,
            "current_hazard": None if pd.isna(current_hazard) else current_hazard,
            "current_active_source_count": _safe_float(current_sources),
            "has_geology": bool(geo_summary_segment.get("has_geology", False))
            if isinstance(geo_summary_segment, dict) else False,
            "high_risk_segment_count": int(geo_summary_segment.get("high_risk_segment_count", 0))
            if isinstance(geo_summary_segment, dict) else 0,
            "multi_source_segment_count": int(geo_summary_segment.get("multi_source_segment_count", 0))
            if isinstance(geo_summary_segment, dict) else 0,
        },
        "safety_state": {
            "gas_exceed_type_count": len(gas_exceed_types),
            "gas_exceed_types": gas_exceed_types,
        },
        "forward_risk_state": {
            "has_forward_risk": bool(forward_risk_summary.get("has_forward_risk", False))
            if isinstance(forward_risk_summary, dict) else False,
            "lookahead_m": _safe_float(forward_risk_summary.get("lookahead_m"))
            if isinstance(forward_risk_summary, dict) else None,
            "advice_level": forward_risk_summary.get("advice_level")
            if isinstance(forward_risk_summary, dict) else None,
            "main_hazards": forward_risk_summary.get("main_hazards", [])
            if isinstance(forward_risk_summary, dict) else [],
        },
        "coupling_state": {
            "has_coupling": bool(coupling_summary.get("has_coupling", False))
            if isinstance(coupling_summary, dict) else False,
            "level_counts": coupling_summary.get("level_counts", {})
            if isinstance(coupling_summary, dict) else {},
            "summary_text": coupling_summary.get("summary_text")
            if isinstance(coupling_summary, dict) else None,
        },
    }
