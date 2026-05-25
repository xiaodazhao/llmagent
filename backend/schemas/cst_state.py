from __future__ import annotations

from copy import deepcopy
from typing import Any


def build_empty_cst_state() -> dict[str, Any]:
    """Return the canonical CST structure."""
    return {
        "cst_id": None,
        "state_key": None,
        "previous_cst_id": None,
        "version": "recursive_cst_v2",
        "updated_at": None,
        "case_id": None,
        "date": None,
        "time_window": {
            "start_time": None,
            "end_time": None,
            "duration_min": 0.0,
        },
        "temporal_state": {
            "sample_count": 0,
            "analysis_mode": "daily",
            "source_name": None,
            "previous_date": None,
            "continuity_gap_days": None,
            "state_stability": 1.0,
        },
        "spatial_state": {
            "chainage_start": None,
            "chainage_end": None,
            "face_chainage": None,
            "advance_length": 0.0,
            "forward_window": [],
            "forward_focus_level": None,
            "chainage_delta_from_previous": None,
        },
        "operation_state": {
            "main_state": None,
            "working_duration_min": 0.0,
            "stoppage_duration_min": 0.0,
            "state_switch_count": 0,
            "efficiency_summary": None,
            "work_ratio": None,
            "stop_ratio": None,
            "previous_main_state": None,
            "work_duration_delta": None,
            "stop_duration_delta": None,
        },
        "geological_state": {
            "face_condition": None,
            "segment_grade": None,
            "hazards": [],
            "evidence_count": 0,
            "uncertainty": None,
            "persistent_hazards": [],
        },
        "response_state": {
            "RAI": 0.0,
            "anomaly_type": None,
            "key_parameters": [],
            "RAI_delta": None,
        },
        "attention_state": {
            "GRS": 0.0,
            "GRCI": 0.0,
            "high_attention_segments": [],
            "forward_attention": {},
            "persistent_attention_segments": [],
            "trend_label": "initialized",
            "GRS_delta": None,
            "GRCI_delta": None,
        },
        "provenance_state": {
            "evidence_list": [],
            "state_update_sources": [],
            "previous_change_summary": None,
            "lineage": [],
            "changed_fields": [],
            "state_confidence": 0.0,
            "update_strategy": None,
        },
        "raw_twin_state": {},
        "llm_summary": {},
        "warnings": [],
        "gas_state": {},
    }


def normalize_cst_state(payload: dict[str, Any] | None) -> dict[str, Any]:
    """Merge a partial payload into the canonical CST structure."""
    state = build_empty_cst_state()
    if not isinstance(payload, dict):
        return state

    for key, value in payload.items():
        if key not in state:
            state[key] = value
            continue
        if isinstance(state[key], dict) and isinstance(value, dict):
            merged = deepcopy(state[key])
            merged.update(value)
            state[key] = merged
        else:
            state[key] = value
    return state
