"""
ML Model Training Script for Crop Yield Prediction.
Trains Linear Regression, Random Forest, and Gradient Boosting regressors,
selects the best model, and saves it with its preprocessing pipeline.

Train/test split is chronological (by year) to prevent data leakage.
Evaluation metrics are computed on the held-out test set only.
"""
import os
import sys
import json
import logging
import joblib
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Dict, Tuple, Optional

from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import cross_val_score

# Paths
ROOT = Path(__file__).parent.parent
ML_DIR = ROOT / "ml"
MODELS_DIR = ML_DIR / "saved_models"
DATASETS_DIR = ROOT / "datasets" / "processed"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

sys.path.insert(0, str(ROOT))
from ml.feature_engineering import TRAINING_FEATURES


MODELS_TO_TRAIN = {
    "linear_regression": Pipeline([
        ("scaler", StandardScaler()),
        ("model", LinearRegression()),
    ]),
    "random_forest": Pipeline([
        ("scaler", StandardScaler()),
        ("model", RandomForestRegressor(
            n_estimators=200,
            max_depth=12,
            min_samples_split=5,
            random_state=42,
            n_jobs=-1,
        )),
    ]),
    "gradient_boosting": Pipeline([
        ("scaler", StandardScaler()),
        ("model", GradientBoostingRegressor(
            n_estimators=200,
            max_depth=5,
            learning_rate=0.05,
            subsample=0.8,
            random_state=42,
        )),
    ]),
}


