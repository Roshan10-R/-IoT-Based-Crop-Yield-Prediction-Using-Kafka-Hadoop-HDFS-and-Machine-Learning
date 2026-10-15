"""
Prediction Module — Load trained model and generate crop yield predictions.
Ensures predictions use only features available at the 30-day prediction cutoff.
"""
import json
import logging
import os
import sys
import joblib
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple, Any

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from ml.feature_engineering import (
    TRAINING_FEATURES, CROP_GROWTH_DAYS,
    build_prediction_features, sample_prediction_features
)

logger = logging.getLogger(__name__)

MODELS_DIR = ROOT / "ml" / "saved_models"
MODEL_FILE = MODELS_DIR / "crop_yield_model.joblib"
META_FILE = MODELS_DIR / "model_metadata.json"


class ModelNotFoundError(Exception):
    pass


class CropYieldPredictor:
    """
    Loads the trained model pipeline and generates crop yield predictions.
    All predictions include a full metadata dict describing inputs and limitations.
    """

    def __init__(self, model_path: Optional[str] = None):
        self.model_path = Path(model_path or os.getenv("MODEL_PATH", str(MODEL_FILE)))
        self._pipeline = None
        self._metadata: Dict = {}
        self._load_model()

    def _load_model(self):
        """Load model pipeline and metadata from disk."""
        if not self.model_path.exists():
            logger.warning(
                "Model file not found at %s. Run ml/train.py first.", self.model_path
            )
            return
        try:
            self._pipeline = joblib.load(self.model_path)
            logger.info("Model loaded from %s", self.model_path)
        except Exception as exc:
            logger.error("Failed to load model: %s", exc)
            self._pipeline = None

        if META_FILE.exists():
            with open(META_FILE, 'r') as f:
                self._metadata = json.load(f)
        else:
            self._metadata = {"model_name": "unknown", "version": "unknown"}

    def is_loaded(self) -> bool:
        return self._pipeline is not None

    def reload(self):
        """Reload model from disk (e.g., after retraining)."""
        self._pipeline = None
        self._load_model()

    def predict(
        self,
        field_id: str,
        crop_type: str,
        season: str,
        area_ha: float,
        year: int,
        base_year: int = 2015,
        sensor_readings: Optional[List[Dict]] = None,
        feature_overrides: Optional[Dict[str, float]] = None,
        demo_mode: bool = False,
    ) -> Dict[str, Any]:
        """
        Generate a crop yield prediction for a given field.

        30-day prediction design:
        - Only features available up to (harvest_date - 30 days) are used.
        - Rolling sensor stats cover the last 30 days of the growing season.
        - The prediction_cutoff_date is documented in the response.

        Returns a comprehensive prediction dict with all metadata.
        """
        if not self.is_loaded():
            raise ModelNotFoundError(
                "Model is not loaded. Run 'python ml/train.py' to train the model."
            )

        if demo_mode:
            feature_df, warnings = sample_prediction_features(crop_type)
            warnings.append(
                "DEMO MODE: Prediction uses sample feature values, not live sensor data."
            )
        else:
            feature_df, warnings = build_prediction_features(
                field_id=field_id,
                crop_type=crop_type,
                season=season,
                area_ha=area_ha,
                year=year,
                base_year=base_year,
                sensor_readings=sensor_readings,
                overrides=feature_overrides,
            )

        # Validate no NaN remains
        if feature_df.isnull().any().any():
            nan_cols = feature_df.columns[feature_df.isnull().any()].tolist()
            warnings.append(f"NaN in features {nan_cols}; using column median.")
            feature_df = feature_df.fillna(feature_df.median())

        try:
            raw_pred = self._pipeline.predict(feature_df)[0]
            predicted_yield = max(0.0, float(raw_pred))
        except Exception as exc:
            logger.error("Model predict() failed: %s", exc)
            raise RuntimeError(f"Prediction failed: {exc}") from exc

        # 30-day-ahead timestamps
        growth_days = CROP_GROWTH_DAYS.get(crop_type.lower(), 120)
        now = datetime.now(timezone.utc)
        planting_estimate = now - timedelta(days=growth_days - 30)
        harvest_estimate = planting_estimate + timedelta(days=growth_days)
        cutoff_date = harvest_estimate - timedelta(days=30)

        result = {
            "field_id": field_id,
            "crop_type": crop_type,
            "season": season,
            "prediction_timestamp": now.isoformat(),
            "prediction_cutoff_date": cutoff_date.date().isoformat(),
            "expected_harvest_date": harvest_estimate.date().isoformat(),
            "predicted_yield": round(predicted_yield, 3),
            "yield_unit": "tonnes_per_hectare",
            "area_ha": area_ha,
            "total_predicted_production_tonnes": round(predicted_yield * area_ha, 3),
            "model_version": self._metadata.get("version", "unknown"),
            "model_name": self._metadata.get("model_name", "unknown"),
            "features_used": TRAINING_FEATURES,
            "feature_values": feature_df.iloc[0].to_dict(),
            "data_quality_warnings": warnings,
            "prediction_limitations": [
                "Prediction is based on a model trained on historical/synthetic data.",
                "Accuracy depends on data quality and how representative training data is.",
                "30-day-ahead prediction uses features available at the cutoff date only.",
                "External factors (pests, flood, government policy) are not modeled.",
            ],
            "demo_mode": demo_mode,
            "data_source": "simulated/demo" if demo_mode else "sensor_readings",
        }

        logger.info(
            "Prediction for field=%s crop=%s yield=%.3f t/ha (warnings: %d)",
            field_id, crop_type, predicted_yield, len(warnings)
        )
        return result


# Singleton instance used by Flask
_predictor: Optional[CropYieldPredictor] = None


def get_predictor() -> CropYieldPredictor:
    global _predictor
    if _predictor is None:
        _predictor = CropYieldPredictor()
    return _predictor


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate a crop yield prediction")
    parser.add_argument("--field", default="FIELD_001")
    parser.add_argument("--crop", default="wheat")
    parser.add_argument("--season", default="rabi")
    parser.add_argument("--area", type=float, default=5.0)
    parser.add_argument("--year", type=int, default=2024)
    parser.add_argument("--demo", action="store_true")
    args = parser.parse_args()

    predictor = CropYieldPredictor()
    if not predictor.is_loaded():
        print("ERROR: Model not found. Run 'python ml/train.py' first.")
        sys.exit(1)

    result = predictor.predict(
        field_id=args.field,
        crop_type=args.crop,
        season=args.season,
        area_ha=args.area,
        year=args.year,
        demo_mode=args.demo,
    )
    print(json.dumps(result, indent=2))
