from __future__ import annotations

import sys
from pathlib import Path

from src.exception import CustomException
from src.logger import logging
from src.components.data_ingestion import DataIngestion, DataIngestionConfig
from src.components.data_transformation import DataTransformation
from src.components.model_trainer import ModelTrainer


def run_training_pipeline() -> float:
    """
    Orchestrates the full flow:
      1) Data ingestion      -> saves raw/train/test into artifacts/
      2) Data transformation  -> prepares training/test arrays
      3) Model training       -> trains model, returns a metric (R^2)

    Returns:
        float: R^2 score on the test set.
    """
    try:
        logging.info("=== Training pipeline start ===")

        # 1) Data ingestion
        ingestion_cfg = DataIngestionConfig()
        ingestion = DataIngestion(ingestion_cfg)
        train_csv, test_csv = ingestion.initiate_data_ingestion()
        logging.info("Data ingestion finished. Train CSV: %s | Test CSV: %s", train_csv, test_csv)

        # 2) Data transformation
        transformer = DataTransformation()
        train_arr, test_arr, _ = transformer.initiate_data_transformation(train_csv, test_csv)
        logging.info(
            "Data transformation finished. Train shape: %s | Test shape: %s",
            getattr(train_arr, "shape", None),
            getattr(test_arr, "shape", None),
        )

        # 3) Model training
        trainer = ModelTrainer()
        r2_square: float = trainer.initiate_model_trainer(train_arr, test_arr)
        logging.info("Model training finished. R^2 = %.6f", r2_square)

        logging.info("=== Training pipeline end ===")
        return r2_square

    except Exception as e:
        # Wrap any error in CustomException to keep stack trace and context
        logging.exception("Training pipeline failed.")
        raise CustomException(e, sys) from e


if __name__ == "__main__":
    # Run from the PROJECT ROOT directory:
    #   python -m src.pipeline.train_pipeline
    r2 = run_training_pipeline()
    print(f"r2_square = {r2}")
