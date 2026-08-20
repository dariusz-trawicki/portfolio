import json

from confluent_kafka import Consumer

consumer_config = {
    "bootstrap.servers": "localhost:9092",
    "group.id": "payment-tracker",
    "auto.offset.reset": "earliest"
}

consumer = Consumer(consumer_config)

consumer.subscribe(["payments"])

print("🟢 Consumer is running and subscribed to payments topic")

try:
    while True:
        msg = consumer.poll(1.0)
        if msg is None:
            continue
        if msg.error():
            print("❌ Error:", msg.error())
            continue

        value = msg.value().decode("utf-8")
        data = json.loads(value)

        print(f"💳 Payment: {data['amount']} {data['currency']} via {data['method']} from {data['user']} at {data['timestamp']}")

except KeyboardInterrupt:
    print("\n🔴 Stopping consumer")

finally:
    consumer.close()
