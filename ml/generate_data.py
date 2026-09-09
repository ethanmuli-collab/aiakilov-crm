"""Generate 10,000 synthetic AIAKILOV leads with realistic predictive structure.

Design rules (see docs / README):
  * The target `purchased` is NOT random - it is driven by a latent logit built
    from features that are genuinely known BEFORE a purchase decision.
  * No leakage: `status`, `payment_status`, enrolments and invoices are derived
    FROM the target afterwards, and are excluded from the model feature set.
  * Controlled data problems are injected on purpose (missing values, outliers,
    class imbalance) so the preprocessing pipeline has something to do.
"""

from __future__ import annotations

import os

import numpy as np
import pandas as pd

SEED = 42
N_ROWS = 10_000

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_CSV = os.path.join(BASE_DIR, "data", "synthetic_leads.csv")

LEAD_SOURCES = [
    "Facebook",
    "Instagram",
    "Google Ads",
    "Website",
    "Referral",
    "Organic",
    "WhatsApp",
    "Event",
]
SOURCE_WEIGHTS = [0.20, 0.16, 0.15, 0.14, 0.08, 0.12, 0.10, 0.05]
# Referral / Event convert far better than cold social traffic.
SOURCE_EFFECT = {
    "Facebook": -0.25,
    "Instagram": -0.35,
    "Google Ads": 0.20,
    "Website": 0.30,
    "Referral": 1.05,
    "Organic": 0.35,
    "WhatsApp": 0.10,
    "Event": 0.75,
}

COURSES = [
    "Python for AI",
    "Machine Learning",
    "AI Automation",
    "Prompt Engineering",
    "AI Agents",
    "Data Science",
]
COURSE_WEIGHTS = [0.24, 0.18, 0.16, 0.18, 0.12, 0.12]
COURSE_EFFECT = {
    "Python for AI": 0.30,
    "Machine Learning": 0.05,
    "AI Automation": 0.35,
    "Prompt Engineering": 0.45,
    "AI Agents": -0.05,
    "Data Science": -0.15,
}
COURSE_PRICE = {
    "Python for AI": 3900,
    "Machine Learning": 6400,
    "AI Automation": 4500,
    "Prompt Engineering": 2900,
    "AI Agents": 5800,
    "Data Science": 7200,
}

OCCUPATIONS = [
    "מפתח תוכנה",
    "אנליסט",
    "סטודנט",
    "מנהל שיווק",
    "יזם",
    "מורה",
    "מעצב",
    "איש מכירות",
    "מהנדס",
    "אחר",
]
OCCUPATION_WEIGHTS = [0.16, 0.11, 0.15, 0.10, 0.08, 0.08, 0.07, 0.09, 0.10, 0.06]
OCCUPATION_EFFECT = {
    "מפתח תוכנה": 0.55,
    "אנליסט": 0.40,
    "סטודנט": -0.45,
    "מנהל שיווק": 0.20,
    "יזם": 0.35,
    "מורה": -0.10,
    "מעצב": 0.00,
    "איש מכירות": 0.10,
    "מהנדס": 0.30,
    "אחר": -0.15,
}

EDUCATIONS = ["תיכונית", "הנדסאי", "תואר ראשון", "תואר שני", "דוקטורט"]
EDUCATION_WEIGHTS = [0.18, 0.14, 0.40, 0.23, 0.05]
EDUCATION_EFFECT = {
    "תיכונית": -0.30,
    "הנדסאי": 0.00,
    "תואר ראשון": 0.20,
    "תואר שני": 0.40,
    "דוקטורט": 0.45,
}

SCHEDULES = ["בוקר", "ערב", "סופ\"ש", "גמיש"]
SCHEDULE_WEIGHTS = [0.18, 0.42, 0.20, 0.20]
SCHEDULE_EFFECT = {"בוקר": -0.20, "ערב": 0.25, "סופ\"ש": 0.05, "גמיש": 0.45}

CITIES = [
    "תל אביב",
    "ירושלים",
    "חיפה",
    "באר שבע",
    "ראשון לציון",
    "פתח תקווה",
    "נתניה",
    "רמת גן",
    "אשדוד",
    "הרצליה",
    "רעננה",
    "מודיעין",
]
CITY_WEIGHTS = [0.18, 0.10, 0.09, 0.07, 0.09, 0.08, 0.07, 0.07, 0.06, 0.07, 0.06, 0.06]

SALES_REPS = ["דנה לוי", "יוסי כהן", "מאיה בר", "אורי שרון", "נועה גל"]

FIRST_NAMES = [
    "אביב", "נועה", "איתי", "שירה", "יונתן", "מיכל", "עומר", "תמר", "רון", "יעל",
    "גיא", "ליאור", "אורי", "הדר", "אלון", "רותם", "עידו", "טל", "נדב", "שני",
    "אסף", "מור", "דור", "ענבר", "יובל", "אורן", "גלי", "ניר", "עדי", "רועי",
]
LAST_NAMES = [
    "כהן", "לוי", "מזרחי", "פרץ", "ביטון", "אברהם", "פרידמן", "שפירא", "אזולאי",
    "דהן", "אוחיון", "גבאי", "אשכנזי", "סלומון", "ברק", "רוזן", "שגב", "נחום",
]

