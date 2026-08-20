# Simulation of Temperature Sensor (IoT) Data Collection and Visualization in Grafana

NOTE: Using Kafka, MySQL, and Prometheus, where data flows through Kafka into the database – not in parallel (unlike the example 01-IoT-MySQL-Kafka-Promet-Grafana).


## Project Goal
Simulate a full data flow pipeline:

```text
[Producer (Python - sensor simulation)]
      └──> Kafka (topic: temperature)
               └──> Consumer (Python)
                         └──> MySQL (temperature history)
                                 └──> Exporter (Flask /metrics) - reads from DB
                                         └──> Prometheus (scrapes /metrics)
                                                 └──> Grafana (dashboard)
```


## Technologies and Components
- `Docker Compose`- To orchestrate all services
- `Kafka + Zookeeper` - Message queuing
- `MySQL` - Storing historical temperature data
- `Prometheus` - Metrics collection
- `Grafana` - Data visualization
- `Python` - Sensor simulation, Kafka consumer, and Prometheus exporter

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
# Example: 02-iot-mysql-kafka-promet-grafana-mysql-1
```

Connect to the `sensors` database:

```bash
docker exec -it 02-iot-kafka-db-promet-grafana-mysql-1 mysql -uroot -proot sensors
```

Sample MySQL queries:

```sql
SHOW TABLES;
SELECT * FROM readings ORDER BY timestamp DESC LIMIT 5;
```

### Full Data Flow Test

1. Check that Kafka is receiving data
```bash
# List Kafka topics
docker exec -it 02-iot-kafka-db-promet-grafana-kafka-1 /opt/bitnami/kafka/bin/kafka-topics.sh \
  --list \
  --bootstrap-server localhost:9092
# Should return: temperature

# Listen to the temperature topic
docker exec -it 02-iot-kafka-db-promet-grafana-kafka-1 \
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

2. Verify that Prometheus is collecting metrics

Open your browser and visit:
http://localhost:9090/targets

The `STATE` should show `UP`.


3. Create a Grafana dashboard
- Open: http://localhost:3000
  - Login: admin / Password: admin (you will be prompted to change it)
- Add a data source:
  - Choose Prometheus
  - Set Connection to: http://prometheus:9090
  - Click Save & Test
- Create a dashboard:
  - Go to Dashboards → Create Dashboard
  - Or: Dashboards > New (top-right) > New Dashboard
  - Click Add visualization
  - Select data source: prometheus
  - In the Metric Browser, type or select: current_temperature
    - Then click Use query
- You can add more queries:
  - Click Add query, select Metric browser, and choose another metric (e.g. up)
  - Click Use query
- In Panel options (right side), name the panel (e.g., Temperature)


### If needed: restart and wipe volumes
```bash
docker-compose down -v
docker-compose up --build
```
