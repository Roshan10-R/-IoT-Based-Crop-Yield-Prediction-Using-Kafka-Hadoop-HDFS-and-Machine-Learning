"""
Model Evaluation Script.
Loads the trained model, runs it against the test set, and produces a full
evaluation report. Prevents data leakage by using chronological split.
"""
import json
import logging
import sys
import numpy as np
import pandas as pd
import joblib
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend for server environments
import matplotlib.pyplot as plt

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from ml.feature_engineering import TRAINING_FEATURES
from ml.train import chronological_split

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

MODELS_DIR = ROOT / "ml" / "saved_models"
DATASETS_DIR = ROOT / "datasets" / "processed"
REPORTS_DIR = ROOT / "ml" / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def load_model(model_path: Optional[str] = None):
    path = Path(model_path or MODELS_DIR / "crop_yield_model.joblib")
    if not path.exists():
        raise FileNotFoundError(f"Model not found: {path}. Run ml/train.py first.")
    pipeline = joblib.load(path)
    logger.info("Model loaded from %s", path)
    return pipeline


def evaluate_model(
    pipeline,
    test_df: pd.DataFrame,
    target_col: str = "yield_tonnes_per_ha",
) -> Dict:
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

    X_test = test_df[TRAINING_FEATURES].fillna(test_df[TRAINING_FEATURES].median())
    y_test = test_df[target_col].values

    y_pred = np.clip(pipeline.predict(X_test), 0, None)

    mae = mean_absolute_error(y_test, y_pred)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    r2 = r2_score(y_test, y_pred)

    logger.info("Evaluation Results:")
    logger.info("  MAE  = %.4f t/ha", mae)
    logger.info("  RMSE = %.4f t/ha", rmse)
    logger.info("  R²   = %.4f", r2)

    # Per-crop
    per_crop = {}
    if "crop_type" in test_df.columns:
        for crop in test_df["crop_type"].unique():
            mask = test_df["crop_type"] == crop
            if mask.sum() < 5:
                continue
            yt = y_test[mask]
            yp = y_pred[mask]
            per_crop[crop] = {
                "mae": round(mean_absolute_error(yt, yp), 4),
                "rmse": round(np.sqrt(mean_squared_error(yt, yp)), 4),
                "r2": round(r2_score(yt, yp), 4),
                "n": int(mask.sum()),
            }

    # Sample actual vs predicted
    sample_size = min(20, len(y_test))
    idx = np.random.choice(len(y_test), sample_size, replace=False)
    samples = [
        {"actual": round(float(y_test[i]), 3), "predicted": round(float(y_pred[i]), 3)}
        for i in sorted(idx)
    ]

    return {
        "mae": round(mae, 4),
        "rmse": round(rmse, 4),
        "r2": round(r2, 4),
        "n_test_samples": len(y_test),
        "per_crop_metrics": per_crop,
        "sample_predictions": samples,
        "evaluation_timestamp": datetime.now().isoformat(),
        "evaluation_note": (
            "Evaluated on chronologically held-out test set (most recent years). "
            "No data from the test period was used during training."
        ),
    }


def plot_actual_vs_predicted(
    pipeline, test_df: pd.DataFrame, target_col: str = "yield_tonnes_per_ha"
):
    """Save an actual vs predicted scatter plot."""
    X_test = test_df[TRAINING_FEATURES].fillna(test_df[TRAINING_FEATURES].median())
    y_test = test_df[target_col].values
    y_pred = np.clip(pipeline.predict(X_test), 0, None)

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # Scatter
    axes[0].scatter(y_test, y_pred, alpha=0.4, color="#4CAF50", edgecolors='none', s=20)
    max_val = max(y_test.max(), y_pred.max())
    axes[0].plot([0, max_val], [0, max_val], 'r--', lw=1.5, label="Perfect Prediction")
    axes[0].set_xlabel("Actual Yield (t/ha)")
    axes[0].set_ylabel("Predicted Yield (t/ha)")
    axes[0].set_title("Actual vs. Predicted Yield")
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)

    # Residuals
    residuals = y_pred - y_test
    axes[1].hist(residuals, bins=30, color="#2196F3", edgecolor='white', alpha=0.8)
    axes[1].axvline(0, color='red', linestyle='--')
    axes[1].set_xlabel("Residual (Predicted - Actual)")
    axes[1].set_ylabel("Count")
    axes[1].set_title("Residual Distribution")
    axes[1].grid(True, alpha=0.3)

    plt.tight_layout()
    plot_path = REPORTS_DIR / "actual_vs_predicted.png"
    plt.savefig(plot_path, dpi=120, bbox_inches='tight')
    plt.close()
    logger.info("Plot saved to %s", plot_path)
    return str(plot_path)


def run_evaluation(dataset_path: Optional[str] = None, model_path: Optional[str] = None):
    """Full evaluation pipeline."""
    logger.info("=== Starting Model Evaluation ===")
    pipeline = load_model(model_path)

    path = Path(dataset_path or DATASETS_DIR / "crop_yield_processed.csv")
    if not path.exists():
        logger.warning("Processed dataset not found. Running ingestion...")
        from ml.data_ingestion import run_ingestion
        _, processed_df = run_ingestion()
    else:
        processed_df = pd.read_csv(path)

    _, test_df = chronological_split(processed_df)
    if len(test_df) == 0:
        logger.error("Test set is empty after chronological split.")
        return

    metrics = evaluate_model(pipeline, test_df)
    plot_path = plot_actual_vs_predicted(pipeline, test_df)
    metrics["plot_path"] = plot_path

    # Save report
    report_path = REPORTS_DIR / "evaluation_report.json"
    with open(report_path, 'w') as f:
        json.dump(metrics, f, indent=2)

    logger.info("Evaluation report saved to %s", report_path)
    logger.info("=== Evaluation Complete ===")
    print(json.dumps(metrics, indent=2))
    return metrics


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Evaluate trained crop yield model")
    parser.add_argument("--dataset", type=str, default=None)
    parser.add_argument("--model", type=str, default=None)
    args = parser.parse_args()
    run_evaluation(args.dataset, args.model)
