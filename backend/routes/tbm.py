from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import pandas as pd
from fastapi import APIRouter, FastAPI

from agent.supervisor_agent import TBMSupervisorAgent
from agent.tbm_agent import TBMAgent
from llm.llm_api import call_llm
from llm.prompt_builder import build_prompt
from llm.prompt_builder_timewindow import build_prompt_timewindow
from schemas.api import AgentRequest, DailyReportRequest, EvidenceImportRequest, TimeWindowRequest
from schemas.responses import (
    ApiEnvelope,
    DatesPayload,
    DigitalTwinPayload,
    EvidenceImportPayload,
    GeologyPayload,
    HistoryMemoryPayload,
    ReportPayload,
    RiskProfilePayload,
    StatePayload,
    SummaryPayload,
)
from services.analysis_cache_service import get_or_compute_file_cache
from services.evidence_import_service import import_evidence_files
from services.history_memory_service import (
    build_history_comparison,
    build_history_record,
    load_history_records,
    save_history_record,
)
from utils.api_response import api_error, api_success
from utils.io_utils import get_all_csv_paths, get_csv_path_by_date, get_latest_csv_path, load_csv, load_csv_by_date
from utils.serialization import serialize_for_json
from utils.time_window_utils import load_df_by_time


DAILY_ANALYSIS_CACHE_NAMESPACE = "tbm_daily_analysis"


def _date_from_csv_path(path: Path) -> str | None:
    raw = path.name.replace("tbm_data_", "").replace(".csv", "")
    try:
        return datetime.strptime(raw, "%Y%m%d").strftime("%Y-%m-%d")
    except ValueError:
        return None


def _build_analysis_meta(path: Path, cache_hit: bool, resolved_date: str | None) -> dict:
    return {
        "cache_hit": cache_hit,
        "resolved_date": resolved_date,
        "source_file": path.name,
        "source_path": str(path),
    }


def _collect_warnings(result: dict | None, extra_warnings: list[str] | None = None) -> list[str]:
    warnings = list((result or {}).get("warnings", []))
    if extra_warnings:
        warnings.extend(extra_warnings)
    return warnings


def _summary_value(summary: dict | None, keys: list[str], default: Any):
    if not isinstance(summary, dict):
        return default
    for key in keys:
        if key in summary and summary[key] is not None:
            return summary[key]
    return default


