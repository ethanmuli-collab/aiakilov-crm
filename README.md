# AIAKILOV CRM

> **⚠️ פרויקט לימודי / Educational project.**
> This is an academic student project, not a commercial product. The data is
> fully synthetic, payments are simulated, and the invoices are demonstration
> documents only — they are **not** legally compliant Israeli tax invoices.

A compact, demo-ready CRM for **AIAKILOV**, a fictional online AI course
academy. It manages the full commercial funnel — lead → pipeline → student →
enrolment → invoice — and layers a machine-learning purchase-probability model
on top of it. The interface is Hebrew, RTL, light-theme only.

---

## Educational objectives

1. Build a working CRM with a real relational data model.
2. Generate a synthetic dataset with **genuine predictive structure** rather
   than random noise.
3. Train and compare five classifiers on the same preprocessing pipeline.
4. Demonstrate **target-leakage avoidance** and a correct train/test protocol.
5. Show why classification metrics — not regression metrics — decide the winner
   for a binary classification task.

---

## Features

| Area | What it does |
| --- | --- |
| **Dashboard** | 6 KPIs, 6 charts, sales-pipeline funnel, ML probability distribution |
| **Leads** | Table view + Kanban board with drag & drop, filters, pagination over 10,000 records |
| **Lead detail** | Contact + lead data, activity timeline, notes, follow-up tasks, live ML prediction with model switcher |
| **Pipeline** | 8 stages (New → … → Won / Lost), status change from table, board or detail page |
| **Conversion** | A `Won` lead converts to a Student, creating an enrolment and a demo invoice |
| **Courses** | 6 online courses with capacity, revenue and lead counts |
| **Students** | Student cards with all their enrolments and invoices (a student may buy several courses) |
| **Enrolments** | Payment-status management, totals, printable invoice |
| **ML models** | Side-by-side comparison of 5 models, confusion matrix, feature importance |
| **Prediction sandbox** | Score an ad-hoc lead profile with any trained model |
| **Reports** | Conversion by source, sales-rep performance, course revenue, payment breakdown |
| **API** | JSON endpoints with proper status codes and validation |
| **Auth** | 6 CRM roles with a role→permission map; Supabase Auth integration + demo mode |

---

## Architecture

```
Browser (Jinja templates, vanilla JS, Chart.js)
    │
Flask app (application factory)
    ├── routes/      auth · dashboard · leads · courses · students
    │                enrollments · predictions · reports · api
    ├── services/    db (SQLite) · supabase_service · auth_service · ml_service
    └── templates/   RTL Hebrew UI, Linear/Vercel-inspired light theme
    │
Data layer
    ├── SQLite  (demo mode, seeded from the synthetic CSV)   ← default
    └── Supabase / PostgreSQL  (aiakilov_* tables, RLS enabled)
    │
ML layer
    └── ml/artifacts/*.joblib  (sklearn Pipelines) + metrics.json
```

The SQLite tables mirror the Supabase schema one-to-one (same `aiakilov_*`
names and columns), so the demo never depends on network configuration while
the migration path stays a drop-in swap.

### Tech stack

Python 3.11+ · Flask 3 · Jinja2 · vanilla JS · Chart.js 4 · SQLite ·
Supabase/PostgreSQL · pandas · numpy · scikit-learn · XGBoost · LightGBM ·
CatBoost · pytest · ruff

---

## Pages

`/login` · `/` dashboard · `/leads/` table · `/leads/kanban` · `/leads/<id>`
· `/leads/new` · `/leads/<id>/edit` · `/courses/` · `/courses/<id>`
· `/students/` · `/students/<id>` · `/enrollments/`
· `/enrollments/invoice/<id>` · `/ml/models` · `/ml/predict` · `/reports/`
· `/settings` · `404` / `500`

---

## Database

Ten prefixed tables, all isolated under `aiakilov_`:

`aiakilov_profiles` · `aiakilov_leads` · `aiakilov_lead_activities` ·
`aiakilov_followups` · `aiakilov_courses` · `aiakilov_students` ·
`aiakilov_enrollments` · `aiakilov_payments` · `aiakilov_invoices` ·
`aiakilov_ml_predictions`

UUID primary keys, foreign keys with explicit delete behaviour, check
constraints on every enumerated column, and indexes on the columns the app
actually filters by. RLS is enabled on all ten tables with a read policy for
authenticated staff and role-scoped write policies for leads, courses and
enrolments.

Schema: `database/schema.sql` · seed: `database/seed.sql` · migration:
`database/migrations/0001_aiakilov_schema.sql`

---

## Synthetic dataset

`ml/generate_data.py` produces **10,000 leads** with `numpy` seed `42`.

The target is *not* random. Each lead gets a latent logit built from
pre-purchase signals only:

