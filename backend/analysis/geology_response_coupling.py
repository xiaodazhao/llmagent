from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from analysis.geo_risk_model import apply_dynamic_grs_correction, compute_row_grs_base
from utils.chainage_utils import format_chainage_range_dk
from utils.serialization import serialize_for_json


GEOLOGY_METHOD_VERSION = "GRS_RAI_GRCI_v3_engineering_dynamic"

GRADE_SCORES = {
    "I": 0.05,
    "II": 0.20,
    "III": 0.40,
    "IV": 0.70,
    "V": 1.00,
    "1": 0.05,
    "2": 0.20,
    "3": 0.40,
    "4": 0.70,
    "5": 1.00,
    "Ⅰ": 0.05,
    "Ⅱ": 0.20,
    "Ⅲ": 0.40,
    "Ⅳ": 0.70,
    "Ⅴ": 1.00,
}

HAZARD_KEYWORDS = [
    (("突水", "涌水", "出水", "富水", "water", "inrush"), 0.35),
    (("坍塌", "塌方", "掉块", "collapse", "fall"), 0.35),
    (("破碎", "极破碎", "围岩破碎", "broken", "fractured"), 0.30),
    (("裂隙", "裂缝", "裂隙密集", "joint", "fissure", "crack"), 0.25),
    (("异常反射", "明显反射异常", "反射异常", "reflection"), 0.25),
    (("断层", "软弱", "岩溶", "溶洞", "fault", "karst", "weak"), 0.35),
    (("变形", "挤压", "deformation", "squeeze"), 0.20),
]

CLASS_LABELS = {
    "A": "A类：地质响应耦合型高风险",
    "B": "B类：地质预警型潜在风险",
    "C": "C类：施工异常型未知风险",
    "D": "D类：正常稳定区段",
}

COUPLING_LEVEL_LABELS = {
    "strong": "强耦合区",
    "medium": "中耦合区",
    "weak": "弱耦合区",
    "low": "低耦合区",
    "unknown": "未知耦合区",
}

FIELD_ALIASES = {
    "chainage": ["chainage", "里程", "当前里程", "桩号", "推进里程"],
    "time": ["时间", "timestamp", "datetime", "date_time", "采集时间"],
    "speed": ["推进速度", "advance_speed", "speed", "actual_speed"],
    "set_speed": ["推进给定速度", "给定速度", "target_speed", "set_speed"],
    "thrust": ["推力", "总推力", "thrust", "total_thrust"],
    "torque": ["刀盘扭矩", "扭矩", "cutter_torque", "torque"],
    "rpm": ["刀盘转速", "转速", "cutter_rpm", "rpm"],
    "penetration": ["贯入度", "penetration"],
    "state": ["掘进状态", "施工状态", "state", "excavation_state"],
    "risk_score": ["risk_score", "地质风险分数", "风险分数"],
    "geo_prior_score": ["geo_prior_score", "geo_risk_score", "地质先验分数"],
    "active_source_count": ["active_source_count", "source_count", "命中来源数", "多源命中数"],
    "water_flag": ["water_flag_fused", "water_flag", "出水标记"],
    "collapse_flag": ["collapse_flag_fused", "collapse_flag", "坍塌标记", "掉块标记"],
    "deformation_flag": ["deformation_flag_fused", "deformation_flag", "变形标记"],
    "grade": ["fused_grade", "围岩等级", "grade", "rock_grade"],
    "risk": ["risk", "risk_mode", "风险等级"],
    "hazard": ["hazard", "hazard_mode", "灾害", "灾害表现", "hazard_desc"],
    "coverage": ["coverage", "coverage_mode", "覆盖情况"],
    "uncertainty": ["uncertainty", "不确定性"],
    "active_sources": ["active_sources", "sources", "证据来源"],
}

METRIC_COLUMNS = [
    "segment",
    "GRS",
    "geo_risk_score",
    "GRS_base",
    "GRS_corrected",
    "GRS_smooth",
    "GRS_final",
    "correction",
    "correction_factor",
    "GRS_mean",
    "GRS_max",
    "RAI",
    "response_anomaly_index",
    "stop_anomaly",
    "efficiency_anomaly",
    "param_anomaly",
    "anomaly_type",
    "anomaly_type_score",
    "GRCI",
    "coupling_index",
    "coupling_class",
    "coupling_type",
    "delta_RAI",
    "delta_GRS",
    "geo_risk_norm",
    "source_evidence_norm",
    "response_consistency",
    "sync_coupling",
    "lag_coupling",
    "lag_response",
    "response_change_coupling",
    "risk_response_coupling_index",
    "coupling_level",
    "coupling_label",
    "grci_class_code",
    "grci_class_label",
    "coupling_interpretation",
    "weak_anomaly_label",
    "weak_anomaly_reasons",
    "speed_drop_score",
    "speed_volatility_score",
    "thrust_anomaly_score",
    "torque_anomaly_score",
    "rpm_anomaly_score",
    "penetration_anomaly_score",
    "efficiency_anomaly_score",
    "speed_zero_ratio",
    "stop_state_ratio",
]


