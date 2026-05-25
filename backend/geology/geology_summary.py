import json
import pandas as pd


def summarize_geology_record_level(df: pd.DataFrame):
    """Generate record-level geology summary for auxiliary interpretation."""
    result = {}

    if "active_source_count" not in df.columns:
        return {
            "has_geology": False,
            "summary_text": "未进行地质融合分析。",
        }

    result["has_geology"] = True
    result["sample_count"] = len(df)

    coverage_counts = df["coverage"].value_counts(dropna=False).to_dict() if "coverage" in df.columns else {}
    risk_counts = df["risk"].value_counts(dropna=False).to_dict() if "risk" in df.columns else {}
    hazard_counts = df["hazard"].value_counts(dropna=False).head(5).to_dict() if "hazard" in df.columns else {}

    result["coverage_counts"] = coverage_counts
    result["risk_counts"] = risk_counts
    result["hazard_counts"] = hazard_counts

    result["max_attention"] = int(df["active_source_count"].max()) if "active_source_count" in df.columns else None
    result["mean_attention"] = float(df["active_source_count"].mean()) if "active_source_count" in df.columns else None

    high_attention_df = df[df["active_source_count"] >= 4] if "active_source_count" in df.columns else pd.DataFrame()
    result["high_attention_count"] = int(len(high_attention_df))

    lines = [f"本时段共匹配到 {len(df)} 条带地质标签的 PLC 记录。"]

    if coverage_counts:
        lines.append(f"地质覆盖情况：{', '.join([f'{k}={v}' for k, v in coverage_counts.items()])}。")

    if risk_counts:
        lines.append(f"风险分布情况：{', '.join([f'{k}={v}' for k, v in risk_counts.items()])}。")

    if result["max_attention"] is not None:
        lines.append(
            f"多源报告最大命中数为 {result['max_attention']}，平均命中数为 {result['mean_attention']:.2f}。"
        )

    if result["high_attention_count"] > 0:
        lines.append(f"active_source_count≥4 的较高关注记录共 {result['high_attention_count']} 条。")

    if hazard_counts:
        top_hazard_text = "、".join([f"{k}({v})" for k, v in hazard_counts.items()])
        lines.append(f"主要关注表现为：{top_hazard_text}。")

    result["summary_text"] = "\n".join(lines)
    return result


def summarize_geology_segment_level(segment_df: pd.DataFrame):
    """Generate segment-level geology summary for report generation."""
    if segment_df is None or len(segment_df) == 0:
        return {
            "has_geology": False,
            "summary_text": "未形成区段级地质融合分析结果。",
        }

    result = {
        "has_geology": True,
        "segment_count": int(len(segment_df)),
    }

    risk_dist = segment_df["risk_mode"].value_counts(dropna=False).to_dict() if "risk_mode" in segment_df.columns else {}
    interpretation_dist = (
        segment_df["interpretation"].value_counts(dropna=False).to_dict()
        if "interpretation" in segment_df.columns else {}
    )

    result["risk_dist"] = risk_dist
    result["interpretation_dist"] = interpretation_dist

    high_risk_df = segment_df[segment_df["risk_score_max"] >= 3] if "risk_score_max" in segment_df.columns else pd.DataFrame()
    multi_source_df = segment_df[segment_df["active_source_count_max"] >= 3] if "active_source_count_max" in segment_df.columns else pd.DataFrame()

    result["high_risk_segment_count"] = int(len(high_risk_df))
    result["multi_source_segment_count"] = int(len(multi_source_df))

    lines = [f"本次区段级分析共识别 {len(segment_df)} 个施工区段。"]

    if risk_dist:
        lines.append(f"区段风险分布为：{', '.join([f'{k}={v}' for k, v in risk_dist.items()])}。")

    if len(high_risk_df) > 0:
        lines.append(f"其中高关注区段共 {len(high_risk_df)} 个。")

    if len(multi_source_df) > 0:
        lines.append(f"多源共同关注区段共 {len(multi_source_df)} 个。")

    if interpretation_dist:
        lines.append(f"施工响应判读结果：{', '.join([f'{k}={v}' for k, v in interpretation_dist.items()])}。")

    if "segment" in segment_df.columns and "interpretation" in segment_df.columns:
        typical = segment_df.head(3)
        typical_lines = []
        for _, row in typical.iterrows():
            seg = row.get("segment", "")
            interp = row.get("interpretation", "")
            risk = row.get("risk_mode", "")
            typical_lines.append(f"{seg}（{risk}，{interp}）")
        if typical_lines:
            lines.append("典型区段包括：" + "；".join(typical_lines) + "。")

    result["summary_text"] = "\n".join(lines)
    return result


def geology_summary_to_text(geo_summary: dict):
    """Convert geology summary dict to text."""
    if not geo_summary or not geo_summary.get("has_geology", False):
        return "本时段未进行地质融合分析。"
    return geo_summary.get("summary_text", "本时段已完成地质融合分析。")


