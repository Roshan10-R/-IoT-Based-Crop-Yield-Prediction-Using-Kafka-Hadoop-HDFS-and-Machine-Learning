"""
Feature Engineering Module for Crop Yield Prediction.
Converts raw sensor readings and field metadata into
model-ready features, matching exactly the format used during training.
"""
import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Feature names in exact order expected by the trained model
TRAINING_FEATURES = [
    "crop_type_encoded",
    "season_encoded",
    "avg_temperature_c",
    "total_rainfall_mm",
    "avg_soil_moisture_pct",
    "temp_stress",
    "rainfall_adequacy",
    "year_normalized",
    "area_ha",
    "growth_days",
]

# Crop encoding (must match data_ingestion.py)
CROP_ENCODING = {
    "wheat": 0, "rice": 1, "maize": 2,
    "cotton": 3, "soybean": 4, "potato": 5,
}
SEASON_ENCODING = {"kharif": 0, "rabi": 1, "summer": 2, "whole year": 3}

CROP_GROWTH_DAYS = {
    "wheat": 120, "rice": 140, "maize": 100,
    "cotton": 160, "soybean": 110, "potato": 90,
}

VALID_RANGES = {
    "avg_temperature_c": (-10, 55),
    "total_rainfall_mm": (0, 5000),
    "avg_soil_moisture_pct": (0, 100),
    "area_ha": (0.01, 10000),
}

# Median rainfall used in training for adequacy ratio calculation
TRAINING_RAINFALL_MEDIAN = 700.0


def encode_crop(crop_type: str) -> int:
    """Encode crop type to integer. Returns -1 for unknown crops."""
    val = CROP_ENCODING.get(str(crop_type).lower().strip(), -1)
    if val == -1:
        logger.warning("Unknown crop type: '%s'. Encoding as -1.", crop_type)
    return val


def encode_season(season: str) -> int:
    """Encode season string to integer."""
    return SEASON_ENCODING.get(str(season).lower().strip(), -1)


def validate_feature_value(name: str, value: float) -> List[str]:
    """Check if a feature value is within valid agronomic range."""
    warnings = []
    if name in VALID_RANGES:
        lo, hi = VALID_RANGES[name]
        if not (lo <= value <= hi):
            warnings.append(
                f"Feature '{name}'={value:.2f} is outside expected range [{lo}, {hi}]"
            )
    if np.isnan(value) or np.isinf(value):
        warnings.append(f"Feature '{name}' has non-finite value: {value}")
    return warnings


def compute_rolling_stats(
    readings: List[Dict[str, Any]],
    window_days: int = 30,
) -> Dict[str, float]:
    """
    Compute rolling aggregates from a list of sensor readings.
    Only readings within the last `window_days` are considered.
    Readings must have 'timestamp', 'soil_moisture', 'temperature', 'rainfall' keys.
    Returns aggregated features or None if insufficient data.
    """
    if not readings:
        logger.warning("No sensor readings provided for rolling stats.")
        return {}

    df = pd.DataFrame(readings)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    df = df.dropna(subset=["timestamp"])

    if df.empty:
        logger.warning("All readings had invalid timestamps.")
        return {}

    cutoff = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=window_days)
    df_window = df[df["timestamp"] >= cutoff]

    if df_window.empty:
        logger.warning(
            "No readings in the last %d days. Using all available.", window_days
        )
        df_window = df

    stats = {}
    if "temperature" in df_window.columns:
        temps = pd.to_numeric(df_window["temperature"], errors="coerce").dropna()
        stats["avg_temperature_c"] = float(temps.mean()) if not temps.empty else 20.0
        stats["max_temperature_c"] = float(temps.max()) if not temps.empty else 20.0
        stats["min_temperature_c"] = float(temps.min()) if not temps.empty else 20.0
    if "soil_moisture" in df_window.columns:
        sm = pd.to_numeric(df_window["soil_moisture"], errors="coerce").dropna()
        stats["avg_soil_moisture_pct"] = float(sm.mean()) if not sm.empty else 50.0
        stats["min_soil_moisture_pct"] = float(sm.min()) if not sm.empty else 50.0
    if "rainfall" in df_window.columns:
        rf = pd.to_numeric(df_window["rainfall"], errors="coerce").dropna()
        stats["total_rainfall_mm"] = float(rf.sum()) if not rf.empty else 0.0

    return stats


