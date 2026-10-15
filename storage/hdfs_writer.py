"""
HDFS Writer for Crop Yield Sensor Data.
Writes batches of sensor messages to Hadoop HDFS with a local fallback.
"""
import json
import logging
import os
import time
import gzip
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Dict, Any

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)


class HDFSWriteError(Exception):
    """Raised when an HDFS write cannot be completed."""
    pass


class HDFSWriter:
    """
    Writes sensor data batches to Hadoop HDFS via WebHDFS REST API.
    Falls back to local filesystem storage if HDFS is unavailable.
    The fallback is always logged explicitly — it is never silent.
    """

    HDFS_PATHS = {
        "raw_sensors": "/crop-yield/raw/sensor-readings",
        "processed": "/crop-yield/processed/features",
        "historical": "/crop-yield/datasets/historical-yield",
        "models": "/crop-yield/models",
        "predictions": "/crop-yield/predictions",
    }

    def __init__(
        self,
        namenode_url: Optional[str] = None,
        hdfs_user: str = "hadoop",
        local_fallback_path: Optional[str] = None,
        use_hdfs: bool = True,
        max_retries: int = 3,
        retry_delay: float = 2.0,
    ):
        self.namenode_url = namenode_url or os.getenv(
            "HDFS_NAMENODE_URL", "http://localhost:9870"
        )
        self.hdfs_user = hdfs_user or os.getenv("HDFS_USER", "hadoop")
        self.local_fallback_path = Path(
            local_fallback_path
            or os.getenv("LOCAL_STORAGE_PATH", "./data/local_fallback")
        )
        self.use_hdfs = use_hdfs and os.getenv("USE_HDFS", "true").lower() == "true"
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._hdfs_available = False
        self._bytes_written_hdfs = 0
        self._bytes_written_local = 0
        self._batches_written = 0
        self._check_hdfs_connectivity()
        self.local_fallback_path.mkdir(parents=True, exist_ok=True)

    def _check_hdfs_connectivity(self) -> bool:
        """Check if HDFS NameNode is reachable."""
        if not self.use_hdfs or not REQUESTS_AVAILABLE:
            self._hdfs_available = False
            return False
        try:
            url = f"{self.namenode_url}/webhdfs/v1/?op=GETFILESTATUS"
            resp = requests.get(url, params={"user.name": self.hdfs_user}, timeout=5)
            self._hdfs_available = resp.status_code in (200, 403, 404)
            if self._hdfs_available:
                logger.info("HDFS NameNode reachable at %s", self.namenode_url)
            return self._hdfs_available
        except Exception as exc:
            logger.warning(
                "HDFS NameNode not reachable (%s). Local fallback will be used.", exc
            )
            self._hdfs_available = False
            return False

    def _webhdfs_url(self, path: str, op: str, **params) -> str:
        base = f"{self.namenode_url}/webhdfs/v1{path}"
        query = {"op": op, "user.name": self.hdfs_user, **params}
        qs = "&".join(f"{k}={v}" for k, v in query.items())
        return f"{base}?{qs}"

    def _hdfs_mkdir(self, path: str) -> bool:
        """Create HDFS directory if it doesn't exist."""
        try:
            url = self._webhdfs_url(path, "MKDIRS")
            resp = requests.put(url, timeout=10)
            return resp.status_code == 200
        except Exception as exc:
            logger.error("HDFS mkdir failed for %s: %s", path, exc)
            return False

    def _hdfs_write_file(self, hdfs_path: str, content: bytes) -> bool:
        """Write content to HDFS using WebHDFS two-step PUT protocol."""
        try:
            # Step 1: Initiate create — follow redirect to DataNode
            url = self._webhdfs_url(hdfs_path, "CREATE", overwrite="true")
            resp = requests.put(url, allow_redirects=False, timeout=15)
            if resp.status_code != 307:
                logger.error(
                    "HDFS CREATE step 1 failed: %s %s", resp.status_code, resp.text
                )
                return False

            # Step 2: Write to DataNode
            datanode_url = resp.headers["Location"]
            resp2 = requests.put(
                datanode_url,
                data=content,
                headers={"Content-Type": "application/octet-stream"},
                timeout=30,
            )
            if resp2.status_code == 201:
                self._bytes_written_hdfs += len(content)
                return True
            else:
                logger.error(
                    "HDFS CREATE step 2 failed: %s %s", resp2.status_code, resp2.text
                )
                return False
        except Exception as exc:
            logger.error("HDFS write error: %s", exc)
            return False

    def _write_to_local(self, filename: str, content: bytes, subdir: str = "sensor-readings"):
        """Write content to local fallback storage."""
        dest_dir = self.local_fallback_path / subdir
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_file = dest_dir / filename
        with open(dest_file, 'wb') as f:
            f.write(content)
        self._bytes_written_local += len(content)
        logger.info(
            "[LOCAL FALLBACK] Wrote %d bytes to %s (HDFS was unavailable)",
            len(content), dest_file
        )

    def write_batch(self, messages: List[dict]) -> dict:
        """
        Write a batch of sensor messages.
        Attempts HDFS first; falls back to local storage explicitly.
        Returns a status dict.
        """
        if not messages:
            return {"status": "skipped", "reason": "empty batch"}

        now = datetime.now(timezone.utc)
        date_str = now.strftime("%Y%m%d")
        ts_str = now.strftime("%H%M%S")
        filename = f"sensors_{date_str}_{ts_str}_{len(messages)}msgs.jsonl"

        # Serialize as JSON Lines
        content = b"\n".join(
            json.dumps(m, default=str).encode('utf-8') for m in messages
        ) + b"\n"

        result = {
            "batch_size": len(messages),
            "filename": filename,
            "timestamp": now.isoformat(),
            "storage_backend": None,
            "success": False,
            "bytes_written": len(content),
        }

        # Try HDFS first
        if self._hdfs_available and REQUESTS_AVAILABLE:
            hdfs_dir = f"{self.HDFS_PATHS['raw_sensors']}/dt={date_str}"
            hdfs_path = f"{hdfs_dir}/{filename}"

            for attempt in range(1, self.max_retries + 1):
                self._hdfs_mkdir(hdfs_dir)
                if self._hdfs_write_file(hdfs_path, content):
                    result["storage_backend"] = "hdfs"
                    result["hdfs_path"] = hdfs_path
                    result["success"] = True
                    self._batches_written += 1
                    logger.info(
                        "[HDFS] Wrote batch of %d messages to %s",
                        len(messages), hdfs_path
                    )
                    return result
                else:
                    logger.warning(
                        "HDFS write attempt %d/%d failed. Retrying...", attempt, self.max_retries
                    )
                    time.sleep(self.retry_delay)

            # HDFS failed after retries — switch to fallback
            logger.warning(
                "HDFS write failed after %d attempts. Switching to LOCAL FALLBACK.",
                self.max_retries
            )
            self._hdfs_available = False

        # Local fallback (explicit, not silent)
        logger.warning(
            "[LOCAL FALLBACK ACTIVE] HDFS unavailable. Writing to local storage. "
            "This data will need to be migrated to HDFS when connectivity is restored."
        )
        self._write_to_local(filename, content)
        result["storage_backend"] = "local_fallback"
        result["local_path"] = str(self.local_fallback_path / "sensor-readings" / filename)
        result["success"] = True
        result["warning"] = "Stored locally — HDFS unavailable"
        self._batches_written += 1
        return result

    def write_model_to_hdfs(self, local_model_path: str, model_name: str) -> bool:
        """Upload a trained model file to HDFS."""
        if not self._hdfs_available:
            logger.warning("HDFS unavailable; model not uploaded to HDFS.")
            return False
        try:
            with open(local_model_path, 'rb') as f:
                content = f.read()
            hdfs_path = f"{self.HDFS_PATHS['models']}/{model_name}"
            self._hdfs_mkdir(self.HDFS_PATHS['models'])
            success = self._hdfs_write_file(hdfs_path, content)
            if success:
                logger.info("Model uploaded to HDFS: %s", hdfs_path)
            return success
        except Exception as exc:
            logger.error("Error uploading model to HDFS: %s", exc)
            return False

    def initialize_hdfs_directories(self) -> bool:
        """Create all required HDFS directories."""
        if not self._hdfs_available:
            logger.warning("HDFS not available; cannot create directories.")
            return False
        success = True
        for name, path in self.HDFS_PATHS.items():
            if not self._hdfs_mkdir(path):
                logger.error("Failed to create HDFS directory: %s", path)
                success = False
            else:
                logger.info("HDFS directory OK: %s", path)
        return success

    def status(self) -> dict:
        """Return current writer status."""
        self._check_hdfs_connectivity()
        return {
            "hdfs_available": self._hdfs_available,
            "namenode_url": self.namenode_url,
            "local_fallback_path": str(self.local_fallback_path),
            "batches_written": self._batches_written,
            "bytes_written_hdfs": self._bytes_written_hdfs,
            "bytes_written_local": self._bytes_written_local,
            "active_backend": "hdfs" if self._hdfs_available else "local_fallback",
        }
