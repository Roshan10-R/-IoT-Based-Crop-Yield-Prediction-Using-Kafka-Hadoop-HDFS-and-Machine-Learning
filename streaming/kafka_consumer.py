"""
Kafka Consumer for IoT Crop Yield Sensor Readings.
Consumes messages from the sensor-readings topic and forwards them
to HDFS storage and the SQLite metadata database.
"""
import json
import time
import logging
import os
import sys
import signal
import threading
from datetime import datetime, timezone
from typing import Optional, Callable, List
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from kafka import KafkaConsumer
    from kafka.errors import KafkaError, NoBrokersAvailable
    KAFKA_AVAILABLE = True
except ImportError:
    KAFKA_AVAILABLE = False
    logging.warning("kafka-python not installed.")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)


class MessageBuffer:
    """Thread-safe buffer for batching messages before writing to storage."""

    def __init__(self, max_size: int = 50, flush_interval: float = 30.0):
        self.max_size = max_size
        self.flush_interval = flush_interval
        self._buffer: List[dict] = []
        self._lock = threading.Lock()
        self._last_flush = time.time()

    def add(self, message: dict) -> bool:
        """Add message to buffer. Returns True if flush is needed."""
        with self._lock:
            self._buffer.append(message)
            return (
                len(self._buffer) >= self.max_size
                or (time.time() - self._last_flush) >= self.flush_interval
            )

    def drain(self) -> List[dict]:
        """Return and clear current buffer contents."""
        with self._lock:
            messages = list(self._buffer)
            self._buffer.clear()
            self._last_flush = time.time()
            return messages

    def size(self) -> int:
        with self._lock:
            return len(self._buffer)


