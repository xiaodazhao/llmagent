import json
import pandas as pd

from utils.chainage_utils import format_chainage_dk


RISK_SCORE_MAP = {
    "low": 1,
    "medium": 2,
    "high": 3,
}


def _safe_load_attrs(x):
    """Safely load serialized evidence attributes."""
    try:
        if pd.isna(x):
            return {}
        obj = json.loads(x)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _format_dk(chainage):
    """Format numeric chainage as DK string."""
    if pd.isna(chainage):
        return "未知里程"
    return format_chainage_dk(chainage)


def _normalize_hazard(attrs):
    """Normalize hazards from evidence attributes."""
    hazards = []
    if attrs.get("water_flag"):
        hazards.append("出水")
    if attrs.get("collapse_flag"):
        hazards.append("掉块")
    if attrs.get("deformation_flag"):
        hazards.append("变形")
    return hazards


def _summarize_forward_evidence(forward_df):
    """Summarize forward evidence records inside the look-ahead window."""
    if forward_df.empty:
        return {
            "forward_segment_count": 0,
            "high_risk_count": 0,
            "multi_source_count": 0,
            "risk_level_dist": {},
            "main_hazards": [],
            "source_types": [],
            "covered_start": None,
            "covered_end": None,
        }

    temp = forward_df.copy()
    temp["attrs_obj"] = temp["attrs_json"].apply(_safe_load_attrs)
    temp["risk_level"] = temp["attrs_obj"].apply(lambda x: x.get("risk_level", "low"))
    temp["risk_score"] = temp["risk_level"].map(RISK_SCORE_MAP).fillna(1)
    temp["hazards"] = temp["attrs_obj"].apply(_normalize_hazard)

    risk_level_dist = temp["risk_level"].value_counts().to_dict()
    high_risk_count = int((temp["risk_score"] >= 3).sum())
    source_types = sorted(set(temp["source_type"].astype(str).dropna().tolist()))

    dedup = temp[["source_type", "report_id"]].astype(str).drop_duplicates()
    multi_source_count = len(dedup)

    hazard_counter = {}
    for hazards in temp["hazards"]:
        for hazard in hazards:
            hazard_counter[hazard] = hazard_counter.get(hazard, 0) + 1

    main_hazards = [
        key for key, _ in sorted(hazard_counter.items(), key=lambda x: x[1], reverse=True)
    ]

    return {
        "forward_segment_count": int(len(temp)),
        "high_risk_count": high_risk_count,
        "multi_source_count": int(multi_source_count),
        "risk_level_dist": risk_level_dist,
        "main_hazards": main_hazards,
        "source_types": source_types,
        "covered_start": float(temp["start_num"].min()) if "start_num" in temp.columns else None,
        "covered_end": float(temp["end_num"].max()) if "end_num" in temp.columns else None,
    }


