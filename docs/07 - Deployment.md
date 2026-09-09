# Deployment (not performed)

Per project instructions, no deployment was carried out in this session. This
file documents what a future deploy would need.

## Target

Any WSGI-capable host (Render, Railway, Fly.io). No infra was provisioned.

## Requirements for a future deploy

1. **Web service**
   - Build: `pip install -r requirements.txt`
   - Start: `gunicorn "app:create_app()"` (add `gunicorn` to `requirements.txt`)
   - Port: read from `$PORT` if the host requires it

2. **Environment variables** (set in the host's dashboard, never committed)
   - `FLASK_SECRET_KEY` — a real random secret, not the dev default
   - `AIAKILOV_DEMO_MODE=false` to require real Supabase Auth
   - `SUPABASE_URL`, `SUPABASE_ANON_KEY`
   - `SUPABASE_SERVICE_ROLE_KEY` — only if server-side admin operations are added later

3. **Database**
   - Apply `database/schema.sql` (already applied to the live Supabase project
     used during development — see the Supabase status in the final session
     report)
   - Run `database/seed.sql` for courses/profiles, or leave empty for a clean
     production start

4. **ML artifacts**
   - `ml/artifacts/*.joblib` and `metrics.json` must ship inside the deployed
     image/build — they are committed to the repo, so a standard build step
     is enough; no separate training job is required at deploy time
   - Optionally re-run `python ml/train_models.py` in a CI step before deploy
     to refresh metrics

5. **Public URL**
   - Once deployed, share the URL with the instructor; no additional DNS/TLS
     work is expected from a platform like Render/Railway (they provide it)

## Explicitly not done in this session

- No Render/Railway/Fly project was created
- No production Supabase project was created (the existing `systema` Supabase
  project was reused, isolated via `aiakilov_*` prefixing)
- No custom domain, TLS or CDN configuration
