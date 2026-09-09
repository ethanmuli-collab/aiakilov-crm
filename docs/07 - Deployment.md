# Deployment — Railway

**Live:** https://zooming-imagination-production-8369.up.railway.app
(Railway project `humorous-creation`, service `zooming-imagination`,
deployed from `main` via GitHub, US West region.)

## Target

Railway, via `Procfile` + `requirements.txt` (Nixpacks/Railpack auto-detects
Python).

## What's deployment-ready in the repo

1. **Web service**
   - `Procfile`: `web: gunicorn run:app --bind 0.0.0.0:$PORT --workers 1 --timeout 60`
   - `run.py` exposes `app = create_app()` at module level — that's the
     `run:app` gunicorn target
   - **1 worker, deliberately.** `db.init_db()` seeds SQLite on first boot by
     checking `if seeded == 0`; two workers cold-starting together could both
     pass that check before either finishes inserting the 10,000-row seed,
     causing duplicate rows or a `database is locked` error. A single worker
     is correctness-safe and plenty for a low-traffic demo link.
   - `.python-version` pins `3.12` — a well-supported version with prebuilt
     Linux wheels for xgboost/lightgbm/catboost (avoids build-from-source on
     a brand-new Python release)

2. **Environment variables** (set in Railway's dashboard, never committed)
   - `FLASK_SECRET_KEY` — a real random secret, not the dev default
   - `AIAKILOV_DEMO_MODE=true` — demo login (pick a user, no password) is the
     right choice for sharing a link with an instructor; flip to `false` only
     once Supabase Auth is actually wired up (see `03 - Database.md`)

3. **Database** — nothing to do at deploy time. `data/aiakilov.db` is
   ephemeral and regenerated from `data/synthetic_leads.csv` on first boot
   (both committed) — every fresh deploy or restart gives a clean, fully
   seeded demo state, which is actually desirable here.

4. **ML artifacts** — `ml/artifacts/*.joblib` and `metrics.json` are committed
   to the repo, so a standard build ships them; no training step needed at
   deploy time.

## Deploy steps

1. Railway dashboard → New Project → **Deploy from GitHub repo** →
   `ethanmuli-collab/aiakilov-crm`, branch `main`.
2. Set `FLASK_SECRET_KEY` (generate one) and `AIAKILOV_DEMO_MODE=true` in the
   service's Variables tab.
3. Railway auto-detects the `Procfile`; first build took ~2 minutes (all
   packages, catboost/lightgbm included, installed from prebuilt wheels - no
   compilation needed).
4. **Public URL is not automatic** - Settings → Networking → Public
   Networking → Generate Domain, port `8080` (Railway's `$PORT` for this
   deploy). Only then does the `*.up.railway.app` domain exist. A custom
   domain isn't necessary for this.

Actual result: https://zooming-imagination-production-8369.up.railway.app —
verified end-to-end (login, dashboard, all 5 ML models including LightGBM,
which loads fine on Railway's Linux container - the Windows Application
Control block never applied there).

## Known limitation of this deploy shape

Filesystem storage on Railway isn't guaranteed persistent across redeploys —
by design here, since a clean reseed on every restart is a feature, not a bug,
for a demo link. If this ever needs to hold real, persisted state, the SQLite
file would need a Railway volume, or the app would need to actually switch to
the dedicated Supabase project instead (already provisioned and ready — see
`03 - Database.md`).
