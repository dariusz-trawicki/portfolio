import json
import os

import joblib
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from src.custom_exception import CustomException
from src.data_processing import CATEGORICAL, NUMERIC
from src.logger import get_logger

logger = get_logger(__name__)

MIN_ACCURACY = 0.75


class ModelTraining:
    def __init__(self, processed_data_path, model_output_path):
        self.processed_path = processed_data_path
        self.model_path = model_output_path
        self.clf = None
        self.label_encoder = None
        self.X_train = self.X_test = self.y_train = self.y_test = None

        os.makedirs(self.model_path, exist_ok=True)
        logger.info("Model Training initialized...")

    def load_data(self):
        try:
            for name in ["X_train", "X_test", "y_train", "y_test"]:
                setattr(self, name, joblib.load(os.path.join(self.processed_path, f"{name}.pkl")))
            self.label_encoder = joblib.load(os.path.join(self.processed_path, "label_encoder.pkl"))
            logger.info("Data loaded successfully...")
        except Exception as e:
            logger.error(f"Error while loading data {e}")
            raise CustomException("Failed to load data", e) from e

    def train_model(self):
        try:
            preprocessor = ColumnTransformer(
                transformers=[
                    ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL),
                    ("num", StandardScaler(), NUMERIC),
                ]
            )
            self.clf = Pipeline(
                steps=[
                    ("preprocess", preprocessor),
                    ("model", LogisticRegression(
                        random_state=42, max_iter=1000, class_weight="balanced"
                    )),
                ]
            )
            self.clf.fit(self.X_train, self.y_train)
            logger.info("Model trained successfully...")
        except Exception as e:
            logger.error(f"Error while training model {e}")
            raise CustomException("Failed to train model", e) from e

    def evaluate_model(self):
        try:
            y_pred = self.clf.predict(self.X_test)
            names = list(self.label_encoder.classes_)

            accuracy = accuracy_score(self.y_test, y_pred)
            report = classification_report(self.y_test, y_pred, target_names=names)
            report_dict = classification_report(
                self.y_test, y_pred, target_names=names, output_dict=True
            )

            logger.info(f"Accuracy : {accuracy}")
            logger.info(f"\n{report}")

            if accuracy < MIN_ACCURACY:
                raise ValueError(f"Accuracy {accuracy:.4f} below the threshold {MIN_ACCURACY}")

            joblib.dump(self.clf, os.path.join(self.model_path, "model.pkl"))
            joblib.dump(self.label_encoder, os.path.join(self.model_path, "label_encoder.pkl"))

            with open(os.path.join(self.model_path, "metrics.json"), "w") as f:
                json.dump(
                    {"accuracy": accuracy, "classes": names, "report": report_dict},
                    f, indent=2,
                )

            logger.info("Model Evaluation Done..")
        except Exception as e:
            logger.error(f"Error while evaluating model {e}")
            raise CustomException("Failed to evaluate model", e) from e

    def run(self):
        self.load_data()
        self.train_model()
        self.evaluate_model()
