import json
import os
import pickle
from datetime import datetime, timezone

from sklearn.datasets import load_iris
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split

iris = load_iris()
X, y = iris.data, iris.target

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

model = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)
model.fit(X_train, y_train)

y_pred = model.predict(X_test)
accuracy = round(accuracy_score(y_test, y_pred), 4)

print(f"Test accuracy: {accuracy:.4f}")
print(classification_report(y_test, y_pred, target_names=iris.target_names))

os.makedirs("model", exist_ok=True)

with open("model/iris_model.pkl", "wb") as f:
    pickle.dump(model, f)

metadata = {
    "accuracy": accuracy,
    "trained_at": datetime.now(timezone.utc).isoformat(),
    "features": list(iris.feature_names),
    "classes": list(iris.target_names),
    "n_estimators": model.n_estimators,
    "max_depth": model.max_depth,
}
with open("model/metadata.json", "w") as f:
    json.dump(metadata, f, indent=2)

print("Model and metadata saved to model/")