def _stringify_dict_keys(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _stringify_dict_keys(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_stringify_dict_keys(item) for item in value]
    return value


def _build_summary_payload(result: dict) -> dict:
    stats = result["stats"]
    geo_summary = result.get("geo_summary_segment", {})
    return {
        "stop_count": stats.get("stop_count", 0),
        "transition_count": stats.get("transition_count", 0),
        "work_count": stats.get("work_count", 0),
        "abnormal_count": stats.get("abnormal_count", 0),
        "stop_total_min": round(stats.get("stop_total_min", 0), 1),
        "transition_total_min": round(stats.get("transition_total_min", 0), 1),
        "work_total_min": round(stats.get("work_total_min", 0), 1),
        "abnormal_total_min": round(stats.get("abnormal_total_min", 0), 1),
        "geology_has": geo_summary.get("has_geology", False),
        "geology_high_risk_segment_count": geo_summary.get("high_risk_segment_count", 0),
        "geology_multi_source_segment_count": geo_summary.get("multi_source_segment_count", 0),
    }


def _build_state_payload(result: dict) -> dict:
    state_segments = result.get("state_segments") or {}
    state_labels = result.get("state_labels") or {}
    llm_summary = result.get("llm_summary") or {}
    segments = []
    for state, pairs in state_segments.items():
        try:
            state_label = int(state)
        except (TypeError, ValueError):
            continue
        label_text = state_labels.get(state_label, f"施工状态 {state_label}")
        for start_time, end_time in pairs:
            segments.append({
                "label": state_label,
                "label_text": label_text,
                "start": start_time.strftime("%H:%M:%S"),
                "end": end_time.strftime("%H:%M:%S"),
                "duration": (end_time - start_time).total_seconds(),
            })

    efficiency = []
    eff_df = result.get("eff_df")
    if isinstance(eff_df, pd.DataFrame) and not eff_df.empty:
        efficiency = eff_df.to_dict(orient="records")
    elif isinstance(eff_df, list):
        efficiency = eff_df

    return {
        "segments": serialize_for_json(segments),
        "efficiency": serialize_for_json(efficiency),
        "state_labels": serialize_for_json(_stringify_dict_keys(state_labels)),
        "state_stats": serialize_for_json(_stringify_dict_keys(result.get("state_stats", {}))),
        "valid_samples": int(_summary_value(llm_summary, ["有效状态样本数", "鏈夋晥鐘舵€佹牱鏈暟"], 0) or 0),
        "state_config": serialize_for_json(
            _summary_value(llm_summary, ["状态识别配置", "鐘舵€佽瘑鍒厤缃�"], {})
        ),
    }


def _build_geology_payload(result: dict) -> dict:
    segment_df = result.get("segment_df", pd.DataFrame())
    typical_df = result.get("typical_segments_df", pd.DataFrame())

    preferred_cols = [
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
        "grci_class_code",
        "grci_class_label",
        "sync_coupling",
        "lag_coupling",
        "lag_response",
        "response_change_coupling",
        "response_consistency",
        "weak_anomaly_label",
        "weak_anomaly_reasons",
        "risk_mode",
        "risk_score_max",
        "active_source_count_max",
        "hazard_mode",
        "fused_grade_mode",
        "推进速度_mean",
        "推进速度_std",
        "推力_mean",
        "刀盘扭矩_mean",
        "efficiency",
        "geo_risk_norm",
        "source_evidence_norm",
        "load_response_norm",
        "speed_decay_norm",
        "risk_response_coupling_index",
        "coupling_label",
        "coupling_interpretation",
        "interpretation",
    ]

    if not segment_df.empty:
        keep_cols = [col for col in preferred_cols if col in segment_df.columns]
        if keep_cols:
            segment_df = segment_df[keep_cols].copy()
        if "segment_start_first" in segment_df.columns:
            segment_df = segment_df.sort_values("segment_start_first").reset_index(drop=True)

    if not typical_df.empty:
        keep_cols = [col for col in preferred_cols if col in typical_df.columns]
        if keep_cols:
            typical_df = typical_df[keep_cols].copy()
        if "segment_start_first" in typical_df.columns:
            typical_df = typical_df.sort_values("segment_start_first").reset_index(drop=True)

    return {
        "record_summary": serialize_for_json(result["geo_summary_record"]),
        "segment_summary": serialize_for_json(result["geo_summary_segment"]),
        "segment_table": serialize_for_json(
            segment_df.to_dict(orient="records") if not segment_df.empty else []
        ),
        "typical_segments": serialize_for_json(
            typical_df.to_dict(orient="records") if not typical_df.empty else []
        ),
        "coupling_summary": serialize_for_json(result.get("coupling_summary", {})),
        "coupling_validation": serialize_for_json(result.get("coupling_validation", {})),
        "coupling_output_paths": serialize_for_json(result.get("coupling_output_paths", {})),
        "high_attention_segments": serialize_for_json(result.get("high_attention_segments", [])),
        "digital_twin_state": serialize_for_json(result.get("digital_twin_state", {})),
    }


def _build_history_payload(current_date: str, result: dict, limit: int) -> dict:
    current_record = build_history_record(current_date, result)
    history_records = load_history_records(limit=limit, before_date=current_date)
    history_comparison = build_history_comparison(current_record, history_records)
    return {
        "date": current_date,
        "current_record": serialize_for_json(current_record),
        "history_comparison": serialize_for_json(history_comparison),
    }


def register_tbm_routes(
    app: FastAPI,
    analyze_tbm_data,
    build_risk_profile,
    build_speed_profile,
):
    router = APIRouter(prefix="/api/tbm", tags=["tbm"])
    tbm_agent = TBMAgent(
        analyze_tbm_data=analyze_tbm_data,
        build_risk_profile=build_risk_profile,
        build_speed_profile=build_speed_profile,
    )
    tbm_supervisor_agent = TBMSupervisorAgent(
        analyze_tbm_data=analyze_tbm_data,
        build_risk_profile=build_risk_profile,
        build_speed_profile=build_speed_profile,
    )

    def _resolve_daily_path(date: Optional[str] = None) -> Path:
        return get_csv_path_by_date(date) if date else get_latest_csv_path()

    def _get_daily_analysis(date: Optional[str] = None) -> tuple[Path, dict, list[str], dict, str | None]:
        path = _resolve_daily_path(date)
        result, cache_hit = get_or_compute_file_cache(
            DAILY_ANALYSIS_CACHE_NAMESPACE,
            path,
            lambda: analyze_tbm_data(load_csv(path)),
        )
        resolved_date = date or _date_from_csv_path(path)
        meta = _build_analysis_meta(path, cache_hit, resolved_date)
        return path, result, _collect_warnings(result), meta, resolved_date

    def _internal_error(prefix: str, exc: Exception, *, status_code: int = 500, meta: dict | None = None):
        print(f"[{prefix}] {exc}")
        return api_error(
            f"{prefix}：{exc}",
            status_code=status_code,
            meta=meta,
            error_code="INTERNAL_ERROR",
        )

    @router.get("/dates", response_model=ApiEnvelope[DatesPayload])
    def get_available_dates():
        try:
            dates = []
            for file_path in get_all_csv_paths():
                parsed = _date_from_csv_path(file_path)
                if parsed:
                    dates.append(parsed)
            dates.sort(reverse=True)
            return api_success({"dates": dates})
        except Exception as exc:
            return _internal_error("日期列表加载失败", exc)

    @router.post("/agent")
    def run_tbm_agent(req: AgentRequest):
        return tbm_agent.run(
            query=req.query,
            date=req.date,
            use_llm=req.use_llm,
        )

    @router.get("/agent/capabilities")
    def tbm_agent_capabilities():
        return tbm_agent.capabilities()

    @router.post("/agent_v2")
    def run_tbm_supervisor_agent(req: AgentRequest):
        return tbm_supervisor_agent.run(
            query=req.query,
            date=req.date,
            use_llm=req.use_llm,
            verbose=req.verbose,
        )

    @router.get("/agent_v2/capabilities")
    def tbm_supervisor_agent_capabilities():
        return tbm_supervisor_agent.capabilities()

    @router.post("/evidence/import", response_model=ApiEnvelope[EvidenceImportPayload])
    def import_evidence_api(req: EvidenceImportRequest):
        try:
            result = import_evidence_files(
                paths=req.paths,
                source_type=req.source_type,
                dry_run=req.dry_run,
                replace_existing=req.replace_existing,
                recursive=req.recursive,
            )
            warnings = [item.get("error", "") for item in result.get("errors", []) if item.get("error")]
            return api_success(result, warnings=warnings)
        except FileNotFoundError as exc:
            return api_error(str(exc), status_code=404, error_code="IMPORT_PATH_NOT_FOUND")
        except Exception as exc:
            return _internal_error("证据库导入失败", exc)

    @router.post("/report", response_model=ApiEnvelope[ReportPayload])
    def generate_daily_report(req: DailyReportRequest):
        try:
            _, result, warnings, meta, _ = _get_daily_analysis(req.date)
            current_record = build_history_record(req.date, result)
            history_records = load_history_records(limit=10, before_date=req.date)
            history_comparison = build_history_comparison(current_record, history_records)
            save_history_record(current_record)

            llm_summary = deepcopy(result["llm_summary"])
            llm_summary["施工历史记忆对比"] = history_comparison

            prompt = build_prompt(
                seg_text=result["seg_text"],
                stats_text=result["stats_text"],
                state_text=result["state_text"],
                eff_text=result["eff_text"],
                state_stats_text=result["state_stats_text"],
                gas_text=result["gas_text"],
                geo_text=result["geo_text"],
                face_geo_text=result["face_geo_text"],
                llm_summary=llm_summary,
                risk_prob_text=result["risk_prob_text"],
            )

            return api_success({"report": call_llm(prompt)}, warnings=warnings, meta=meta)
        except FileNotFoundError as exc:
            return api_error(str(exc), status_code=404, error_code="DATA_FILE_NOT_FOUND")
        except Exception as exc:
            return _internal_error("日报生成失败", exc, meta={"requested_date": req.date})

    @router.get("/summary", response_model=ApiEnvelope[SummaryPayload])
    def tbm_summary(date: Optional[str] = None):
        try:
            _, result, warnings, meta, _ = _get_daily_analysis(date)
            return api_success(_build_summary_payload(result), warnings=warnings, meta=meta)
        except FileNotFoundError as exc:
            return api_error(str(exc), status_code=404, error_code="DATA_FILE_NOT_FOUND")
        except Exception as exc:
            return _internal_error("概览数据加载失败", exc, meta={"requested_date": date})

    @router.get("/state", response_model=ApiEnvelope[StatePayload])
    def state_api(date: Optional[str] = None):
        try:
            _, result, warnings, meta, _ = _get_daily_analysis(date)
            return api_success(_build_state_payload(result), warnings=warnings, meta=meta)
        except FileNotFoundError as exc:
            return api_error(str(exc), status_code=404, error_code="DATA_FILE_NOT_FOUND")
        except Exception as exc:
            return _internal_error("施工状态数据加载失败", exc, meta={"requested_date": date})

    @router.get("/gas", response_model=ApiEnvelope[dict[str, Any]])
    def gas_api(date: Optional[str] = None):
        try:
            _, result, warnings, meta, _ = _get_daily_analysis(date)
            return api_success(result["gas_stats"], warnings=warnings, meta=meta)
        except FileNotFoundError as exc:
            return api_error(str(exc), status_code=404, error_code="DATA_FILE_NOT_FOUND")
        except Exception as exc:
            return _internal_error("气体监测数据加载失败", exc, meta={"requested_date": date})

    @router.get("/geology", response_model=ApiEnvelope[GeologyPayload])
    def geology_api(date: Optional[str] = None):
        try:
            _, result, warnings, meta, _ = _get_daily_analysis(date)
            return api_success(_build_geology_payload(result), warnings=warnings, meta=meta)
        except FileNotFoundError as exc:
            return api_error(str(exc), status_code=404, error_code="DATA_FILE_NOT_FOUND")
        except Exception as exc:
            return _internal_error("地质融合数据加载失败", exc, meta={"requested_date": date})

    @router.get("/digital_twin_state", response_model=ApiEnvelope[DigitalTwinPayload])
    def digital_twin_state_api(date: Optional[str] = None):
        try:
            _, result, warnings, meta, resolved_date = _get_daily_analysis(date)
            payload = {
                "date": resolved_date,
                "digital_twin_state": serialize_for_json(result.get("digital_twin_state", {})),
                "coupling_summary": serialize_for_json(result.get("coupling_summary", {})),
            }
            return api_success(payload, warnings=warnings, meta=meta)
        except FileNotFoundError as exc:
            return api_error(str(exc), status_code=404, error_code="DATA_FILE_NOT_FOUND")
        except Exception as exc:
            return _internal_error("数字孪生状态加载失败", exc, meta={"requested_date": date})

    @router.get("/history_memory", response_model=ApiEnvelope[HistoryMemoryPayload])
    def history_memory_api(date: Optional[str] = None, limit: int = 10):
        try:
            _, result, warnings, meta, resolved_date = _get_daily_analysis(date)
            current_date = resolved_date or date or datetime.now().strftime("%Y-%m-%d")
            payload = _build_history_payload(current_date, result, limit)
            return api_success(payload, warnings=warnings, meta=meta)
        except FileNotFoundError as exc:
            return api_error(str(exc), status_code=404, error_code="DATA_FILE_NOT_FOUND")
        except Exception as exc:
            return _internal_error("历史记忆加载失败", exc, meta={"requested_date": date, "limit": limit})

    @router.post("/report_by_time", response_model=ApiEnvelope[ReportPayload])
    def generate_report_by_time(req: TimeWindowRequest):
        start = req.start_time.replace("T", " ")
        end = req.end_time.replace("T", " ")
        date = start.split(" ")[0]
        meta = {
            "date": date,
            "start_time": start,
            "end_time": end,
        }

        try:
            _, df_day = load_csv_by_date(date)
            df = load_df_by_time(df_day, start, end)

            if df.empty:
                return api_error(
                    "该时间段无数据。",
                    status_code=404,
                    meta=meta,
                    error_code="EMPTY_TIME_WINDOW",
                )

            result = analyze_tbm_data(df)
            prompt = build_prompt_timewindow(
                start_time=start,
                end_time=end,
                seg_text=result["seg_text"],
                stats_text=result["stats_text"],
                state_text=result["state_text"],
                eff_text=result["eff_text"],
                state_stats_text=result["state_stats_text"],
                gas_text=result["gas_text"],
                geo_text=result["geo_text"],
                llm_summary=result["llm_summary"],
            )

            return api_success(
                {"report": call_llm(prompt)},
                warnings=_collect_warnings(result),
                meta=meta,
            )
        except FileNotFoundError as exc:
            return api_error(str(exc), status_code=404, meta=meta, error_code="DATA_FILE_NOT_FOUND")
        except Exception as exc:
            return _internal_error("时间段报告生成失败", exc, meta=meta)

    @router.get("/risk_profile", response_model=ApiEnvelope[RiskProfilePayload])
    def risk_profile_api(date: Optional[str] = None):
        try:
            _, result, warnings, meta, resolved_date = _get_daily_analysis(date)
            payload = {
                "date": resolved_date,
                "risk_profile": build_risk_profile(result["df_geo"]),
                "speed_profile": build_speed_profile(result["df_geo"]),
            }
            return api_success(payload, warnings=warnings, meta=meta)
        except FileNotFoundError as exc:
            return api_error(str(exc), status_code=404, error_code="DATA_FILE_NOT_FOUND")
        except Exception as exc:
            return _internal_error("空间风险剖面加载失败", exc, meta={"requested_date": date})

    app.include_router(router)
