"""
RecoverAI - model training and evaluation.

Predicts `recoverable` (0/1) for FAILED payments. Compares Logistic Regression,
Random Forest and Gradient Boosting.

Model selection uses 5-fold cross-validation on the TRAINING split only. The
held-out test split is touched once, at the end, to report final metrics, so
the numbers in metrics.json are an honest estimate on SYNTHETIC data.

Usage (from repo root):
    python ml/train.py

Outputs (ml/models/):
    model.joblib         fitted sklearn Pipeline (preprocessing + classifier)
    metrics.json         metrics computed from the actual test set
    feature_stats.json   reference statistics used by the recovery score
"""
import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder, StandardScaler

ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "data" / "payments.csv"
MODEL_DIR = ROOT / "ml" / "models"
SEED = 42

LOG_NUMERIC = ["amount", "customerLifetimeValue"]
COUNT_NUMERIC = ["previousSuccessfulPayments", "previousFailedPayments", "previousRecoveryAttempts"]
CATEGORICAL = ["paymentMethod", "failureReason", "customerType", "subscriptionStatus"]
FEATURES = LOG_NUMERIC + COUNT_NUMERIC + CATEGORICAL
TARGET = "recoverable"


def build_preprocessor():
    log_pipe = Pipeline(
        [("log", FunctionTransformer(np.log1p, feature_names_out="one-to-one")), ("scale", StandardScaler())]
    )
    return ColumnTransformer(
        [
            ("log_num", log_pipe, LOG_NUMERIC),
            ("count_num", StandardScaler(), COUNT_NUMERIC),
            ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL),
        ]
    )


def candidate_models():
    return {
        "logistic_regression": LogisticRegression(max_iter=1000, random_state=SEED),
        "random_forest": RandomForestClassifier(
            n_estimators=300, min_samples_leaf=5, random_state=SEED, n_jobs=-1
        ),
        "gradient_boosting": GradientBoostingClassifier(
            n_estimators=200, learning_rate=0.05, max_depth=3, random_state=SEED
        ),
    }


def evaluate(pipe, X, y):
    proba = pipe.predict_proba(X)[:, 1]
    pred = (proba >= 0.5).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, pred).ravel()
    return {
        "precision": round(float(precision_score(y, pred)), 4),
        "recall": round(float(recall_score(y, pred)), 4),
        "f1": round(float(f1_score(y, pred)), 4),
        "roc_auc": round(float(roc_auc_score(y, proba)), 4),
        "accuracy": round(float(accuracy_score(y, pred)), 4),
        "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
    }


def top_features(pipe, name, k=10):
    """Human-readable global importance for the chosen model."""
    pre = pipe.named_steps["prep"]
    clf = pipe.named_steps["clf"]
    names = [n.split("__", 1)[-1] for n in pre.get_feature_names_out()]
    if hasattr(clf, "coef_"):
        vals = clf.coef_[0]
        kind = "logistic_regression_coefficient"
    else:
        vals = clf.feature_importances_
        kind = "feature_importance"
    order = np.argsort(-np.abs(vals))[:k]
    return {
        "kind": kind,
        "top": [{"feature": names[i], "value": round(float(vals[i]), 4)} for i in order],
    }


def main():
    df = pd.read_csv(DATA_PATH)
    failed = df[df["paymentStatus"] == "failed"].copy()
    failed[TARGET] = failed[TARGET].astype(int)

    X, y = failed[FEATURES], failed[TARGET]
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=SEED
    )
    print(f"Failed payments: {len(failed):,}  train={len(X_train):,}  test={len(X_test):,}")
    print(f"Recoverable rate  train={y_train.mean():.1%}  test={y_test.mean():.1%}\n")

    # ---- model selection: CV on train only ----
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)
    results, fitted = {}, {}
    for name, clf in candidate_models().items():
        pipe = Pipeline([("prep", build_preprocessor()), ("clf", clf)])
        cv_auc = cross_val_score(pipe, X_train, y_train, cv=cv, scoring="roc_auc")
        pipe.fit(X_train, y_train)
        fitted[name] = pipe
        results[name] = {
            "cv_roc_auc_mean": round(float(cv_auc.mean()), 4),
            "cv_roc_auc_std": round(float(cv_auc.std()), 4),
            "test": evaluate(pipe, X_test, y_test),
        }
        t = results[name]["test"]
        print(
            f"{name:<20} CV AUC {cv_auc.mean():.4f} (+/-{cv_auc.std():.4f}) | "
            f"test AUC {t['roc_auc']:.4f}  P {t['precision']:.3f}  R {t['recall']:.3f}  F1 {t['f1']:.3f}"
        )

    best = max(results, key=lambda n: results[n]["cv_roc_auc_mean"])
    print(f"\nSelected (best CV ROC-AUC on training data): {best}")

    # ---- reference stats for the recovery score (from all payments) ----
    stats = {
        "ltv_p95": round(float(df["customerLifetimeValue"].quantile(0.95)), 2),
        "amount_p95": round(float(df["amount"].quantile(0.95)), 2),
        "amount_median": round(float(df["amount"].median()), 2),
    }

    metrics = {
        "data_disclaimer": "Computed on a SYNTHETIC dataset. Not real merchant data.",
        "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "dataset": {
            "total_payments": int(len(df)),
            "failed_payments": int(len(failed)),
            "train_size": int(len(X_train)),
            "test_size": int(len(X_test)),
            "positive_rate_train": round(float(y_train.mean()), 4),
            "positive_rate_test": round(float(y_test.mean()), 4),
        },
        "features": FEATURES,
        "decision_threshold": 0.5,
        "selected_model": best,
        "selection_criterion": "mean 5-fold CV ROC-AUC on the training split",
        "selected_metrics": results[best]["test"],
        "all_models": results,
        "feature_importance": top_features(fitted[best], best),
    }

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(fitted[best], MODEL_DIR / "model.joblib")
    (MODEL_DIR / "metrics.json").write_text(json.dumps(metrics, indent=2))
    (MODEL_DIR / "feature_stats.json").write_text(json.dumps(stats, indent=2))

    sel = results[best]["test"]
    print("\nTest-set metrics for the selected model (threshold 0.5):")
    print(f"  precision {sel['precision']}  recall {sel['recall']}  F1 {sel['f1']}  ROC-AUC {sel['roc_auc']}")
    print(f"  confusion matrix {sel['confusion_matrix']}")
    print(f"\nSaved -> {MODEL_DIR}")


if __name__ == "__main__":
    main()