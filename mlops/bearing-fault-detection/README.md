# Bearing Fault Detection — MLOps Demo

## The problem

Train wheel bearings fail over time due to wear on the outer race, inner
race, rolling elements (balls), or the cage that holds them in place. Left
undetected, a failing bearing can escalate from a minor vibration anomaly to
a safety-critical mechanical failure. The earlier a fault is detected — and
the more precisely its type is identified — the cheaper and safer the fix.

Vibration signals from a sensor mounted near the bearing carry the
signature of these faults: each fault type resonates at a distinct
characteristic frequency (determined by the bearing's geometry and its
rotational speed). The goal of this system is to continuously monitor that
vibration signal, detect when a bearing is behaving abnormally, and
classify *which* type of fault is occurring — all in an architecture that
can run unattended, retrain itself as conditions change, and serve
predictions in real time.

## The solution

This demo implements a full, containerized MLOps pipeline: a
simulated sensor streams vibration data through `Kafka`, a `feature-extraction` service turns raw signals into a structured `feature store`, `Airflow`
periodically checks for `data drift` and retrains models when needed, `MLflow`
tracks every experiment and manages which model version is "live," and a
`FastAPI` serving layer exposes real-time predictions — both on demand and as
a continuous stream.

## Tech stack

### Infrastructure / orchestration
| Tool | Version / image | Role |
|---|---|---|
| Docker Compose | v2 | wires together all 10 services, startup dependencies, healthchecks |

### Streaming
| Tool | Version | Role |
|---|---|---|
| Apache Kafka | `apache/kafka:latest` | message bus: `vibration-raw`, `vibration-features`, `predictions` |
| kafka-python | 2.0.2 | Kafka client used by `producer`, `feature-consumer`, `feature-store-writer`, `serving-api` |

### Database
| Tool | Version | Role |
|---|---|---|
| PostgreSQL | 16 (`postgres:16-alpine`) | single instance, 3 databases: `feature_store`, `mlflow`, `airflow` |


### MLOps: tracking + orchestration
| Tool | Version | Role |
|---|---|---|
| MLflow | 2.14.1 | experiment tracking + Model Registry (`champion`/`challenger` aliases) |
| Apache Airflow | 2.9.3 (Python 3.11) | orchestrates the `ct_bearing_pipeline` Continuous Training DAG, `LocalExecutor` |