def run_coupling_analysis(
    df_geo: pd.DataFrame,
    segment_length: float = 10.0,
    base_segment_df: pd.DataFrame | None = None,
    output_dir: str | Path | None = None,
    output_prefix: str | None = None,
    top_k: int = 10,
    risk_threshold: float = 0.55,
    response_threshold: float = 0.55,
) -> dict[str, Any]:
    """Run segment-level geology-risk and construction-response coupling analysis.

    The method builds three core values:
    - GRS: Geology Risk Score, 0-1
    - RAI: Response Anomaly Index, 0-1
    - GRCI: Geology Response Coupling Index, 0-1
    """
    warnings: list[str] = []
    if df_geo is None or df_geo.empty:
        empty = pd.DataFrame()
        return {
            "segment_df": empty,
            "high_attention_segments": [],
            "summary": _empty_summary("input dataframe is empty", warnings),
            "validation": _empty_validation(),
            "output_paths": {},
            "warnings": warnings,
        }

    df = df_geo.copy()
    colmap = _resolve_columns(df, warnings)
    if not colmap.get("chainage"):
        warnings.append("missing chainage column; coupling analysis skipped")
        empty = base_segment_df.copy() if base_segment_df is not None else pd.DataFrame()
        return {
            "segment_df": empty,
            "high_attention_segments": [],
            "summary": _empty_summary("missing chainage column", warnings),
            "validation": _empty_validation(),
            "output_paths": {},
            "warnings": warnings,
        }

    df = _prepare_raw_dataframe(df, colmap, segment_length)
    if df.empty:
        warnings.append("no valid chainage rows after cleaning")
        empty = base_segment_df.copy() if base_segment_df is not None else pd.DataFrame()
        return {
            "segment_df": empty,
            "high_attention_segments": [],
            "summary": _empty_summary("no valid chainage rows", warnings),
            "validation": _empty_validation(),
            "output_paths": {},
            "warnings": warnings,
        }

    df["row_grs_base"], df["source_evidence_norm"], _grs_components = _compute_row_geology_scores(
        df,
        colmap,
        warnings,
    )
    df["row_grs"] = df["row_grs_base"]
    segment_metrics = _aggregate_segment_features(df, colmap, warnings)
    segment_metrics = _add_response_anomaly_index(segment_metrics, warnings)
    segment_metrics, grs_metadata = apply_dynamic_grs_correction(segment_metrics)
    segment_metrics = _add_coupling_index(
        segment_metrics,
        risk_threshold=risk_threshold,
        response_threshold=response_threshold,
    )
    segment_metrics = _add_weak_validation_labels(segment_metrics)

    segment_df = _merge_with_base_segments(base_segment_df, segment_metrics)
    if "segment_start_first" in segment_df.columns:
        segment_df = segment_df.sort_values("segment_start_first").reset_index(drop=True)
    elif "segment_start" in segment_df.columns:
        segment_df = segment_df.sort_values("segment_start").reset_index(drop=True)

    validation = _validate_coupling(segment_df, top_k=top_k)
    high_attention_segments = _build_high_attention(segment_df, top_k=top_k)
    summary = _build_summary(
        segment_df=segment_df,
        validation=validation,
        high_attention_segments=high_attention_segments,
        segment_length=segment_length,
        warnings=warnings,
        grs_metadata=grs_metadata,
    )
    output_paths = _write_outputs(
        segment_df=segment_df,
        high_attention_segments=high_attention_segments,
        summary=summary,
        output_dir=output_dir,
        output_prefix=output_prefix or _infer_output_prefix(df, colmap),
        warnings=warnings,
    )
    summary["output_paths"] = output_paths
    summary["warnings"] = warnings

    return {
        "segment_df": segment_df,
        "high_attention_segments": high_attention_segments,
        "summary": summary,
        "validation": validation,
        "output_paths": output_paths,
        "warnings": warnings,
    }


def _resolve_columns(df: pd.DataFrame, warnings: list[str]) -> dict[str, str | None]:
    """Resolve columns."""
    resolved = {}
    for key, aliases in FIELD_ALIASES.items():
        resolved[key] = _find_column(df, aliases)

    required_response = ["speed", "thrust", "torque"]
    missing_response = [key for key in required_response if not resolved.get(key)]
    if missing_response:
        warnings.append(f"missing response fields: {', '.join(missing_response)}")

    geology_fields = [
        "risk_score",
        "geo_prior_score",
        "active_source_count",
        "water_flag",
        "collapse_flag",
        "deformation_flag",
        "grade",
        "hazard",
        "risk",
    ]
    if not any(resolved.get(key) for key in geology_fields):
        warnings.append("no geology risk fields found; GRS will be near zero")

    return resolved


def _find_column(df: pd.DataFrame, aliases: list[str]) -> str | None:
    """Internal helper for find column."""
    lower_map = {str(col).strip().lower(): col for col in df.columns}
    for alias in aliases:
        key = alias.strip().lower()
        if key in lower_map:
            return lower_map[key]

    for alias in aliases:
        key = alias.strip().lower()
        for col in df.columns:
            if key and key in str(col).strip().lower():
                return col
    return None


def _prepare_raw_dataframe(df: pd.DataFrame, colmap: dict[str, str | None], segment_length: float) -> pd.DataFrame:
    """Prepare raw dataframe."""
    out = df.copy()
    chainage_col = colmap["chainage"]
    out["chainage"] = pd.to_numeric(out[chainage_col], errors="coerce")
    out = out.dropna(subset=["chainage"]).copy()

    for key in ["speed", "set_speed", "thrust", "torque", "rpm", "penetration", "state"]:
        col = colmap.get(key)
        if col:
            out[f"__{key}"] = pd.to_numeric(out[col], errors="coerce")

    for key in [
        "risk_score",
        "geo_prior_score",
        "active_source_count",
        "water_flag",
        "collapse_flag",
        "deformation_flag",
    ]:
        col = colmap.get(key)
        if col:
            out[f"__{key}"] = pd.to_numeric(out[col], errors="coerce")

    out["segment_start"] = (np.floor(out["chainage"] / segment_length) * segment_length).astype(float)
    out["segment_end"] = out["segment_start"] + segment_length
    out["segment_id"] = out["segment_start"].map(_number_key) + "_" + out["segment_end"].map(_number_key)
    return out


def _compute_row_geology_scores(
    df: pd.DataFrame,
    colmap: dict[str, str | None],
    warnings: list[str],
) -> tuple[pd.Series, pd.Series, pd.DataFrame]:
    """Delegate GRS_base calculation to the engineering-prior geology model."""
    return compute_row_grs_base(df, colmap, warnings)



