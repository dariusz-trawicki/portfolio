import os

import joblib
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

from src.custom_exception import CustomException
from src.logger import get_logger

logger = get_logger(__name__)

TARGET = "Efficiency_Status"
CATEGORICAL = ["Operation_Mode"]
NUMERIC = [
    "Temperature_C", "Vibration_Hz", "Power_Consumption_kW",
    "Network_Latency_ms", "Packet_Loss_%", "Quality_Control_Defect_Rate_%",
    "Production_Speed_units_per_hr", "Predictive_Maintenance_Score",
    "Error_Rate_%", "Year", "Month", "Day", "Hour",
]
FEATURES = CATEGORICAL + NUMERIC


class DataProcessing:
    def __init__(self, input_path, output_path):
        self.input_path = input_path
        self.output_path = output_path
        self.df = None

        os.makedirs(self.output_path, exist_ok=True)
        logger.info("Data Processing initialized...")

    def load_data(self):
        try:
            self.df = pd.read_csv(self.input_path)
            logger.info("Data loaded successfully...")
        except Exception as e:
            logger.error(f"Error while loading data {e}")
            raise CustomException("Failed to load data", e) from e

    def preprocess(self):
        try:
            ts = pd.to_datetime(self.df["Timestamp"], errors="coerce")
            if ts.isna().any():
                raise ValueError(f"Unparseable timestamps: {int(ts.isna().sum())}")

            self.df["Year"] = ts.dt.year
            self.df["Month"] = ts.dt.month
            self.df["Day"] = ts.dt.day
            self.df["Hour"] = ts.dt.hour

            missing = set([*FEATURES, TARGET]) - set(self.df.columns)
            if missing:
                raise ValueError(f"Missing columns: {sorted(missing)}")

            for col in CATEGORICAL:
                self.df[col] = self.df[col].astype(str)

            if self.df["Year"].nunique() == 1:
                logger.warning("Year column has zero variance - consider dropping it")

            logger.info("All basic data preprocessing done..")
        except Exception as e:
            logger.error(f"Error while preprocessing data {e}")
            raise CustomException("Failed to preprocess data", e) from e

    def split_and_save(self):
        try:
            X = self.df[FEATURES]

            label_encoder = LabelEncoder()
            y = label_encoder.fit_transform(self.df[TARGET].astype(str))

            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42, stratify=y
            )

            for name, obj in [
                ("X_train", X_train), ("X_test", X_test),
                ("y_train", y_train), ("y_test", y_test),
                ("label_encoder", label_encoder),
            ]:
                joblib.dump(obj, os.path.join(self.output_path, f"{name}.pkl"))

            logger.info(f"Splits saved. Classes: {list(label_encoder.classes_)}")
        except Exception as e:
            logger.error(f"Error while split and save data {e}")
            raise CustomException("Failed to split and save data", e) from e

    def run(self):
        self.load_data()
        self.preprocess()
        self.split_and_save()
