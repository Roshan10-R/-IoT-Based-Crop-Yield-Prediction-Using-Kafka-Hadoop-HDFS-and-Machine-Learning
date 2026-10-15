"""
Unit tests for Feature Engineering Module and Rolling Stats Logic
"""
import pytest
from datetime import datetime, timedelta, timezone
from ml.feature_engineering import (
    encode_crop,
    encode_season,
    compute_rolling_stats,
    build_prediction_features,
    validate_feature_value,
    CROP_ENCODING,
    SEASON_ENCODING,
    TRAINING_FEATURES,
)


def test_categorical_encodings():
    assert encode_crop("wheat") == CROP_ENCODING["wheat"]
    assert encode_crop("rice") == CROP_ENCODING["rice"]
    assert encode_crop("unknown_crop") == -1

    assert encode_season("rabi") == SEASON_ENCODING["rabi"]
    assert encode_season("kharif") == SEASON_ENCODING["kharif"]
    assert encode_season("unknown_season") == -1


def test_validate_feature_value():
    assert len(validate_feature_value("avg_temperature_c", 25.0)) == 0
    assert len(validate_feature_value("avg_soil_moisture_pct", 55.0)) == 0
    # Out of range test
    warnings = validate_feature_value("avg_soil_moisture_pct", 150.0)
    assert len(warnings) > 0


def test_compute_rolling_stats():
    now = datetime.now(timezone.utc)
    readings = [
        {
            "sensor_id": "SENSOR_001",
            "field_id": "FIELD_001",
            "timestamp": (now - timedelta(days=i)).isoformat(),
            "soil_moisture": 50.0 + i,
            "temperature": 20.0 + (i * 0.5),
            "rainfall": 2.0,
            "crop_type": "wheat",
        }
        for i in range(5)
    ]

    stats = compute_rolling_stats(readings, window_days=30)
    assert "avg_soil_moisture_pct" in stats
    assert "avg_temperature_c" in stats
    assert "total_rainfall_mm" in stats
    assert stats["total_rainfall_mm"] == 10.0
    assert stats["avg_soil_moisture_pct"] == 52.0


def test_build_prediction_features():
    df, warnings = build_prediction_features(
        field_id="FIELD_001",
        crop_type="wheat",
        season="rabi",
        area_ha=5.0,
        year=2024,
        base_year=2015,
        overrides={
            "avg_soil_moisture_pct": 55.0,
            "avg_temperature_c": 22.0,
            "total_rainfall_mm": 500.0,
        }
    )
    assert len(df) == 1
    for feat in TRAINING_FEATURES:
        assert feat in df.columns
    assert df["crop_type_encoded"].iloc[0] == CROP_ENCODING["wheat"]
    assert df["area_ha"].iloc[0] == 5.0
