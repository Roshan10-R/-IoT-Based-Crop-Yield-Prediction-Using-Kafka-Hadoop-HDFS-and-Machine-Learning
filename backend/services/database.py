"""
SQLite Database Service for Crop Yield Prediction System.
Handles fields, sensor readings, predictions, and actual yield records.
"""
import sqlite3
import json
import logging
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Optional, Any

logger = logging.getLogger(__name__)

DB_PATH = os.getenv("DATABASE_PATH", "./data/crop_yield.db")


class DatabaseService:
    def __init__(self, db_path: str = None):
        self.db_path = Path(db_path or DB_PATH)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init_db(self):
        """Create all tables."""
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS fields (
                    field_id TEXT PRIMARY KEY,
                    sensor_id TEXT NOT NULL,
                    crop_type TEXT NOT NULL,
                    area_ha REAL,
                    latitude REAL,
                    longitude REAL,
                    state TEXT,
                    season TEXT DEFAULT 'rabi',
                    planting_date TEXT,
                    created_at TEXT DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS sensor_readings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sensor_id TEXT NOT NULL,
                    field_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    soil_moisture REAL,
                    temperature REAL,
                    rainfall REAL,
                    crop_type TEXT,
                    growth_stage TEXT,
                    battery_level REAL,
                    is_anomaly INTEGER DEFAULT 0,
                    data_source TEXT DEFAULT 'simulated',
                    quality_warnings TEXT,
                    consumed_at TEXT,
                    created_at TEXT DEFAULT (datetime('now'))
                );

                CREATE INDEX IF NOT EXISTS idx_sensor_field ON sensor_readings(field_id);
                CREATE INDEX IF NOT EXISTS idx_sensor_ts ON sensor_readings(timestamp);

                CREATE TABLE IF NOT EXISTS predictions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    field_id TEXT NOT NULL,
                    crop_type TEXT NOT NULL,
                    season TEXT,
                    prediction_timestamp TEXT NOT NULL,
                    prediction_cutoff_date TEXT,
                    expected_harvest_date TEXT,
                    predicted_yield REAL NOT NULL,
                    yield_unit TEXT DEFAULT 'tonnes_per_hectare',
                    area_ha REAL,
                    total_predicted_production REAL,
                    model_version TEXT,
                    model_name TEXT,
                    feature_values TEXT,
                    data_quality_warnings TEXT,
                    demo_mode INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS actual_yields (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    field_id TEXT NOT NULL,
                    crop_type TEXT NOT NULL,
                    season TEXT,
                    year INTEGER,
                    actual_yield REAL NOT NULL,
                    yield_unit TEXT DEFAULT 'tonnes_per_hectare',
                    area_ha REAL,
                    harvest_date TEXT,
                    data_source TEXT DEFAULT 'historical',
                    notes TEXT,
                    created_at TEXT DEFAULT (datetime('now'))
                );
            """)
        logger.info("Database initialized at %s", self.db_path)
        self._seed_demo_data()

    def _seed_demo_data(self):
        """Insert demo fields if the DB is empty."""
        with self._conn() as conn:
            count = conn.execute("SELECT COUNT(*) FROM fields").fetchone()[0]
            if count > 0:
                return
        fields = [
            ("FIELD_001", "SENSOR_001", "wheat", 8.5, 30.7333, 76.7794, "Punjab", "rabi", "2024-11-01"),
            ("FIELD_002", "SENSOR_002", "rice", 5.2, 22.5726, 88.3639, "West Bengal", "kharif", "2024-06-15"),
            ("FIELD_003", "SENSOR_003", "maize", 3.8, 25.3176, 82.9739, "Uttar Pradesh", "kharif", "2024-07-01"),
            ("FIELD_004", "SENSOR_004", "cotton", 12.0, 21.1702, 72.8311, "Gujarat", "kharif", "2024-05-20"),
            ("FIELD_005", "SENSOR_005", "soybean", 6.7, 22.7196, 75.8577, "Madhya Pradesh", "kharif", "2024-06-25"),
        ]
        with self._conn() as conn:
            conn.executemany(
                "INSERT OR IGNORE INTO fields (field_id, sensor_id, crop_type, area_ha, latitude, longitude, state, season, planting_date) VALUES (?,?,?,?,?,?,?,?,?)",
                fields
            )
        logger.info("Seeded %d demo fields.", len(fields))

    def store_sensor_reading(self, reading: Dict[str, Any]):
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO sensor_readings
                (sensor_id, field_id, timestamp, soil_moisture, temperature, rainfall,
                 crop_type, growth_stage, battery_level, is_anomaly, data_source,
                 quality_warnings, consumed_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    reading.get("sensor_id"),
                    reading.get("field_id"),
                    reading.get("timestamp"),
                    reading.get("soil_moisture"),
                    reading.get("temperature"),
                    reading.get("rainfall"),
                    reading.get("crop_type"),
                    reading.get("growth_stage"),
                    reading.get("battery_level"),
                    1 if reading.get("is_anomaly") else 0,
                    reading.get("data_source", "simulated"),
                    json.dumps(reading.get("_quality_warnings", [])),
                    reading.get("consumed_at"),
                )
            )

    def get_latest_sensor_readings(self, limit: int = 50) -> List[Dict]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM sensor_readings
                ORDER BY timestamp DESC LIMIT ?
                """, (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def get_sensor_history(
        self, field_id: Optional[str] = None,
        limit: int = 200, offset: int = 0,
        start_date: Optional[str] = None, end_date: Optional[str] = None,
    ) -> List[Dict]:
        query = "SELECT * FROM sensor_readings WHERE 1=1"
        params = []
        if field_id:
            query += " AND field_id = ?"
            params.append(field_id)
        if start_date:
            query += " AND timestamp >= ?"
            params.append(start_date)
        if end_date:
            query += " AND timestamp <= ?"
            params.append(end_date)
        query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        with self._conn() as conn:
            rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    def get_fields(self) -> List[Dict]:
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM fields ORDER BY field_id").fetchall()
        return [dict(r) for r in rows]

    def get_field(self, field_id: str) -> Optional[Dict]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM fields WHERE field_id = ?", (field_id,)
            ).fetchone()
        return dict(row) if row else None

    def save_prediction(self, prediction: Dict) -> int:
        with self._conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO predictions
                (field_id, crop_type, season, prediction_timestamp, prediction_cutoff_date,
                 expected_harvest_date, predicted_yield, yield_unit, area_ha,
                 total_predicted_production, model_version, model_name, feature_values,
                 data_quality_warnings, demo_mode)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    prediction.get("field_id"),
                    prediction.get("crop_type"),
                    prediction.get("season"),
                    prediction.get("prediction_timestamp"),
                    prediction.get("prediction_cutoff_date"),
                    prediction.get("expected_harvest_date"),
                    prediction.get("predicted_yield"),
                    prediction.get("yield_unit", "tonnes_per_hectare"),
                    prediction.get("area_ha"),
                    prediction.get("total_predicted_production_tonnes"),
                    prediction.get("model_version"),
                    prediction.get("model_name"),
                    json.dumps(prediction.get("feature_values", {})),
                    json.dumps(prediction.get("data_quality_warnings", [])),
                    1 if prediction.get("demo_mode") else 0,
                )
            )
        return cur.lastrowid

    def get_predictions(
        self, field_id: Optional[str] = None, limit: int = 50
    ) -> List[Dict]:
        query = "SELECT * FROM predictions WHERE 1=1"
        params = []
        if field_id:
            query += " AND field_id = ?"
            params.append(field_id)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        with self._conn() as conn:
            rows = conn.execute(query, params).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["feature_values"] = json.loads(d.get("feature_values") or "{}")
            d["data_quality_warnings"] = json.loads(d.get("data_quality_warnings") or "[]")
            result.append(d)
        return result

    def get_actual_yields(
        self, field_id: Optional[str] = None, limit: int = 100
    ) -> List[Dict]:
        query = "SELECT * FROM actual_yields WHERE 1=1"
        params = []
        if field_id:
            query += " AND field_id = ?"
            params.append(field_id)
        query += " ORDER BY year DESC, created_at DESC LIMIT ?"
        params.append(limit)
        with self._conn() as conn:
            rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    def seed_actual_yields(self):
        """Seed historical actual yield data for demonstration."""
        records = [
            ("FIELD_001", "wheat", "rabi", 2022, 3.8, "tonnes_per_hectare", 8.5, "2023-04-15", "historical"),
            ("FIELD_001", "wheat", "rabi", 2023, 4.1, "tonnes_per_hectare", 8.5, "2024-04-10", "historical"),
            ("FIELD_002", "rice", "kharif", 2022, 3.5, "tonnes_per_hectare", 5.2, "2022-11-20", "historical"),
            ("FIELD_002", "rice", "kharif", 2023, 3.7, "tonnes_per_hectare", 5.2, "2023-11-18", "historical"),
            ("FIELD_003", "maize", "kharif", 2022, 4.2, "tonnes_per_hectare", 3.8, "2022-10-30", "historical"),
            ("FIELD_003", "maize", "kharif", 2023, 4.5, "tonnes_per_hectare", 3.8, "2023-10-28", "historical"),
            ("FIELD_004", "cotton", "kharif", 2022, 1.9, "tonnes_per_hectare", 12.0, "2023-01-15", "historical"),
            ("FIELD_005", "soybean", "kharif", 2023, 1.6, "tonnes_per_hectare", 6.7, "2023-10-20", "historical"),
        ]
        with self._conn() as conn:
            count = conn.execute("SELECT COUNT(*) FROM actual_yields").fetchone()[0]
            if count > 0:
                return
            conn.executemany(
                "INSERT INTO actual_yields "
                "(field_id, crop_type, season, year, actual_yield, yield_unit, area_ha, harvest_date, data_source) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                records
            )
        logger.info("Seeded %d historical yield records.", len(records))
