"""
RecoverAI - synthetic payment dataset generator.

Generates customers first (history, value, subscription), then payments that
inherit those customer attributes, then a recovery outcome for FAILED payments
drawn from a noisy latent model. The latent probability is never written to the
CSV, so the ML model has to learn the relationships from data.

Usage (from repo root):
    python ml/generate_dataset.py
    python ml/generate_dataset.py --payments 10000 --customers 2500 --seed 42

Output: data/payments.csv   (SYNTHETIC DATA - no real customers or payments)
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = ROOT / "data" / "payments.csv"

FIRST_NAMES = [
    "Aarav", "Vivaan", "Aditya", "Arjun", "Rohan", "Kabir", "Ishaan", "Rahul",
    "Ananya", "Diya", "Isha", "Kavya", "Meera", "Neha", "Priya", "Riya",
    "Sanjay", "Vikram", "Karan", "Nikhil", "Pooja", "Sneha", "Tanvi", "Zoya",
]
LAST_NAMES = [
    "Sharma", "Verma", "Gupta", "Patel", "Singh", "Mehta", "Iyer", "Nair",
    "Reddy", "Joshi", "Kulkarni", "Das", "Bose", "Khan", "Malhotra", "Chopra",
]

PAYMENT_METHODS = ["card", "upi", "netbanking", "wallet"]
METHOD_WEIGHTS = [0.30, 0.45, 0.15, 0.10]

# Failure-reason mix depends on payment method (rows sum to 1).
REASONS = [
    "insufficient_funds", "expired_card", "bank_declined", "gateway_error",
    "incorrect_details", "network_error", "authentication_failed", "unknown",
]
REASON_MIX = {
    "card":       [0.24, 0.20, 0.18, 0.08, 0.08, 0.04, 0.14, 0.04],
    "upi":        [0.30, 0.00, 0.14, 0.14, 0.06, 0.22, 0.08, 0.06],
    "netbanking": [0.18, 0.00, 0.20, 0.18, 0.06, 0.20, 0.12, 0.06],
    "wallet":     [0.38, 0.00, 0.06, 0.16, 0.06, 0.18, 0.04, 0.12],
}

# How recoverable each reason is, as a log-odds shift.
REASON_EFFECT = {
    "gateway_error": 1.7,
    "network_error": 1.4,
    "insufficient_funds": 0.2,
    "bank_declined": -0.1,
    "authentication_failed": -0.3,
    "expired_card": -0.6,
    "incorrect_details": -0.8,
    "unknown": -0.7,
}
METHOD_EFFECT = {"card": 0.0, "upi": 0.15, "netbanking": -0.05, "wallet": -0.1}
SUBSCRIPTION_EFFECT = {"active": 0.45, "past_due": -0.1, "cancelled": -0.8, "none": 0.0}


def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


def build_customers(rng, n):
    ids = [f"C{i:04d}" for i in range(1, n + 1)]
    ctype = rng.choice(["new", "returning", "vip"], size=n, p=[0.30, 0.50, 0.20])

    # Latent per-customer payment risk: drives failed history and failure rate.
    risk = rng.beta(2, 6, size=n)

    prev_success = np.where(
        ctype == "new", rng.poisson(1.0, n),
        np.where(ctype == "returning", rng.poisson(8, n), rng.poisson(24, n)),
    )
    prev_failed = rng.poisson(0.2 + 4.0 * risk * (1 + 0.1 * np.minimum(prev_success, 20)), n)

    ltv_scale = np.where(ctype == "new", 1200, np.where(ctype == "returning", 9000, 42000))
    ltv = np.round(rng.lognormal(mean=np.log(ltv_scale), sigma=0.45, size=n), 2)
    ltv = np.where(prev_success == 0, np.round(ltv * 0.2, 2), ltv)

    sub_probs = {
        "new": [0.35, 0.05, 0.05, 0.55],
        "returning": [0.55, 0.12, 0.10, 0.23],
        "vip": [0.70, 0.08, 0.07, 0.15],
    }
    subs = np.array(
        [rng.choice(["active", "past_due", "cancelled", "none"], p=sub_probs[t]) for t in ctype]
    )

    names = [
        f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}" for _ in range(n)
    ]
    return pd.DataFrame(
        {
            "customerId": ids,
            "customerName": names,
            "customerType": ctype,
            "subscriptionStatus": subs,
            "customerLifetimeValue": ltv,
            "previousSuccessfulPayments": prev_success,
            "previousFailedPayments": prev_failed,
            "_risk": risk,
        }
    )


def build_payments(rng, customers, n_payments, days=60):
    cust_idx = rng.integers(0, len(customers), size=n_payments)
    c = customers.iloc[cust_idx].reset_index(drop=True)

    method = rng.choice(PAYMENT_METHODS, size=n_payments, p=METHOD_WEIGHTS)

    # Amount: log-normal, bigger for higher-value customers, in INR.
    type_mult = c["customerType"].map({"new": 0.8, "returning": 1.0, "vip": 1.6}).to_numpy()
    amount = rng.lognormal(mean=np.log(1500), sigma=0.9, size=n_payments) * type_mult
    amount = np.clip(np.round(amount, 0), 99, 150000)

    # Timestamps over the last `days` days, a bit busier on recent days.
    now = pd.Timestamp.now().floor("min")
    offsets = rng.beta(1.3, 1.0, size=n_payments) * days * 24 * 60
    ts = now - pd.to_timedelta(offsets, unit="m")

    # Failure probability rises with customer risk and for wallet/netbanking.
    method_fail = pd.Series(method).map(
        {"card": 0.00, "upi": 0.02, "netbanking": 0.03, "wallet": 0.04}
    ).to_numpy()
    p_fail = np.clip(0.07 + 0.30 * c["_risk"].to_numpy() + method_fail, 0.02, 0.60)
    u = rng.random(n_payments)
    pending = u > 0.98
    failed = (u < p_fail) & ~pending
    status = np.where(pending, "pending", np.where(failed, "failed", "success"))

    reasons = np.full(n_payments, "", dtype=object)
    for m in PAYMENT_METHODS:
        mask = failed & (method == m)
        if mask.any():
            reasons[mask] = rng.choice(REASONS, size=int(mask.sum()), p=REASON_MIX[m])

    # Previous recovery attempts only exist for failed payments; riskier = more tries.
    attempts = np.zeros(n_payments, dtype=int)
    lam = 0.35 + 1.6 * c["_risk"].to_numpy() + 0.25 * np.minimum(c["previousFailedPayments"].to_numpy(), 6) / 3
    attempts[failed] = np.minimum(rng.poisson(lam[failed]), 5)

    last_attempt = pd.Series(pd.NaT, index=range(n_payments), dtype="datetime64[ns]")
    gap_hours = rng.integers(1, 72, size=n_payments)
    has_attempt = failed & (attempts > 0)
    last_attempt[has_attempt] = ts[has_attempt] + pd.to_timedelta(gap_hours[has_attempt], unit="h")
    last_attempt = last_attempt.where(last_attempt <= now, pd.NaT)

    df = pd.DataFrame(
        {
            "customerId": c["customerId"],
            "customerName": c["customerName"],
            "amount": amount,
            "currency": "INR",
            "paymentMethod": method,
            "paymentStatus": status,
            "failureReason": reasons,
            "customerType": c["customerType"],
            "previousSuccessfulPayments": c["previousSuccessfulPayments"],
            "previousFailedPayments": c["previousFailedPayments"],
            "previousRecoveryAttempts": attempts,
            "subscriptionStatus": c["subscriptionStatus"],
            "customerLifetimeValue": c["customerLifetimeValue"],
            "timestamp": ts,
            "lastAttemptAt": last_attempt,
        }
    )
    return df


def assign_recovery_outcome(rng, df):
    """Draw `recoverable` (0/1) for failed payments from a noisy latent model."""
    f = df["paymentStatus"] == "failed"
    d = df[f]

    logit = (
        -0.35
        + d["failureReason"].map(REASON_EFFECT).to_numpy()
        + d["paymentMethod"].map(METHOD_EFFECT).to_numpy()
        + d["subscriptionStatus"].map(SUBSCRIPTION_EFFECT).to_numpy()
        + 0.38 * np.log1p(d["previousSuccessfulPayments"].to_numpy())
        - 0.28 * d["previousFailedPayments"].to_numpy()
        - 0.85 * d["previousRecoveryAttempts"].to_numpy()
        + 0.22 * (np.log1p(d["customerLifetimeValue"].to_numpy()) - 9.0)
        - 0.30 * np.log(d["amount"].to_numpy() / 1500.0)
    )
    # Repeated retry attempts on a bad profile look suspicious: extra penalty.
    logit -= 0.9 * (d["previousRecoveryAttempts"].to_numpy() >= 3)

    # Irreducible noise so the model cannot reach a perfect score.
    logit += rng.normal(0, 0.9, size=len(d))
    prob = sigmoid(logit)

    out = pd.Series(np.nan, index=df.index, dtype="float")
    out[f] = (rng.random(len(d)) < prob).astype(int)
    df["recoverable"] = out.astype("Int64")
    return df


def main():
    ap = argparse.ArgumentParser(description="Generate synthetic RecoverAI payments")
    ap.add_argument("--payments", type=int, default=10000)
    ap.add_argument("--customers", type=int, default=2500)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    rng = np.random.default_rng(args.seed)
    customers = build_customers(rng, args.customers)
    df = build_payments(rng, customers, args.payments)
    df = assign_recovery_outcome(rng, df)

    df = df.sort_values("timestamp").reset_index(drop=True)
    df.insert(0, "paymentId", [f"P{1000 + i}" for i in range(len(df))])
    df["timestamp"] = df["timestamp"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    df["lastAttemptAt"] = pd.to_datetime(df["lastAttemptAt"]).dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_PATH, index=False)

    # ---- sanity summary (computed from the generated data) ----
    failed = df[df["paymentStatus"] == "failed"]
    print(f"Saved {len(df):,} payments -> {OUT_PATH}")
    print(f"Customers used: {df['customerId'].nunique():,}")
    print(f"Status mix:\n{df['paymentStatus'].value_counts(normalize=True).round(3).to_string()}")
    print(f"\nFailed payments: {len(failed):,} ({len(failed) / len(df):.1%})")
    print(f"Overall recoverable rate (failed): {failed['recoverable'].astype(float).mean():.1%}")
    print("\nRecoverable rate by failure reason:")
    print(failed.groupby("failureReason")["recoverable"].apply(lambda s: s.astype(float).mean()).round(3).sort_values(ascending=False).to_string())
    print("\nRecoverable rate by previous recovery attempts:")
    print(failed.groupby("previousRecoveryAttempts")["recoverable"].apply(lambda s: s.astype(float).mean()).round(3).to_string())
    print("\nRecoverable rate by customer type:")
    print(failed.groupby("customerType")["recoverable"].apply(lambda s: s.astype(float).mean()).round(3).to_string())


if __name__ == "__main__":
    main()