### Machine learning / data processing
| Tool | Version | Role |
|---|---|---|
| scikit-learn | 1.5.0 | `IsolationForest` (anomaly detection) + `RandomForestClassifier` (fault type) |
| pandas | 2.2.2 | DataFrames for the training dataset and model inputs |
| NumPy | 1.26.4 | signal operations, synthetic data generator |
| SciPy | 1.13.0 | `scipy.stats` (kurtosis, skewness, KS test), `scipy.signal` (Hilbert transform, Welch's method) |
| joblib | 1.4.2 | scikit-learn/MLflow model serialization dependency |

### Serving (API)
| Tool | Version | Role |
|---|---|---|
| FastAPI | 0.111.0 | REST API (`/predict`, `/health`, `/reload-model`) |
| Uvicorn | 0.30.1 | ASGI server running FastAPI |
| requests | 2.32.3 | HTTP call from Airflow to `serving-api` (`notify_serving`) |

### Languages & base images
- **Python 3.11** — common baseline across all custom services (`python:3.11-slim` or `apache/airflow:...-python3.11`)
- **Bash** — database initialization script (`postgres/init-multiple-dbs.sh`)
- **SQL** (Postgres DDL/DML) — `features` / `predictions` table schemas


## Architecture

```
[producer] -- topic "vibration-raw" -->  [feature-consumer]  --topic "vibration-feature"s--> [serving-api]
                                                |                                                |
                                                v                                                v
                                      Postgres: feature_store.features              topic "predictions"
                                                |                                   Postgres: predictions
                                                v
                                      [Airflow DAG: ct_bearing_pipeline]
                                        build_dataset -> check_drift -> (retrain) -> validate_and_promote
                                                |
                                                v
                                      [MLflow: tracking + model registry]
                                                |
                                                +--> serving-api loads models:/<name>@champion
```

| Layer | Component | Responsibility |
|---|---|---|
| Ingest | `kafka` (official `apache/kafka` image, KRaft mode, no ZooKeeper) + `producer` | Simulates an on-line vibration sensor and streams raw signals |
| Feature pipeline | `feature-consumer` | Consumes raw signals, extracts 16 features per sample, writes to the feature store, republishes for real-time serving |
| Feature store | Postgres `feature_store.features` | Single source of truth for both training and monitoring |
| Continuous Training | Airflow (`airflow/dags/ct_bearing_pipeline.py`) | Periodically builds a training snapshot, checks for drift, retrains and validates models |
| Experiment tracking & model registry | MLflow | Tracks every training run; manages `champion`/`challenger` model aliases |
| Serving | `serving-api` (FastAPI) | REST `/predict` endpoint + continuous streaming inference from Kafka |
| Monitoring | `common/drift.py` (KS test + PSI) | Detects when the underlying data distribution has shifted enough to warrant retraining |

## How the detection actually works

1. A wheel bearing spinning at a given `RPM` produces vibration with
   characteristic frequencies for each fault type — **BPFO** (outer race),
   **BPFI** (inner race), **BSF** (ball/rolling element), and **FTF** (cage).
   These are computed from bearing geometry and shaft speed
   (`shared/bearing_physics.py`).
2. The raw time-domain signal is converted into `16 features`
   (`shared/feature_extraction.py`): 8 time-domain statistics (mean, RMS,
   kurtosis, crest factor, etc.), 4 frequency-domain statistics (dominant
   frequency, spectral centroid/energy/entropy), and 4 envelope-spectrum
   amplitudes measured exactly at the BPFO/BPFI/BSF/FTF frequencies. These
   envelope-spectrum features are the strongest signal: a damaged outer race
   produces a sharp amplitude spike precisely at its BPFO frequency.
3. Prediction is a **two-stage cascade**: an `Isolation Forest` (trained only
   on `normal` operating data) first decides whether a sample is `anomalous` at
   all. Only if it is, a `Random Forest classifier` — trained only on labeled
   `fault samples` — determines which of the four fault types it most closely
   matches. This avoids ever asking "what type of fault is this?" about a
   perfectly healthy bearing.
4. Because operating conditions change over time (e.g. different routes,
   loads, or speeds), the feature distributions can `drift`. `Airflow`
   periodically re-evaluates this with a `Kolmogorov-Smirnov test` (PSI as a
   supplementary signal) and retrains the models when the drift is
   significant enough to matter — or on the very first run, when no model
   exists yet at all.

## Requirements

- Docker + Docker Compose v2 (`docker compose version`)
- ~4 GB of free RAM for all containers (Kafka + Postgres + MLflow + Airflow)
- Free host ports: `5432` (Postgres), `29092` (Kafka — host access only;
  internally services connect via `kafka:9092`), `5000` (MLflow), `8080`
  (Airflow UI), `8000` (Serving API)

## Running it

```bash
mv .env.example .env
docker compose up -d --build
```

Startup order is controlled by `depends_on` + healthchecks: Postgres and
Kafka first, then MLflow, then `init-shared-data` (a one-off container that
fixes permissions on the shared data volume), then `airflow-init` (DB
migration + creating the `admin`/`admin` user), and finally the
webserver/scheduler plus producer/consumer/serving.

### Checking that everything is healthy

```bash
docker compose ps
docker compose logs -f producer feature-consumer   # confirm data is flowing
```

- **MLflow UI**: http://localhost:5000
- **Airflow UI**: http://localhost:8080 (login: `admin` / `admin`)
- **Serving API**: http://localhost:8000/health, http://localhost:8000/docs

### First full cycle (no model exists yet)

1. Wait 2–3 minutes for `producer` + `feature-consumer` to populate the
   feature store:
   ```bash
   docker compose exec postgres psql -U postgres -d feature_store -c "select count(*), fault_type from features group by fault_type;"
   ```
2. In the Airflow UI, unpause and manually trigger the `ct_bearing_pipeline`
   DAG (or wait for the schedule — every 15 min).
3. **Bootstrap behavior**: on the very first run, if no champion model
   exists yet, the pipeline forces a training run regardless of whether
   drift was detected — otherwise the system would never train its first
   model in the absence of drift. See `_champions_exist()` in
   `ct_bearing_pipeline.py`.
4. `serving-api` is notified automatically by the `notify_serving` task
   (`POST /reload-model`), so it picks up the new champion without a
   restart.

### Trying a prediction

```bash
curl -X POST http://localhost:8000/predict -H "Content-Type: application/json" -d '{
  "t_mean": 0, "t_std": 1, "t_rms": 1, "t_kurtosis": 3, "t_skewness": 0,
  "t_peak_to_peak": 4, "t_crest_factor": 3, "t_shape_factor": 1.1,
  "f_dominant_freq": 500, "f_spectral_centroid": 1000, "f_spectral_energy": 10, "f_spectral_entropy": 5,
  "env_amp_bpfo": 40, "env_amp_bpfi": 30, "env_amp_bsf": 25, "env_amp_ftf": 45
}'
# Output:
# {"is_anomaly":true,"predicted_fault_type":"inner","confidence":0.5533333333333333}
```

Or watch predictions being written continuously from the live stream:

```bash
docker compose exec postgres psql -U postgres -d feature_store -c "select * from predictions order by event_ts desc limit 10;"
```

### Forcing drift (for testing)

```bash
docker compose stop producer
docker compose run -e DRIFT_AFTER_N_EMISSIONS=50 producer
```

After ~50 emissions the producer shifts the baseline RPM (1780 → 1650),
which — once it reaches the feature store — should be picked up by the KS
test on the next DAG run and trigger a retrain.

## Repo structure

```
.
├── docker-compose.yml
├── .env
├── postgres/init-multiple-dbs.sh  # creates: mlflow, airflow, feature_store databases
├── shared/                        # shared logic (used by producer + feature-consumer)
│   ├── bearing_physics.py         # BPFO/BPFI/BSF/FTF formulas
│   ├── data_generator.py          # signal generator (5 classes: normal/outer/inner/ball/cage)
│   └── feature_extraction.py      # 16 features: time/frequency/envelope-spectrum
├── producer/                      # Kafka producer (simulated on-line sensor)
├── feature_consumer/              # Kafka consumer -> feature extraction -> feature store
├── serving/                       # FastAPI: anomaly->classification cascade + streaming inference
├── mlflow/Dockerfile              # MLflow server (backend: Postgres, artifacts: volume)
└── airflow/
    ├── Dockerfile                 # Airflow + ML/MLflow dependencies
    └── dags/
        ├── .airflowignore         # excludes common/ from DAG file scanning
        ├── ct_bearing_pipeline.py # main Continuous Training DAG
        └── common/                # config.py, dataset.py, drift.py, train.py, promote.py
```

## Simplifications

- The `feature store` is a single `Postgres` table, not a dedicated engine
  (Feast) — sufficient to demonstrate a single `source of truth` for
  online/offline features.
- Airflow runs with `LocalExecutor` on a single host — scaling out would
  require `CeleryExecutor`/`KubernetesExecutor`.
- No `TLS/auth` between services (Kafka is PLAINTEXT, MLflow has no auth,
  passwords are plaintext in `.env`) — must be added before any real production
  deployment.
- Fault labels are available instantly via simulation
  (`sim_fault_label`) — in a real system this is where a human-in-the-loop
  process / delayed label from a service inspection would go.
- Data is 100% synthetic.

## Cleaning up

```bash
docker compose down -v
```