def _aggregate_segment_features(
    df: pd.DataFrame,
    colmap: dict[str, str | None],
    warnings: list[str],
) -> pd.DataFrame:
    """Internal helper for aggregate segment features."""
    grouped = df.groupby("segment_id", sort=False)

    out = grouped.agg(
        chainage_min=("chainage", "min"),
        chainage_max=("chainage", "max"),
        chainage_mean=("chainage", "mean"),
        chainage_count=("chainage", "count"),
        segment_start_first=("segment_start", "first"),
        segment_end_first=("segment_end", "first"),
        GRS_mean=("row_grs_base", "mean"),
        GRS_max=("row_grs_base", "max"),
        source_evidence_norm=("source_evidence_norm", "max"),
    ).reset_index()

    out["GRS_base"] = (0.35 * out["GRS_mean"] + 0.65 * out["GRS_max"]).clip(0, 1)
    out["GRS"] = out["GRS_base"]
    out["geo_risk_score"] = out["GRS"]
    out["geo_risk_norm"] = out["GRS"]
    out["segment"] = out.apply(
        lambda row: format_chainage_range_dk(row["segment_start_first"], row["segment_end_first"]),
        axis=1,
    )

    for key in ["speed", "set_speed", "thrust", "torque", "rpm", "penetration"]:
        col = f"__{key}"
        if col not in df.columns:
            continue
        stats = grouped[col].agg(["mean", "std", "min", "max", "median"]).reset_index()
        stats = stats.rename(columns={
            "mean": f"{key}_mean",
            "std": f"{key}_std",
            "min": f"{key}_min",
            "max": f"{key}_max",
            "median": f"{key}_median",
        })
        out = out.merge(stats, on="segment_id", how="left")
        mean_col = f"{key}_mean"
        std_col = f"{key}_std"
        if mean_col in out.columns and std_col in out.columns:
            denom = out[mean_col].abs().replace(0, np.nan)
            out[f"{key}_cv"] = (out[std_col] / denom).replace([np.inf, -np.inf], np.nan).fillna(0)

    for key, source_col in [
        ("risk_mode", colmap.get("risk")),
        ("hazard_mode", colmap.get("hazard")),
        ("fused_grade_mode", colmap.get("grade")),
        ("coverage_mode", colmap.get("coverage")),
    ]:
        if source_col:
            out[key] = grouped[source_col].agg(_mode_text).values

    if "__speed" in df.columns:
        speed_reference = _safe_positive_median(df["__speed"])
        low_threshold = speed_reference * 0.10 if speed_reference > 0 else 1e-6
        zero_ratio = grouped["__speed"].apply(
            lambda x: float((pd.to_numeric(x, errors="coerce").fillna(0).abs() <= low_threshold).mean())
        )
        out = out.merge(zero_ratio.rename("speed_zero_ratio").reset_index(), on="segment_id", how="left")
    else:
        out["speed_zero_ratio"] = 0.0

    if "__state" in df.columns:
        stop_ratio = grouped["__state"].apply(
            lambda x: float((pd.to_numeric(x, errors="coerce").fillna(-1) == 0).mean())
        )
        out = out.merge(stop_ratio.rename("stop_state_ratio").reset_index(), on="segment_id", how="left")
    else:
        out["stop_state_ratio"] = 0.0

    if "speed_mean" in out.columns and "set_speed_mean" in out.columns:
        denom = pd.to_numeric(out["set_speed_mean"], errors="coerce").replace(0, np.nan)
        out["efficiency"] = (pd.to_numeric(out["speed_mean"], errors="coerce") / denom).replace(
            [np.inf, -np.inf], np.nan
        )

    if "speed_mean" not in out.columns:
        warnings.append("speed column not found; speed decay and efficiency anomalies are limited")
    if "torque_mean" not in out.columns:
        warnings.append("torque column not found; torque anomaly validation is limited")

    return out


def _add_response_anomaly_index(segment_df: pd.DataFrame, warnings: list[str]) -> pd.DataFrame:
    """Internal helper for add response anomaly index."""
    out = segment_df.copy()
    idx = out.index
    score_cols: list[str] = []
    group_scores: dict[str, pd.Series] = {}

    def add_score(name: str, series: pd.Series, side: str, group: str) -> None:
        """Handle add score."""
        score = _robust_score(series, side=side)
        out[name] = score
        score_cols.append(name)
        if group in group_scores:
            group_scores[group] = pd.concat([group_scores[group], score], axis=1).max(axis=1)
        else:
            group_scores[group] = score

    if "speed_mean" in out.columns:
        add_score("speed_drop_score", out["speed_mean"], "low", "speed")
    else:
        out["speed_drop_score"] = _zero_series(idx)

    if "speed_cv" in out.columns:
        add_score("speed_volatility_score", out["speed_cv"], "high", "speed")
    elif "speed_std" in out.columns:
        add_score("speed_volatility_score", out["speed_std"], "high", "speed")
    else:
        out["speed_volatility_score"] = _zero_series(idx)

    load_parts = []
    if "thrust_mean" in out.columns:
        thrust_score = _robust_score(out["thrust_mean"], side="high")
        load_parts.append(thrust_score)
    if "thrust_cv" in out.columns:
        load_parts.append(_robust_score(out["thrust_cv"], side="high"))
    out["thrust_anomaly_score"] = _combine_scores(load_parts, idx)
    if load_parts:
        score_cols.append("thrust_anomaly_score")
        group_scores["thrust"] = out["thrust_anomaly_score"]

    torque_parts = []
    if "torque_mean" in out.columns:
        torque_parts.append(_robust_score(out["torque_mean"], side="high"))
    if "torque_cv" in out.columns:
        torque_parts.append(_robust_score(out["torque_cv"], side="high"))
    out["torque_anomaly_score"] = _combine_scores(torque_parts, idx)
    if torque_parts:
        score_cols.append("torque_anomaly_score")
        group_scores["torque"] = out["torque_anomaly_score"]

    rpm_parts = []
    if "rpm_mean" in out.columns:
        rpm_parts.append(_robust_score(out["rpm_mean"], side="two"))
    if "rpm_cv" in out.columns:
        rpm_parts.append(_robust_score(out["rpm_cv"], side="high"))
    out["rpm_anomaly_score"] = _combine_scores(rpm_parts, idx)
    if rpm_parts:
        score_cols.append("rpm_anomaly_score")
        group_scores["rpm"] = out["rpm_anomaly_score"]

    penetration_parts = []
    if "penetration_mean" in out.columns:
        penetration_parts.append(_robust_score(out["penetration_mean"], side="two"))
    if "penetration_cv" in out.columns:
        penetration_parts.append(_robust_score(out["penetration_cv"], side="high"))
    out["penetration_anomaly_score"] = _combine_scores(penetration_parts, idx)
    if penetration_parts:
        score_cols.append("penetration_anomaly_score")
        group_scores["penetration"] = out["penetration_anomaly_score"]

    if "efficiency" in out.columns:
        out["efficiency_anomaly_score"] = _robust_score(out["efficiency"], side="low")
        score_cols.append("efficiency_anomaly_score")
        group_scores["efficiency"] = out["efficiency_anomaly_score"]
    else:
        out["efficiency_anomaly_score"] = _zero_series(idx)

    if score_cols:
        score_matrix = out[score_cols].fillna(0).clip(0, 1)
        top_mean = score_matrix.apply(
            lambda row: float(np.mean(sorted(row.tolist(), reverse=True)[: min(3, len(row))])),
            axis=1,
        )
        mean_all = score_matrix.mean(axis=1)
    else:
        warnings.append("no PLC parameter anomaly fields available; param_anomaly is set to zero")
        top_mean = _zero_series(idx)
        mean_all = _zero_series(idx)

    if group_scores:
        group_matrix = pd.concat(group_scores, axis=1).fillna(0).clip(0, 1)
        out["response_consistency"] = (group_matrix >= 0.55).sum(axis=1) / max(len(group_matrix.columns), 1)
    else:
        out["response_consistency"] = 0.0

    out["stop_anomaly"] = _compute_stop_anomaly(out, warnings)
    out["efficiency_anomaly"] = _compute_efficiency_anomaly(out, warnings)
    out["param_anomaly"] = (
        0.60 * top_mean
        + 0.25 * mean_all
        + 0.15 * pd.to_numeric(out["response_consistency"], errors="coerce").fillna(0)
    ).clip(0, 1)

    out["RAI"] = (
        0.50 * out["stop_anomaly"]
        + 0.30 * out["efficiency_anomaly"]
        + 0.20 * out["param_anomaly"]
    ).clip(0, 1)
    out["response_anomaly_index"] = out["RAI"]
    out["load_response_norm"] = pd.concat(
        [out["thrust_anomaly_score"], out["torque_anomaly_score"]],
        axis=1,
    ).max(axis=1).fillna(0)
    out["speed_decay_norm"] = out["speed_drop_score"].fillna(0)
    out = _add_anomaly_pattern(out)
    return out


