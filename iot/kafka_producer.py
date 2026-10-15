"""
Kafka Producer for IoT Sensor Readings
Sends sensor data to the 'sensor-readings' Kafka topic.
"""
import json
import time
import logging
import os
from typing import Optional
from datetime import datetime

try:
    from kafka import KafkaProducer
    from kafka.errors import KafkaError, NoBrokersAvailable
    KAFKA_AVAILABLE = True
except ImportError:
    KAFKA_AVAILABLE = False
    logging.warning("kafka-python not installed. Producer will run in dry-run mode.")

from sensor_simulator import SensorSimulator, SensorReading

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)


class CropYieldKafkaProducer:
    """Kafka producer that sends sensor readings to a Kafka topic."""

    def __init__(
        self,
        bootstrap_servers: str = "localhost:9092",
        topic: str = "sensor-readings",
        max_retries: int = 2,
        retry_delay: float = 1.0,
        dry_run: bool = False,
    ):
        self.bootstrap_servers = bootstrap_servers
        self.topic = topic
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._producer: Optional[object] = None
        self._messages_sent = 0
        self._dry_run = dry_run or (not KAFKA_AVAILABLE)
        if not self._dry_run:
            self._connect()
        else:
            logger.info("Starting in Local Development Mode (streaming directly to SQLite).")

    def _connect(self):
        """Attempt to connect to Kafka with retries."""
        if self._dry_run:
            logger.warning("[DRY RUN] kafka-python unavailable. Messages will be logged only.")
            return

        for attempt in range(1, self.max_retries + 1):
            try:
                self._producer = KafkaProducer(
                    bootstrap_servers=self.bootstrap_servers,
                    value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                    key_serializer=lambda k: k.encode('utf-8') if k else None,
                    acks=1,
                    retries=3,
                    request_timeout_ms=5000,
                    api_version_auto_timeout_ms=5000,
                )
                logger.info(
                    "Kafka producer connected to %s (topic: %s)",
                    self.bootstrap_servers, self.topic
                )
                return
            except NoBrokersAvailable:
                logger.warning(
                    "Kafka broker not reachable at %s (attempt %d/%d).",
                    self.bootstrap_servers, attempt, self.max_retries
                )
                time.sleep(self.retry_delay)
            except Exception as exc:
                logger.warning("Kafka connection error: %s (attempt %d/%d)", exc, attempt, self.max_retries)
                time.sleep(self.retry_delay)

        logger.info(
            "Kafka broker not active. Running in Local Dev Mode: writing telemetry directly to SQLite & Fallback Storage."
        )
        self._dry_run = True

    def _on_send_success(self, record_metadata):
        logger.debug(
            "Message delivered to %s [partition %d] offset %d",
            record_metadata.topic, record_metadata.partition, record_metadata.offset
        )

    def _on_send_error(self, exc):
        logger.error("Failed to deliver message: %s", exc)

    def send_reading(self, reading: SensorReading) -> bool:
        """Send a single sensor reading to Kafka (or SQLite in local dev mode)."""
        payload = reading.to_dict()
        key = reading.field_id

        if self._dry_run:
            logger.info("[STREAMING] field=%s crop=%s moisture=%.1f%% temp=%.1f°C rain=%.1fmm (Local Mode)",
                        reading.field_id, reading.crop_type, reading.soil_moisture, reading.temperature, reading.rainfall)
            # Store in SQLite so dashboard receives live updates immediately
            try:
                import sys
                from pathlib import Path
                root = Path(__file__).parent.parent
                if str(root) not in sys.path:
                    sys.path.insert(0, str(root))
                from backend.services.database import DatabaseService
                db = DatabaseService()
                db.store_sensor_reading(payload)
            except Exception as e:
                logger.debug("Local SQLite save error: %s", e)
            self._messages_sent += 1
            return True

        try:
            future = self._producer.send(
                self.topic,
                key=key,
                value=payload
            )
            future.add_callback(self._on_send_success)
            future.add_errback(self._on_send_error)
            self._messages_sent += 1
            return True
        except KafkaError as exc:
            logger.error("KafkaError sending reading: %s", exc)
            return False
        except Exception as exc:
            logger.error("Unexpected error sending reading: %s", exc)
            return False

    def send_batch(self, readings: list) -> int:
        """Send a list of readings. Returns number successfully sent."""
        sent = 0
        for reading in readings:
            if self.send_reading(reading):
                sent += 1
        if not self._dry_run and self._producer:
            self._producer.flush()
        logger.info("Batch complete: %d/%d messages sent.", sent, len(readings))
        return sent

    def health_check(self) -> dict:
        """Check Kafka connectivity."""
        if self._dry_run:
            return {
                "status": "dry_run",
                "message": "Kafka unavailable, running in dry-run mode",
                "messages_sent": self._messages_sent,
            }
        try:
            topics = self._producer.partitions_for(self.topic)
            return {
                "status": "ok",
                "broker": self.bootstrap_servers,
                "topic": self.topic,
                "partitions": list(topics) if topics else [],
                "messages_sent": self._messages_sent,
            }
        except Exception as exc:
            return {
                "status": "error",
                "message": str(exc),
                "messages_sent": self._messages_sent,
            }

    def close(self):
        if self._producer and not self._dry_run:
            self._producer.flush(timeout=10)
            self._producer.close()
            logger.info("Kafka producer closed. Total messages sent: %d", self._messages_sent)


def main():
    import argparse
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

    parser = argparse.ArgumentParser(description="Kafka Sensor Producer")
    parser.add_argument("--broker", default=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"))
    parser.add_argument("--topic", default=os.getenv("KAFKA_TOPIC_SENSOR", "sensor-readings"))
    parser.add_argument("--fields", type=int, default=int(os.getenv("SIMULATOR_FIELDS", "5")))
    parser.add_argument("--interval", type=float, default=float(os.getenv("SIMULATOR_INTERVAL", "5")))
    parser.add_argument("--seed", type=int, default=int(os.getenv("SIMULATOR_SEED", "42")))
    parser.add_argument("--mode", choices=["stream", "demo"], default="stream")
    parser.add_argument("--count", type=int, default=50)
    parser.add_argument("--local", action="store_true", help="Fast local mode: writes directly to SQLite without waiting for Kafka broker")
    args = parser.parse_args()

    sim = SensorSimulator(num_fields=args.fields, seed=args.seed)
    producer = CropYieldKafkaProducer(
        bootstrap_servers=args.broker, 
        topic=args.topic,
        dry_run=args.local,
    )

    logger.info("Health check: %s", producer.health_check())

    try:
        if args.mode == "demo":
            readings = sim.generate_demo_batch(args.count)
            sent = producer.send_batch(readings)
            logger.info("Demo complete: sent %d readings.", sent)
        else:
            logger.info("Streaming sensor data to Kafka (Ctrl+C to stop)...")
            for reading in sim.stream_readings(interval=args.interval):
                producer.send_reading(reading)
    except KeyboardInterrupt:
        logger.info("Producer stopped by user.")
    finally:
        producer.close()


if __name__ == "__main__":
    main()
