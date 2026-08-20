"""
Compares the challenger's metrics (from the freshly trained run) against
the current champion (if one exists) and decides whether to flip the
`champion` alias in the MLflow Model Registry. If there is no champion yet
(first run ever), the challenger automatically becomes champion.
"""
from __future__ import annotations
import logging

import mlflow
from mlflow.exceptions import MlflowException
from mlflow.tracking import MlflowClient

from .config import (
    ANOMALY_MODEL_NAME, CHALLENGER_ALIAS, CHAMPION_ALIAS,
    CLASSIFIER_MODEL_NAME, MLFLOW_TRACKING_URI, PROMOTION_MIN_IMPROVEMENT,
)

log = logging.getLogger(__name__)


def _metric_for_version(client: MlflowClient, model_name: str, version: str, metric_key: str):
    mv = client.get_model_version(model_name, version)
    run = client.get_run(mv.run_id)
    return run.data.metrics.get(metric_key)


def _promote_if_better(client: MlflowClient, model_name: str, metric_key: str,
                        higher_is_better: bool = True) -> dict:
    challenger_version = client.get_model_version_by_alias(model_name, CHALLENGER_ALIAS).version
    challenger_metric = _metric_for_version(client, model_name, challenger_version, metric_key)

    try:
        champion_version = client.get_model_version_by_alias(model_name, CHAMPION_ALIAS).version
        champion_metric = _metric_for_version(client, model_name, champion_version, metric_key)
    except MlflowException:
        champion_version, champion_metric = None, None

    promote = champion_metric is None
    if not promote and challenger_metric is not None and champion_metric is not None:
        delta = challenger_metric - champion_metric
        if not higher_is_better:
            delta = -delta
        promote = delta > PROMOTION_MIN_IMPROVEMENT

    if promote:
        client.set_registered_model_alias(model_name, CHAMPION_ALIAS, challenger_version)
        log.info("Promoting %s version %s to champion (metric %s=%s, previous champion=%s)",
                  model_name, challenger_version, metric_key, challenger_metric, champion_metric)
    else:
        log.info("Keeping the current champion for %s (challenger %s=%s <= champion=%s)",
                  model_name, metric_key, challenger_metric, champion_metric)

    return {
        "model_name": model_name,
        "promoted": promote,
        "challenger_version": challenger_version,
        "challenger_metric": challenger_metric,
        "champion_version": champion_version,
        "champion_metric": champion_metric,
    }


def validate_and_promote() -> dict:
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    client = MlflowClient()

    anomaly_result = _promote_if_better(client, ANOMALY_MODEL_NAME, "anomaly_f1")
    classifier_result = _promote_if_better(
        client, CLASSIFIER_MODEL_NAME, "classifier_balanced_accuracy"
    )
    return {"anomaly_model": anomaly_result, "classifier_model": classifier_result}