def generate_forward_risk_summary(df_plc: pd.DataFrame, evidence_df: pd.DataFrame, lookahead_m=30):
    """Generate structured forward-attention summary from evidence in the look-ahead window."""
    if df_plc is None or len(df_plc) == 0:
        return {
            "has_forward_risk": False,
            "message": "PLC 数据为空，无法生成前方风险提示。",
        }

    df = df_plc.copy()

    if "chainage" in df.columns:
        df["chainage"] = pd.to_numeric(df["chainage"], errors="coerce")
    elif "导向盾首里程" in df.columns:
        df["chainage"] = pd.to_numeric(df["导向盾首里程"], errors="coerce")
    elif "开累进尺" in df.columns:
        df["chainage"] = pd.to_numeric(df["开累进尺"], errors="coerce")
    else:
        return {
            "has_forward_risk": False,
            "message": "PLC 数据中缺少可用里程字段，无法生成前方风险提示。",
        }

    df = df.dropna(subset=["chainage"]).copy()
    if df.empty:
        return {
            "has_forward_risk": False,
            "message": "PLC 里程字段为空，无法生成前方风险提示。",
        }

    current_chainage = float(df["chainage"].iloc[-1])
    forward_start = current_chainage
    forward_end = current_chainage + float(lookahead_m)

    ev = evidence_df.copy()
    ev["start_num"] = pd.to_numeric(ev["start_num"], errors="coerce")
    ev["end_num"] = pd.to_numeric(ev["end_num"], errors="coerce")
    ev = ev.dropna(subset=["start_num", "end_num"]).copy()

    forward_df = ev[
        (ev["end_num"] >= forward_start) &
        (ev["start_num"] <= forward_end)
    ].copy()

    stat = _summarize_forward_evidence(forward_df)

    if stat["high_risk_count"] > 0 and stat["multi_source_count"] >= 3:
        advice_level = "high"
    elif stat["high_risk_count"] > 0 or stat["multi_source_count"] >= 2:
        advice_level = "medium"
    elif stat["forward_segment_count"] > 0:
        advice_level = "low"
    else:
        advice_level = "none"

    monitoring_focus = ["推进速度", "推力", "刀盘扭矩"]
    if "出水" in stat["main_hazards"]:
        monitoring_focus.append("涌水量")
        monitoring_focus.append("排水状态")
    if "掉块" in stat["main_hazards"]:
        monitoring_focus.append("掌子面稳定性")
        monitoring_focus.append("掉块征兆")

    support_actions = []
    if "出水" in stat["main_hazards"]:
        support_actions.append("提前检查排水与止水准备")
    if "掉块" in stat["main_hazards"]:
        support_actions.append("提前准备加强支护与围岩稳定控制措施")
    if not support_actions:
        support_actions.append("保持常规支护与监测准备")

    if stat["forward_segment_count"] == 0:
        advice_text = (
            f"截至当前掘进位置 {_format_dk(current_chainage)}，前方 {lookahead_m} m 范围内未识别到明确的前视关注段，"
            "建议保持常规施工监测，并继续跟踪后续地质资料更新。"
        )
    else:
        hazard_text = "、".join(stat["main_hazards"][:3]) if stat["main_hazards"] else "未见明确风险类型"
        monitoring_text = "、".join(dict.fromkeys(monitoring_focus))
        support_text = "；".join(dict.fromkeys(support_actions))

        if advice_level == "high":
            advice_text = (
                f"截至当前掘进位置 {_format_dk(current_chainage)}，前方 {lookahead_m} m 范围内识别出 {stat['forward_segment_count']} 个关注段，"
                f"其中高风险段 {stat['high_risk_count']} 个，多源共同关注程度较高。主要关注类型为{hazard_text}。"
                f"建议在进入该范围前重点加强 {monitoring_text} 的联动监测，并{support_text}。"
            )
        elif advice_level == "medium":
            advice_text = (
                f"截至当前掘进位置 {_format_dk(current_chainage)}，前方 {lookahead_m} m 范围内存在 {stat['forward_segment_count']} 个关注段，"
                f"主要关注类型为{hazard_text}。建议继续跟踪 {monitoring_text} 的变化，并{support_text}。"
            )
        else:
            advice_text = (
                f"截至当前掘进位置 {_format_dk(current_chainage)}，前方 {lookahead_m} m 范围内识别出 {stat['forward_segment_count']} 个一般关注段，"
                f"主要关注类型为{hazard_text}。建议保持常规监测，并关注 {monitoring_text} 的后续变化。"
            )

    return {
        "has_forward_risk": True,
        "current_chainage": current_chainage,
        "current_chainage_dk": _format_dk(current_chainage),
        "lookahead_m": float(lookahead_m),
        "forward_start": forward_start,
        "forward_end": forward_end,
        "forward_start_dk": _format_dk(forward_start),
        "forward_end_dk": _format_dk(forward_end),
        "forward_segment_count": stat["forward_segment_count"],
        "high_risk_count": stat["high_risk_count"],
        "multi_source_count": stat["multi_source_count"],
        "risk_level_dist": stat["risk_level_dist"],
        "main_hazards": stat["main_hazards"],
        "source_types": stat["source_types"],
        "advice_level": advice_level,
        "advice_text": advice_text,
        "monitoring_focus": list(dict.fromkeys(monitoring_focus)),
        "support_actions": list(dict.fromkeys(support_actions)),
    }


def forward_risk_to_text(summary: dict):
    """Convert structured forward-risk summary into report text."""
    if not summary or not summary.get("has_forward_risk", False):
        return "未形成可用的前方风险提示。"

    if summary.get("forward_segment_count", 0) == 0:
        return summary.get("advice_text", "当前前方区段未识别到明确的前视关注提示。")

    hazards = summary.get("main_hazards", [])
    hazard_text = "、".join(hazards[:3]) if hazards else "未见明确风险类型"
    monitoring_text = "、".join(summary.get("monitoring_focus", [])) or "推进参数与现场状态"
    support_text = "；".join(summary.get("support_actions", [])) or "保持常规支护与准备"

    lines = [
        (
            f"截至当前掘进位置 {summary.get('current_chainage_dk', '未知里程')}，前方 "
            f"{int(summary.get('lookahead_m', 0))} m 范围（{summary.get('forward_start_dk', '')} ~ "
            f"{summary.get('forward_end_dk', '')}）内共识别出 {summary.get('forward_segment_count', 0)} 个风险提示段。"
        ),
        (
            f"其中高风险段 {summary.get('high_risk_count', 0)} 个，多源共同关注程度为 "
            f"{summary.get('multi_source_count', 0)}，主要风险类型表现为{hazard_text}。"
        ),
        f"建议重点加强 {monitoring_text} 的联合监测，并{support_text}。",
        summary.get("advice_text", "建议后续施工过程中保持持续关注。"),
    ]
    return "\n".join(lines)