STATUS_NON_BUYER = ["New", "Contacted", "Interested", "Follow-up", "Counseling", "Offer Sent", "Lost"]
STATUS_NON_BUYER_W = [0.20, 0.18, 0.14, 0.12, 0.08, 0.08, 0.20]


def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-x))


def generate(n: int = N_ROWS, seed: int = SEED) -> pd.DataFrame:
    rng = np.random.default_rng(seed)

    age = np.clip(rng.normal(33, 9, n), 18, 68).round().astype(int)
    course = rng.choice(COURSES, n, p=COURSE_WEIGHTS)
    source = rng.choice(LEAD_SOURCES, n, p=SOURCE_WEIGHTS)
    occupation = rng.choice(OCCUPATIONS, n, p=OCCUPATION_WEIGHTS)
    education = rng.choice(EDUCATIONS, n, p=EDUCATION_WEIGHTS)
    schedule = rng.choice(SCHEDULES, n, p=SCHEDULE_WEIGHTS)
    city = rng.choice(CITIES, n, p=CITY_WEIGHTS)
    prev_ai = rng.choice([0, 1], n, p=[0.62, 0.38])

    # Budget correlates with the course of interest and education level.
    course_price = np.array([COURSE_PRICE[c] for c in course], dtype=float)
    edu_bonus = np.array([EDUCATION_EFFECT[e] for e in education]) * 900
    budget = np.clip(rng.normal(course_price * 0.85 + edu_bonus, 1600), 500, 25000).round(-1)

    # Interaction count: warmer sources produce more interactions.
    src_eff = np.array([SOURCE_EFFECT[s] for s in source])
    interactions = np.clip(rng.poisson(np.clip(2.6 + src_eff * 1.4, 0.4, None)), 0, 25)

    days_since_created = rng.integers(0, 180, n)

    # ---- latent logit: real structure, all pre-purchase signals only ----
    budget_ratio = budget / course_price  # can the lead actually afford it?
    logit = (
        -4.05
        + 1.55 * np.clip(budget_ratio, 0, 2.2)
        + 0.185 * interactions
        + 0.62 * prev_ai
        + src_eff
        + np.array([COURSE_EFFECT[c] for c in course])
        + np.array([OCCUPATION_EFFECT[o] for o in occupation])
        + np.array([EDUCATION_EFFECT[e] for e in education])
        + np.array([SCHEDULE_EFFECT[s] for s in schedule])
        - 0.012 * np.abs(age - 31)
        + rng.normal(0, 0.55, n)  # irreducible noise -> AUC stays realistic
    )
    prob = _sigmoid(logit)
    purchased = (rng.random(n) < prob).astype(int)

    first = rng.choice(FIRST_NAMES, n)
    last = rng.choice(LAST_NAMES, n)

    df = pd.DataFrame(
        {
            "first_name": first,
            "last_name": last,
            "email": [
                f"{i}.{a}.{b}@example.com".replace(" ", "")
                for i, (a, b) in enumerate(zip(first, last))
            ],
            "phone": ["05" + str(rng.integers(10000000, 99999999)) for _ in range(n)],
            "age": age,
            "city": city,
            "occupation": occupation,
            "education": education,
            "course_interest": course,
            "lead_source": source,
            "budget": budget,
            "preferred_schedule": schedule,
            "previous_ai_experience": prev_ai,
            "interaction_count": interactions,
            "assigned_sales_rep": rng.choice(SALES_REPS, n),
            "days_since_created": days_since_created,
            "purchased": purchased,
        }
    )

    # ---- post-hoc fields DERIVED from the target (leaky - never used as features) ----
    status = np.where(
        df["purchased"] == 1,
        "Won",
        rng.choice(STATUS_NON_BUYER, n, p=STATUS_NON_BUYER_W),
    )
    df["status"] = status
    df["payment_status"] = np.where(df["purchased"] == 1, "paid", "pending")

    # ---- injected data-quality problems (educational preprocessing) ----
    for col, frac in (("budget", 0.045), ("age", 0.03), ("occupation", 0.04), ("education", 0.035)):
        idx = rng.choice(n, size=int(n * frac), replace=False)
        df.loc[idx, col] = np.nan

    # A handful of numeric outliers.
    out_idx = rng.choice(n, size=25, replace=False)
    df.loc[out_idx, "budget"] = rng.uniform(90000, 250000, size=25).round(-2)
    out_idx2 = rng.choice(n, size=15, replace=False)
    df.loc[out_idx2, "interaction_count"] = rng.integers(80, 160, size=15)

    return df


def main() -> None:
    df = generate()
    os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
    df.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
    rate = df["purchased"].mean()
    print(f"wrote {len(df):,} rows -> {OUT_CSV}")
    print(f"purchase rate: {rate:.3%}  (class balance {1 - rate:.1%} / {rate:.1%})")
    print("missing values per column:")
    print(df.isna().sum()[df.isna().sum() > 0].to_string())


if __name__ == "__main__":
    main()
