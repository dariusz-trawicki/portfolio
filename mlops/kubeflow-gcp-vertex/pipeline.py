from kfp import dsl
from kfp.dsl import Input, Output, Dataset, Model, Metrics

PKGS = ["pandas==2.2.2", "scikit-learn==1.5.0"]


@dsl.component(packages_to_install=PKGS)
def prepare_data(train_set: Output[Dataset], test_set: Output[Dataset]):
    from sklearn.datasets import load_iris
    from sklearn.model_selection import train_test_split

    X, y = load_iris(return_X_y=True, as_frame=True)
    df = X.assign(target=y)
    train, test = train_test_split(df, test_size=0.2, random_state=42)

    train.to_csv(train_set.path, index=False)
    test.to_csv(test_set.path, index=False)


@dsl.component(packages_to_install=PKGS)
def train_model(train_set: Input[Dataset], n_estimators: int, model: Output[Model]):
    from sklearn.ensemble import RandomForestClassifier
    import pandas as pd
    import pickle

    df = pd.read_csv(train_set.path)
    clf = RandomForestClassifier(n_estimators=n_estimators, random_state=42)
    clf.fit(df.drop(columns="target"), df["target"])

    with open(model.path, "wb") as f:
        pickle.dump(clf, f)

    model.metadata["framework"] = "scikit-learn"
    model.metadata["n_estimators"] = n_estimators


@dsl.component(packages_to_install=PKGS)
def evaluate(test_set: Input[Dataset], model: Input[Model], metrics: Output[Metrics]):
    from sklearn.metrics import accuracy_score, f1_score
    import pandas as pd
    import pickle

    df = pd.read_csv(test_set.path)
    with open(model.path, "rb") as f:
        clf = pickle.load(f)

    preds = clf.predict(df.drop(columns="target"))
    metrics.log_metric("accuracy", float(accuracy_score(df["target"], preds)))
    metrics.log_metric("f1_macro", float(f1_score(df["target"], preds, average="macro")))


@dsl.pipeline(name="iris-demo", description="First pipeline on Vertex")
def iris_pipeline(n_estimators: int = 100):
    data = prepare_data()
    trained = train_model(
        train_set=data.outputs["train_set"],
        n_estimators=n_estimators,
    )
    evaluate(
        test_set=data.outputs["test_set"],
        model=trained.outputs["model"],
    )