```
logit = -4.05
      + 1.55 · clip(budget / course_price, 0, 2.2)   # affordability
      + 0.185 · interaction_count                    # engagement
      + 0.62 · previous_ai_experience
      + source_effect      # Referral +1.05 … Instagram −0.35
      + course_effect + occupation_effect + education_effect + schedule_effect
      − 0.012 · |age − 31|
      + N(0, 0.55)                                   # irreducible noise
purchased ~ Bernoulli(sigmoid(logit))
```

Resulting positive rate: **27.2%** — a moderate, deliberate class imbalance.

**Injected data problems** (so preprocessing has real work to do):

* ~3–4.5% missing values in `budget`, `age`, `occupation`, `education`
* 25 extreme `budget` outliers (₪90k–₪250k) and 15 `interaction_count` outliers
* six categorical features requiring encoding

### Target-leakage avoidance

`status`, `payment_status`, enrolment existence and invoice existence are
generated **from** the target afterwards. They reveal the answer directly, so
they are excluded from the feature set and listed explicitly in
`train_models.LEAKY_COLUMNS_EXCLUDED` and on the ML Models page.

**Features used (10):** `age`, `budget`, `interaction_count`,
`previous_ai_experience`, `city`, `occupation`, `education`, `course_interest`,
`lead_source`, `preferred_schedule`.

---

## ML pipeline

**Split.** 80/20, stratified on the target, `random_state=42`.

**Preprocessing** — inside a `Pipeline`, so every transformer is fitted on the
training fold only and the test fold never leaks into imputation statistics,
scaling parameters or category vocabularies:

