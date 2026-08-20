import json
import uuid
from datetime import datetime, timezone

from confluent_kafka import Producer

producer_config = {
    "bootstrap.servers": "localhost:9092"
}

producer = Producer(producer_config)

def delivery_report(err, msg):
    if err:
        print(f"❌ Delivery failed: {err}")
    else:
        print(f"✅ Delivered {msg.value().decode('utf-8')}")
        print(f"✅ Delivered to {msg.topic()} : partition {msg.partition()} : at offset {msg.offset()}")

payment = {
    "payment_id": str(uuid.uuid4()),
    "user": "marek",
    "amount": 249.99,
    "currency": "PLN",
    "method": "credit_card",
    "timestamp": datetime.now(timezone.utc).isoformat()
}

value = json.dumps(payment).encode("utf-8")

producer.produce(
    topic="payments",
    value=value,
    callback=delivery_report
)

producer.flush()
