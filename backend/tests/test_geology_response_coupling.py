import pandas as pd

from analysis.geology_response_coupling import run_coupling_analysis


def _sample_coupling_df():
    return pd.DataFrame(
        [
            {
                "chainage": 100.0,
                "fused_grade": "IV",
                "hazard": "断层 富水 掉块",
                "risk": "high",
                "active_sources": "tsp;sketch",
                "active_source_count": 3,
                "__water_flag": 1,
                "__collapse_flag": 1,
                "__deformation_flag": 0,
                "推进速度": 0.20,
                "推力": 1200,
                "刀盘扭矩": 900,
                "刀盘转速": 1.4,
                "掘进状态": 1,
            },
            {
                "chainage": 105.0,
                "fused_grade": "V",
                "hazard": "极破碎 突水",
                "risk": "high",
                "active_sources": "tsp;hsp;sketch",
                "active_source_count": 4,
                "__water_flag": 1,
                "__collapse_flag": 0,
                "__deformation_flag": 1,
                "推进速度": 0.05,
                "推力": 1600,
                "刀盘扭矩": 1300,
                "刀盘转速": 0.8,
                "掘进状态": 0,
            },
            {
                "chainage": 120.0,
                "fused_grade": "II",
                "hazard": "完整",
                "risk": "low",
                "active_sources": "tsp",
                "active_source_count": 1,
                "__water_flag": 0,
                "__collapse_flag": 0,
                "__deformation_flag": 0,
                "推进速度": 1.20,
                "推力": 600,
                "刀盘扭矩": 500,
                "刀盘转速": 2.0,
                "掘进状态": 1,
            },
        ]
    )


def test_run_coupling_analysis_returns_segment_metrics_and_summary():
    result = run_coupling_analysis(_sample_coupling_df(), segment_length=10, output_dir=None, top_k=5)

    assert any("stop_anomaly uses" in warning for warning in result["warnings"])
    assert result["summary"]["has_coupling"] is True
    assert len(result["segment_df"]) == 2
    assert {"GRS", "RAI", "GRCI", "coupling_class", "anomaly_type"}.issubset(
        set(result["segment_df"].columns)
    )
    assert result["segment_df"]["GRS"].between(0, 1).all()
    assert result["segment_df"]["GRCI"].between(0, 1).all()
    assert isinstance(result["high_attention_segments"], list)


def test_run_coupling_analysis_warns_when_chainage_missing():
    df = pd.DataFrame([{"推进速度": 1.0, "推力": 10, "刀盘扭矩": 10}])

    result = run_coupling_analysis(df, output_dir=None)

    assert result["segment_df"].empty
    assert result["summary"]["has_coupling"] is False
    assert any("missing chainage column" in warning for warning in result["warnings"])
