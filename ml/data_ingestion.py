"""
Historical Crop Yield Data Ingestion and Preparation Script.
Loads, validates, cleans, and prepares crop yield data for ML training.
Generates a synthetic demo dataset with documented structure when real data is unavailable.
"""
import os
import sys
import logging
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

# Project root
ROOT = Path(__file__).parent.parent
DATASETS_DIR = ROOT / "datasets"
PROCESSED_DIR = DATASETS_DIR / "processed"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


CROP_NAMES_NORMALIZED = {
    "wheat": "wheat", "WHEAT": "wheat",
    "rice": "rice", "RICE": "rice", "paddy": "rice",
    "maize": "maize", "MAIZE": "maize", "corn": "maize",
    "cotton": "cotton", "COTTON": "cotton",
    "soybean": "soybean", "SOYBEAN": "soybean", "soya": "soybean",
    "potato": "potato", "POTATO": "potato",
}

EXPECTED_COLUMNS = {
    "required": ["crop_type", "season", "yield_tonnes_per_ha"],
    "optional": [
        "state", "district", "year", "area_ha", "production_tonnes",
        "avg_temperature", "total_rainfall", "avg_soil_moisture",
    ]
}


def generate_synthetic_demo_dataset(
    num_records: int = 2000,
    seed: int = 42,
    output_path: Optional[Path] = None,
) -> pd.DataFrame:
    """
    Generate a synthetic crop yield dataset for demonstration purposes.
    All values are algorithmically derived from realistic agronomic relationships.
    
    DATA SOURCE: SYNTHETIC (algorithmically generated for demonstration)
    NOT based on real observations. Relationships are illustrative.
    """
    rng = np.random.default_rng(seed)
    logger.info("Generating synthetic demo dataset (n=%d, seed=%d)...", num_records, seed)

    crops = ["wheat", "rice", "maize", "cotton", "soybean", "potato"]
    seasons = ["kharif", "rabi", "summer"]
    states = [
        "Punjab", "Haryana", "Maharashtra", "Karnataka",
        "Andhra Pradesh", "Uttar Pradesh", "Madhya Pradesh",
    ]

    # Realistic baseline yields per crop (tonnes/hectare)
    baseline_yields = {
        "wheat": 3.5, "rice": 3.8, "maize": 4.0,
        "cotton": 1.8, "soybean": 1.5, "potato": 22.0,
    }

    records = []
    years = list(range(2015, 2025))

    for i in range(num_records):
        crop = rng.choice(crops)
        year = int(rng.choice(years))
        season = rng.choice(seasons)
        state = rng.choice(states)

        # Agronomic relationships (illustrative, not actual data)
        avg_temp = float(rng.uniform(15, 35))
        total_rainfall = float(rng.uniform(200, 1500))  # mm per season
        avg_soil_moisture = float(rng.uniform(30, 85))
        area_ha = float(rng.uniform(0.5, 15.0))

        # Optimal conditions lookup
        optimal_temp = {"wheat": 20, "rice": 28, "maize": 25, "cotton": 30,
                        "soybean": 22, "potato": 18}[crop]
        optimal_rain = {"wheat": 600, "rice": 1100, "maize": 700, "cotton": 800,
                        "soybean": 650, "potato": 750}[crop]

        # Yield depends on how close conditions are to optimal
        temp_factor = 1.0 - 0.02 * abs(avg_temp - optimal_temp)
        rain_factor = 1.0 - 0.0003 * abs(total_rainfall - optimal_rain)
        moisture_factor = 0.8 + 0.004 * avg_soil_moisture
        noise = rng.normal(1.0, 0.08)
        year_trend = 1.0 + 0.01 * (year - 2015)  # slight improvement over years

        base = baseline_yields[crop]
        yield_val = (
            base * temp_factor * rain_factor * moisture_factor * noise * year_trend
        )
        yield_val = max(0.1, round(yield_val, 3))

        # Days from planting to harvest (approximate)
        growth_days = {"wheat": 120, "rice": 140, "maize": 100,
                       "cotton": 160, "soybean": 110, "potato": 90}[crop]
        planting_date = datetime(year, rng.integers(1, 7), rng.integers(1, 28))
        harvest_date = planting_date + timedelta(days=growth_days)

        # Rolling stats for 30-day prediction window (day = harvest - 30)
        cutoff_date = harvest_date - timedelta(days=30)

        records.append({
            "record_id": f"REC_{i+1:05d}",
            "crop_type": crop,
            "season": season,
            "state": state,
            "year": year,
            "area_ha": round(area_ha, 2),
            "avg_temperature_c": round(avg_temp, 2),
            "total_rainfall_mm": round(total_rainfall, 2),
            "avg_soil_moisture_pct": round(avg_soil_moisture, 2),
            "planting_date": planting_date.date().isoformat(),
            "harvest_date": harvest_date.date().isoformat(),
            "prediction_cutoff_date": cutoff_date.date().isoformat(),
            "growth_days": growth_days,
            "yield_tonnes_per_ha": yield_val,
            "data_source": "synthetic_demo",
            "data_quality": "generated",
        })

    df = pd.DataFrame(records)
    logger.info("Generated %d synthetic records.", len(df))
    logger.warning(
        "NOTICE: This is a SYNTHETIC dataset. All values are algorithmically "
        "generated for demonstration. Do not use for real agronomic decisions."
    )

    if output_path:
        df.to_csv(output_path, index=False)
        logger.info("Synthetic dataset saved to %s", output_path)

    return df


