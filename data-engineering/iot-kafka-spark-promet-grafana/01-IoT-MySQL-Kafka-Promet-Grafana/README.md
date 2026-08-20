# Simulating Temperature Sensor Data Collection and Visualization in Grafana Using Kafka, MySQL, and Prometheus

Note: Kafka is not strictly required in this example. The data is sent directly to MySQL, then exported to Prometheus and visualized in Grafana. However, Kafka might make sense for future scalability or database-related issues (e.g., buffering or decoupling producers and consumers).

## Project Goal

Simulate a data flow like this:

```text
[Simulated Sensors in Python]
      └─→ Kafka (temperature)
      └─→ MySQL (historical data)
            └─→ exporter (reads from DB)
                  └─→ Prometheus (latest readings)
                                  └─→ Grafana (dashboard)
```

## Technologies and Components
- `Docker Compose`- To orchestrate all services
- `Kafka + Zookeeper` - Message queuing
- `MySQL` - Storing historical temperature data
- `Prometheus` - Metrics collection
- `Grafana` - Data visualization
- `Python` - Simulated sensor & Prometheus exporter

## RUN

```bash
docker-compose up --build
```

### TESTING

#### MySQL
Find the container name (in a new terminal window):

```bash
docker ps --filter "name=mysql"
# Example: 01-iot-mysql-kafka-promet-grafana-mysql-1

# Connect to the MySQL container and database sensors:
docker exec -it 01-iot-mysql-kafka-promet-grafana-mysql-1 mysql -uroot -proot sensors
```

Sample MySQL queries:

```sql
SHOW TABLES;
SELECT * FROM readings ORDER BY timestamp DESC LIMIT 5;
```

#### Data Flow Test
1. Verify Kafka is receiving messages:
```bash
# Check existing topics
docker exec -it 01-iot-mysql-kafka-promet-grafana-kafka-1 /opt/bitnami/kafka/bin/kafka-topics.sh \
  --list \
  --bootstrap-server localhost:9092
# Expected output: temperature

# Listen to messages:
docker exec -it 01-iot-mysql-kafka-promet-grafana-kafka-1 \
  /opt/bitnami/kafka/bin/kafka-console-consumer.sh \
  --bootstrap-server kafka:9092 \
  --topic temperature \
  --from-beginning
# Expected messages:
# {"temperature": 28.99, "timestamp": 1750167754}
# {"temperature": 21.17, "timestamp": 1750167759}
# {"temperature": 18.62, "timestamp": 1750167764}
# {"temperature": 25.8, "timestamp": 1750167769}
```

2. Check `Prometheus` targets
Open: http://localhost:9090/targets
Ensure the `STATE` column shows `UP`.


3. Create a Dashboard in Grafana:
- Go to http://localhost:3000
  - Login: admin / Password: admin (you may be prompted to change it)
- Add a data source:
  - Choose Prometheus
  - Set URL to: http://prometheus:9090
  - Click Save & Test
- Create a new dashboard:
  - Go to Dashboards → New → New Dashboard
  - Click Add visualization
  - Set Data source to Prometheus
  - Panel title: Temperature
  - In the query editor, select the metric current_temperature (as defined in exporter.py)
  - Add additional queries like up if desired


#### If Needed: Cleanup and Rebuild

```bash
docker-compose down -v
docker-compose up --build
```