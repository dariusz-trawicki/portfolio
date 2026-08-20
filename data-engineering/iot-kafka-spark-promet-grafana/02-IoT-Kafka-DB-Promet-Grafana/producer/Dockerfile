FROM python:3.10
WORKDIR /app
COPY producer.py .
RUN pip install kafka-python mysql-connector-python
CMD ["python", "-u", "producer.py"]
