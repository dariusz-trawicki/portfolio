import json
import os
import pickle

from flask import Flask, request, render_template

app = Flask(__name__)

MODEL_PATH = "model/iris_model.pkl"
METADATA_PATH = "model/metadata.json"
SPECIES_NAMES = {0: "Iris setosa", 1: "Iris versicolor", 2: "Iris virginica"}

if not os.path.exists(MODEL_PATH):
    raise Exception("Model file not found. Run train.py first.")

with open(MODEL_PATH, "rb") as f:
    model = pickle.load(f)


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/predict", methods=["POST"])
def predict():
    try:
        features = [
            float(request.form[k])
            for k in ["sepal_length", "sepal_width", "petal_length", "petal_width"]
        ]
    except KeyError as e:
        return render_template("index.html", prediction_text=f"Missing field: {e}"), 200
    except ValueError:
        return render_template("index.html", prediction_text="Invalid input value"), 200

    prediction = model.predict([features])[0]
    species = SPECIES_NAMES.get(int(prediction), str(prediction))
    return render_template("index.html", prediction_text=f"Predicted Iris Class: {species}")


@app.route("/health")
def health():
    try:
        with open(METADATA_PATH) as f:
            metadata = json.load(f)
        accuracy = metadata.get("accuracy")
    except FileNotFoundError:
        accuracy = None
    return {"status": "ok", "model_accuracy": accuracy}, 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
