from kafka import KafkaConsumer
import json
import mysql.connector
import time

# Połączenie z MySQL z retry
while True:
    try:
        db = mysql.connector.connect(
            host='mysql',
            user='root',
            password='root',
            database='sensors'
        )
        break
    except mysql.connector.Error as err:
        print("MySQL not ready, retrying in 5s...")
        time.sleep(5)

cursor = db.cursor()

# Tworzenie tabeli jeśli nie istnieje
cursor.execute("""
CREATE TABLE IF NOT EXISTS readings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    timestamp BIGINT,
    temperature FLOAT
)
""")
db.commit()

# Kafka Consumer
consumer = KafkaConsumer(
    'temperature',
    bootstrap_servers='kafka:9092',
    value_deserializer=lambda m: json.loads(m.decode('utf-8')),
    auto_offset_reset='earliest',
    enable_auto_commit=True,
    group_id='temperature-group'
)

print("Listening for messages from Kafka...")

for message in consumer:
    data = message.value
    temperature = data.get('temperature')
    timestamp = data.get('timestamp')

    print(f"Received: temperature={temperature}, timestamp={timestamp}")
    cursor.execute(
        "INSERT INTO readings (timestamp, temperature) VALUES (%s, %s)",
        (timestamp, temperature)
    )
    db.commit()
