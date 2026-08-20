# click_producer.py
from confluent_kafka import Producer
import json, time, random

producer = Producer({'bootstrap.servers': 'localhost:9092'})
users = ["Anna", "John", "Tom", "Sophie"]

while True:
    data = {
        "user": random.choice(users),
        "action": "click"
    }
    producer.produce("user_clicks", value=json.dumps(data))
    producer.flush()
    print(f"Sent: {data}")
    time.sleep(1)
