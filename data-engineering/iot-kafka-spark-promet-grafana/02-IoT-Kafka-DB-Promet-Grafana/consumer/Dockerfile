FROM python:3.10
WORKDIR /app
COPY consumer.py .
RUN pip install kafka-python mysql-connector-python
CMD ["python", "consumer.py"]