def load_dataset(dataset_path: Optional[str] = None) -> pd.DataFrame:
    """
    Load a CSV crop yield dataset.
    Falls back to synthetic data if none is provided or found.
    """
    if dataset_path and Path(dataset_path).exists():
        logger.info("Loading dataset from %s", dataset_path)
        df = pd.read_csv(dataset_path)
        logger.info("Loaded %d rows, %d columns: %s", len(df), len(df.columns), list(df.columns))
        return df
    else:
        logger.warning("No real dataset found. Generating synthetic demo dataset.")
        return generate_synthetic_demo_dataset(
            output_path=PROCESSED_DIR / "synthetic_crop_yield.csv"
        )


def normalize_crop_names(df: pd.DataFrame, col: str = "crop_type") -> pd.DataFrame:
    """Normalize crop names to a standard lowercase set."""
    before = df[col].nunique()
    df[col] = df[col].str.strip().map(
        lambda x: CROP_NAMES_NORMALIZED.get(x, x.lower() if isinstance(x, str) else x)
    )
    after = df[col].nunique()
    logger.info("Crop names normalized: %d → %d unique values", before, after)
    return df


def clean_dataset(df: pd.DataFrame) -> pd.DataFrame:
    """Handle missing values, duplicates, and invalid entries."""
    initial_rows = len(df)

    # Remove exact duplicates
    df = df.drop_duplicates()
    logger.info("Removed %d duplicate rows.", initial_rows - len(df))

    # Normalize crop names if column exists
    if "crop_type" in df.columns:
        df = normalize_crop_names(df)

    # Drop rows with missing target
    target_col = next(
        (c for c in ["yield_tonnes_per_ha", "yield", "production_per_ha"] if c in df.columns),
        None
    )
    if target_col and target_col != "yield_tonnes_per_ha":
        df = df.rename(columns={target_col: "yield_tonnes_per_ha"})

    if "yield_tonnes_per_ha" in df.columns:
        before = len(df)
        df = df.dropna(subset=["yield_tonnes_per_ha"])
        df = df[df["yield_tonnes_per_ha"] > 0]
        logger.info("Dropped %d rows with missing/invalid yield.", before - len(df))

    # Fill numeric nulls with median
    numeric_cols = df.select_dtypes(include=np.number).columns
    for col in numeric_cols:
        null_count = df[col].isna().sum()
        if null_count > 0:
            median_val = df[col].median()
            df[col] = df[col].fillna(median_val)
            logger.info("Filled %d nulls in '%s' with median=%.3f", null_count, col, median_val)

    # Fill categorical nulls
    cat_cols = df.select_dtypes(include="object").columns
    for col in cat_cols:
        null_count = df[col].isna().sum()
        if null_count > 0:
            df[col] = df[col].fillna("unknown")
            logger.info("Filled %d nulls in '%s' with 'unknown'", null_count, col)

    logger.info("Cleaned dataset: %d → %d rows.", initial_rows, len(df))
    return df


def validate_schema(df: pd.DataFrame) -> bool:
    """Verify required columns are present after cleaning."""
    required = EXPECTED_COLUMNS["required"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        logger.error("Dataset missing required columns: %s", missing)
        return False
    logger.info("Schema validation passed. All required columns present.")
    return True


def prepare_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add derived features for ML training."""
    # Encode crop type as integer
    crop_map = {"wheat": 0, "rice": 1, "maize": 2, "cotton": 3, "soybean": 4, "potato": 5}
    if "crop_type" in df.columns:
        df["crop_type_encoded"] = df["crop_type"].map(crop_map).fillna(-1).astype(int)

    # Encode season
    season_map = {"kharif": 0, "rabi": 1, "summer": 2, "whole year": 3}
    if "season" in df.columns:
        df["season_encoded"] = df["season"].str.lower().map(season_map).fillna(-1).astype(int)

    # Year normalized
    if "year" in df.columns:
        min_year = df["year"].min()
        df["year_normalized"] = df["year"] - min_year

    # Temperature stress index
    if "avg_temperature_c" in df.columns:
        df["temp_stress"] = (df["avg_temperature_c"] - 25).abs()

    # Rainfall adequacy ratio
    if "total_rainfall_mm" in df.columns:
        df["rainfall_adequacy"] = df["total_rainfall_mm"] / df["total_rainfall_mm"].median()

    logger.info("Feature engineering complete. DataFrame now has %d columns.", len(df.columns))
    return df


def run_ingestion(dataset_path: Optional[str] = None) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Full ingestion pipeline. Returns (raw_df, processed_df).
    """
    logger.info("=== Starting Data Ingestion Pipeline ===")
    raw_df = load_dataset(dataset_path)
    clean_df = clean_dataset(raw_df.copy())

    if not validate_schema(clean_df):
        logger.warning("Schema validation failed. Falling back to synthetic dataset.")
        clean_df = generate_synthetic_demo_dataset(
            output_path=PROCESSED_DIR / "synthetic_crop_yield.csv"
        )
        clean_df = clean_dataset(clean_df)

    processed_df = prepare_features(clean_df)

    # Save processed dataset
    output_path = PROCESSED_DIR / "crop_yield_processed.csv"
    processed_df.to_csv(output_path, index=False)
    logger.info("Processed dataset saved to %s", output_path)
    logger.info("Columns: %s", list(processed_df.columns))
    logger.info("Shape: %s", processed_df.shape)
    logger.info("=== Ingestion Complete ===")
    return raw_df, processed_df


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Crop Yield Data Ingestion")
    parser.add_argument("--dataset", type=str, help="Path to CSV dataset", default=None)
    parser.add_argument("--synthetic", action="store_true", help="Force synthetic data generation")
    args = parser.parse_args()

    path = None if args.synthetic else args.dataset
    raw, processed = run_ingestion(path)
    print(f"\nRaw dataset: {raw.shape}")
    print(f"Processed dataset: {processed.shape}")
    print(f"\nSample:\n{processed.head(3).to_string()}")
