"""ML artifacts, metrics contract and prediction tests."""

import os

import pandas as pd
import pytest

from app.services import ml_service
from ml import train_models

DATA_CSV = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "data", "synthetic_leads.csv")

PROFILE = {
    "age": 32, "budget": 8000, "interaction_count": 6, "previous_ai_experience": 1,
    "city": "תל אביב", "occupation": "מפתח תוכנה", "education": "תואר שני",
    "course_interest": "Prompt Engineering", "lead_source": "Referral",
    "preferred_schedule": "גמיש",
}


def test_dataset_has_10000_rows():
    df = pd.read_csv(DATA_CSV)
    assert len(df) == 10_000
    assert df["purchased"].isin([0, 1]).all()


def test_dataset_has_injected_data_problems():
    df = pd.read_csv(DATA_CSV)
    missing = df[train_models.FEATURES].isna().sum()
    assert missing.sum() > 0, "expected injected missing values"
    assert df["budget"].max() > 50_000, "expected injected outliers"
    rate = df["purchased"].mean()
    assert 0.1 < rate < 0.45, "expected moderate class imbalance"


def test_no_target_leakage_in_features():
    for leaky in ("status", "payment_status", "purchased"):
        assert leaky not in train_models.FEATURES


def test_metrics_file_exists_and_documents_the_split():
    m = ml_service.load_metrics()
    assert m["dataset"]["rows"] == 10_000
    assert m["dataset"]["test_size"] == 0.20
    assert m["dataset"]["split"] == "stratified"
    assert m["dataset"]["train_rows"] + m["dataset"]["test_rows"] == 10_000


def test_baseline_models_are_trained():
    trained = {m["key"] for m in ml_service.available_models()}
    assert {"logistic_regression", "random_forest"} <= trained


def test_every_trained_model_exposes_all_metrics():
    required = {"accuracy", "precision", "recall", "f1", "roc_auc",
                "log_loss", "brier", "mae", "rmse", "r2", "confusion_matrix"}
    models = ml_service.available_models()
    assert models
    for m in models:
        assert required <= set(m["metrics"]), f"{m['key']} is missing metrics"
        assert 0.0 <= m["metrics"]["roc_auc"] <= 1.0


def test_best_model_selected_by_roc_auc():
    m = ml_service.load_metrics()
    trained = {k: v for k, v in m["models"].items() if v.get("status") == "trained"}
    best_auc = max(v["metrics"]["roc_auc"] for v in trained.values())
    assert trained[m["best_model"]]["metrics"]["roc_auc"] == best_auc


def test_unavailable_models_degrade_gracefully():
    """A missing optional dependency must not break the project."""
    for m in ml_service.load_metrics()["models"].values():
        assert m["status"] in {"trained", "unavailable", "failed"}
        if m["status"] != "trained":
            assert m.get("reason")


@pytest.mark.parametrize("key", [m["key"] for m in ml_service.available_models()])
def test_prediction_returns_probability_in_range(key):
    result = ml_service.predict(PROFILE, key)
    assert 0.0 <= result["probability"] <= 1.0
    assert result["level"] in {"high", "medium", "low"}
    assert result["model"] == key


def test_priority_thresholds():
    assert ml_service.priority_level(0.95)[0] == "high"
    assert ml_service.priority_level(0.70)[0] == "high"
    assert ml_service.priority_level(0.55)[0] == "medium"
    assert ml_service.priority_level(0.40)[0] == "medium"
    assert ml_service.priority_level(0.10)[0] == "low"


def test_prediction_handles_unseen_categories():
    """OneHotEncoder(handle_unknown='ignore') must absorb unknown values."""
    profile = dict(PROFILE, city="עיר שלא קיימת", occupation="עיסוק חדש")
    assert 0.0 <= ml_service.predict(profile)["probability"] <= 1.0


def test_prediction_handles_missing_values():
    profile = dict(PROFILE, age=None, budget=None)
    assert 0.0 <= ml_service.predict(profile)["probability"] <= 1.0


def test_api_predict_endpoint(auth_client):
    res = auth_client.post("/api/predict", json=PROFILE)
    assert res.status_code == 200
    body = res.get_json()
    assert 0.0 <= body["probability"] <= 1.0
    assert body["percent"] == round(body["probability"] * 100, 1)


def test_api_predict_rejects_unknown_model(auth_client):
    assert auth_client.post("/api/predict", json={"model": "nope"}).status_code == 400


def test_api_model_metrics_endpoint(auth_client):
    res = auth_client.get("/api/models/metrics")
    assert res.status_code == 200
    assert "models" in res.get_json()
