FROM python:slim

# Set environment variables to prevent Python from writing .pyc files & Ensure Python output is not buffered
# This reduces the docker image size and ensures that logs are output in real-time, 
# which is important for debugging and monitoring in production environments.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Set the working directory in the container
WORKDIR /app

RUN apt-get update && apt-get install -y curl --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Copy only the requirements file first to leverage Docker's caching mechanism
COPY requirements.txt requirements.txt

# Install required packages but do not store cache files 
# to reduce image size and speed up subsequent builds
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code into the container
COPY . .

# Expose the port that Flask will run on (5000 by default)
EXPOSE 5000

# Command to run the app when the container starts
CMD ["python", "app.py"]
