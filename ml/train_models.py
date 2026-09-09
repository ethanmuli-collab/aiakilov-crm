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

Metrics contract
----------------
This is binary CLASSIFICATION, not regression: only classification metrics are
reported (accuracy, precision, recall, F1, ROC-AUC, log loss, Brier score,
confusion matrix). MAE/RMSE/R² do not apply here and are deliberately absent.

Class imbalance & decision threshold
-------------------------------------
The positive rate is ~27%, so a fixed 0.5 cutoff under-predicts the minority
class (this is what tanked F1 in the first pass - Random Forest was scoring
F1=0.14 while ROC-AUC was a respectable 0.71). Two fixes, both standard and
leakage-safe:
  1. Every estimator is class-weighted (or given `scale_pos_weight`) so the
     loss itself accounts for the imbalance.
  2. The 0.5 decision threshold is replaced by one tuned to maximise F1 on an
     internal validation split carved out of the TRAINING fold only (never
     the test fold) - then the final model is refit on the full training set
     and evaluated on the test fold using that tuned threshold. ROC-AUC, log
     loss and Brier score are threshold-independent and computed on the raw
     probabilities regardless.
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
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

warnings.filterwarnings("ignore")

SEED = 42
TEST_SIZE = 0.20
VAL_SIZE = 0.20  # carved out of the training fold only, for threshold tuning
THRESHOLD_GRID = np.round(np.arange(0.02, 0.99, 0.01), 2)

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


def candidate_models(y_train: pd.Series) -> list[tuple[str, object, bool, str | None]]:
    """(key, estimator, needs_scaling, unavailable_reason).

    Every estimator is class-weighted for the ~27% positive rate so the loss
    function itself compensates for the imbalance, on top of the tuned
    decision threshold applied later.
    """
    neg, pos = int((y_train == 0).sum()), int((y_train == 1).sum())
    scale_pos_weight = neg / pos if pos else 1.0

    models: list[tuple[str, object, bool, str | None]] = [
        (
            "logistic_regression",
            LogisticRegression(max_iter=2000, class_weight="balanced", random_state=SEED),
            True,
            None,
        ),
        (
            "random_forest",
            RandomForestClassifier(
                n_estimators=400, max_depth=14, min_samples_leaf=3,
                class_weight="balanced", random_state=SEED, n_jobs=-1,
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
                    n_estimators=400, max_depth=5, learning_rate=0.06,
                    subsample=0.9, colsample_bytree=0.9, eval_metric="logloss",
                    scale_pos_weight=scale_pos_weight, random_state=SEED, n_jobs=-1,
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
                    n_estimators=400, learning_rate=0.06, num_leaves=31,
                    class_weight="balanced", random_state=SEED, n_jobs=-1, verbose=-1,
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
                    iterations=400, depth=6, learning_rate=0.06,
                    auto_class_weights="Balanced", random_seed=SEED, verbose=0,
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


def best_f1_threshold(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    """Grid-search the classification threshold that maximises F1."""
    scores = [f1_score(y_true, (y_prob >= t).astype(int), zero_division=0) for t in THRESHOLD_GRID]
    return float(THRESHOLD_GRID[int(np.argmax(scores))])


def evaluate(y_true: np.ndarray, y_pred: np.ndarray, y_prob: np.ndarray, threshold: float) -> dict:
    cm = confusion_matrix(y_true, y_pred).tolist()
    return {
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
        "precision": round(float(precision_score(y_true, y_pred, zero_division=0)), 4),
        "recall": round(float(recall_score(y_true, y_pred, zero_division=0)), 4),
        "f1": round(float(f1_score(y_true, y_pred, zero_division=0)), 4),
        "roc_auc": round(float(roc_auc_score(y_true, y_prob)), 4),
        "log_loss": round(float(log_loss(y_true, y_prob)), 4),
        "brier": round(float(brier_score_loss(y_true, y_prob)), 4),
        "confusion_matrix": cm,
        "threshold": round(float(threshold), 2),
    }


def main() -> dict:
    df = pd.read_csv(DATA_CSV)
    X, y = df[FEATURES], df[TARGET].astype(int)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=TEST_SIZE, stratify=y, random_state=SEED
    )
    # Carved out of the TRAINING fold only - the test fold never informs the
    # threshold choice, so this stays leakage-safe.
    X_sub, X_val, y_sub, y_val = train_test_split(
        X_train, y_train, test_size=VAL_SIZE, stratify=y_train, random_state=SEED
    )

    os.makedirs(ARTIFACT_DIR, exist_ok=True)
    results: dict[str, dict] = {}

    for key, estimator, needs_scaling, reason in candidate_models(y_train):
        label = MODEL_LABELS[key]
        if estimator is None:
            results[key] = {"key": key, "label": label, "status": "unavailable", "reason": reason}
            print(f"[skip] {label}: {reason}")
            continue
        try:
            # Pass 1: fit on the sub-train split, tune the decision threshold
            # against the held-out validation split.
            val_pipe = Pipeline([("prep", build_preprocessor(needs_scaling)),
                                 ("model", estimator)])
            val_pipe.fit(X_sub, y_sub)
            val_prob = val_pipe.predict_proba(X_val)[:, 1]
            threshold = best_f1_threshold(y_val.to_numpy(), val_prob)

            # Pass 2: refit a fresh estimator on the FULL training fold (don't
            # waste the validation rows in the final model) and evaluate once
            # on the untouched test fold, using the tuned threshold.
            estimator_final = estimator.__class__(**estimator.get_params())
            pipe = Pipeline([("prep", build_preprocessor(needs_scaling)),
                             ("model", estimator_final)])
            pipe.fit(X_train, y_train)
            y_prob = pipe.predict_proba(X_test)[:, 1]
            y_pred = (y_prob >= threshold).astype(int)

            metrics = evaluate(y_test.to_numpy(), y_pred, y_prob, threshold)
            joblib.dump(pipe, os.path.join(ARTIFACT_DIR, f"{key}.joblib"))
            results[key] = {
                "key": key,
                "label": label,
                "status": "trained",
                "metrics": metrics,
                "feature_importance": feature_importance(pipe, key),
            }
            print(f"[ok]   {label}: ROC-AUC={metrics['roc_auc']} F1={metrics['f1']} "
                  f"threshold={metrics['threshold']}")
        except Exception as exc:
            results[key] = {
                "key": key, "label": label, "status": "failed",
                "reason": f"{type(exc).__name__}: {exc}",
            }
            print(f"[fail] {label}: {exc}")

    trained = {k: v for k, v in results.items() if v.get("status") == "trained"}
    # Selection is driven by ROC-AUC, tie-broken by F1. Never by accuracy.
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
        "class_imbalance_handling": "class_weight=balanced / scale_pos_weight "
                                     "+ F1-maximising decision threshold tuned on an "
                                     "internal validation split (not the test fold)",
        "models": results,
    }
    with open(METRICS_JSON, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)

    print(f"\nbest model: {best}  ->  {METRICS_JSON}")
    return payload


if __name__ == "__main__":
    main()
