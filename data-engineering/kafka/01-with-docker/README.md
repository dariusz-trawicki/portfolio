# Using Kafka with Docker (Example)

## Project: User Click Logging System

## Goal:
Build a system where:
- A Producer sends user click data to Kafka (e.g. {"user": "Anna", "action": "click"})
- A Consumer reads the data and displays it
- Bonus: add simple analytics (e.g. number of clicks per user)

## Requirements
- Python 3
- Kafka
- confluent_kafka library (or kafka-python)


## Step 1: Run Kafka
### Option: Docker (recommended)
```bash
docker network create kafka-net

docker run -d --name zookeeper --network kafka-net \
  -e ZOOKEEPER_CLIENT_PORT=2181 \
  -e ZOOKEEPER_TICK_TIME=2000 \
  confluentinc/cp-zookeeper:7.5.0

docker run -d --name kafka --network kafka-net \
  -e KAFKA_BROKER_ID=1 \
  -e KAFKA_ZOOKEEPER_CONNECT=zookeeper:2181 \
  -e KAFKA_ADVERTISED_LISTENERS=PLAINTEXT://localhost:9092 \
  -e KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR=1 \
  -p 9092:9092 \
  confluentinc/cp-kafka:7.5.0
  ```

## Step 2: Install the confluent-kafka Library
The official and most stable Python library for working with Kafka.
In the terminal (on the host machine, not inside Docker):

```bash
pip install confluent-kafka
```

## Use Kafka from local Python code

### In `producer.py` and `consumer.py`, use:

```python
'bootstrap.servers': 'localhost:9092'
```

## Step 3: Create topics (manually)

```bash
docker exec kafka kafka-topics --create \
  --bootstrap-server localhost:9092 \
  --replication-factor 1 --partitions 1 \
  --topic user_clicks

# Output:
# Created topic user_clicks.
```

## Running Python Scripts

1. In the `first` terminal:

```bash
python click_consumer.py
# Output:
# Listening for clicks...
```

2. In the `second` terminal:

```bash
python click_producer.py
# Output:
# Sent: {'user': 'Sophie', 'action': 'click'}
# Sent: {'user': 'John', 'action': 'click'}
# Sent: {'user': 'Tom', 'action': 'click'}
# Sent: {'user': 'Tom', 'action': 'click'}
# Sent: {'user': 'Sophie', 'action': 'click'}
```

3. And in the `first` (consumer) terminal, we get:

```bash
# Sophie clicked – total: 1
# John clicked – total: 1
# Tom clicked – total: 1
# Tom clicked – total: 2
# Sophie clicked – total: 2
```

## Shutdown:

```bash
docker stop kafka zookeeper
# cleaning:
docker rm -f zookeeper 
docker rm -f kafka
docker network rm kafka-net
```
