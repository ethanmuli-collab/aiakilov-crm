"""Train and compare purchase-probability models for AIAKILOV CRM.

Anti-leakage contract
---------------------
FEATURES contains only information available BEFORE the purchase decision.
`status`, `payment_status`, enrolment and invoice existence are deliberately
excluded - they are consequences of the target, not predictors of it.

Split contract
--------------
80/20 stratified split with a fixed random_state. Every preprocessor is fitted
inside a Pipeline on the TRAINING FOLD ONLY, so the test fold never influences
imputation statistics, scaling or category vocabularies.
"""

from __future__ import annotations

import json
import os
import warnings

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    log_loss,
    mean_absolute_error,
    precision_score,
    r2_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

warnings.filterwarnings("ignore")

SEED = 42
TEST_SIZE = 0.20

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_CSV = os.path.join(BASE_DIR, "data", "synthetic_leads.csv")
ARTIFACT_DIR = os.path.join(BASE_DIR, "ml", "artifacts")
METRICS_JSON = os.path.join(ARTIFACT_DIR, "metrics.json")

NUMERIC_FEATURES = ["age", "budget", "interaction_count", "previous_ai_experience"]
CATEGORICAL_FEATURES = [
    "city",
    "occupation",
    "education",
    "course_interest",
    "lead_source",
    "preferred_schedule",
]
FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES
TARGET = "purchased"

# Explicitly documented so the exclusion is auditable in the UI and the README.
LEAKY_COLUMNS_EXCLUDED = ["status", "payment_status", "enrollment", "invoice", "purchased"]

MODEL_LABELS = {
    "logistic_regression": "Logistic Regression",
    "random_forest": "Random Forest",
    "xgboost": "XGBoost",
    "lightgbm": "LightGBM",
    "catboost": "CatBoost",
}


