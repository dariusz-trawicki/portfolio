# Simulating Temperature Sensor (IoT) Data Collection and Visualization in Grafana

These three projects (in different configurations) use `Kafka`, `MySQL`, `Prometheus`, `Grafana`, and `Apache Spark` to process incoming temperature data.

## Technologies and Components
- `Docker Compose` – platform to orchestrate and run all services
- `Kafka` + `Zookeeper` – message queuing and data streaming
- `Apache Spark` – real-time data processing via Structured Streaming
- `MySQL` – storage of historical temperature data
- `Prometheus` – metric collection
- `Grafana` – data visualization
- `Python` – sensor simulation, data processing, and Prometheus exporter