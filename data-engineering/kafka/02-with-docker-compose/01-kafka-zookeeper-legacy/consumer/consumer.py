from confluent_kafka import Consumer
import json
from collections import Counter

counter = Counter()

c = Consumer({
    'bootstrap.servers': 'kafka:9092',
    'group.id': 'click_analysis',
    'auto.offset.reset': 'earliest'
})

c.subscribe(['user_clicks'])
print("Listening for clicks...\n")

while True:
    msg = c.poll(1.0)
    if msg is None:
        continue
    if msg.error():
        print("Error:", msg.error())
    else:
        data = json.loads(msg.value().decode("utf-8"))
        counter[data["user"]] += 1
        print(f"{data['user']} clicked – total: {counter[data['user']]}")
