"""
IoT Sensor Simulator for Agricultural Field Monitoring
Generates realistic soil moisture, temperature, and rainfall readings
for multiple fields and crop types.
"""
import json
import time
import random
import logging
import argparse
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)


class CropType(str, Enum):
    WHEAT = "wheat"
    RICE = "rice"
    MAIZE = "maize"
    COTTON = "cotton"
    SOYBEAN = "soybean"
    POTATO = "potato"


class GrowthStage(str, Enum):
    GERMINATION = "germination"
    SEEDLING = "seedling"
    VEGETATIVE = "vegetative"
    FLOWERING = "flowering"
    GRAIN_FILL = "grain_fill"
    MATURITY = "maturity"


# Realistic ranges per crop type (soil_moisture_min, soil_moisture_max,
# temp_min, temp_max, rainfall_per_reading_mm)
CROP_PROFILES: Dict[str, Dict] = {
    CropType.WHEAT: {
        "soil_moisture": (35, 70),
        "temperature": (5, 25),
        "rainfall_bias": 0.3,
        "optimal_moisture": 55,
        "growth_days": 120,
    },
    CropType.RICE: {
        "soil_moisture": (60, 95),
        "temperature": (20, 35),
        "rainfall_bias": 0.6,
        "optimal_moisture": 80,
        "growth_days": 140,
    },
    CropType.MAIZE: {
        "soil_moisture": (40, 75),
        "temperature": (15, 35),
        "rainfall_bias": 0.4,
        "optimal_moisture": 60,
        "growth_days": 100,
    },
    CropType.COTTON: {
        "soil_moisture": (30, 65),
        "temperature": (20, 38),
        "rainfall_bias": 0.25,
        "optimal_moisture": 50,
        "growth_days": 160,
    },
    CropType.SOYBEAN: {
        "soil_moisture": (45, 80),
        "temperature": (15, 30),
        "rainfall_bias": 0.35,
        "optimal_moisture": 62,
        "growth_days": 110,
    },
    CropType.POTATO: {
        "soil_moisture": (50, 85),
        "temperature": (10, 25),
        "rainfall_bias": 0.45,
        "optimal_moisture": 70,
        "growth_days": 90,
    },
}

GROWTH_STAGE_ORDER = [
    GrowthStage.GERMINATION,
    GrowthStage.SEEDLING,
    GrowthStage.VEGETATIVE,
    GrowthStage.FLOWERING,
    GrowthStage.GRAIN_FILL,
    GrowthStage.MATURITY,
]


@dataclass
class SensorReading:
    sensor_id: str
    field_id: str
    timestamp: str
    soil_moisture: float       # percentage (0-100)
    temperature: float         # Celsius
    rainfall: float            # mm over measurement interval
    crop_type: str
    growth_stage: str
    latitude: float
    longitude: float
    battery_level: float       # percentage
    is_anomaly: bool           # True if value is a labeled simulated anomaly
    data_source: str = "simulated"

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)


@dataclass
class FieldConfig:
    field_id: str
    sensor_id: str
    crop_type: CropType
    planting_date: datetime
    latitude: float
    longitude: float
    area_hectares: float


