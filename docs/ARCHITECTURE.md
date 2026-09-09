# Architecture

See the top-level [README.md](../README.md) for the full architecture diagram,
tech stack, database schema summary and ML pipeline description — this file
adds implementation notes that don't belong in the README.

## Request flow

```
Browser → Flask route (app/routes/*.py)
        → service layer (app/services/*.py)
        → SQLite (demo) or Supabase/PostgreSQL (aiakilov_* tables)
        → Jinja template (app/templates/*.html) → HTML response
```

Routes never touch SQL directly beyond calling `app/services/db.py` helpers
(`query`, `query_one`, `execute`) — all statements are parameterised, no
string-interpolated SQL.

## Why SQLite for the demo

The academic deliverable must run with zero external configuration. SQLite is
seeded once from `data/synthetic_leads.csv` on first boot
(`app/services/db.py: init_db`), and its table names/columns mirror the
Supabase schema exactly, so swapping the data layer to
`app/services/supabase_service.py` does not require touching route code.

## ML integration

`app/services/ml_service.py` loads pre-trained `joblib` pipelines from
`ml/artifacts/*.joblib` and reads `ml/artifacts/metrics.json` for the
comparison table. Training happens offline via `ml/train_models.py` — the
Flask app never trains a model at request time.

## Permission layer

A flat `permission -> {roles}` dict in `app/services/auth_service.py`,
enforced by the `@permission_required("x.y")` decorator on routes. `ADMIN`
always passes. This is intentionally not a general-purpose IAM system.
