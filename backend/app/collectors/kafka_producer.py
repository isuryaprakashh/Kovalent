import json
import logging
from typing import Any
from confluent_kafka import Producer
from app.config import get_settings

logger = logging.getLogger(__name__)

class TelemetryProducer:
    """Produces normalized telemetry signals to Kafka/Redpanda topics."""
    
    def __init__(self):
        self.settings = get_settings()
        conf = {
            'bootstrap.servers': self.settings.kafka_bootstrap_servers,
            'client.id': 'kovalent-collector'
        }
        try:
            self.producer = Producer(conf)
            self.enabled = True
            logger.info("Kafka producer connected to %s", self.settings.kafka_bootstrap_servers)
        except Exception as e:
            logger.warning("Kafka producer failed to initialize (streaming disabled): %s", e)
            self.enabled = False

    def produce(self, topic: str, key: str, value: dict[str, Any]):
        if not self.enabled:
            return
            
        try:
            self.producer.produce(
                topic,
                key=key.encode('utf-8'),
                value=json.dumps(value, default=str).encode('utf-8'),
                callback=self._delivery_report
            )
            # Poll to trigger callbacks
            self.producer.poll(0)
        except Exception as e:
            logger.error("Failed to produce to Kafka: %s", e)

    def flush(self, timeout=1.0):
        if self.enabled:
            self.producer.flush(timeout)

    def _delivery_report(self, err, msg):
        if err is not None:
            logger.error("Message delivery failed: %s", err)
        else:
            logger.debug("Message delivered to %s [%d]", msg.topic(), msg.partition())
