# NASA APOD ETL Pipeline with Airflow (Astronomer)

This project demonstrates a complete ETL (Extract–Transform–Load) pipeline built with **Apache Airflow** running on **Astronomer Runtime** using `astro dev`.  
The pipeline fetches NASA’s *Astronomy Picture of the Day (APOD)* API, processes the data, and stores it in a **PostgreSQL** database.

---

## Project Overview

### Workflow Summary
The pipeline performs the following steps:

1. **Extract**  
   Uses `HttpOperator` to call the NASA APOD REST API and retrieve JSON metadata.

2. **Transform**  
   Uses Python tasks (`@task`) to clean and normalize the API response.

3. **Load**  
   Uses `PostgresHook` or SQL operators to:
   - Create the target table (`apod_data`)
   - Insert the transformed APOD record into PostgreSQL

The DAG runs on a defined schedule (e.g., daily) and stores each day’s APOD entry.

---

## Architecture

The environment is provided by **Astronomer**:

- Airflow components:
  - Webserver
  - Scheduler
  - Triggerer
- Default PostgreSQL (metadata + used for the ETL target table)
- User DAGs mounted from `./dags/`

---

## Setup Instructions

### Astro CLI installation

```bash
brew install astro
astro version
# Example output:
# Astro CLI Version: 1.36.0
```

### Create new Astronomer/Airflow project

```bash
mkdir astro_project
cd astro_project
astro dev init
```

### Project Configuration

- Copy: `etl.py` into the `astro_project/dags/` folder.
- In `requirements.txt` file insert the lines:
```text
apache-airflow-providers-http
apache-airflow-providers-postgres
```

#### Project Structure

```
.
├── dags/
│   └── etl.py        # Main ETL DAG
├── requirements.txt  # Additional Airflow providers
```

---

### Running the Project

Start Airflow locally:

```bash
astro dev start
```

Open Airflow UI (default):

```
http://localhost:8080
```

---

## Required Airflow Connections

### DATA – API Access Procedure

To access the NASA APOD API:

1. Go to: **https://api.nasa.gov**
2. Create an account (if you do not have one)
3. Generate an API Key:
   - Enter your info (example:  
     *Name:* John Smith  
     *Email:* john.smith@gmail.com)

4. You will receive an API key by email, for example:

```
Zc5stujuDjYXXXXXXXXXXXXXXXXXXlIhdb8TKBhf
```

5. You can now access APOD:

```
https://api.nasa.gov/planetary/apod?api_key=Zc5stujuDjYXXXXXXXXXXXXXXXXXXlIhdb8TKBhf
```

### 1. NASA API Connection

**Conn Id:** `nasa_api`  
**Conn Type:** `HTTP`  
**Host:** `https://api.nasa.gov`  
**Extra:**

```json
{ "api_key": "Zc5stujuDjYXXXXXXXXXXXXXXXXXXlIhdb8TKBhf" }
```

---

### 2. PostgreSQL Connection

#### PostgreSQL Access Details

- **Conn Id:** `my_postgres_connection`
- **Conn Type:** `Postgres`
- **Host:** `localhost`
- **Database:** `postgres`
- **Login:** `postgres`
- **Password:** `postgres`
- **Port:** `5432`

---

In Airflow UI: http://localhost:8080

Trigger the DAG:

1. Find DAG: **`nasa_apod_postgres`**
2. Turn it on
3. Click **Trigger DAG**

---

## TESTS - Validating Data in PostgreSQL

```bash
# Using docker:
docker ps --filter "name=postgres"
# Example output (NAMES):
# astro-project_ace069-postgres-1

docker exec -it astro-project_ace069-postgres-1 psql -U postgres -d postgres
```

```sql
SELECT * FROM apod_data;
\q
```

## The END

```bash
astro dev stop
```
