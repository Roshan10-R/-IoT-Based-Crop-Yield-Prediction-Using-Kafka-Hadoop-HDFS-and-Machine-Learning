"""
HDFS Reader for Crop Yield Data.
Reads and inspects files stored in HDFS or local fallback.
"""
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

logger = logging.getLogger(__name__)


class HDFSReader:
    """Reads files from HDFS or local fallback storage."""

    def __init__(
        self,
        namenode_url: Optional[str] = None,
        hdfs_user: str = "hadoop",
        local_fallback_path: Optional[str] = None,
    ):
        self.namenode_url = namenode_url or os.getenv(
            "HDFS_NAMENODE_URL", "http://localhost:9870"
        )
        self.hdfs_user = hdfs_user or os.getenv("HDFS_USER", "hadoop")
        self.local_fallback_path = Path(
            local_fallback_path
            or os.getenv("LOCAL_STORAGE_PATH", "./data/local_fallback")
        )

    def _webhdfs_url(self, path: str, op: str, **params) -> str:
        base = f"{self.namenode_url}/webhdfs/v1{path}"
        query = {"op": op, "user.name": self.hdfs_user, **params}
        qs = "&".join(f"{k}={v}" for k, v in query.items())
        return f"{base}?{qs}"

    def list_directory(self, hdfs_path: str) -> List[Dict]:
        """List files in an HDFS directory."""
        try:
            url = self._webhdfs_url(hdfs_path, "LISTSTATUS")
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                statuses = resp.json().get("FileStatuses", {}).get("FileStatus", [])
                return [
                    {
                        "name": s["pathSuffix"],
                        "type": s["type"],
                        "length": s["length"],
                        "modificationTime": datetime.fromtimestamp(
                            s["modificationTime"] / 1000
                        ).isoformat(),
                    }
                    for s in statuses
                ]
            else:
                logger.error("HDFS list failed: %s", resp.status_code)
                return []
        except Exception as exc:
            logger.error("HDFS list error: %s", exc)
            return []

    def read_file(self, hdfs_path: str) -> Optional[str]:
        """Read a file from HDFS as text."""
        try:
            url = self._webhdfs_url(hdfs_path, "OPEN")
            resp = requests.get(url, timeout=30, allow_redirects=True)
            if resp.status_code == 200:
                return resp.text
            else:
                logger.error("HDFS read failed: %s", resp.status_code)
                return None
        except Exception as exc:
            logger.error("HDFS read error: %s", exc)
            return None

    def read_jsonl_file(self, hdfs_path: str) -> List[dict]:
        """Read a JSONL file from HDFS and parse each line."""
        content = self.read_file(hdfs_path)
        if not content:
            return []
        records = []
        for line in content.strip().split("\n"):
            if line.strip():
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    logger.warning("Could not parse line: %s", exc)
        return records

    def read_local_fallback(self, subdir: str = "sensor-readings") -> List[dict]:
        """Read all JSONL files from local fallback storage."""
        records = []
        base = self.local_fallback_path / subdir
        if not base.exists():
            return records
        for f in sorted(base.glob("*.jsonl")):
            try:
                with open(f, 'r') as fp:
                    for line in fp:
                        line = line.strip()
                        if line:
                            records.append(json.loads(line))
            except Exception as exc:
                logger.error("Error reading local file %s: %s", f, exc)
        return records

    def inspect_storage(self) -> dict:
        """Return a summary of stored data in HDFS and local fallback."""
        summary = {
            "hdfs": {},
            "local_fallback": {},
        }
        # HDFS
        hdfs_base = "/crop-yield/raw/sensor-readings"
        hdfs_files = self.list_directory(hdfs_base)
        summary["hdfs"] = {
            "base_path": hdfs_base,
            "file_count": len(hdfs_files),
            "files": hdfs_files[:10],
        }
        # Local
        local_base = self.local_fallback_path / "sensor-readings"
        local_files = list(local_base.glob("*.jsonl")) if local_base.exists() else []
        summary["local_fallback"] = {
            "base_path": str(local_base),
            "file_count": len(local_files),
            "files": [f.name for f in local_files[:10]],
            "total_bytes": sum(f.stat().st_size for f in local_files),
        }
        return summary
