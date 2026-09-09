"""Loads trained model artifacts and serves purchase-probability predictions."""

from __future__ import annotations

import json
import os

import joblib
import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ARTIFACT_DIR = os.path.join(BASE_DIR, "ml", "artifacts")
METRICS_JSON = os.path.join(ARTIFACT_DIR, "metrics.json")

FEATURES = [
    "age", "budget", "interaction_count", "previous_ai_experience",
    "city", "occupation", "education", "course_interest",
    "lead_source", "preferred_schedule",
]

HIGH_THRESHOLD = 0.70
MEDIUM_THRESHOLD = 0.40

_cache: dict[str, object] = {}


def load_metrics() -> dict:
    if not os.path.exists(METRICS_JSON):
        return {"models": {}, "best_model": None, "dataset": {}, "features": {}}
    with open(METRICS_JSON, encoding="utf-8") as fh:
        return json.load(fh)


def available_models() -> list[dict]:
    metrics = load_metrics()
    return [m for m in metrics.get("models", {}).values() if m.get("status") == "trained"]


def best_model_key() -> str | None:
    metrics = load_metrics()
    best = metrics.get("best_model")
    if best:
        return best
    models = available_models()
    return models[0]["key"] if models else None


def load_model(key: str):
    if key in _cache:
        return _cache[key]
    path = os.path.join(ARTIFACT_DIR, f"{key}.joblib")
    if not os.path.exists(path):
        return None
    _cache[key] = joblib.load(path)
    return _cache[key]


def priority_level(probability: float) -> tuple[str, str]:
    """Return (english_level, hebrew_label)."""
    if probability >= HIGH_THRESHOLD:
        return "high", "סיכוי גבוה"
    if probability >= MEDIUM_THRESHOLD:
        return "medium", "סיכוי בינוני"
    return "low", "סיכוי נמוך"


def predict(lead: dict, model_key: str | None = None) -> dict:
    """Predict purchase probability for a single lead dict."""
    key = model_key or best_model_key()
    if not key:
        return {"error": "no trained model available", "model": None}
    model = load_model(key)
    if model is None:
        return {"error": f"model artifact '{key}' not found", "model": key}

    row = {f: lead.get(f) for f in FEATURES}
    prob = float(model.predict_proba(pd.DataFrame([row]))[0][1])
    level, label = priority_level(prob)
    return {
        "model": key,
        "model_label": load_metrics().get("models", {}).get(key, {}).get("label", key),
        "probability": round(prob, 4),
        "percent": round(prob * 100, 1),
        "level": level,
        "level_label": label,
    }


def predict_batch(leads: list[dict], model_key: str | None = None) -> list[dict]:
    key = model_key or best_model_key()
    model = load_model(key) if key else None
    if model is None:
        return [{"error": "no trained model available"} for _ in leads]
    frame = pd.DataFrame([{f: lead.get(f) for f in FEATURES} for lead in leads])
    probs = model.predict_proba(frame)[:, 1]
    out = []
    for p in probs:
        level, label = priority_level(float(p))
        out.append({
            "model": key, "probability": round(float(p), 4),
            "percent": round(float(p) * 100, 1), "level": level, "level_label": label,
        })
    return out