def _safe_load_attrs(x):
    """Safely load serialized evidence attributes."""
    try:
        obj = json.loads(x)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _mid_chainage(row: pd.Series) -> float | None:
    """Return the midpoint chainage for one evidence row."""
    start = pd.to_numeric(row.get("start_num"), errors="coerce")
    end = pd.to_numeric(row.get("end_num"), errors="coerce")
    if pd.notna(start) and pd.notna(end):
        return float((start + end) / 2.0)
    if pd.notna(start):
        return float(start)
    if pd.notna(end):
        return float(end)
    return None


def build_face_geo_text(
    evidence_df: pd.DataFrame,
    current_chainage: float | None = None,
    tolerance_m: float = 20.0,
) -> str:
    """
    Build the current face geology text from on-site sketch evidence only.

    Rules:
    - Only use `sketch` + `point` evidence as current face reveal.
    - If a current chainage is provided, prefer the nearest sketch point.
    - If the nearest sketch point is too far away, do not replace the current face
      with forecast information. Explicitly state that direct current-face reveal is unavailable.
    """
    if evidence_df is None or len(evidence_df) == 0:
        return "当前掌子面缺少可用的现场素描或揭示资料，不能直接依据超前预报替代当前掌子面情况。"

    if "source_type" not in evidence_df.columns or "source_level" not in evidence_df.columns:
        return "当前掌子面缺少可用的现场素描或揭示资料，不能直接依据超前预报替代当前掌子面情况。"

    sketch_df = evidence_df[
        (evidence_df["source_type"] == "sketch") &
        (evidence_df["source_level"] == "point")
    ].copy()

    if sketch_df.empty:
        return "当前掌子面缺少现场素描点位揭示，当前掌子面地质情况不能直接由超前预报替代。"

    if current_chainage is not None:
        sketch_df["__mid_chainage"] = sketch_df.apply(_mid_chainage, axis=1)
        sketch_df["__distance_to_face"] = (
            pd.to_numeric(sketch_df["__mid_chainage"], errors="coerce") - float(current_chainage)
        ).abs()
        sketch_df = sketch_df.sort_values("__distance_to_face")
        row = sketch_df.iloc[0]
        distance = pd.to_numeric(row.get("__distance_to_face"), errors="coerce")
        if pd.notna(distance) and float(distance) > float(tolerance_m):
            return (
                f"当前掌子面里程附近未找到与掌子面位置相匹配的现场素描揭示"
                f"（最近素描点距当前掌子面约 {float(distance):.1f} m），"
                "因此当前掌子面地质情况不能直接依据超前预报或远距离历史素描替代。"
            )
    else:
        row = sketch_df.iloc[-1]

    attrs = _safe_load_attrs(row.get("attrs_json", ""))
    parts = []

    grade = attrs.get("support_grade") or attrs.get("rock_grade")
    if grade:
        parts.append(f"围岩等级为{grade}级")

    lithology = attrs.get("lithology")
    if lithology:
        parts.append(f"岩性为{lithology}")

    weathering = attrs.get("weathering")
    if weathering:
        parts.append(f"{weathering}")

    rock_uniformity = attrs.get("rock_uniformity")
    if rock_uniformity:
        parts.append(f"岩质{rock_uniformity}")

    joint_degree = attrs.get("joint_degree")
    if joint_degree:
        parts.append(f"节理裂隙{joint_degree}")

    rock_mass_state = attrs.get("rock_mass_state")
    if rock_mass_state:
        parts.append(f"岩体{rock_mass_state}")

    stability = attrs.get("stability")
    if stability:
        parts.append(f"整体稳定性{stability}")

    water_type = attrs.get("water_type")
    water_flag = attrs.get("water_flag", 0)
    if water_type:
        parts.append(f"掌子面存在{water_type}")
    elif water_flag:
        parts.append("掌子面存在出水现象")

    collapse_flag = attrs.get("collapse_flag", 0)
    if collapse_flag:
        parts.append("局部存在掉块现象")

    if not parts:
        return "当前掌子面已有现场素描记录，但未提取到明确的掌子面地质特征。"

    distance = None
    if current_chainage is not None and "__distance_to_face" in row and pd.notna(row["__distance_to_face"]):
        distance = float(row["__distance_to_face"])

    if distance is None:
        prefix = "现场素描揭示"
    elif distance <= 0.5:
        prefix = f"与当前掌子面里程基本一致的现场素描揭示（距当前掌子面约 {distance:.1f} m）"
    else:
        prefix = f"距当前掌子面最近的现场素描点揭示（距当前掌子面约 {distance:.1f} m）"

    return (
        prefix
        + "： "
        + "，".join(parts)
        + "。该描述来源于现场素描点位记录，不能简单等同为当前掌子面实时直接观察结论。"
    )