def _add_anomaly_pattern(segment_df: pd.DataFrame) -> pd.DataFrame:
    """Internal helper for add anomaly pattern."""
    out = segment_df.copy()
    idx = out.index

    stop_dominant = pd.to_numeric(out.get("stop_anomaly", _zero_series(idx)), errors="coerce").fillna(0).clip(0, 1)
    efficiency_drop = pd.to_numeric(
        out.get("efficiency_anomaly", _zero_series(idx)),
        errors="coerce",
    ).fillna(0).clip(0, 1)
    speed_drop = pd.to_numeric(out.get("speed_drop_score", _zero_series(idx)), errors="coerce").fillna(0).clip(0, 1)
    high_load = pd.concat([
        pd.to_numeric(out.get("thrust_anomaly_score", _zero_series(idx)), errors="coerce").fillna(0),
        pd.to_numeric(out.get("torque_anomaly_score", _zero_series(idx)), errors="coerce").fillna(0),
        pd.to_numeric(out.get("load_response_norm", _zero_series(idx)), errors="coerce").fillna(0),
    ], axis=1).max(axis=1).clip(0, 1)
    volatility = _volatility_pattern_score(out, idx)
    pattern_scores = pd.DataFrame(
        {
            "stop_dominant": stop_dominant,
            "efficiency_drop": efficiency_drop,
            "high_load": high_load,
            "volatility": volatility,
            "speed_drop": speed_drop,
        },
        index=idx,
    ).fillna(0).clip(0, 1)
    out["anomaly_type_score"] = pattern_scores.max(axis=1).fillna(0)
    out["anomaly_type"] = [
        _classify_anomaly_pattern(row)
        for _, row in pattern_scores.iterrows()
    ]
    return out


def _compute_stop_anomaly(out: pd.DataFrame, warnings: list[str]) -> pd.Series:
    """Build a 0-1 stop anomaly score from explicit ratios or segment fallbacks."""
    idx = out.index
    explicit_cols = [
        "stop_ratio",
        "stop_duration_ratio",
        "stop_time_ratio",
        "stop_total_ratio",
        "stoppage_ratio",
    ]
    explicit_parts = [_ratio_series(out[col]) for col in explicit_cols if col in out.columns]
    if explicit_parts:
        return pd.concat(explicit_parts, axis=1).max(axis=1).fillna(0).clip(0, 1)

    working_cols = [
        "working_ratio",
        "work_ratio",
        "working_time_ratio",
        "work_time_ratio",
        "effective_working_ratio",
        "effective_digging_ratio",
        "digging_ratio",
    ]
    working_parts = [(1.0 - _ratio_series(out[col])).clip(0, 1) for col in working_cols if col in out.columns]
    if working_parts:
        warnings.append("stop_anomaly uses working_ratio fallback because stop-ratio fields are missing")
        return pd.concat(working_parts, axis=1).max(axis=1).fillna(0).clip(0, 1)

    fallback_cols = [col for col in ["stop_state_ratio", "speed_zero_ratio"] if col in out.columns]
    if fallback_cols:
        warnings.append("stop_anomaly uses segment-level stop samples / zero-speed fallback")
        return pd.concat([_ratio_series(out[col]) for col in fallback_cols], axis=1).max(axis=1).fillna(0).clip(0, 1)

    warnings.append("stop_anomaly fields are missing; stop_anomaly is set to zero")
    return _zero_series(idx)