def build_prediction_features(
    field_id: str,
    crop_type: str,
    season: str,
    area_ha: float,
    year: int,
    base_year: int,
    sensor_readings: Optional[List[Dict]] = None,
    overrides: Optional[Dict[str, float]] = None,
) -> Tuple[pd.DataFrame, List[str]]:
    """
    Build a single-row feature DataFrame for yield prediction.
    
    Uses sensor_readings to compute rolling stats if available.
    overrides can supply pre-computed feature values directly.
    
    Returns: (feature_df with TRAINING_FEATURES columns, quality_warnings)
    """
    warnings: List[str] = []
    features: Dict[str, Any] = {}

    # Crop encoding
    features["crop_type_encoded"] = encode_crop(crop_type)
    if features["crop_type_encoded"] == -1:
        warnings.append(f"Unknown crop '{crop_type}'. Prediction may be unreliable.")

    # Season encoding
    features["season_encoded"] = encode_season(season)
    if features["season_encoded"] == -1:
        warnings.append(f"Unknown season '{season}'.")

    # Growth days
    features["growth_days"] = CROP_GROWTH_DAYS.get(crop_type.lower(), 120)

    # Year
    features["year_normalized"] = max(0, year - base_year)

    # Area
    features["area_ha"] = area_ha

    # Sensor-derived features
    if sensor_readings:
        rolling = compute_rolling_stats(sensor_readings, window_days=30)
        if rolling:
            features.update(rolling)
            logger.info(
                "Built rolling stats from %d sensor readings for field %s",
                len(sensor_readings), field_id
            )
        else:
            warnings.append("Could not compute rolling stats from sensor readings.")

    # Apply overrides (for direct API calls or testing)
    if overrides:
        features.update(overrides)

    # Fill missing features with safe defaults and warn
    defaults = {
        "avg_temperature_c": 22.0,
        "total_rainfall_mm": 600.0,
        "avg_soil_moisture_pct": 55.0,
        "max_temperature_c": 30.0,
        "min_temperature_c": 15.0,
        "min_soil_moisture_pct": 40.0,
    }
    for key, default_val in defaults.items():
        if key not in features:
            features[key] = default_val
            warnings.append(
                f"Feature '{key}' not available from sensors; using default={default_val}."
            )

    # Derived features (must match training pipeline)
    features["temp_stress"] = abs(features["avg_temperature_c"] - 25.0)
    features["rainfall_adequacy"] = features["total_rainfall_mm"] / TRAINING_RAINFALL_MEDIAN

    # Validate
    for name in TRAINING_FEATURES:
        val = features.get(name, np.nan)
        warnings.extend(validate_feature_value(name, float(val)))

    # Build DataFrame with exact column order
    row = {name: features.get(name, np.nan) for name in TRAINING_FEATURES}
    feature_df = pd.DataFrame([row], columns=TRAINING_FEATURES)

    logger.info(
        "Feature vector built for field=%s crop=%s: %s",
        field_id, crop_type, row
    )
    return feature_df, warnings


def sample_prediction_features(crop_type: str = "wheat") -> Tuple[pd.DataFrame, List[str]]:
    """
    Generate a clearly-labeled sample feature vector for API demo purposes.
    Uses documented agronomic defaults, NOT real sensor data.
    """
    logger.info("[DEMO] Generating sample features for crop=%s", crop_type)
    overrides = {
        "avg_temperature_c": 22.5,
        "total_rainfall_mm": 580.0,
        "avg_soil_moisture_pct": 58.0,
        "area_ha": 5.0,
    }
    df, warnings = build_prediction_features(
        field_id="DEMO_FIELD",
        crop_type=crop_type,
        season="rabi",
        area_ha=5.0,
        year=2024,
        base_year=2015,
        overrides=overrides,
    )
    warnings.append(
        "DEMO MODE: These features are sample values, not live sensor data. "
        "Predictions are illustrative only."
    )
    return df, warnings
