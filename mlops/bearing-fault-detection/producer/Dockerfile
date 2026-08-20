FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    numpy==1.26.4 \
    scipy==1.13.0 \
    kafka-python==2.0.2

COPY shared/ /app/shared/
COPY producer/producer.py /app/producer.py

ENV PYTHONUNBUFFERED=1
CMD ["python", "producer.py"]
