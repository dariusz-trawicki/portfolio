FROM python:3.10
WORKDIR /app
COPY exporter.py .
RUN pip install flask mysql-connector-python
CMD ["python", "exporter.py"]