def _compute_efficiency_anomaly(out: pd.DataFrame, warnings: list[str]) -> pd.Series:
    """Build a 0-1 efficiency anomaly score from work ratio or speed efficiency."""
    idx = out.index
    working_cols = [
        "working_ratio",
        "work_ratio",
        "working_time_ratio",
        "work_time_ratio",
        "effective_working_ratio",
        "effective_digging_ratio",
        "digging_ratio",
    ]
    working_parts = [(1.0 - _ratio_series(out[col])).clip(0, 1) for col in working_cols if col in out.columns]
    if working_parts:
        return pd.concat(working_parts, axis=1).max(axis=1).fillna(0).clip(0, 1)

    if "stop_anomaly" in out.columns:
        warnings.append("efficiency_anomaly uses inferred working-ratio fallback from stop_anomaly")
        return pd.to_numeric(out["stop_anomaly"], errors="coerce").fillna(0).clip(0, 1)

    if "efficiency" in out.columns:
        values = pd.to_numeric(out["efficiency"], errors="coerce").replace([np.inf, -np.inf], np.nan)
        if values.notna().any():
            efficiency_score = (1.0 - values.fillna(0)).clip(0, 1)
            if float(efficiency_score.max(skipna=True) or 0) > 1e-9:
                return efficiency_score

    if "speed_drop_score" in out.columns:
        warnings.append("efficiency_anomaly uses speed-drop fallback because working_ratio/efficiency fields are missing")
        return pd.to_numeric(out["speed_drop_score"], errors="coerce").fillna(0).clip(0, 1)

    if "speed_mean" in out.columns:
        speed = pd.to_numeric(out["speed_mean"], errors="coerce").replace([np.inf, -np.inf], np.nan)
        reference = speed[speed > 0].quantile(0.75)
        if pd.notna(reference) and reference > 1e-9:
            warnings.append("efficiency_anomaly uses relative speed fallback because working_ratio is missing")
            return (1.0 - (speed.fillna(0) / reference)).clip(0, 1)

    warnings.append("efficiency_anomaly fields are missing; efficiency_anomaly is set to zero")
    return _zero_series(idx)


def _ratio_series(series: pd.Series) -> pd.Series:
    """Internal helper for ratio series."""
    values = pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0)
    max_value = values.max(skipna=True)
    if pd.notna(max_value) and max_value > 1.0 and max_value <= 100.0:
        values = values / 100.0
    return values.clip(0, 1)


def _classify_anomaly_pattern(row: pd.Series) -> str:
    """Classify anomaly pattern."""
    stop_score = float(row.get("stop_dominant", 0) or 0)
    efficiency_score = float(row.get("efficiency_drop", 0) or 0)
    high_load_score = float(row.get("high_load", 0) or 0)
    volatility_score = float(row.get("volatility", 0) or 0)
    speed_score = float(row.get("speed_drop", 0) or 0)

    max_key = str(row.idxmax())
    max_score = float(row.max())
    if max_key == "stop_dominant" and stop_score >= 0.50:
        return "停机主导型"
    if max_key == "efficiency_drop" and efficiency_score >= 0.40:
        return "效率下降型"
    if max_key == "high_load" and high_load_score >= 0.35:
        return "高负载型"
    if max_key == "volatility" and volatility_score >= 0.35:
        return "波动型"
    if max_key == "speed_drop" and speed_score >= 0.35:
        return "速度下降型"
    if max_score >= 0.35:
        return "综合异常型"
    return "轻微异常型"


def _volatility_pattern_score(out: pd.DataFrame, idx: pd.Index) -> pd.Series:
    """Internal helper for volatility pattern score."""
    candidates = []
    for col in ["speed_volatility_score"]:
        if col in out.columns:
            candidates.append(pd.to_numeric(out[col], errors="coerce").fillna(0).clip(0, 1))
    for col in ["speed_cv", "thrust_cv", "torque_cv", "rpm_cv", "penetration_cv"]:
        if col in out.columns:
            values = pd.to_numeric(out[col], errors="coerce").replace([np.inf, -np.inf], np.nan)
            reference = values.quantile(0.75)
            if pd.notna(reference) and reference > 1e-9:
                candidates.append((values / (reference * 2.0)).fillna(0).clip(0, 1))
    return _combine_scores(candidates, idx)


def _add_coupling_index(
    segment_df: pd.DataFrame,
    risk_threshold: float,
    response_threshold: float,
) -> pd.DataFrame:
    """Internal helper for add coupling index."""
    out = segment_df.copy()
    grs = pd.to_numeric(out.get("GRS", 0), errors="coerce").fillna(0).clip(0, 1)
    rai = pd.to_numeric(out.get("RAI", 0), errors="coerce").fillna(0).clip(0, 1)

    balance = (1 - (grs - rai).abs()).clip(0, 1)
    sync = (
        0.50 * np.minimum(grs, rai)
        + 0.30 * np.sqrt((grs * rai).clip(0, 1))
        + 0.20 * balance * ((grs + rai) / 2)
    ).clip(0, 1)

    prev_grs = grs.shift(1).fillna(0)
    prev_rai = rai.shift(1).fillna(0)
    delta_grs = (grs - prev_grs).fillna(0).clip(lower=-1, upper=1)
    delta_rai = (rai - prev_rai).fillna(0).clip(lower=-1, upper=1)
    risk_entry = (grs - prev_grs).clip(lower=0, upper=1)
    response_rise = delta_rai.clip(lower=0, upper=1)
    lag = pd.concat([
        np.minimum(prev_grs, rai),
        np.minimum(grs, response_rise * 1.5),
        np.minimum(risk_entry * 1.5, rai),
    ], axis=1).max(axis=1).clip(0, 1)
    response_change = pd.concat([
        np.minimum(grs, response_rise * 1.8),
        np.sqrt((risk_entry * response_rise).clip(0, 1)),
        np.minimum((delta_grs.abs() * 1.2).clip(0, 1), rai),
    ], axis=1).max(axis=1).clip(0, 1)

    consistency = pd.to_numeric(out.get("response_consistency", 0), errors="coerce").fillna(0).clip(0, 1)
    source = pd.to_numeric(out.get("source_evidence_norm", 0), errors="coerce").fillna(0).clip(0, 1)
    multi_param = (consistency * rai).clip(0, 1)
    confidence = (0.85 + 0.15 * source).clip(0.85, 1.0)

    grci = (0.40 * sync + 0.25 * lag + 0.25 * response_change + 0.10 * multi_param) * confidence
    out["delta_RAI"] = delta_rai
    out["delta_GRS"] = delta_grs
    out["sync_coupling"] = sync.clip(0, 1)
    out["lag_coupling"] = lag.clip(0, 1)
    out["lag_response"] = lag.clip(0, 1)
    out["response_change_coupling"] = response_change.clip(0, 1)
    out["GRCI"] = grci.clip(0, 1).fillna(0)
    out["coupling_index"] = out["GRCI"]
    out["risk_response_coupling_index"] = out["GRCI"]

    out["coupling_level"] = out["GRCI"].map(_coupling_level)
    out["coupling_label"] = out["coupling_level"].map(COUPLING_LEVEL_LABELS).fillna(COUPLING_LEVEL_LABELS["unknown"])
    out["grci_class_code"] = [
        _classify_segment(risk, response, risk_threshold, response_threshold)
        for risk, response in zip(grs, rai)
    ]
    out["grci_class_label"] = out["grci_class_code"].map(CLASS_LABELS)
    out["coupling_class"] = out["grci_class_code"]
    out["coupling_type"] = out["grci_class_label"]
    out["coupling_interpretation"] = out.apply(_build_interpretation, axis=1)
    return out


