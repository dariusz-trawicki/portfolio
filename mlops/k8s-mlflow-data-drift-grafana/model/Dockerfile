FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY train.py .

# Create models folder
RUN mkdir -p /models

CMD ["python", "train.py"]