def chronological_split(
    df: pd.DataFrame,
    year_col: str = "year",
    test_fraction: float = 0.2,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Split dataset chronologically by year to prevent data leakage.
    Latest `test_fraction` of years go into the test set.
    """
    if year_col not in df.columns:
        logger.warning("No '%s' column found. Using random 80/20 split.", year_col)
        from sklearn.model_selection import train_test_split
        return train_test_split(df, test_size=test_fraction, random_state=42)

    years = sorted(df[year_col].unique())
    split_idx = int(len(years) * (1 - test_fraction))
    train_years = years[:split_idx]
    test_years = years[split_idx:]

    train_df = df[df[year_col].isin(train_years)]
    test_df = df[df[year_col].isin(test_years)]

    logger.info(
        "Chronological split: train years=%s, test years=%s",
        list(map(int, train_years)), list(map(int, test_years))
    )
    logger.info("Train: %d rows, Test: %d rows", len(train_df), len(test_df))
    return train_df, test_df


def compute_metrics(y_true: np.ndarray, y_pred: np.ndarray, name: str) -> Dict:
    """Compute regression evaluation metrics."""
    mae = mean_absolute_error(y_true, y_pred)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    r2 = r2_score(y_true, y_pred)
    logger.info(
        "[%s] MAE=%.4f  RMSE=%.4f  R²=%.4f",
        name, mae, rmse, r2
    )
    return {"model": name, "mae": round(mae, 4), "rmse": round(rmse, 4), "r2": round(r2, 4)}


def per_crop_metrics(
    y_true, y_pred, crop_types
) -> Dict[str, Dict]:
    """Compute metrics per crop type."""
    results = {}
    y_true_arr = np.asarray(y_true)
    y_pred_arr = np.asarray(y_pred)
    crops_arr = np.asarray(crop_types)
    for crop in np.unique(crops_arr):
        mask = (crops_arr == crop)
        if mask.sum() < 5:
            continue
        yt = y_true_arr[mask]
        yp = y_pred_arr[mask]
        results[str(crop)] = {
            "mae": round(float(mean_absolute_error(yt, yp)), 4),
            "rmse": round(float(np.sqrt(mean_squared_error(yt, yp))), 4),
            "r2": round(float(r2_score(yt, yp)), 4),
            "count": int(mask.sum()),
        }
    return results


def train_all_models(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    target_col: str = "yield_tonnes_per_ha",
) -> Tuple[str, Pipeline, Dict]:
    """
    Train all candidate models and select best by test RMSE.
    Preprocessing (scaling) is fitted only on training data.
    Returns: (best_model_name, best_pipeline, all_metrics)
    """
    if target_col not in train_df.columns:
        raise ValueError(f"Target column '{target_col}' not found in training data.")

    X_train = train_df[TRAINING_FEATURES].copy()
    y_train = train_df[target_col].values
    X_test = test_df[TRAINING_FEATURES].copy()
    y_test = test_df[target_col].values

    # Handle any remaining NaN in features
    X_train = X_train.fillna(X_train.median())
    X_test = X_test.fillna(X_train.median())

    all_metrics = []
    trained_models = {}

    for model_name, pipeline in MODELS_TO_TRAIN.items():
        logger.info("Training: %s ...", model_name)
        try:
            # Fit only on training data (no leakage)
            pipeline.fit(X_train, y_train)
            y_pred = pipeline.predict(X_test)
            y_pred_clipped = np.clip(y_pred, 0, None)  # yields cannot be negative

            metrics = compute_metrics(y_test, y_pred_clipped, model_name)
            all_metrics.append(metrics)
            trained_models[model_name] = (pipeline, y_pred_clipped)

            # Cross-val on training set for additional validation
            cv_scores = cross_val_score(
                pipeline, X_train, y_train,
                cv=5, scoring="neg_root_mean_squared_error", n_jobs=-1
            )
            metrics["cv_rmse_mean"] = round(-cv_scores.mean(), 4)
            metrics["cv_rmse_std"] = round(cv_scores.std(), 4)
            logger.info(
                "[%s] CV RMSE: %.4f ± %.4f",
                model_name, -cv_scores.mean(), cv_scores.std()
            )
        except Exception as exc:
            logger.error("Error training %s: %s", model_name, exc)

    if not trained_models:
        raise RuntimeError("All models failed to train.")

    # Select best by test RMSE
    best = min(all_metrics, key=lambda m: m["rmse"])
    best_name = best["model"]
    best_pipeline, best_preds = trained_models[best_name]

    logger.info("Best model: %s (RMSE=%.4f)", best_name, best["rmse"])

    # Per-crop breakdown for best model
    crop_breakdown = {}
    if "crop_type" in test_df.columns:
        crop_breakdown = per_crop_metrics(
            y_test, best_preds, test_df["crop_type"].values
        )

    return best_name, best_pipeline, {
        "all_models": all_metrics,
        "best_model": best,
        "per_crop_test_metrics": crop_breakdown,
        "target_column": target_col,
        "target_unit": "tonnes_per_hectare",
        "features_used": TRAINING_FEATURES,
        "train_size": len(train_df),
        "test_size": len(test_df),
        "split_method": "chronological_by_year",
        "evaluation_note": (
            "Metrics computed on chronologically held-out test set. "
            "Model trained on earlier years, evaluated on more recent years."
        ),
        "data_source_note": (
            "If training on synthetic data: metrics are illustrative. "
            "Real accuracy requires real observation data."
        ),
    }


def save_model(
    pipeline: Pipeline,
    model_name: str,
    metrics: Dict,
    version: str = "1.0.0",
) -> str:
    """Save model pipeline and metadata."""
    model_file = MODELS_DIR / f"crop_yield_model.joblib"
    meta_file = MODELS_DIR / f"model_metadata.json"

    joblib.dump(pipeline, model_file)
    logger.info("Model saved to %s", model_file)

    metadata = {
        "model_name": model_name,
        "version": version,
        "trained_at": datetime.now().isoformat(),
        "model_file": str(model_file),
        "features": TRAINING_FEATURES,
        "target": "yield_tonnes_per_ha",
        "target_unit": "tonnes_per_hectare",
        "metrics": metrics,
    }
    with open(meta_file, 'w') as f:
        json.dump(metadata, f, indent=2)
    logger.info("Model metadata saved to %s", meta_file)

    return str(model_file)


def run_training(dataset_path: Optional[str] = None) -> str:
    """Full training pipeline. Returns path to saved model."""
    logger.info("=== Starting Model Training ===")

    # Load processed dataset
    if dataset_path:
        processed_path = Path(dataset_path)
    else:
        processed_path = DATASETS_DIR / "crop_yield_processed.csv"

    if not processed_path.exists():
        logger.warning("Processed dataset not found. Running data ingestion first...")
        sys.path.insert(0, str(ROOT))
        from ml.data_ingestion import run_ingestion
        _, processed_df = run_ingestion()
        processed_df.to_csv(processed_path, index=False)
    else:
        processed_df = pd.read_csv(processed_path)
        logger.info("Loaded processed dataset: %s rows from %s", len(processed_df), processed_path)

    # Check for required columns
    missing = [f for f in TRAINING_FEATURES if f not in processed_df.columns]
    if missing:
        logger.error("Missing features: %s. Re-running data ingestion.", missing)
        from ml.data_ingestion import run_ingestion
        _, processed_df = run_ingestion(str(dataset_path) if dataset_path else None)
        processed_df.to_csv(processed_path, index=False)

    # Chronological split
    train_df, test_df = chronological_split(processed_df)

    if len(test_df) < 10:
        logger.warning("Test set is very small (%d rows). Metrics may not be reliable.", len(test_df))

    # Train and evaluate
    best_name, best_pipeline, metrics = train_all_models(train_df, test_df)

    # Save model
    model_path = save_model(best_pipeline, best_name, metrics)

    logger.info("=== Training Complete ===")
    logger.info("Best model: %s", best_name)
    logger.info("Test MAE: %.4f t/ha", metrics["best_model"]["mae"])
    logger.info("Test RMSE: %.4f t/ha", metrics["best_model"]["rmse"])
    logger.info("Test R²: %.4f", metrics["best_model"]["r2"])

    return model_path


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Train Crop Yield Prediction Model")
    parser.add_argument("--dataset", type=str, help="Path to processed CSV dataset")
    args = parser.parse_args()
    path = run_training(args.dataset)
    print(f"\nModel saved to: {path}")
