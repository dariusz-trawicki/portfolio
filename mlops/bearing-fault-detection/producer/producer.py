"""
Simulates an on-line sensor on a train wheel: every `EMIT_INTERVAL_S`
seconds it generates a 1-second vibration waveform and publishes it to the
Kafka topic `vibration-raw`.

In a real system this process would live on an edge gateway. For this demo
we also simulate a shift in operating conditions over time (RPM change) -
the same phenomenon modeled by the original `drift_monitor.py`.
"""
from __future__ import annotations
import json
import logging
import os
import sys
import time
import uuid

import numpy as np
from kafka import KafkaProducer
from kafka.errors import NoBrokersAvailable

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "shared"))
from data_generator import generate_signal, random_shaft_rpm  # noqa: E402
from bearing_physics import FAULT_TYPES  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [producer] %(message)s")
log = logging.getLogger(__name__)

KAFKA_BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
TOPIC = os.environ.get("VIBRATION_TOPIC", "vibration-raw")
SENSOR_IDS = os.environ.get("SENSOR_IDS", "wheel-01,wheel-02,wheel-03").split(",")
EMIT_INTERVAL_S = float(os.environ.get("EMIT_INTERVAL_S", "2"))
FS = int(os.environ.get("SAMPLING_RATE_HZ", "20000"))
DURATION_S = float(os.environ.get("SIGNAL_DURATION_S", "1.0"))
# Probability weights for each fault type (including the normal state)
FAULT_WEIGHTS = {"normal": 0.70, "outer": 0.12, "inner": 0.10, "ball": 0.06, "cage": 0.02}
# Force a simulated shift in operating conditions (RPM drift) after this
# many emissions, 0 = disabled
DRIFT_AFTER_N = int(os.environ.get("DRIFT_AFTER_N_EMISSIONS", "0"))


def connect_producer(bootstrap: str, retries: int = 30, delay_s: float = 2.0) -> KafkaProducer:
    for attempt in range(retries):
        try:
            return KafkaProducer(
                bootstrap_servers=bootstrap,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                key_serializer=lambda k: k.encode("utf-8") if k else None,
            )
        except NoBrokersAvailable:
            log.info("Kafka not available yet, retrying (%d/%d)...", attempt + 1, retries)
            time.sleep(delay_s)
    raise RuntimeError("Could not connect to Kafka after multiple attempts")


def main() -> None:
    rng = np.random.default_rng()
    producer = connect_producer(KAFKA_BOOTSTRAP)
    log.info("Connected to Kafka (%s), publishing to topic '%s'", KAFKA_BOOTSTRAP, TOPIC)

    fault_types = list(FAULT_WEIGHTS.keys())
    weights = np.array(list(FAULT_WEIGHTS.values()))
    weights = weights / weights.sum()

    base_rpm = 1780.0
    emission = 0
    while True:
        emission += 1
        if DRIFT_AFTER_N and emission == DRIFT_AFTER_N:
            log.warning("Simulating a shift in operating conditions: base RPM 1780 -> 1650")
            base_rpm = 1650.0

        sensor_id = str(rng.choice(SENSOR_IDS))
        fault_type = str(rng.choice(fault_types, p=weights))
        shaft_rpm = random_shaft_rpm(rng, base_rpm=base_rpm)

        signal = generate_signal(fault_type, shaft_rpm, duration_s=DURATION_S, fs=FS)

        message = {
            "message_id": str(uuid.uuid4()),
            "sensor_id": sensor_id,
            "timestamp": time.time(),
            "sampling_rate_hz": FS,
            "shaft_rpm": shaft_rpm,
            "signal": signal.tolist(),
            # Label available ONLY in simulation - used to build the
            # training dataset and to evaluate drift. In a real system this
            # would have to come from an inspection / human-in-the-loop.
            "sim_fault_label": fault_type,
        }
        producer.send(TOPIC, key=sensor_id, value=message)
        if emission % 20 == 0:
            producer.flush()
            log.info("Sent %d messages (last: sensor=%s, fault=%s, rpm=%.1f)",
                      emission, sensor_id, fault_type, shaft_rpm)

        time.sleep(EMIT_INTERVAL_S)


if __name__ == "__main__":
    main()
