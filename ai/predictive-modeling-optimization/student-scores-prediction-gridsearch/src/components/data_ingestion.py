import sys
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from sklearn.model_selection import train_test_split

from src.exception import CustomException
from src.logger import logging
from src.components.data_transformation import DataTransformation
from src.components.model_trainer import ModelTrainer


# Artifacts directory and input CSV (configurable)
ARTIFACTS_DIR = Path("artifacts")
INPUT_CSV = Path("data") / "stud.csv"

@dataclass
class DataIngestionConfig:
    train_data_path: Path = ARTIFACTS_DIR / "train.csv"
    test_data_path: Path = ARTIFACTS_DIR / "test.csv"
    raw_data_path: Path = ARTIFACTS_DIR / "data.csv"

class DataIngestion:
    def __init__(self, config: DataIngestionConfig | None = None):
        self.ingestion_config = config or DataIngestionConfig()

    def initiate_data_ingestion(self):
        logging.info("Data ingestion started.")
        try:
            # 1) Load data
            if not INPUT_CSV.exists():
                raise FileNotFoundError(f"Input CSV not found: {INPUT_CSV.resolve()}")
            df = pd.read_csv(INPUT_CSV)
            logging.info("Input dataset loaded: %s", INPUT_CSV)

            # 2) Ensure artifacts directory exists
            self.ingestion_config.train_data_path.parent.mkdir(parents=True, exist_ok=True)

            # 3) Save raw data to artifacts/
            df.to_csv(self.ingestion_config.raw_data_path, index=False)
            logging.info("Raw dataset saved to %s", self.ingestion_config.raw_data_path)

            # 4) Train/test split
            logging.info("Train/test split (test_size=0.20, random_state=42)")
            train_set, test_set = train_test_split(df, test_size=0.2, random_state=42)

            # 5) Save splits
            train_set.to_csv(self.ingestion_config.train_data_path, index=False)
            test_set.to_csv(self.ingestion_config.test_data_path, index=False)
            logging.info("Ingestion completed. Train: %s | Test: %s",
                         self.ingestion_config.train_data_path, self.ingestion_config.test_data_path)

            return str(self.ingestion_config.train_data_path), str(self.ingestion_config.test_data_path)

        except Exception as e:
            # Wrap any exception in our CustomException
            raise CustomException(e, sys)

# For testing:
if __name__ == "__main__":
    # Run from the PROJECT ROOT directory:
    #   python -m src.components.data_ingestion
    obj = DataIngestion()
    train_data, test_data = obj.initiate_data_ingestion()

    data_transformation = DataTransformation()
    train_arr, test_arr, _ = data_transformation.initiate_data_transformation(train_data, test_data)

    model_trainer = ModelTrainer()
    # print(model_trainer.initiate_model_trainer(train_arr, test_arr))
    r2_square = model_trainer.initiate_model_trainer(train_arr, test_arr)
    print(f"r2_square = {r2_square}")
