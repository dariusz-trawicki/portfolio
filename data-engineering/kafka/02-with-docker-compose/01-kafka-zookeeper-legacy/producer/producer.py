from confluent_kafka import Producer
import json, time, random

producer = Producer({'bootstrap.servers': 'kafka:9092'})

users = ["Anna", "John", "Tom", "Sophie"]

while True:
    data = {"user": random.choice(users), "action": "click"}
    producer.produce("user_clicks", value=json.dumps(data))
    print("Sent:", data)
    producer.flush()
    time.sleep(1)
