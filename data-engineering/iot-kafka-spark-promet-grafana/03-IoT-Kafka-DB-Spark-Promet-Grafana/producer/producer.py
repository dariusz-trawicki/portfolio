import time, random, json
from kafka import KafkaProducer
from kafka.errors import NoBrokersAvailable, KafkaError

# Retry Kafka connection
while True:
    try:
        producer = KafkaProducer(
            bootstrap_servers='kafka:9092',
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        break
    except NoBrokersAvailable:
        print("Kafka not ready, retrying in 5s...")
        time.sleep(5)

# Main loop
while True:
    temp = round(random.uniform(18, 30), 2)
    timestamp = int(time.time())

    data = {'temperature': temp, 'timestamp': timestamp}
    producer.send('temperature', data)

    print(f"Sent: {data}")
    time.sleep(5)
