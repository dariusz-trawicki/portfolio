# Stock Price ETL Pipeline Using Yahoo Finance API (financial market data of AAPL (Apple Inc.)), Spark, MinIO and Postgres

Designed and implemented a **data pipeline** to fetch, process, and store **stock market data** using modern, cloud-native technologies.

Example based on Udemy course: Master Apache Airflow from A to Z. Hands-on videos on Airflow with AWS, Kubernetes, Docker and more (author: Marc Lamberti).

## DATA - Yahoo Finance API (financial market data in JSON format of AAPL (Apple Inc.)

Open in the browser:
http://query1.finance.yahoo.com/v8/finance/chart/aapl?metrics=hight?&interval=1d&range=1y

## **Workflow Overview:**

1. **Yahoo Finance API Integration**  
   - Implemented an **availability check** (`is_api_available`) to ensure API responsiveness.  
   - Built a module to **fetch real-time stock prices** (`fetch_stock_prices`) for selected tickers.

2. **Data Storage and Preprocessing**  
   - Stored raw data in **MinIO** (**S3-compatible object storage**) using the `store_prices` function.  
   - Applied **formatting and cleansing** through `format_prices`.

3. **Data Transformation with Apache Spark**  
   - Utilized **Apache Spark** for **scalable and distributed processing** of stock data.  
   - Generated cleaned and normalized datasets (`get_formatted_csv`).

4. **Structured Output and Loading to Data Warehouse**  
   - Saved transformed data as **CSV files** in **MinIO**.  
   - Loaded the final dataset into a **PostgreSQL data warehouse** (`load_to_dw`) for **analytical querying and reporting**.

### **Key Technologies:**
- **APIs**: Yahoo Finance  
- **Storage**: **MinIO**, **PostgreSQL**  
- **Processing**: **Apache Spark**  
- **ETL Orchestration**: Custom **Python** modules/functions

### Data pipeline

```text
Yahoo Finance API
      └─→ is_api_available
            └─→ fetch_stock_prices
                   └─→ store_prices
                          └─→ MinIO (data storage)
                          └─→ format_prices
                                 └─→ Spark (data transformation framework)
                                 └─→ get_formatted_csv
                                        └─→ MinIO (data storage like S3 AWS)
                                        └─→ load_to_dw
                                              └─→ Postgres (data storage)
```

## RUN

### ASTRO CLI - installation

Info: `https://www.astronomer.io/docs/astro/cli/overview`

```bash
# installation
brew install astro
```

Run:

```bash
# Start Airflow (uses Docker) – requires port 8080 to be available.
cd airflow
astro dev start                      # 60 sec. for running (default)
# OR (if needed):
astro dev start --wait 180s          # 180 sec for running
# *** output ***
# Project started
# ➤ Airflow UI: http://localhost:8080
# ➤ Postgres Database: postgresql://localhost:5432/postgres
# ➤ The default Airflow UI credentials are: 
#   - user: admin
#   - pass: admin
# ➤ The default Postgres DB credentials are: postgres:postgres
```

### NOTE: Using the CLI interface (helpfull for e.g. CD/CI)

```bash
docker ps
# *** output (example) ***
# CONTAINER ID   IMAGE                                 COMMAND                  CREATED         STATUS         PORTS                                                                                                                                  NAMES
# ...
# 5c9cf8df4a55   airflow_30f904/airflow:latest         "tini -- /entrypoint…"   3 minutes ago    Up 2 minutes   127.0.0.1:8080->8080/tcp                                                                                                               airflow_30f904-webserver-1
# ...

docker exec -it airflow_30f904-webserver-1 bash
# *** output ***
# astro@5c9cf8df4a55:/usr/local/airflow$
# RUN:
# astro@5c9cf8df4a55:/usr/local/airflow$ airflow -h
# astro@5c9cf8df4a55:/usr/local/airflow$ airflow cheat-sheet    # wait > 30 sec.
# astro@5c9cf8df4a55:/usr/local/airflow$ airflow db check
# astro@5c9cf8df4a55:/usr/local/airflow$ airflow dags list

# or use shorter astro command:
astro dev bash # Execing into the scheduler container
# *** output ***
# astro@13537f1c5dd1:/usr/local/airflow$
# Run:
# astro@13537f1c5dd1:/usr/local/airflow$ airflow -h
# etc.
```

### Build Docker images

```bash
cd spark/master
docker build -t airflow/spark-master .

cd ../worker
docker build -t airflow/spark-worker .

cd ../notebooks/stock_transform
docker build -t airflow/stock-app .

cd ../../..
astro dev restart                      # 60 sec. for running (default)
# OR (if needed):
astro dev restart --wait 180s          # 180 sec for running
# *** output ***
# ✔ Project image has been updated
# ✔ Project started
# ➤ Airflow UI: http://localhost:8080
# ➤ Postgres Database: postgresql://localhost:5432/postgres
# ➤ The default Airflow UI credentials are: admin:admin
# ➤ The default Postgres DB credentials are: postgres:postgres
```

