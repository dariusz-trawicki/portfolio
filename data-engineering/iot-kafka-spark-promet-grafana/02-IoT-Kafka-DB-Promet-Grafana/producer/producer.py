import time, random, json
from kafka import KafkaProducer
# import mysql.connector
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

# Retry MySQL connection
# while True:
#     try:
#         db = mysql.connector.connect(
#             user='root',
#             password='root',
#             host='mysql',
#             database='sensors'
#         )
#         break
#     except mysql.connector.Error:
#         print("MySQL not ready, retrying in 5s...")
#         time.sleep(5)

# cursor = db.cursor()

# Main loop
while True:
    temp = round(random.uniform(18, 30), 2)
    timestamp = int(time.time())

    data = {'temperature': temp, 'timestamp': timestamp}
    producer.send('temperature', data)

    # cursor.execute("INSERT INTO readings (timestamp, temperature) VALUES (%s, %s)", (timestamp, temp))
    # db.commit()

    print(f"Sent: {data}")
    time.sleep(5)
