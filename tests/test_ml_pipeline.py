"""
Integration tests for ML Training, Evaluation, and Prediction Pipeline
"""
import pytest
import os
from pathlib import Path
from ml.data_ingestion import generate_synthetic_demo_dataset, clean_dataset, prepare_features
from ml.train import chronological_split, TRAINING_FEATURES
from ml.predict import CropYieldPredictor


def test_synthetic_data_generation():
    df = generate_synthetic_demo_dataset(num_records=100, seed=42)
    assert len(df) == 100
    assert "yield_tonnes_per_ha" in df.columns
    assert (df["yield_tonnes_per_ha"] > 0).all()
    assert (df["avg_soil_moisture_pct"] >= 0).all()
    assert (df["total_rainfall_mm"] >= 0).all()


def test_data_cleaning_and_validation():
    raw_df = generate_synthetic_demo_dataset(num_records=50, seed=123)
    cleaned_df = clean_dataset(raw_df)
    assert len(cleaned_df) == 50
    feat_df = prepare_features(cleaned_df)
    for col in ["crop_type_encoded", "season_encoded", "temp_stress", "rainfall_adequacy"]:
        assert col in feat_df.columns


def test_chronological_split_no_leakage():
    raw_df = generate_synthetic_demo_dataset(num_records=200, seed=42)
    cleaned_df = clean_dataset(raw_df)
    feat_df = prepare_features(cleaned_df)
    train_df, test_df = chronological_split(feat_df, test_fraction=0.2)

    assert len(train_df) > 0
    assert len(test_df) > 0
    assert train_df["year"].max() < 2023
    assert test_df["year"].min() >= 2023
    # Check no year overlap between train and test
    assert set(train_df["year"].unique()).isdisjoint(set(test_df["year"].unique()))


def test_prediction_inference():
    predictor = CropYieldPredictor()
    result = predictor.predict(
        field_id="FIELD_TEST",
        crop_type="wheat",
        season="rabi",
        area_ha=4.0,
        year=2024,
        demo_mode=True,
    )

    assert "predicted_yield" in result
    assert result["predicted_yield"] > 0
    assert "total_predicted_production_tonnes" in result
    assert result["yield_unit"] == "tonnes_per_hectare"
    assert "prediction_cutoff_date" in result
    assert "expected_harvest_date" in result
    assert result["model_name"] in ["gradient_boosting", "random_forest", "linear_regression"]