def _add_weak_validation_labels(segment_df: pd.DataFrame) -> pd.DataFrame:
    """Internal helper for add weak validation labels."""
    out = segment_df.copy()
    reasons = []
    labels = []
    for _, row in out.iterrows():
        row_reasons = []
        if float(row.get("speed_zero_ratio", 0) or 0) >= 0.45 or float(row.get("stop_state_ratio", 0) or 0) >= 0.45:
            row_reasons.append("long_stop_proxy")
        if float(row.get("speed_drop_score", 0) or 0) >= 0.65:
            row_reasons.append("speed_drop")
        if float(row.get("torque_anomaly_score", 0) or 0) >= 0.65:
            row_reasons.append("torque_fluctuation")
        if float(row.get("efficiency_anomaly_score", 0) or 0) >= 0.65:
            row_reasons.append("low_efficiency")
        if float(row.get("RAI", 0) or 0) >= 0.75 and float(row.get("response_consistency", 0) or 0) >= 0.40:
            row_reasons.append("multi_parameter_response")

        labels.append(bool(row_reasons))
        reasons.append(",".join(row_reasons))

    out["weak_anomaly_label"] = labels
    out["weak_anomaly_reasons"] = reasons
    return out


def _validate_coupling(segment_df: pd.DataFrame, top_k: int) -> dict[str, Any]:
    """Internal helper for validate coupling."""
    if segment_df is None or segment_df.empty:
        return _empty_validation()

    labels = segment_df.get("weak_anomaly_label", pd.Series(False, index=segment_df.index)).astype(bool)
    scores = pd.to_numeric(segment_df.get("GRCI", 0), errors="coerce").fillna(0)
    top_n = int(min(max(top_k, 1), len(segment_df)))
    top_idx = scores.sort_values(ascending=False).head(top_n).index
    top_hits = int(labels.loc[top_idx].sum()) if len(top_idx) else 0

    threshold = 0.60
    pred = scores >= threshold
    tp = int((pred & labels).sum())
    fp = int((pred & ~labels).sum())
    fn = int((~pred & labels).sum())

    precision = _safe_div(tp, tp + fp)
    recall = _safe_div(tp, tp + fn)

    return {
        "has_validation": True,
        "weak_label_count": int(labels.sum()),
        "segment_count": int(len(segment_df)),
        "top_k": top_n,
        "top_k_hits": top_hits,
        "top_k_hit_rate": _safe_div(top_hits, top_n),
        "baseline_weak_label_rate": _safe_div(int(labels.sum()), len(segment_df)),
        "threshold": threshold,
        "precision": precision,
        "recall": recall,
        "tp": tp,
        "fp": fp,
        "fn": fn,
    }


def _build_high_attention(segment_df: pd.DataFrame, top_k: int) -> list[dict[str, Any]]:
    """Build high attention."""
    if segment_df is None or segment_df.empty:
        return []

    sort_col = "GRCI" if "GRCI" in segment_df.columns else "risk_response_coupling_index"
    keep_cols = [
        "segment",
        "segment_start_first",
        "segment_end_first",
        "GRS",
        "geo_risk_score",
        "GRS_base",
        "GRS_corrected",
        "GRS_smooth",
        "GRS_final",
        "correction",
        "correction_factor",
        "RAI",
        "response_anomaly_index",
        "stop_anomaly",
        "efficiency_anomaly",
        "param_anomaly",
        "anomaly_type",
        "anomaly_type_score",
        "GRCI",
        "coupling_index",
        "delta_RAI",
        "lag_response",
        "response_change_coupling",
        "risk_response_coupling_index",
        "coupling_label",
        "grci_class_code",
        "grci_class_label",
        "coupling_class",
        "coupling_type",
        "weak_anomaly_label",
        "weak_anomaly_reasons",
        "coupling_interpretation",
    ]
    top = segment_df.sort_values(sort_col, ascending=False).head(top_k)
    return serialize_for_json(top[[c for c in keep_cols if c in top.columns]].to_dict(orient="records"))


