"""
Reads from the real feature store (the
`features` table in the `feature_store` Postgres database), fed by
`feature_consumer` consuming the Kafka stream.

This is the ONLY source of training data for the whole pipeline - all
Airflow tasks (training, validation, drift monitoring) use the same CSV
snapshot written to a shared volume, so there's no divergence like in the
original demo version.
"""
from __future__ import annotations
import os

import pandas as pd
import psycopg2

from .config import FEATURE_STORE_DSN, FEATURE_COLUMNS, DATASET_SNAPSHOT_PATH


def load_feature_dataset(since_hours: int | None = None, require_labels: bool = True) -> pd.DataFrame:
    """Reads features from the feature store. `since_hours=None` = full history.
    """
    where_clause = ""
    if since_hours is not None:
        where_clause = f"WHERE event_ts >= now() - interval '{since_hours} hours'"
    if require_labels:
        where_clause += (" AND" if where_clause else "WHERE") + " fault_type IS NOT NULL"

    query = f"""
        SELECT event_ts, sensor_id, shaft_rpm, fault_type, {", ".join(FEATURE_COLUMNS)}
        FROM features
        {where_clause}
        ORDER BY event_ts ASC
    """
    with psycopg2.connect(FEATURE_STORE_DSN) as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            colnames = [desc[0] for desc in cur.description]
            rows = cur.fetchall()
    return pd.DataFrame(rows, columns=colnames)


def build_dataset_snapshot(since_hours: int | None = None) -> str:
    """Writes a dataset snapshot to CSV on the shared volume and returns the
    path. The snapshot is also logged as an MLflow artifact (lineage) by the
    task that calls this function."""
    df = load_feature_dataset(since_hours=since_hours, require_labels=True)
    if df.empty:
        raise ValueError(
            "The feature store is empty (no rows with a fault_type label). "
            "Make sure the producer + feature_consumer are running and have "
            "had enough time to collect data before the first DAG run."
        )
    os.makedirs(os.path.dirname(DATASET_SNAPSHOT_PATH), exist_ok=True)
    df.to_csv(DATASET_SNAPSHOT_PATH, index=False)
    return DATASET_SNAPSHOT_PATH