class CropYieldKafkaConsumer:
    """Kafka consumer with batching, retry logic, and graceful shutdown."""

    def __init__(
        self,
        bootstrap_servers: str = "localhost:9092",
        topic: str = "sensor-readings",
        group_id: str = "crop-yield-consumer-group",
        auto_offset_reset: str = "earliest",
        batch_size: int = 50,
        flush_interval: float = 30.0,
        storage_callback: Optional[Callable[[List[dict]], None]] = None,
        db_callback: Optional[Callable[[dict], None]] = None,
        max_connect_retries: int = 10,
        retry_delay: float = 5.0,
    ):
        self.bootstrap_servers = bootstrap_servers
        self.topic = topic
        self.group_id = group_id
        self.auto_offset_reset = auto_offset_reset
        self.storage_callback = storage_callback
        self.db_callback = db_callback
        self.max_connect_retries = max_connect_retries
        self.retry_delay = retry_delay
        self._consumer: Optional[object] = None
        self._running = False
        self._shutdown_event = threading.Event()
        self._buffer = MessageBuffer(max_size=batch_size, flush_interval=flush_interval)
        self._messages_processed = 0
        self._messages_failed = 0
        self._dry_run = not KAFKA_AVAILABLE
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

    def _handle_signal(self, signum, frame):
        logger.info("Shutdown signal received (%s). Stopping consumer...", signum)
        self.stop()

    def _connect(self) -> bool:
        if self._dry_run:
            logger.warning("[DRY RUN] kafka-python unavailable.")
            return False
        for attempt in range(1, self.max_connect_retries + 1):
            try:
                self._consumer = KafkaConsumer(
                    self.topic,
                    bootstrap_servers=self.bootstrap_servers,
                    group_id=self.group_id,
                    auto_offset_reset=self.auto_offset_reset,
                    enable_auto_commit=True,
                    auto_commit_interval_ms=5000,
                    value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                    max_poll_records=100,
                    session_timeout_ms=30000,
                    heartbeat_interval_ms=10000,
                    api_version_auto_timeout_ms=10000,
                )
                logger.info(
                    "Kafka consumer connected to %s, topic: %s, group: %s",
                    self.bootstrap_servers, self.topic, self.group_id
                )
                return True
            except NoBrokersAvailable:
                logger.warning(
                    "Kafka not available (attempt %d/%d). Retrying in %.1fs...",
                    attempt, self.max_connect_retries, self.retry_delay
                )
                time.sleep(self.retry_delay)
            except Exception as exc:
                logger.error("Unexpected Kafka connection error: %s", exc)
                time.sleep(self.retry_delay)
        logger.error("Failed to connect to Kafka after %d attempts.", self.max_connect_retries)
        return False

    def _validate_message(self, msg: dict) -> tuple:
        """Validate message schema. Returns (is_valid, warnings)."""
        required = [
            "sensor_id", "field_id", "timestamp",
            "soil_moisture", "temperature", "rainfall",
            "crop_type", "growth_stage"
        ]
        missing = [f for f in required if f not in msg]
        if missing:
            return False, [f"Missing fields: {missing}"]
        warnings = []
        if not (0 <= msg.get("soil_moisture", -1) <= 100):
            warnings.append("soil_moisture out of range")
        if msg.get("rainfall", -1) < 0:
            warnings.append("negative rainfall")
        return True, warnings

    def _process_message(self, msg: dict):
        """Validate and buffer a single message."""
        valid, warnings = self._validate_message(msg)
        if not valid:
            logger.warning("Invalid message discarded: %s", warnings)
            self._messages_failed += 1
            return

        if warnings and not msg.get("is_anomaly", False):
            logger.warning("Message warnings for %s: %s", msg.get("sensor_id"), warnings)

        # Add processing metadata
        msg["consumed_at"] = datetime.now(timezone.utc).isoformat()
        msg["_quality_warnings"] = warnings

        should_flush = self._buffer.add(msg)

        # Call DB callback immediately for real-time API updates
        if self.db_callback:
            try:
                self.db_callback(msg)
            except Exception as exc:
                logger.error("DB callback error: %s", exc)

        if should_flush:
            self._flush_buffer()

        self._messages_processed += 1

    def _flush_buffer(self):
        """Flush buffered messages to storage."""
        messages = self._buffer.drain()
        if not messages:
            return
        logger.info("Flushing %d messages to storage...", len(messages))
        if self.storage_callback:
            try:
                self.storage_callback(messages)
            except Exception as exc:
                logger.error("Storage flush error: %s", exc)

    def start(self):
        """Start consuming messages."""
        if not self._connect():
            logger.warning("Consumer starting in degraded mode (no Kafka connection).")

        self._running = True
        logger.info("Consumer started. Waiting for messages...")

        flush_timer = time.time()
        try:
            while self._running and not self._shutdown_event.is_set():
                if self._dry_run or self._consumer is None:
                    logger.info("[DRY RUN] No Kafka connection. Sleeping...")
                    time.sleep(10)
                    continue

                try:
                    records = self._consumer.poll(timeout_ms=1000, max_records=100)
                    for tp, messages in records.items():
                        for message in messages:
                            self._process_message(message.value)

                    # Periodic flush based on time
                    if time.time() - flush_timer >= self._buffer.flush_interval:
                        self._flush_buffer()
                        flush_timer = time.time()

                except KafkaError as exc:
                    logger.error("Kafka poll error: %s", exc)
                    time.sleep(2)
                except Exception as exc:
                    logger.error("Unexpected consumer error: %s", exc)
                    time.sleep(2)

        finally:
            self._flush_buffer()  # Final flush on shutdown
            self._cleanup()

    def stop(self):
        logger.info("Stopping consumer...")
        self._running = False
        self._shutdown_event.set()

    def _cleanup(self):
        if self._consumer:
            try:
                self._consumer.close()
                logger.info("Kafka consumer closed.")
            except Exception as exc:
                logger.error("Error closing consumer: %s", exc)
        logger.info(
            "Consumer stopped. Processed: %d, Failed: %d",
            self._messages_processed, self._messages_failed
        )

    def health_check(self) -> dict:
        return {
            "status": "running" if self._running else "stopped",
            "dry_run": self._dry_run,
            "topic": self.topic,
            "group_id": self.group_id,
            "messages_processed": self._messages_processed,
            "messages_failed": self._messages_failed,
            "buffer_size": self._buffer.size(),
        }


if __name__ == "__main__":
    import argparse
    from storage.hdfs_writer import HDFSWriter
    from backend.services.database import DatabaseService

    parser = argparse.ArgumentParser(description="Kafka Consumer")
    parser.add_argument("--broker", default=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"))
    parser.add_argument("--topic", default=os.getenv("KAFKA_TOPIC_SENSOR", "sensor-readings"))
    parser.add_argument("--group", default=os.getenv("KAFKA_CONSUMER_GROUP", "crop-yield-consumer-group"))
    parser.add_argument("--batch-size", type=int, default=int(os.getenv("HDFS_BATCH_SIZE", "50")))
    parser.add_argument("--flush-interval", type=float, default=float(os.getenv("HDFS_FLUSH_INTERVAL", "30")))
    args = parser.parse_args()

    hdfs_writer = HDFSWriter()
    db_service = DatabaseService()
    db_service.init_db()

    consumer = CropYieldKafkaConsumer(
        bootstrap_servers=args.broker,
        topic=args.topic,
        group_id=args.group,
        batch_size=args.batch_size,
        flush_interval=args.flush_interval,
        storage_callback=hdfs_writer.write_batch,
        db_callback=db_service.store_sensor_reading,
    )
    consumer.start()
