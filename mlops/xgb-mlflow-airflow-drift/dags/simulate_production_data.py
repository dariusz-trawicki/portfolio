"""Simulates labelled production traffic. drift=0 -> unchanged market, drift>0 -> market shift."""
from __future__ import annotations

import time
from datetime import datetime

from airflow.decorators import dag, task
from airflow.models.param import Param
from airflow.operators.python import get_current_context


@dag(
    dag_id="simulate_production_data",
    description="Writes production/latest.csv with optional drift",
    schedule=None,
    start_date=datetime(2026, 1, 1),
    catchup=False,
    params={
        "drift": Param(0.8, type="number", minimum=0.0, maximum=1.0, description="0 = no drift, 1 = strong drift"),
        "n_rows": Param(2000, type="integer", minimum=200, maximum=20000),
    },
    tags=["mlops", "demo"],
)
def simulate_production_data():
    @task
    def generate() -> dict:
        from mlops_demo.config import PRODUCTION_PATH
        from mlops_demo.data import make_dataset

        p = get_current_context()["params"]
        PRODUCTION_PATH.parent.mkdir(parents=True, exist_ok=True)
        df = make_dataset(p["n_rows"], seed=int(time.time()) % 1_000_000, drift=p["drift"])
        df.to_csv(PRODUCTION_PATH, index=False)
        print(f"Wrote {len(df)} rows (drift={p['drift']}) to {PRODUCTION_PATH}")
        return {"rows": len(df), "drift": p["drift"]}

    generate()


simulate_production_data()
