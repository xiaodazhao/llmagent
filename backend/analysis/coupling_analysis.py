import pandas as pd


COUPLING_WEIGHTS = {
    "geo_risk": 0.35,
    "source_evidence": 0.20,
    "load_response": 0.25,
    "speed_decay": 0.20,
}


def _zero_series(index):
    return pd.Series(0.0, index=index)


def _norm_by_reference(series: pd.Series, reference: float) -> pd.Series:
    if reference is None or pd.isna(reference) or reference <= 0:
        return _zero_series(series.index)
    return (pd.to_numeric(series, errors="coerce").fillna(0) / reference).clip(0, 1)


def classify_coupling_level(value: float) -> str:
    if pd.isna(value):
        return "unknown"
    if value >= 0.75:
        return "strong"
    if value >= 0.50:
        return "medium"
    if value >= 0.25:
        return "weak"
    return "low"


COUPLING_LABELS = {
    "strong": "强耦合风险区",
    "medium": "中等耦合风险区",
    "weak": "弱耦合风险区",
    "low": "低耦合区",
    "unknown": "耦合判读条件不足",
}


def _build_interpretation(row) -> str:
    label = row.get("coupling_label", "耦合判读条件不足")
    cri = row.get("risk_response_coupling_index", 0)
    geo = row.get("geo_risk_norm", 0)
    load = row.get("load_response_norm", 0)
    speed = row.get("speed_decay_norm", 0)
    source = row.get("source_evidence_norm", 0)

    if row.get("coupling_level") == "strong":
        return (
            f"{label}，CRI={cri:.2f}。该区段地质风险、多源证据和施工响应共同表现较强，"
            "建议作为后续掘进监测和参数调整的重点关注区。"
        )
    if row.get("coupling_level") == "medium":
        return (
            f"{label}，CRI={cri:.2f}。该区段存在一定地质关注或施工响应特征，"
            "建议结合掌子面揭示和后续参数变化持续核实。"
        )
    if row.get("coupling_level") == "weak":
        return (
            f"{label}，CRI={cri:.2f}。当前仅表现出局部关注特征，"
            "风险解释需结合现场揭示进一步判断。"
        )
    if max(geo, load, speed, source) > 0:
        return f"{label}，CRI={cri:.2f}。当前综合耦合程度较低，保持常规监测。"
    return "耦合判读条件不足，当前区段缺少可用于综合评价的风险或施工响应字段。"


def add_risk_response_coupling(segment_df: pd.DataFrame) -> pd.DataFrame:
    """
    Add a Coupled Risk-response Index (CRI) to segment-level analysis.

    CRI integrates:
    - geo_risk_norm: geological risk intensity
    - source_evidence_norm: multi-source evidence strength
    - load_response_norm: thrust/torque load response
    - speed_decay_norm: advance speed decay
    """
    if segment_df is None or segment_df.empty:
        return segment_df

    out = segment_df.copy()
    idx = out.index

    if "risk_score_max" in out.columns:
        risk_max = pd.to_numeric(out["risk_score_max"], errors="coerce").max()
        risk_reference = max(float(risk_max), 3.0) if pd.notna(risk_max) else 3.0
        out["geo_risk_norm"] = _norm_by_reference(out["risk_score_max"], risk_reference)
    elif "geo_prior_score_max" in out.columns:
        risk_max = pd.to_numeric(out["geo_prior_score_max"], errors="coerce").max()
        risk_reference = max(float(risk_max), 3.0) if pd.notna(risk_max) else 3.0
        out["geo_risk_norm"] = _norm_by_reference(out["geo_prior_score_max"], risk_reference)
    else:
        out["geo_risk_norm"] = _zero_series(idx)

    if "active_source_count_max" in out.columns:
        out["source_evidence_norm"] = _norm_by_reference(out["active_source_count_max"], 4.0)
    else:
        out["source_evidence_norm"] = _zero_series(idx)

    load_parts = []
    for col in ["推力_mean", "刀盘扭矩_mean"]:
        if col in out.columns:
            values = pd.to_numeric(out[col], errors="coerce")
            mean_value = values.mean(skipna=True)
            if pd.notna(mean_value) and mean_value > 0:
                load_parts.append(((values - mean_value) / mean_value).clip(lower=0).fillna(0))

    if load_parts:
        out["load_response_norm"] = (sum(load_parts) / len(load_parts)).clip(0, 1)
    else:
        out["load_response_norm"] = _zero_series(idx)

    if "推进速度_mean" in out.columns:
        speed = pd.to_numeric(out["推进速度_mean"], errors="coerce")
        speed_mean = speed.mean(skipna=True)
        if pd.notna(speed_mean) and speed_mean > 0:
            out["speed_decay_norm"] = ((speed_mean - speed) / speed_mean).clip(lower=0, upper=1).fillna(0)
        else:
            out["speed_decay_norm"] = _zero_series(idx)
    else:
        out["speed_decay_norm"] = _zero_series(idx)

    out["risk_response_coupling_index"] = (
        COUPLING_WEIGHTS["geo_risk"] * out["geo_risk_norm"]
        + COUPLING_WEIGHTS["source_evidence"] * out["source_evidence_norm"]
        + COUPLING_WEIGHTS["load_response"] * out["load_response_norm"]
        + COUPLING_WEIGHTS["speed_decay"] * out["speed_decay_norm"]
    ).clip(0, 1)

    out["coupling_level"] = out["risk_response_coupling_index"].apply(classify_coupling_level)
    out["coupling_label"] = out["coupling_level"].map(COUPLING_LABELS).fillna(COUPLING_LABELS["unknown"])
    out["coupling_interpretation"] = out.apply(_build_interpretation, axis=1)

    return out


def summarize_coupling(segment_df: pd.DataFrame, top_n: int = 5) -> dict:
    if segment_df is None or segment_df.empty or "risk_response_coupling_index" not in segment_df.columns:
        return {
            "has_coupling": False,
            "level_counts": {},
            "top_segments": [],
            "summary_text": "区段风险-施工响应耦合分析条件不足。"
        }

    out = segment_df.copy()
    out["risk_response_coupling_index"] = pd.to_numeric(
        out["risk_response_coupling_index"], errors="coerce"
    ).fillna(0)

    level_counts = out.get("coupling_label", pd.Series(dtype=str)).value_counts().to_dict()
    top = (
        out.sort_values("risk_response_coupling_index", ascending=False)
        .head(top_n)
        .copy()
    )

    keep_cols = [
        "segment",
        "risk_response_coupling_index",
        "coupling_label",
        "geo_risk_norm",
        "source_evidence_norm",
        "load_response_norm",
        "speed_decay_norm",
        "coupling_interpretation",
    ]
    top_records = top[[c for c in keep_cols if c in top.columns]].to_dict(orient="records")

    max_row = top.iloc[0] if not top.empty else None
    if max_row is None:
        text = "区段风险-施工响应耦合分析未识别到有效区段。"
    else:
        segment = max_row.get("segment", "未知区段")
        label = max_row.get("coupling_label", "耦合判读条件不足")
        cri = max_row.get("risk_response_coupling_index", 0)
        text = f"区段风险-施工响应耦合分析显示，{segment} 为当前最高关注区段，{label}，CRI={cri:.2f}。"

    return {
        "has_coupling": True,
        "level_counts": level_counts,
        "top_segments": top_records,
        "summary_text": text,
    }
