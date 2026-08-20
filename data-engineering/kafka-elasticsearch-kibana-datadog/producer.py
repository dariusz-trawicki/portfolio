import json
import uuid
import time
import random
from datetime import datetime, timezone

from confluent_kafka import Producer

producer_config = {
    "bootstrap.servers": "localhost:9093"
}

producer = Producer(producer_config)

USERS    = ["alice", "bob", "charlie", "diana", "eve"]
ITEMS    = ["shoes", "jacket", "bag", "hat", "trousers", "scarf"]
METHODS  = ["credit_card", "blik", "paypal", "transfer"]

def delivery_report(err, msg):
    if err:
        print(f"❌ Delivery failed: {err}")
    else:
        data = json.loads(msg.value().decode("utf-8"))
        print(f"✅ Sent → partition {msg.partition()} offset {msg.offset()} | {data['user']} paid {data['amount']} PLN for {data['item']}")

def generate_payment():
    return {
        "payment_id": str(uuid.uuid4()),
        "user":       random.choice(USERS),
        "item":       random.choice(ITEMS),
        "amount":     round(random.uniform(19.99, 499.99), 2),
        "currency":   "PLN",
        "method":     random.choice(METHODS),
        "timestamp":  datetime.now(timezone.utc).isoformat()
    }

print("🚀 Producer started — sending payments every 2 seconds. Ctrl+C to stop.\n")

try:
    while True:
        payment = generate_payment()
        value   = json.dumps(payment).encode("utf-8")

        producer.produce(
            topic="payments",
            key=payment["user"],        # same user → same partition
            value=value,
            callback=delivery_report
        )
        producer.poll(0)
        time.sleep(2)

except KeyboardInterrupt:
    print("\n🔴 Stopping producer")

finally:
    producer.flush()
