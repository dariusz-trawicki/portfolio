# Kafka — Hands-On Project

A minimal Kafka producer/consumer example using Python and `confluent-kafka`.  
The project simulates a **payment processing pipeline** — a producer sends payment events to a Kafka topic, and a consumer reads and displays them in real time.

---

## Project Structure

```
.
├── docker-compose.yml   # Kafka broker (KRaft mode, no Zookeeper)
├── producer.py          # Sends a payment event to the payments topic
├── tracker.py           # Consumes and displays payment events
└── README.md
```

## Getting Started

### 1. Start Kafka

```bash
docker-compose up -d
```

### 2. Set up Python environment

```bash
python -m venv venv
source venv/bin/activate
pip install confluent-kafka
```

---

## Running the Project

### Terminal 1 — Producer

Sends a single payment event as a JSON message to the `payments` topic.

```bash
python producer.py
```

Example output:
```
✅ Delivered {"payment_id": "94ab1a01-064e-4590-88a2-aab4ba9f4a84", "user": "marek", "amount": 249.99, "currency": "PLN", "method": "credit_card", "timestamp": "2026-02-26T09:52:20.102594+00:00"}
✅ Delivered to payments : partition 0 : at offset 2
```

### Terminal 2 — Consumer (tracker)

Listens to the `payments` topic and prints incoming payment events.  
⚠️ Blocks the terminal — stop with `Ctrl+C`.

```bash
python tracker.py
```

Example output:
```
🟢 Consumer is running and subscribed to payments topic
💳 Payment: 249.99 PLN via credit_card from marek at 2026-02-26T09:52:20.102594+00:00
```

### Data flow

```
producer.py
    └── JSON payment event
            └── Kafka Broker (localhost:9092)
                    └── Topic: payments
                            └── Consumer group: payment-tracker
                                    └── tracker.py → print to console
```

---

## Kafka CLI

### List all topics

```bash
docker exec -it kafka kafka-topics --bootstrap-server localhost:9092 --list
```

Example output:
```
__consumer_offsets
payments
```

---

### Describe a topic

```bash
docker exec -it kafka kafka-topics --bootstrap-server localhost:9092 --describe --topic payments
```

Example output:
```
Topic: payments   PartitionCount: 1   ReplicationFactor: 1
  Topic: payments   Partition: 0   Leader: 1   Replicas: 1   Isr: 1
```

| Field | Description |
|---|---|
| `PartitionCount` | number of partitions in the topic |
| `ReplicationFactor` | number of data copies (1 for local dev) |
| `Partition: 0` | partition number |
| `Leader: 1` | ID of the broker handling writes |
| `Replicas: 1` | brokers storing copies of the data |
| `Isr` | **In-Sync Replicas** — replicas in sync with the leader |

`Isr == Replicas` → healthy ✅  
`Isr < Replicas` → a replica is lagging ⚠️

---

### View all events in a topic

Reads and prints all messages from the `payments` topic from the beginning.  
⚠️ Blocks the terminal — stop with `Ctrl+C`.

```bash
docker exec -it kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic payments \
  --from-beginning
```

Example output:
```
{"payment_id": "43fbed67-...", "user": "marek", "amount": 249.99, "currency": "PLN", "method": "credit_card", "timestamp": "2026-02-26T09:37:06.212221"}
{"payment_id": "b3ab5057-...", "user": "marek", "amount": 249.99, "currency": "PLN", "method": "credit_card", "timestamp": "2026-02-26T09:38:57.842551+00:00"}
```

> Kafka retains messages after they are consumed — unlike `RabbitMQ`, messages are not deleted on read. `--from-beginning` replays the entire topic log.
