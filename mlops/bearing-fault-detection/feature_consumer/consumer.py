"""
Consumes raw signals from the `vibration-raw` topic, computes 16 features
(feature_extraction.extract_features - the exact same module used by the
Airflow training tasks, so feature logic is a SINGLE source of truth between
streaming and batch), then:

1. Writes the feature vector + simulation label to the `features` table in
   the `feature_store` database (Postgres) - our simplified feature store.
2. Republishes the feature vector to the `vibration-features` topic, so
   serving-api can run inference in real time without hitting Postgres.
"""
from __future__ import annotations
import json
import logging
import os
import sys
import time

import numpy as np
import psycopg2
from psycopg2.extras import execute_values
from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import NoBrokersAvailable

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "shared"))
from feature_extraction import extract_features, FEATURE_NAMES  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [feature_consumer] %(message)s")
log = logging.getLogger(__name__)

KAFKA_BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
IN_TOPIC = os.environ.get("VIBRATION_TOPIC", "vibration-raw")
OUT_TOPIC = os.environ.get("FEATURES_TOPIC", "vibration-features")
PG_DSN = os.environ.get(
    "FEATURE_STORE_DSN",
    "dbname=feature_store user=postgres password=postgres host=postgres port=5432",
)


def connect_with_retry(connect_fn, name: str, retries: int = 30, delay_s: float = 2.0):
    for attempt in range(retries):
        try:
            return connect_fn()
        except Exception as exc:  # noqa: BLE001
            log.info("%s not available yet (%s), retrying (%d/%d)...", name, exc, attempt + 1, retries)
            time.sleep(delay_s)
    raise RuntimeError(f"Could not connect to {name}")


def insert_features(conn, sensor_id: str, shaft_rpm: float, fault_type: str, feats: dict) -> None:
    cols = ["sensor_id", "shaft_rpm", "fault_type"] + FEATURE_NAMES
    values = [(sensor_id, shaft_rpm, fault_type) + tuple(feats[f] for f in FEATURE_NAMES)]
    query = f"INSERT INTO features ({', '.join(cols)}) VALUES %s"
    with conn.cursor() as cur:
        execute_values(cur, query, values)
    conn.commit()


def main() -> None:
    consumer = connect_with_retry(
        lambda: KafkaConsumer(
            IN_TOPIC,
            bootstrap_servers=KAFKA_BOOTSTRAP,
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
            key_deserializer=lambda k: k.decode("utf-8") if k else None,
            auto_offset_reset="latest",
            enable_auto_commit=True,
            group_id="feature-extraction-group",
        ),
        "Kafka (consumer)",
    )
    producer = connect_with_retry(
        lambda: KafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            key_serializer=lambda k: k.encode("utf-8") if k else None,
        ),
        "Kafka (producer)",
    )
    conn = connect_with_retry(lambda: psycopg2.connect(PG_DSN), "Postgres (feature_store)")

    log.info("Listening on topic '%s', writing to feature_store, publishing to '%s'",
              IN_TOPIC, OUT_TOPIC)

    processed = 0
    for message in consumer:
        payload = message.value
        signal = np.asarray(payload["signal"], dtype=float)
        fs = int(payload["sampling_rate_hz"])
        shaft_rpm = float(payload["shaft_rpm"])
        sensor_id = payload["sensor_id"]
        fault_label = payload.get("sim_fault_label")

        feats = extract_features(signal, fs, shaft_rpm)

        try:
            insert_features(conn, sensor_id, shaft_rpm, fault_label, feats)
        except Exception:
            log.exception("Error writing to feature_store, retrying the database connection")
            conn = connect_with_retry(lambda: psycopg2.connect(PG_DSN), "Postgres (feature_store)")
            insert_features(conn, sensor_id, shaft_rpm, fault_label, feats)

        out_message = {
            "sensor_id": sensor_id,
            "timestamp": payload["timestamp"],
            "shaft_rpm": shaft_rpm,
            "sim_fault_label": fault_label,
            "features": feats,
        }
        producer.send(OUT_TOPIC, key=sensor_id, value=out_message)

        processed += 1
        if processed % 20 == 0:
            producer.flush()
            log.info("Processed %d signals", processed)


if __name__ == "__main__":
    main()
