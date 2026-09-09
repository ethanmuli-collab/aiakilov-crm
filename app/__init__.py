"""AIAKILOV CRM - Flask application factory."""

from __future__ import annotations

import os

from flask import Flask, render_template

try:  # optional dependency
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover
    pass


def create_app(config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "aiakilov-dev-secret")
    app.config["DEMO_MODE"] = os.getenv("AIAKILOV_DEMO_MODE", "true").lower() == "true"
    app.config["SUPABASE_URL"] = os.getenv("SUPABASE_URL", "")
    if config:
        app.config.update(config)

    from .services import db

    db.init_db()

    from .routes import (
        api,
        auth,
        courses,
        dashboard,
        enrollments,
        leads,
        predictions,
        reports,
        students,
    )

    app.register_blueprint(auth.bp)
    app.register_blueprint(dashboard.bp)
    app.register_blueprint(leads.bp)
    app.register_blueprint(courses.bp)
    app.register_blueprint(students.bp)
    app.register_blueprint(enrollments.bp)
    app.register_blueprint(predictions.bp)
    app.register_blueprint(reports.bp)
    app.register_blueprint(api.bp)

    @app.errorhandler(404)
    def not_found(_e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(_e):  # pragma: no cover
        return render_template("errors/500.html"), 500

    @app.context_processor
    def inject_globals():
        from .services.auth_service import current_user

        return {
            "current_user": current_user(),
            "demo_mode": app.config["DEMO_MODE"],
            "app_name": "AIAKILOV CRM",
        }

    app.jinja_env.filters["ils"] = lambda v: f"₪{float(v or 0):,.0f}"
    app.jinja_env.filters["pct"] = lambda v: f"{float(v or 0) * 100:.1f}%"

    from .services.auth_service import register_template_helpers

    register_template_helpers(app)

    return app