* numeric → median imputation, `StandardScaler` **only** for Logistic
  Regression (tree models don't need it)
* categorical → most-frequent imputation → `OneHotEncoder(handle_unknown="ignore")`

**Models.** Logistic Regression, Random Forest, XGBoost, LightGBM, CatBoost.
A model whose library is missing or fails to load is **skipped gracefully** and
shown as unavailable — one optional dependency can never break the CRM.

**Class imbalance.** The positive rate is ~27%, so every estimator is trained
class-weighted (`class_weight="balanced"` for Logistic Regression / Random
Forest / LightGBM, `scale_pos_weight` for XGBoost, `auto_class_weights="Balanced"`
for CatBoost) rather than left to treat the imbalance as noise.

**Decision threshold.** A fixed 0.5 cutoff under-predicts the minority class
here. Instead, the training script carves a validation split out of the
*training* fold only (never the test fold), grid-searches the threshold that
maximises F1 on that validation split, refits the final model on the full
training fold, and evaluates once on the untouched test fold using that tuned
threshold. ROC-AUC, log loss and Brier score are threshold-independent and use
raw probabilities regardless.

### Model comparison (test fold, n = 2,000)

This is **binary classification**, so only classification metrics are
reported — there is no MAE/RMSE/R² here; those are regression metrics and do
not apply to this task.

| Model | Accuracy | Precision | Recall | F1 | ROC-AUC | Log Loss | Threshold |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **CatBoost** ⭐ | 0.660 | 0.418 | 0.633 | 0.504 | **0.717** | 0.576 | 0.45 |
| Random Forest | 0.639 | 0.404 | 0.684 | 0.508 | 0.712 | 0.596 | 0.45 |
| XGBoost | 0.652 | 0.411 | 0.637 | 0.500 | 0.704 | 0.583 | 0.43 |
| Logistic Regression | 0.608 | 0.379 | 0.684 | 0.488 | 0.681 | 0.636 | 0.46 |
| LightGBM | see note below | | | | | | |

⭐ selected model, by ROC-AUC (tie-break F1) — never by accuracy, which is a
misleading metric here (predicting "nobody buys" alone scores ~73% accuracy
while being useless).

Note the F1 jump versus a naive 0.5 cutoff: class-weighting + threshold tuning
roughly doubled F1 on every model (e.g. Random Forest went from F1=0.144 to
0.508) while ROC-AUC — the threshold-independent ranking metric — barely
moved, confirming the models themselves didn't get worse, the *cutoff* was
just wrong for a 27%-positive dataset.

**Also reported:** confusion matrix and Brier score (probability calibration
quality).

Run `python ml/train_models.py` to regenerate; exact values come from
`ml/artifacts/metrics.json`.

---

## Installation

```bash
git clone https://github.com/ethanmuli-collab/aiakilov-crm.git
cd aiakilov-crm
python -m venv .venv && .venv\Scripts\activate     # Windows
pip install -r requirements.txt
```

### Environment variables

Copy `.env.example` to `.env` (never commit `.env`):

| Variable | Purpose |
| --- | --- |
| `FLASK_SECRET_KEY` | Flask session signing key |
| `AIAKILOV_DEMO_MODE` | `true` (default) = local SQLite + demo login |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_ANON_KEY` | Publishable/anon key |
| `SUPABASE_SERVICE_ROLE_KEY` | Server-side only. Never expose or commit. |

### Running locally

```bash
python ml/generate_data.py     # 10,000 synthetic leads  (optional, CSV is committed)
python ml/train_models.py      # train + write ml/artifacts/metrics.json
python run.py                  # http://localhost:5000
```

The SQLite database is created and seeded automatically on first run.
Sign in as any of the six demo users (Admin, Sales, Course Manager, Lecturer,
Marketing, Management) — no password in demo mode.

### Testing

```bash
python -m pytest        # 52 tests
python -m ruff check .
```

---

## Supabase setup

The project has its **own dedicated Supabase project** — `aiakilov-crm`
(`hgkgzrkhlnuqtfoyfeug`, `eu-central-1`), not a shared one. Its schema is
already applied and seeded (6 courses, 6 profiles, 240 sample leads), with RLS
enabled on all ten tables.

* Project URL: `https://hgkgzrkhlnuqtfoyfeug.supabase.co`
* The `anon`/publishable key is safe to commit (`.env.example` already has it)
  — RLS is what actually protects the data, not key secrecy. The
  `service_role` key is never printed, logged or committed anywhere.

To reproduce this setup (or point at a different project) from scratch:

1. Run `database/schema.sql` in the SQL editor — it is **additive only**: no
   `DROP`, no `CASCADE`, no `TRUNCATE`, and every object is `aiakilov_`-prefixed.
2. Run `database/seed.sql` for courses, profiles and a 500-lead sample.
3. Create the CRM users in Supabase Auth and link each `auth.users.id` into
   `aiakilov_profiles.user_id`, setting the appropriate role.
4. Set `SUPABASE_URL` / `SUPABASE_ANON_KEY` in `.env` and
   `AIAKILOV_DEMO_MODE=false`.

RLS is enabled on all ten tables: authenticated staff can read; writes to
leads are limited to ADMIN/SALES, and courses & enrolments to
ADMIN/COURSE_MANAGER, via the `aiakilov_current_role()` helper.

**Note:** the running app still defaults to `AIAKILOV_DEMO_MODE=true` (local
SQLite), by deliberate choice — see Known Limitations. The dedicated Supabase
project above is fully provisioned and ready whenever real Supabase Auth /
Postgres is wired in.

---

## API

| Method | Endpoint | Notes |
| --- | --- | --- |
| `GET` | `/api/leads?limit=&offset=&status=` | 400 on invalid status |
| `GET` | `/api/leads/<id>` | includes the ML prediction; 404 if missing |
| `POST` | `/api/leads` | 201 on success, 422 with field-level errors |
| `GET` | `/api/courses` | |
| `POST` | `/api/predict` | 400 on bad body/model, 503 if no model is trained |
| `GET` | `/api/models/metrics` | full `metrics.json` |

All endpoints require an authenticated session.

---

## Roles and permissions

CRM is internal only — **students are business records, not login users.**

| Role | Access |
| --- | --- |
| `ADMIN` | Everything, including deletion and user management |
| `SALES` | View/create/update leads, change pipeline, notes, follow-ups, ML predictions |
| `COURSE_MANAGER` | Courses, students, enrolments, reports |
| `LECTURER` | Read courses and related students; no deletion |
| `MARKETING` | Read leads, source/campaign reports, conversion analytics |
| `MANAGEMENT` | Dashboards, reports, revenue, ML analytics |

Defined as a flat `permission → {roles}` map in
`app/services/auth_service.py`. Deliberately not an enterprise IAM.

---

## Known limitations

* **Demo mode by default.** Login has no password; it is clearly labelled in
  the UI. Supabase Auth code is written and documented but the demo runs on
  SQLite so it never depends on external configuration.
* **LightGBM unavailable** on the build machine (OS Application Control blocked
  its native DLL). The app reports it as unavailable rather than failing.
* **Invoices are demo documents**, not valid Israeli tax invoices. No PDF
  export — printable HTML only.
* **No real payment provider.** Payment status is edited manually.
* Supabase holds the schema plus a 240-row in-database lead sample; the full
  10,000 rows live in `data/synthetic_leads.csv` and the local SQLite database.
* Kanban shows up to 20 cards per column for performance on 10,000 leads.
* Leads-table ML scoring is computed per visible page, so the probability
  filter applies within the current page.
* No SHAP explanations — feature importances and LR coefficients only.

---

## Future deployment

Not deployed. See `docs/07 - Deployment.md`. The app is deployment-ready:
environment-driven config, no hard-coded secrets, a WSGI entry point in
`run.py`, and committed ML artifacts. A future deploy needs a Render/Railway
web service running `gunicorn "app:create_app()"`, the Supabase environment
variables, and `ml/artifacts/` present in the image.

---

## Project structure

```
app/           Flask application (routes, services, templates, static)
ml/            generate_data.py · train_models.py · artifacts/
data/          synthetic_leads.csv (10,000 rows) · aiakilov.db (generated)
database/      schema.sql · seed.sql · migrations/
tests/         test_app.py · test_routes.py · test_ml.py  (52 tests)
docs/          project documentation
run.py         entry point
```
