# Simulating Temperature Sensor (IoT) Data Collection and Visualization in Grafana

NOTE: 
This project uses `Kafka`, `MySQL`, `Prometheus`, and `Apache Spark`.
`Apache Spark` connects to `Kafka` using `Structured Streaming` and processes incoming temperature data. The results are written to:
- `MySQL` — e.g., 1-minute average temperatures,
- `Prometheus` — via a custom exporter that reads from /metrics (e.g., current average temperature).

## Project Goal
Simulate a data flow like this:

```text
[Producer (Python – simulated sensor)]
        └──> Kafka (topic: temperature)
                  └──> Spark Structured Streaming
                            ├──> MySQL (temperature history + 1-min averages)
                            └──> /tmp/metrics.txt (latest average temperature)
                                      └──> Exporter (Flask /metrics) – reads from file
                                              └──> Prometheus (scrapes /metrics)
                                                      └──> Grafana (dashboard)
```


## Technologies and Components
- `Docker Compose` – platform to orchestrate and run all services
- `Kafka` + `Zookeeper` – message queuing and data streaming
- `Apache Spark` – real-time data processing via Structured Streaming
- `MySQL` – storage of historical temperature data
- `Prometheus` – metric collection
- `Grafana` – data visualization
- `Python` – sensor simulation, data processing, and Prometheus exporter

## RUN
```bash
docker-compose up --build
```

### TESTING

#### MySQL
Check the name of the MySQL container:

```bash
# In a new terminal:
docker ps --filter "name=mysql"
# Example result: 03-iot-kafka-db-spark-promet-grafana-mysql-1

# To connect to the 'sensors' database:
docker exec -it 03-iot-kafka-db-spark-promet-grafana-mysql-1 \
  mysql -uroot -proot sensors

```

Inside MySQL, you can run for example:

```sql
SHOW TABLES;
SELECT * FROM avg_temperatures ORDER BY timestamp DESC LIMIT 5;
```

### Verify Kafka
1. Check that Kafka is receiving data:

```bash
# Check if the topic exists:
docker exec -it 03-iot-kafka-db-spark-promet-grafana-kafka-1 \
  /opt/bitnami/kafka/bin/kafka-topics.sh \
  --list \
  --bootstrap-server localhost:9092
# Expected output: temperature

# Check incoming messages on the topic:
docker exec -it 03-iot-kafka-db-spark-promet-grafana-kafka-1 \
  /opt/bitnami/kafka/bin/kafka-console-consumer.sh \
  --bootstrap-server kafka:9092 \
  --topic temperature \
  --from-beginning
```

Expected output:

```json
{"temperature": 28.99, "timestamp": 1750167754}
{"temperature": 21.17, "timestamp": 1750167759}
{"temperature": 18.62, "timestamp": 1750167764}
{"temperature": 25.8, "timestamp": 1750167769}
```

2. Ensure `Prometheus` is collecting metrics

Open in your browser:
http://localhost:9090/targets

Make sure that the `STATE` is shown as `UP`.

3. Create a dashboard in Grafana
- Go to: http://localhost:3000
- Login: `admin` / Password: `admin` (or another if changed – it will prompt to set a new one)
- Add a `Data Source`:
  - Choose: Prometheus
  - Set connection: http://prometheus:9090
  - Click: Save & Test
- Create a new dashboard:
  - Navigate to: `Dashboards → Create dashboard`
    - Or: `Dashboards → New (top-right) → New dashboard`
  - Click Add visualization
  - Set data source to: `prometheus`
  - In Metric Browser, select or type: `current_temperature` (defined in `exporter.py`) → then click `Use query`
- To add more metrics to the chart:
  - Click `Add query`, open the `Metric browser`
  - Select another metric, e.g. `average_temperature` → then click `Use query`
- Under `Panel Options` (right side), name the panel (e.g. `Temperature`)

#### IF NEEDED: Reset and rebuild
Stop all containers and remove old volumes:

```bash
docker-compose down -v    # also deletes VOLUMEs
# Restart the full stack:
docker-compose up --build
```