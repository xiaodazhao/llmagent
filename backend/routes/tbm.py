from datetime import datetime
from typing import Optional

import pandas as pd
from fastapi import APIRouter, FastAPI

from agent.supervisor_agent import TBMSupervisorAgent
from agent.tbm_agent import TBMAgent
from llm.llm_api import call_llm
from llm.prompt_builder import build_prompt
from llm.prompt_builder_timewindow import build_prompt_timewindow
from schemas.api import AgentRequest, DailyReportRequest, EvidenceImportRequest, TimeWindowRequest
from services.evidence_import_service import import_evidence_files
from services.history_memory_service import (
    build_history_comparison,
    build_history_record,
    load_history_records,
    save_history_record,
)
from utils.io_utils import get_all_csv_paths, load_csv_by_date, load_latest_csv
from utils.serialization import serialize_for_json
from utils.time_window_utils import load_df_by_time


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

    @router.get("/dates")
    def get_available_dates():
        dates = []
        for f in get_all_csv_paths():
            try:
                d = f.name.replace("tbm_data_", "").replace(".csv", "")
                dates.append(datetime.strptime(d, "%Y%m%d").strftime("%Y-%m-%d"))
            except Exception:
                pass
        dates.sort(reverse=True)
        return {"dates": dates}

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

    @router.post("/evidence/import")
    def import_evidence_api(req: EvidenceImportRequest):
        try:
            result = import_evidence_files(
                paths=req.paths,
                source_type=req.source_type,
                dry_run=req.dry_run,
                replace_existing=req.replace_existing,
                recursive=req.recursive,
            )
            return serialize_for_json(result)
        except Exception as e:
            return {
                "ok": False,
                "message": str(e),
            }

    @router.post("/report")
    def generate_daily_report(req: DailyReportRequest):
        try:
            _, df = load_csv_by_date(req.date)
            result = analyze_tbm_data(df)
            current_record = build_history_record(req.date, result)
            history_records = load_history_records(limit=10, before_date=req.date)
            history_comparison = build_history_comparison(current_record, history_records)
            save_history_record(current_record)
            result["llm_summary"]["施工历史记忆对比"] = history_comparison

            prompt = build_prompt(
                seg_text=result["seg_text"],
                stats_text=result["stats_text"],
                state_text=result["state_text"],
                eff_text=result["eff_text"],
                state_stats_text=result["state_stats_text"],
                gas_text=result["gas_text"],
                geo_text=result["geo_text"],
                face_geo_text=result["face_geo_text"],
                llm_summary=result["llm_summary"],
                risk_prob_text=result["risk_prob_text"],
            )

            report = call_llm(prompt)
            return {"report": report}

        except FileNotFoundError:
            return {"report": f"❌ 找不到 {req.date} 的数据文件"}
        except Exception as e:
            return {"report": f"❌ 服务器错误：{e}"}

    @router.get("/summary")
    def tbm_summary(date: Optional[str] = None):
        try:
            _, df = load_csv_by_date(date) if date else load_latest_csv()
            result = analyze_tbm_data(df)

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
        except Exception as e:
            print(f"[Summary Error] {e}")
            return {
                "stop_count": 0,
                "transition_count": 0,
                "work_count": 0,
                "abnormal_count": 0,
                "stop_total_min": 0,
                "transition_total_min": 0,
                "work_total_min": 0,
                "abnormal_total_min": 0,
                "geology_has": False,
                "geology_high_risk_segment_count": 0,
                "geology_multi_source_segment_count": 0,
            }

    @router.get("/state")
    def state_api(date: Optional[str] = None):
        try:
            _, df = load_csv_by_date(date) if date else load_latest_csv()
            result = analyze_tbm_data(df)

            segments = []
            for state, pairs in result["state_segments"].items():
                label_text = result["state_labels"].get(int(state), f"施工状态 {int(state)}")
                for s, e in pairs:
                    segments.append({
                        "label": int(state),
                        "label_text": label_text,
                        "start": s.strftime("%H:%M:%S"),
                        "end": e.strftime("%H:%M:%S"),
                        "duration": (e - s).total_seconds(),
                    })

            efficiency = []
            if not result["eff_df"].empty:
                efficiency = result["eff_df"].to_dict(orient="records")

            return {
                "segments": serialize_for_json(segments),
                "efficiency": serialize_for_json(efficiency),
                "state_labels": serialize_for_json(result["state_labels"]),
                "state_stats": serialize_for_json(result["state_stats"]),
                "valid_samples": result["llm_summary"]["有效状态样本数"],
                "state_config": serialize_for_json(result["llm_summary"]["状态识别配置"]),
            }

        except Exception as e:
            print(f"[State API Error] {e}")
            return {
                "segments": [],
                "efficiency": [],
                "state_labels": {},
                "state_stats": {},
                "valid_samples": 0,
                "state_config": {},
            }

    @router.get("/gas")
    def gas_api(date: Optional[str] = None):
        try:
            _, df = load_csv_by_date(date) if date else load_latest_csv()
            result = analyze_tbm_data(df)
            return serialize_for_json(result["gas_stats"])
        except Exception as e:
            print(f"[Gas API Error] {e}")
            return {}

    @router.get("/geology")
    def geology_api(date: Optional[str] = None):
        try:
            _, df = load_csv_by_date(date) if date else load_latest_csv()
            result = analyze_tbm_data(df)

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
                keep_cols = [c for c in preferred_cols if c in segment_df.columns]
                if keep_cols:
                    segment_df = segment_df[keep_cols].copy()
                if "segment_start_first" in segment_df.columns:
                    segment_df = segment_df.sort_values("segment_start_first").reset_index(drop=True)

            if not typical_df.empty:
                keep_cols2 = [c for c in preferred_cols if c in typical_df.columns]
                if keep_cols2:
                    typical_df = typical_df[keep_cols2].copy()
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

        except Exception as e:
            print(f"[Geology API Error] {e}")
            return {
                "record_summary": {"has_geology": False},
                "segment_summary": {
                    "has_geology": False,
                    "summary_text": "地质融合分析不可用。",
                },
                "segment_table": [],
                "typical_segments": [],
                "coupling_summary": {},
                "coupling_validation": {},
                "coupling_output_paths": {},
                "high_attention_segments": [],
            }

    @router.get("/digital_twin_state")
    def digital_twin_state_api(date: Optional[str] = None):
        try:
            _, df = load_csv_by_date(date) if date else load_latest_csv()
            result = analyze_tbm_data(df)
            return {
                "date": date,
                "digital_twin_state": serialize_for_json(result.get("digital_twin_state", {})),
                "coupling_summary": serialize_for_json(result.get("coupling_summary", {})),
            }
        except Exception as e:
            print(f"[Digital Twin State API Error] {e}")
            return {
                "date": date,
                "digital_twin_state": {},
                "coupling_summary": {},
                "message": str(e),
            }

    @router.get("/history_memory")
    def history_memory_api(date: Optional[str] = None, limit: int = 10):
        try:
            _, df = load_csv_by_date(date) if date else load_latest_csv()
            result = analyze_tbm_data(df)
            current_date = date or datetime.now().strftime("%Y-%m-%d")
            current_record = build_history_record(current_date, result)
            history_records = load_history_records(limit=limit, before_date=current_date)
            history_comparison = build_history_comparison(current_record, history_records)

            return {
                "date": current_date,
                "current_record": serialize_for_json(current_record),
                "history_comparison": serialize_for_json(history_comparison),
            }
        except Exception as e:
            print(f"[History Memory API Error] {e}")
            return {
                "date": date,
                "current_record": {},
                "history_comparison": {
                    "has_history": False,
                    "comparison_text": str(e),
                },
            }

    @router.post("/report_by_time")
    def generate_report_by_time(req: TimeWindowRequest):
        try:
            start = req.start_time.replace("T", " ")
            end = req.end_time.replace("T", " ")
            date = start.split(" ")[0]

            _, df_day = load_csv_by_date(date)
            df = load_df_by_time(df_day, start, end)

            if df.empty:
                return {"report": "⚠️ 该时间段无数据"}

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

            return {"report": call_llm(prompt)}

        except Exception as e:
            return {"report": f"❌ 出错：{e}"}

    @router.get("/risk_profile")
    def risk_profile_api(date: Optional[str] = None):
        try:
            _, df = load_csv_by_date(date) if date else load_latest_csv()
            result = analyze_tbm_data(df)

            risk_profile = build_risk_profile(result["df_geo"])
            speed_profile = build_speed_profile(result["df_geo"])

            return {
                "date": date,
                "risk_profile": risk_profile,
                "speed_profile": speed_profile,
            }

        except Exception as e:
            print(f"[Risk Profile API Error] {e}")
            return {
                "date": date,
                "risk_profile": {
                    "has_data": False,
                    "profile": [],
                    "high_segments": [],
                    "message": str(e),
                },
                "speed_profile": [],
            }

    app.include_router(router)