### Airflow: create `connections`

#### Create `Yahoo api connection` 

In UI: `Admin > Conncetion > Add a new record`, set:
- Connection ID: `stock_api`
- Connection Type: `HTTP`
- Host: `https://query1.finance.yahoo.com/`
- Login:    <empty>
- Password: <empty>
- Extra > put json code:

```json
{
  "endpoint":"/v8/finance/chart/",
  "headers": {
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json"
  }
}
```

#### Create `MinIO connection` 

In UI: `Admin > Conncetion > Add a new record`, set:
- Connection ID: `minio`
- Connection Type: `Amazon Web Service`
- AWS access key: `minio`
- AWS secret access key: `minio123`
- EXTRA > put json code:

```json
{
  "endpoint_url":"http://minio:9000"
}
```

#### Create connection for `Postgres`:

In UI: `Admin > Conncetion > Add a new record`, set:
- Connection ID: `postgres`
- Connection Type: `Postgres`
- Host: `postgres`
- Login: `postgres`
- Password: `postgres`
- port: 5432


## TESTS

### Task: `is_api_available`

Run/test:

```bash
astro dev run tasks test stock_market is_api_available 2025-01-01
# *** output ***
# ...
# [2025-07-08T14:27:12.299+0000] {base.py:84} INFO - Retrieving connection 'stock_api'
# https://query1.finance.yahoo.com//v8/finance/chart/
# [2025-07-08T14:27:12.536+0000] {base.py:339} INFO - Success criteria met. Exiting.
# [2025-07-08T14:27:12.544+0000] {taskinstance.py:341} INFO - ::group::Post task execution logs
# [2025-07-08T14:27:12.545+0000] {taskinstance.py:353} INFO - Marking task as SUCCESS. dag_id=stock_market, task_id=is_api_available, run_id=__***_temporary_run_2025-07-08T14:27:12.220995+00:00__, execution_date=20250101T000000, start_date=, end_date=20250708T142712
```

### Task `get_stock_prices`  - featching stock prices 

In `stock_market.py` set:

```python
    is_api_available() >> get_stock_prices # >> store_prices  >> format_prices >> get_formatted_csv >> load_to_dw
```

Run/test:

```bash
astro dev run dags test stock_market 2025-01-01
# *** output ***
# ...
# [2025-07-08T20:56:20.636+0000] {taskinstance.py:341} INFO - ::group::Post task execution logs
# [2025-07-08T20:56:20.637+0000] {taskinstance.py:353} INFO - Marking task as SUCCESS. dag_id=stock_market, task_id=store_prices, 
# ...
```

### Task `store_prices` (using/in `MinIO`)

In `stock_market.py` set:

```python
    is_api_available() >> get_stock_prices >> store_prices # >> format_prices  >> get_formatted_csv >> load_to_dw
```

Run/test:

```bash
astro dev run dags test stock_market 2025-01-01
# Open: http://localhost:9001/login
# user:minio, 
# pass: minio123
# Open: `Buckets` from left menu.
# Open: http://localhost:9001/browser/stock-market/
# and click NVDA > formatted_prices
```

### Task `format_prices`: formatting prices with `Spark`  

In `stock_market.py` set:

```python
    is_api_available() >> get_stock_prices >> store_prices >> format_prices # >> get_formatted_csv >> load_to_dw
```

Run/test:

```bash
astro dev run dags test stock_market 2025-01-01
# Open: http://localhost:9001/browser/stock-market/
# and click NVDA > formatted_prices
```

### Task `load_to_dw`: load the data into data warehouses with Postgres and Astro SDK - complite pipeline

In `stock_market.py` set:

```python
    is_api_available() >> get_stock_prices >> store_prices >> format_prices >> get_formatted_csv >> load_to_dw
```

Run:

```bash
astro dev run dags test stock_market 2025-01-01

docker ps
# *** output (example) ***
# f4a326e78fa8   postgres:12.6                              "docker-entrypoint.s…"   16 minutes ago   Up 9 minutes               127.0.0.1:5432->5432/tcp                                   airflow_aacfa4-postgres-1
docker exec -it airflow_9593d3-postgres-1 bash
root@f4a326e78fa8:/# psql -U postgres
# postgres=# \dt *.*;
postgres=# SELECT * FROM stock_market;
# *** output ***
# timestamp  |       close        |        high        |        low         |        open        |  volume   |    date    
# ------------+--------------------+--------------------+--------------------+--------------------+-----------+------------
#  1720618200 | 134.91000366210938 | 135.10000610351562 |  132.4199981689453 | 134.02999877929688 | 248978600 | 2024-07-10
#  1720704600 |  127.4000015258789 | 136.14999389648438 |  127.0500030517578 |             135.75 | 374782700 | 2024-07-11
#  1720791000 | 129.24000549316406 |  131.9199981689453 | 127.22000122070312 | 128.25999450683594 | 252680500 | 2024-07-12
postgres=# exit
root@f4a326e78fa8:/# exit
# STOP:
astro dev stop
```