def build_preprocessor(scale_numeric: bool) -> ColumnTransformer:
    """Numeric: median impute (+ optional scaling). Categorical: mode impute + OHE."""
    numeric_steps = [("imputer", SimpleImputer(strategy="median"))]
    if scale_numeric:
        numeric_steps.append(("scaler", StandardScaler()))

    return ColumnTransformer(
        transformers=[
            ("num", Pipeline(numeric_steps), NUMERIC_FEATURES),
            (
                "cat",
                Pipeline(
                    [
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        ("ohe", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
                    ]
                ),
                CATEGORICAL_FEATURES,
            ),
        ],
        remainder="drop",
    )


def candidate_models() -> list[tuple[str, object, bool, str | None]]:
    """(key, estimator, needs_scaling, unavailable_reason)."""
    models: list[tuple[str, object, bool, str | None]] = [
        (
            "logistic_regression",
            LogisticRegression(max_iter=2000, random_state=SEED),
            True,
            None,
        ),
        (
            "random_forest",
            RandomForestClassifier(
                n_estimators=300, max_depth=12, min_samples_leaf=5,
                random_state=SEED, n_jobs=-1,
            ),
            False,
            None,
        ),
    ]

    try:
        from xgboost import XGBClassifier

        models.append(
            (
                "xgboost",
                XGBClassifier(
                    n_estimators=350, max_depth=5, learning_rate=0.07,
                    subsample=0.9, colsample_bytree=0.9, eval_metric="logloss",
                    random_state=SEED, n_jobs=-1,
                ),
                False,
                None,
            )
        )
    except Exception as exc:  # pragma: no cover - environment dependent
        models.append(("xgboost", None, False, f"{type(exc).__name__}: {exc}"))

    try:
        from lightgbm import LGBMClassifier

        models.append(
            (
                "lightgbm",
                LGBMClassifier(
                    n_estimators=350, learning_rate=0.07, num_leaves=31,
                    random_state=SEED, n_jobs=-1, verbose=-1,
                ),
                False,
                None,
            )
        )
    except Exception as exc:  # pragma: no cover - environment dependent
        models.append(("lightgbm", None, False, f"{type(exc).__name__}: {exc}"))

    try:
        from catboost import CatBoostClassifier

        models.append(
            (
                "catboost",
                CatBoostClassifier(
                    iterations=350, depth=6, learning_rate=0.07,
                    random_seed=SEED, verbose=0,
                ),
                False,
                None,
            )
        )
    except Exception as exc:  # pragma: no cover - environment dependent
        models.append(("catboost", None, False, f"{type(exc).__name__}: {exc}"))

    return models


def feature_importance(pipe: Pipeline, key: str) -> list[dict]:
    """Top-12 drivers: tree importances, or strongest LR coefficients."""
    try:
        names = list(pipe.named_steps["prep"].get_feature_names_out())
        clf = pipe.named_steps["model"]
        if hasattr(clf, "feature_importances_"):
            vals = np.asarray(clf.feature_importances_, dtype=float)
            kind = "importance"
        elif hasattr(clf, "coef_"):
            vals = np.asarray(clf.coef_, dtype=float).ravel()
            kind = "coefficient"
        else:
            return []
        order = np.argsort(np.abs(vals))[::-1][:12]
        return [
            {
                "feature": names[i].split("__", 1)[-1],
                "value": round(float(vals[i]), 4),
                "kind": kind,
            }
            for i in order
        ]
    except Exception:
        return []


def evaluate(y_true: np.ndarray, y_pred: np.ndarray, y_prob: np.ndarray) -> dict:
    cm = confusion_matrix(y_true, y_pred).tolist()
    return {
        # --- primary classification metrics ---
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
        "precision": round(float(precision_score(y_true, y_pred, zero_division=0)), 4),
        "recall": round(float(recall_score(y_true, y_pred, zero_division=0)), 4),
        "f1": round(float(f1_score(y_true, y_pred, zero_division=0)), 4),
        "roc_auc": round(float(roc_auc_score(y_true, y_prob)), 4),
        "log_loss": round(float(log_loss(y_true, y_prob)), 4),
        "brier": round(float(brier_score_loss(y_true, y_prob)), 4),
        "confusion_matrix": cm,
        # --- educational regression-style metrics (NOT used for selection) ---
        "mae": round(float(mean_absolute_error(y_true, y_prob)), 4),
        "rmse": round(float(np.sqrt(np.mean((y_true - y_prob) ** 2))), 4),
        "r2": round(float(r2_score(y_true, y_prob)), 4),
    }


def main() -> dict:
    df = pd.read_csv(DATA_CSV)
    X, y = df[FEATURES], df[TARGET].astype(int)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=TEST_SIZE, stratify=y, random_state=SEED
    )

    os.makedirs(ARTIFACT_DIR, exist_ok=True)
    results: dict[str, dict] = {}

    for key, estimator, needs_scaling, reason in candidate_models():
        label = MODEL_LABELS[key]
        if estimator is None:
            results[key] = {"key": key, "label": label, "status": "unavailable", "reason": reason}
            print(f"[skip] {label}: {reason}")
            continue
        try:
            pipe = Pipeline(
                [("prep", build_preprocessor(needs_scaling)), ("model", estimator)]
            )
            pipe.fit(X_train, y_train)  # preprocessors fit on TRAIN ONLY
            y_prob = pipe.predict_proba(X_test)[:, 1]
            y_pred = (y_prob >= 0.5).astype(int)

            metrics = evaluate(y_test.to_numpy(), y_pred, y_prob)
            joblib.dump(pipe, os.path.join(ARTIFACT_DIR, f"{key}.joblib"))
            results[key] = {
                "key": key,
                "label": label,
                "status": "trained",
                "metrics": metrics,
                "feature_importance": feature_importance(pipe, key),
            }
            print(f"[ok]   {label}: ROC-AUC={metrics['roc_auc']} F1={metrics['f1']}")
        except Exception as exc:
            results[key] = {
                "key": key, "label": label, "status": "failed",
                "reason": f"{type(exc).__name__}: {exc}",
            }
            print(f"[fail] {label}: {exc}")

    trained = {k: v for k, v in results.items() if v.get("status") == "trained"}
    # Selection is driven by ROC-AUC, tie-broken by F1. Never by accuracy or R².
    best = max(
        trained,
        key=lambda k: (trained[k]["metrics"]["roc_auc"], trained[k]["metrics"]["f1"]),
    ) if trained else None

    payload = {
        "generated_at": pd.Timestamp.utcnow().isoformat(),
        "dataset": {
            "rows": int(len(df)),
            "train_rows": int(len(X_train)),
            "test_rows": int(len(X_test)),
            "test_size": TEST_SIZE,
            "random_state": SEED,
            "split": "stratified",
            "positive_rate": round(float(y.mean()), 4),
            "missing_values": {c: int(n) for c, n in df[FEATURES].isna().sum().items() if n},
        },
        "features": {
            "numeric": NUMERIC_FEATURES,
            "categorical": CATEGORICAL_FEATURES,
            "excluded_leaky": LEAKY_COLUMNS_EXCLUDED,
        },
        "best_model": best,
        "selection_criterion": "ROC-AUC (tie-break F1)",
        "models": results,
    }
    with open(METRICS_JSON, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)

    print(f"\nbest model: {best}  ->  {METRICS_JSON}")
    return payload


if __name__ == "__main__":
    main()
