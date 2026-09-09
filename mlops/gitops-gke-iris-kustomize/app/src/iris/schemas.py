"""Kontrakt API — request i response dla /predict."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PredictRequest(BaseModel):
    sepal_length_cm: float = Field(gt=0, le=15)
    sepal_width_cm: float = Field(gt=0, le=15)
    petal_length_cm: float = Field(gt=0, le=15)
    petal_width_cm: float = Field(gt=0, le=15)


class PredictResponse(BaseModel):
    predicted_class: str
    confidence: float
    probabilities: dict[str, float]
    model_version: str