class SensorSimulator:
    """
    Simulates multiple IoT sensors across agricultural fields.
    Generates realistic readings based on crop type, season, and growth stage.
    """

    def __init__(
        self,
        num_fields: int = 5,
        seed: Optional[int] = 42,
        anomaly_rate: float = 0.02,
    ):
        self.num_fields = num_fields
        self.anomaly_rate = anomaly_rate
        self._rng = random.Random(seed)
        self.fields: List[FieldConfig] = []
        self._field_states: Dict[str, Dict] = {}
        self._initialize_fields()
        logger.info(
            "SensorSimulator initialized with %d fields (seed=%s)",
            num_fields, seed
        )

    def _initialize_fields(self):
        crop_types = list(CropType)
        for i in range(self.num_fields):
            crop = crop_types[i % len(crop_types)]
            field_id = f"FIELD_{i + 1:03d}"
            sensor_id = f"SENSOR_{i + 1:03d}"
            # Stagger planting dates so fields are at different growth stages
            days_since_planting = self._rng.randint(10, 90)
            from datetime import timedelta
            planting_date = datetime.now(timezone.utc) - timedelta(days=days_since_planting)
            field = FieldConfig(
                field_id=field_id,
                sensor_id=sensor_id,
                crop_type=crop,
                planting_date=planting_date,
                latitude=round(18.0 + self._rng.uniform(0, 12), 4),
                longitude=round(73.0 + self._rng.uniform(0, 20), 4),
                area_hectares=round(self._rng.uniform(1.0, 15.0), 2),
            )
            self.fields.append(field)
            self._field_states[field_id] = {
                "last_moisture": self._rng.uniform(
                    *CROP_PROFILES[crop]["soil_moisture"]
                ),
                "last_temperature": self._rng.uniform(
                    *CROP_PROFILES[crop]["temperature"]
                ),
                "cumulative_rainfall": self._rng.uniform(10, 150),
                "days_since_planting": days_since_planting,
            }

    def _get_growth_stage(self, crop_type: CropType, days_since_planting: int) -> GrowthStage:
        total_days = CROP_PROFILES[crop_type]["growth_days"]
        progress = min(days_since_planting / total_days, 1.0)
        idx = min(int(progress * len(GROWTH_STAGE_ORDER)), len(GROWTH_STAGE_ORDER) - 1)
        return GROWTH_STAGE_ORDER[idx]

    def _simulate_reading(self, field: FieldConfig) -> SensorReading:
        state = self._field_states[field.field_id]
        profile = CROP_PROFILES[field.crop_type]
        is_anomaly = False

        # Simulate anomalies (clearly labeled)
        if self._rng.random() < self.anomaly_rate:
            is_anomaly = True
            soil_moisture = self._rng.uniform(0, 10)   # drought-like anomaly
            temperature = self._rng.uniform(45, 55)     # heat spike anomaly
            rainfall = 0.0
            logger.warning(
                "[LABELED SIMULATED ANOMALY] field=%s moisture=%.1f temp=%.1f",
                field.field_id, soil_moisture, temperature
            )
        else:
            # Realistic value with small drift from last reading
            sm_min, sm_max = profile["soil_moisture"]
            temp_min, temp_max = profile["temperature"]

            soil_moisture = max(sm_min, min(sm_max,
                state["last_moisture"] + self._rng.gauss(0, 1.5)
            ))
            temperature = max(temp_min, min(temp_max,
                state["last_temperature"] + self._rng.gauss(0, 0.8)
            ))

            # Rainfall: mostly 0, occasionally nonzero
            if self._rng.random() < profile["rainfall_bias"]:
                rainfall = round(self._rng.uniform(0.5, 20.0), 2)
            else:
                rainfall = 0.0

        state["last_moisture"] = soil_moisture
        state["last_temperature"] = temperature
        state["cumulative_rainfall"] += rainfall
        state["days_since_planting"] += 1

        growth_stage = self._get_growth_stage(
            field.crop_type, state["days_since_planting"]
        )

        return SensorReading(
            sensor_id=field.sensor_id,
            field_id=field.field_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            soil_moisture=round(soil_moisture, 2),
            temperature=round(temperature, 2),
            rainfall=round(rainfall, 2),
            crop_type=field.crop_type.value,
            growth_stage=growth_stage.value,
            latitude=field.latitude,
            longitude=field.longitude,
            battery_level=round(self._rng.uniform(60, 100), 1),
            is_anomaly=is_anomaly,
            data_source="simulated",
        )

    def generate_all_readings(self) -> List[SensorReading]:
        """Generate one reading per field."""
        readings = []
        for field in self.fields:
            try:
                reading = self._simulate_reading(field)
                readings.append(reading)
            except Exception as exc:
                logger.error("Error generating reading for %s: %s", field.field_id, exc)
        return readings

    def generate_demo_batch(
        self, num_readings: int = 100, fields: Optional[List[str]] = None
    ) -> List[SensorReading]:
        """Generate a fixed batch of readings for demo/testing."""
        readings = []
        target_fields = (
            [f for f in self.fields if f.field_id in fields]
            if fields else self.fields
        )
        for _ in range(num_readings):
            field = self._rng.choice(target_fields)
            readings.append(self._simulate_reading(field))
        return readings

    def validate_reading(self, reading: SensorReading) -> Tuple[bool, List[str]]:
        """Validate sensor reading values. Returns (is_valid, warnings)."""
        warnings = []
        if not (0 <= reading.soil_moisture <= 100):
            warnings.append(f"soil_moisture={reading.soil_moisture} out of range [0,100]")
        if not (-50 <= reading.temperature <= 60):
            warnings.append(f"temperature={reading.temperature} out of physical range")
        if reading.rainfall < 0:
            warnings.append("rainfall cannot be negative")
        if not reading.sensor_id:
            warnings.append("missing sensor_id")
        if not reading.field_id:
            warnings.append("missing field_id")
        return len(warnings) == 0, warnings

    def stream_readings(self, interval: float = 5.0, max_readings: Optional[int] = None):
        """Generator: yields all field readings at each interval."""
        count = 0
        try:
            while True:
                readings = self.generate_all_readings()
                for r in readings:
                    valid, warnings = self.validate_reading(r)
                    if not valid and not r.is_anomaly:
                        logger.warning("Invalid reading from %s: %s", r.sensor_id, warnings)
                    yield r
                    count += 1
                    if max_readings and count >= max_readings:
                        return
                if max_readings and count >= max_readings:
                    return
                time.sleep(interval)
        except KeyboardInterrupt:
            logger.info("Sensor streaming stopped by user.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="IoT Crop Sensor Simulator")
    parser.add_argument("--fields", type=int, default=5, help="Number of fields")
    parser.add_argument("--interval", type=float, default=5.0, help="Sampling interval (seconds)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--mode", choices=["stream", "demo"], default="stream")
    parser.add_argument("--count", type=int, default=20, help="Number of readings in demo mode")
    args = parser.parse_args()

    sim = SensorSimulator(num_fields=args.fields, seed=args.seed)

    if args.mode == "demo":
        readings = sim.generate_demo_batch(args.count)
        for r in readings:
            print(r.to_json())
    else:
        for reading in sim.stream_readings(interval=args.interval):
            print(reading.to_json())
