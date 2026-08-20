# Kafka → Elasticsearch → Kibana and DataDog

Real-time payment processing pipeline using Kafka, Kafka Connect, Elasticsearch, Kibana abd DataDog.

```
producer.py → Kafka (payments) → Kafka Connect → Elasticsearch → Kibana
```

---

## Project Structure

```
.
├── docker-compose.yml   # Kafka + Kafka Connect + Elasticsearch + Kibana
├── producer.py          # sends random payment events every 2 seconds
├── connector.json       # Kafka Connect → Elasticsearch sink config
└── README.md
```

---

## Architecture

```
producer.py (host: localhost:9093)
    │
    ▼
Kafka broker
    ├── internal Docker network: kafka:9092  ← used by Kafka Connect
    └── external host: localhost:9093        ← used by producer.py
    │
    ▼
Kafka Connect (localhost:8083)
    │  ElasticsearchSinkConnector (auto-transfers data)
    ▼
Elasticsearch (localhost:9200)
    │
    ▼
Kibana dashboard (localhost:5601)
```

---

## Ports

| Service | Port | Used by |
|---|---|---|
| Kafka (internal) | `9092` | Kafka Connect, CLI commands |
| Kafka (external) | `9093` | producer.py from host |
| Kafka Connect | `8083` | connector REST API |
| Elasticsearch | `9200` | REST API, data inspection |
| Kibana | `5601` | browser dashboard |

---

## Getting Started

### 1. Start all services

```bash
docker-compose up -d
```

Wait ~2-3 minutes on first start — Kafka Connect downloads the Elasticsearch plugin automatically.

### 2. Verify services are running

```bash
# Kafka
docker exec -it kafka kafka-topics --bootstrap-server localhost:9092 --list

# Elasticsearch
curl http://localhost:9200

# Kafka Connect
curl http://localhost:8083/connectors
```

### 3. Create payments topic

```bash
docker exec -it kafka kafka-topics \
  --bootstrap-server localhost:9092 \
  --create \
  --topic payments \
  --partitions 3 \
  --replication-factor 1
```

### 4. Register the connector

```bash
curl -X POST http://localhost:8083/connectors \
  -H "Content-Type: application/json" \
  -d @connector.json
```

Check connector status — both connector and task must show `RUNNING`:

```bash
curl http://localhost:8083/connectors/payments-elasticsearch-sink/status
```

Expected output:
```json
{
  "connector": {"state": "RUNNING"},
  "tasks": [{"id": 0, "state": "RUNNING"}]
}
```

### 5. Set up Python environment

```bash
python -m venv venv
source venv/bin/activate
pip install confluent-kafka
```

### 6. Run the producer

```bash
python producer.py
```

Example output:
```
🚀 Producer started — sending payments every 2 seconds.

✅ Sent → partition 1 offset 0 | alice paid 249.99 PLN for shoes
✅ Sent → partition 0 offset 0 | bob paid 89.50 PLN for jacket
```

### 7. Open Kibana

Go to **http://localhost:5601** 
- `Discover` → `Create data view`:
  - `name`: payments
  - `index pattern`: payments
  - `Timestamp field`: timestamp
  - `Save data view to Kibana`

---

## Verify Data in Elasticsearch

```bash
# number of documents
curl http://localhost:9200/payments/_count

# preview documents
curl http://localhost:9200/payments/_search?pretty
```

---


## Useful Commands

```bash
# follow Kafka Connect logs
docker logs kafka-connect -f

# list all topics
docker exec -it kafka kafka-topics --bootstrap-server localhost:9092 --list

# restart connector
curl -X POST http://localhost:8083/connectors/payments-elasticsearch-sink/restart

# delete connector
curl -X DELETE http://localhost:8083/connectors/payments-elasticsearch-sink

# stop everything (keep data)
docker-compose down

# stop everything and delete volumes
docker-compose down -v
```
