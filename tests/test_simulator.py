"""
Unit tests for IoT Sensor Simulator
"""
import pytest
from iot.sensor_simulator import SensorSimulator, CropType, GrowthStage, SensorReading


def test_simulator_initialization():
    sim = SensorSimulator(num_fields=5, seed=42)
    assert len(sim.fields) == 5
    assert len(sim._field_states) == 5


def test_reading_structure_and_types():
    sim = SensorSimulator(num_fields=3, seed=123)
    readings = sim.generate_all_readings()
    assert len(readings) == 3

    for r in readings:
        assert isinstance(r, SensorReading)
        assert r.sensor_id.startswith("SENSOR_")
        assert r.field_id.startswith("FIELD_")
        assert 0 <= r.soil_moisture <= 100
        assert -50 <= r.temperature <= 60
        assert r.rainfall >= 0
        assert r.data_source == "simulated"
        assert isinstance(r.is_anomaly, bool)


def test_no_negative_rainfall():
    sim = SensorSimulator(num_fields=4, seed=999)
    batch = sim.generate_demo_batch(num_readings=100)
    for r in batch:
        assert r.rainfall >= 0.0, f"Rainfall cannot be negative, got {r.rainfall}"


def test_reading_validation():
    sim = SensorSimulator(num_fields=1, seed=42)
    valid_reading = SensorReading(
        sensor_id="SENSOR_001",
        field_id="FIELD_001",
        timestamp="2026-10-15T12:00:00Z",
        soil_moisture=55.0,
        temperature=24.5,
        rainfall=2.5,
        crop_type="wheat",
        growth_stage="vegetative",
        latitude=30.0,
        longitude=75.0,
        battery_level=90.0,
        is_anomaly=False,
    )
    is_valid, warnings = sim.validate_reading(valid_reading)
    assert is_valid is True
    assert len(warnings) == 0

    invalid_reading = SensorReading(
        sensor_id="",
        field_id="FIELD_001",
        timestamp="2026-10-15T12:00:00Z",
        soil_moisture=150.0,
        temperature=24.5,
        rainfall=-5.0,
        crop_type="wheat",
        growth_stage="vegetative",
        latitude=30.0,
        longitude=75.0,
        battery_level=90.0,
        is_anomaly=False,
    )
    is_valid, warnings = sim.validate_reading(invalid_reading)
    assert is_valid is False
    assert len(warnings) >= 2


def test_deterministic_seed():
    sim1 = SensorSimulator(num_fields=3, seed=42)
    sim2 = SensorSimulator(num_fields=3, seed=42)

    batch1 = sim1.generate_demo_batch(10)
    batch2 = sim2.generate_demo_batch(10)

    for r1, r2 in zip(batch1, batch2):
        assert r1.soil_moisture == r2.soil_moisture
        assert r1.temperature == r2.temperature
