FROM bitnami/spark:latest

# Copy the Spark application
COPY spark-streaming.py /opt/spark-apps/spark-streaming.py

# Install MySQL connector for Python
RUN pip install mysql-connector-python

# Set the entrypoint to Spark's startup script (with Kafka support)
ENTRYPOINT ["/opt/bitnami/scripts/spark/entrypoint.sh"]

# Run the Spark application using spark-submit with Kafka package
CMD ["spark-submit", "--master", "local[*]", "--packages", "org.apache.spark:spark-sql-kafka-0-10_2.13:4.0.0", "/opt/spark-apps/spark-streaming.py"]
