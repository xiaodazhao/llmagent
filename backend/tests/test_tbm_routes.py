from pathlib import Path

import pandas as pd
from fastapi import FastAPI
from fastapi.testclient import TestClient

import routes.tbm as tbm_routes


def _build_client(monkeypatch, result: dict, *, cache_hit: bool = False) -> TestClient:
    app = FastAPI()
    tbm_routes.register_tbm_routes(
        app,
        analyze_tbm_data=lambda df: result,
        build_risk_profile=lambda df: {},
        build_speed_profile=lambda df: [],
    )

    sample_path = Path("tbm_data_20231230.csv")
    monkeypatch.setattr(tbm_routes, "get_latest_csv_path", lambda: sample_path)
    monkeypatch.setattr(tbm_routes, "get_csv_path_by_date", lambda date: sample_path)
    monkeypatch.setattr(tbm_routes, "load_csv", lambda path: pd.DataFrame())
    monkeypatch.setattr(
        tbm_routes,
        "get_or_compute_file_cache",
        lambda namespace, path, compute: (result, cache_hit),
    )
    return TestClient(app)


def test_state_route_returns_defaults_when_summary_fields_missing(monkeypatch):
    result = {
        "state_segments": {
            "0": [(pd.Timestamp("2023-12-30 08:00:00"), pd.Timestamp("2023-12-30 08:03:00"))]
        },
        "state_labels": {0: "稳定推进"},
        "eff_df": pd.DataFrame(),
        "state_stats": {"状态切换次数": 1},
        "llm_summary": {},
        "warnings": ["状态样本较少"],
    }
    client = _build_client(monkeypatch, result)

    response = client.get("/api/tbm/state?date=2023-12-30")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["warnings"] == ["状态样本较少"]
    assert payload["data"]["valid_samples"] == 0
    assert payload["data"]["state_config"] == {}
    assert payload["data"]["segments"][0]["label_text"] == "稳定推进"
    assert payload["meta"]["resolved_date"] == "2023-12-30"


def test_state_route_returns_efficiency_and_summary_meta(monkeypatch):
    result = {
        "state_segments": {
            1: [(pd.Timestamp("2023-12-30 09:10:00"), pd.Timestamp("2023-12-30 09:16:30"))]
        },
        "state_labels": {1: "高负载推进"},
        "eff_df": pd.DataFrame(
            [
                {
                    "label_text": "高负载推进",
                    "平均推进速度": 22.5,
                    "平均推力": 1034.2,
                }
            ]
        ),
        "state_stats": {1: {"segment_count": 1}},
        "llm_summary": {
            "有效状态样本数": 18,
            "状态识别配置": {"n_states": 3, "min_duration_sec": 20},
        },
        "warnings": [],
    }
    client = _build_client(monkeypatch, result, cache_hit=True)

    response = client.get("/api/tbm/state?date=2023-12-30")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["data"]["valid_samples"] == 18
    assert payload["data"]["state_config"]["n_states"] == 3
    assert payload["data"]["efficiency"][0]["label_text"] == "高负载推进"
    assert payload["data"]["segments"][0]["duration"] == 390.0
    assert payload["meta"]["cache_hit"] is True
    assert payload["meta"]["source_file"] == "tbm_data_20231230.csv"
