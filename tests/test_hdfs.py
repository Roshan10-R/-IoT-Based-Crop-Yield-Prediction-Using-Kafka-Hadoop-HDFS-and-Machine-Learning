"""
Unit tests for HDFS Storage Module and Local Fallback
"""
import pytest
import os
import json
import shutil
from pathlib import Path
from storage.hdfs_writer import HDFSWriter
from storage.hdfs_reader import HDFSReader


@pytest.fixture
def temp_storage(tmp_path):
    fallback_dir = tmp_path / "fallback"
    fallback_dir.mkdir(parents=True, exist_ok=True)
    writer = HDFSWriter(
        namenode_url="http://invalid-host:9999",
        local_fallback_path=str(fallback_dir),
        use_hdfs=False,
    )
    reader = HDFSReader(
        namenode_url="http://invalid-host:9999",
        local_fallback_path=str(fallback_dir),
    )
    yield writer, reader, fallback_dir


def test_local_fallback_batch_write(temp_storage):
    writer, reader, fallback_dir = temp_storage

    messages = [
        {
            "sensor_id": f"SENSOR_{i:03d}",
            "field_id": "FIELD_001",
            "soil_moisture": 50.0 + i,
            "temperature": 25.0,
            "rainfall": 0.0,
            "crop_type": "wheat",
        }
        for i in range(5)
    ]

    res = writer.write_batch(messages)
    assert res["success"] is True
    assert res["storage_backend"] == "local_fallback"
    assert "warning" in res

    # Verify files created in fallback
    files = list((fallback_dir / "sensor-readings").glob("*.jsonl"))
    assert len(files) == 1

    # Verify reader reads back records
    records = reader.read_local_fallback()
    assert len(records) == 5
    assert records[0]["sensor_id"] == "SENSOR_000"


def test_status_reporting(temp_storage):
    writer, reader, fallback_dir = temp_storage
    status = writer.status()
    assert status["hdfs_available"] is False
    assert status["active_backend"] == "local_fallback"