def _build_summary(
    segment_df: pd.DataFrame,
    validation: dict[str, Any],
    high_attention_segments: list[dict[str, Any]],
    segment_length: float,
    warnings: list[str],
    grs_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build summary."""
    if segment_df is None or segment_df.empty:
        return _empty_summary("no segment result", warnings)

    grci = pd.to_numeric(segment_df.get("GRCI", 0), errors="coerce").fillna(0)
    grs = pd.to_numeric(segment_df.get("GRS", 0), errors="coerce").fillna(0)
    rai = pd.to_numeric(segment_df.get("RAI", 0), errors="coerce").fillna(0)
    class_counts = segment_df.get("grci_class_label", pd.Series(dtype=str)).value_counts().to_dict()
    level_counts = segment_df.get("coupling_label", pd.Series(dtype=str)).value_counts().to_dict()
    top = high_attention_segments[0] if high_attention_segments else {}

    summary_text = (
        f"区段级地质风险-施工响应耦合分析完成，共 {len(segment_df)} 个区段，"
        f"最高关注区段为 {top.get('segment', '--')}，"
        f"GRCI={float(top.get('GRCI', top.get('risk_response_coupling_index', 0)) or 0):.2f}，"
        f"类型为 {top.get('grci_class_label', '--')}。"
    )

    grs_metadata = grs_metadata or {}
    return {
        "has_coupling": True,
        "method": GEOLOGY_METHOD_VERSION,
        "grs_model_version": grs_metadata.get("grs_model_version"),
        "segment_length_m": segment_length,
        "segment_count": int(len(segment_df)),
        "GRS_mean": float(grs.mean()),
        "GRS_max": float(grs.max()),
        "RAI_mean": float(rai.mean()),
        "RAI_max": float(rai.max()),
        "GRCI_mean": float(grci.mean()),
        "GRCI_max": float(grci.max()),
        "class_counts": serialize_for_json(class_counts),
        "level_counts": serialize_for_json(level_counts),
        "engineering_weights": serialize_for_json(grs_metadata.get("engineering_weights", {})),
        "grs_weight_method": grs_metadata.get("grs_weight_method", "engineering_prior_dynamic"),
        "correction_lambda": grs_metadata.get("correction_lambda"),
        "min_grs": grs_metadata.get("min_grs"),
        "correction_formula": grs_metadata.get("correction_formula"),
        "grs_correction_mode": grs_metadata.get("correction_mode"),
        "grs_has_rai": grs_metadata.get("has_rai"),
        "grs_has_stop_ratio": grs_metadata.get("has_stop_ratio"),
        "top_segments": high_attention_segments,
        "high_attention_segments": high_attention_segments,
        "validation": validation,
        "summary_text": summary_text,
        "warnings": warnings,
    }


def _write_outputs(
    segment_df: pd.DataFrame,
    high_attention_segments: list[dict[str, Any]],
    summary: dict[str, Any],
    output_dir: str | Path | None,
    output_prefix: str,
    warnings: list[str],
) -> dict[str, str]:
    """Internal helper for write outputs."""
    if output_dir is None or segment_df is None or segment_df.empty:
        return {}

    paths: dict[str, str] = {}
    try:
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        safe_prefix = re.sub(r"[^0-9A-Za-z_.-]+", "_", output_prefix).strip("_") or "tbm_coupling"

        segment_path = out_dir / f"{safe_prefix}_segments.csv"
        high_path = out_dir / f"{safe_prefix}_high_attention.json"
        summary_path = out_dir / f"{safe_prefix}_summary.json"

        segment_df.to_csv(segment_path, index=False, encoding="utf-8-sig")
        high_path.write_text(
            json.dumps(serialize_for_json(high_attention_segments), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        summary_path.write_text(
            json.dumps(serialize_for_json(summary), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        paths = {
            "segment_csv": str(segment_path),
            "high_attention_json": str(high_path),
            "summary_json": str(summary_path),
        }
    except Exception as exc:
        warnings.append(f"failed to write coupling outputs: {exc}")
    return paths


def _merge_with_base_segments(base_segment_df: pd.DataFrame | None, metric_df: pd.DataFrame) -> pd.DataFrame:
    """Internal helper for merge with base segments."""
    if base_segment_df is None or base_segment_df.empty:
        return metric_df.copy()
    if metric_df is None or metric_df.empty:
        return base_segment_df.copy()

    base = base_segment_df.copy()
    metric = metric_df.copy()
    if "segment_id" not in base.columns and not _has_segment_bounds(base):
        return metric.copy()
    if "segment_id" not in metric.columns and not _has_segment_bounds(metric):
        return metric_df.copy()

    base["__segment_key"] = _segment_merge_key(base)
    metric["__segment_key"] = _segment_merge_key(metric)

    metric_cols = [c for c in METRIC_COLUMNS if c in metric.columns]
    extra_cols = [
        c for c in metric.columns
        if c.endswith("_score") or c in {"GRCI", "GRS", "RAI", "response_consistency"}
    ]
    keep_cols = ["__segment_key"] + list(dict.fromkeys(metric_cols + extra_cols))
    keep_cols = [c for c in keep_cols if c in metric.columns]
    drop_cols = [c for c in keep_cols if c != "__segment_key" and c in base.columns]
    base = base.drop(columns=drop_cols)
    merged = base.merge(metric[keep_cols], on="__segment_key", how="left")
    return merged.drop(columns=["__segment_key"])


def _has_segment_bounds(df: pd.DataFrame) -> bool:
    """Internal helper for has segment bounds."""
    start_col = _first_existing(df, ["segment_start_first", "segment_start"])
    end_col = _first_existing(df, ["segment_end_first", "segment_end"])
    return bool(start_col and end_col)


def _segment_merge_key(df: pd.DataFrame) -> pd.Series:
    """Internal helper for segment merge key."""
    start_col = _first_existing(df, ["segment_start_first", "segment_start"])
    end_col = _first_existing(df, ["segment_end_first", "segment_end"])
    if start_col and end_col:
        return (
            pd.to_numeric(df[start_col], errors="coerce").map(_number_key)
            + "_"
            + pd.to_numeric(df[end_col], errors="coerce").map(_number_key)
        )
    return df.get("segment_id", pd.Series("", index=df.index)).map(_normalize_segment_id)


def _first_existing(df: pd.DataFrame, columns: list[str]) -> str | None:
    """Internal helper for first existing."""
    for col in columns:
        if col in df.columns:
            return col
    return None


def _normalize_segment_id(value: Any) -> str:
    """Normalize segment id."""
    parts = str(value).split("_")
    if len(parts) == 2:
        return f"{_number_key(parts[0])}_{_number_key(parts[1])}"
    return str(value)


def _empty_summary(reason: str, warnings: list[str]) -> dict[str, Any]:
    """Internal helper for empty summary."""
    return {
        "has_coupling": False,
        "method": GEOLOGY_METHOD_VERSION,
        "level_counts": {},
        "class_counts": {},
        "top_segments": [],
        "high_attention_segments": [],
        "summary_text": f"区段级地质风险-施工响应耦合分析不可用：{reason}。",
        "warnings": warnings,
    }


def _empty_validation() -> dict[str, Any]:
    """Internal helper for empty validation."""
    return {
        "has_validation": False,
        "weak_label_count": 0,
        "segment_count": 0,
        "top_k": 0,
        "top_k_hits": 0,
        "top_k_hit_rate": 0.0,
        "baseline_weak_label_rate": 0.0,
        "precision": 0.0,
        "recall": 0.0,
        "tp": 0,
        "fp": 0,
        "fn": 0,
    }


def _build_interpretation(row: pd.Series) -> str:
    """Build interpretation."""
    segment = row.get("segment", "--")
    cls = row.get("grci_class_label", "--")
    grs = float(row.get("GRS", 0) or 0)
    rai = float(row.get("RAI", 0) or 0)
    grci = float(row.get("GRCI", row.get("risk_response_coupling_index", 0)) or 0)
    return f"{segment}：{cls}，GRS={grs:.2f}，RAI={rai:.2f}，GRCI={grci:.2f}。"


def _classify_segment(risk: float, response: float, risk_threshold: float, response_threshold: float) -> str:
    """Classify segment."""
    high_risk = risk >= risk_threshold
    high_response = response >= response_threshold
    if high_risk and high_response:
        return "A"
    if high_risk and not high_response:
        return "B"
    if not high_risk and high_response:
        return "C"
    return "D"


def _coupling_level(value: float) -> str:
    """Internal helper for coupling level."""
    if value is None or pd.isna(value):
        return "unknown"
    if value >= 0.75:
        return "strong"
    if value >= 0.50:
        return "medium"
    if value >= 0.25:
        return "weak"
    return "low"


def _grade_score(value: Any) -> float:
    """Internal helper for grade score."""
    text = str(value).strip().upper()
    if not text or text == "NAN":
        return 0.0
    for key, score in GRADE_SCORES.items():
        if key in text:
            return score
    match = re.search(r"[1-5]", text)
    if match:
        return GRADE_SCORES.get(match.group(0), 0.0)
    return 0.0


def _hazard_score(text: Any) -> float:
    """Internal helper for hazard score."""
    haystack = str(text).lower()
    if not haystack or haystack == "nan":
        return 0.0
    score = 0.0
    for keywords, weight in HAZARD_KEYWORDS:
        if any(keyword.lower() in haystack for keyword in keywords):
            score += weight
    return float(np.clip(score, 0, 1))


def _combined_text(df: pd.DataFrame, columns: list[str | None]) -> pd.Series:
    """Internal helper for combined text."""
    existing = [col for col in columns if col and col in df.columns]
    if not existing:
        return pd.Series("", index=df.index)
    out = pd.Series("", index=df.index, dtype=object)
    for col in existing:
        out = out + " " + df[col].fillna("").astype(str)
    return out.str.strip()


def _mode_text(series: pd.Series) -> str:
    """Internal helper for mode text."""
    clean = series.dropna().astype(str)
    clean = clean[clean.str.strip() != ""]
    if clean.empty:
        return ""
    mode = clean.mode()
    return str(mode.iloc[0]) if not mode.empty else str(clean.iloc[0])


def _robust_score(series: pd.Series, side: str = "high") -> pd.Series:
    """Internal helper for robust score."""
    values = pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan)
    if values.notna().sum() < 3:
        return _zero_series(series.index)

    median = values.median(skipna=True)
    mad = (values - median).abs().median(skipna=True)
    if pd.notna(mad) and mad > 1e-9:
        scale = 1.4826 * mad
    else:
        q75 = values.quantile(0.75)
        q25 = values.quantile(0.25)
        iqr = q75 - q25
        scale = iqr / 1.349 if pd.notna(iqr) and iqr > 1e-9 else values.std(skipna=True)

    if scale is None or pd.isna(scale) or scale <= 1e-9:
        return _zero_series(series.index)

    z = (values - median) / scale
    if side == "low":
        score = (-z / 3.0).clip(lower=0, upper=1)
    elif side == "two":
        score = (z.abs() / 3.0).clip(lower=0, upper=1)
    else:
        score = (z / 3.0).clip(lower=0, upper=1)
    return score.fillna(0)


def _combine_scores(scores: list[pd.Series], index: pd.Index) -> pd.Series:
    """Internal helper for combine scores."""
    if not scores:
        return _zero_series(index)
    return pd.concat(scores, axis=1).max(axis=1).fillna(0).clip(0, 1)


def _safe_positive_median(series: pd.Series) -> float:
    """Internal helper for safe positive median."""
    values = pd.to_numeric(series, errors="coerce")
    values = values[values > 0]
    if values.empty:
        return 0.0
    return float(values.median())


def _zero_series(index: pd.Index) -> pd.Series:
    """Build a zero-filled series for the target index."""
    return pd.Series(0.0, index=index)


def _safe_div(num: int | float, den: int | float) -> float:
    """Internal helper for safe div."""
    if not den:
        return 0.0
    return float(num) / float(den)


def _number_key(value: Any) -> str:
    """Internal helper for number key."""
    try:
        x = float(value)
        if math.isfinite(x) and x.is_integer():
            return str(int(x))
        return f"{x:.3f}".rstrip("0").rstrip(".")
    except Exception:
        return str(value)


def _infer_output_prefix(df: pd.DataFrame, colmap: dict[str, str | None]) -> str:
    """Infer output prefix."""
    time_col = colmap.get("time")
    if time_col and time_col in df.columns:
        times = pd.to_datetime(df[time_col], errors="coerce").dropna()
        if not times.empty:
            return f"tbm_coupling_{times.iloc[0].strftime('%Y%m%d')}"
    start = _number_key(df["chainage"].min()) if "chainage" in df.columns else "unknown"
    end = _number_key(df["chainage"].max()) if "chainage" in df.columns else "unknown"
    return f"tbm_coupling_{start}_{end}"
