"""Keras model (Functional API): numeric inputs + categorical embeddings."""
from __future__ import annotations

import keras
import numpy as np
from keras import layers

from .config import TrainConfig
from .preprocessing import Preprocessor


def build_model(pre: Preprocessor, numeric_train: np.ndarray, cfg: TrainConfig) -> keras.Model:
    # Numeric input + normalization "baked into" the model. adapt() computes mean and
    # variance on the TRAINING set (never on validation or test).
    num_in = keras.Input(shape=(len(pre.numeric),), dtype="float32", name="numeric")
    norm = layers.Normalization(name="normalization")
    norm.adapt(numeric_train)

    inputs: dict[str, keras.KerasTensor] = {"numeric": num_in}
    parts = [norm(num_in)]

    # Each categorical feature gets its own embedding: a learned vector instead of one-hot.
    # Size is len(vocab) + 1 because index 0 is the OOV bucket.
    for col, vocab in pre.vocabs.items():
        inp = keras.Input(shape=(1,), dtype="int32", name=col)
        emb = layers.Embedding(len(vocab) + 1, cfg.emb_dim, name=f"emb_{col}")(inp)
        parts.append(layers.Flatten(name=f"flat_{col}")(emb))
        inputs[col] = inp

    x = layers.Concatenate(name="features")(parts)
    for i, units in enumerate(cfg.hidden):
        x = layers.Dense(units, activation="relu", kernel_regularizer=keras.regularizers.l2(cfg.l2), name=f"dense_{i}")(x)
        x = layers.Dropout(cfg.dropout, name=f"dropout_{i}")(x)
    out = layers.Dense(1, activation="sigmoid", name="churn_probability")(x)

    model = keras.Model(inputs, out, name="churn_mlp")
    model.compile(
        optimizer=keras.optimizers.Adam(cfg.lr),
        loss="binary_crossentropy",
        metrics=[keras.metrics.AUC(name="auc"), keras.metrics.AUC(curve="PR", name="pr_auc")],
    )
    return model
