"""Authentication + a deliberately small role-based permission layer.

Demo mode (default): pick one of the seeded CRM users, no password. Clearly
labelled in the UI as a demo environment.
Supabase mode: when SUPABASE_URL / SUPABASE_ANON_KEY are configured and
AIAKILOV_DEMO_MODE=false, sign-in is delegated to Supabase Auth and the role is
read from `aiakilov_profiles`.
"""

from __future__ import annotations

from functools import wraps

from flask import flash, redirect, session, url_for

from . import db

ROLES = ["ADMIN", "SALES", "COURSE_MANAGER", "LECTURER", "MARKETING", "MANAGEMENT"]
ROLE_HE = {
    "ADMIN": "מנהל מערכת",
    "SALES": "מכירות",
    "COURSE_MANAGER": "מנהל קורסים",
    "LECTURER": "מרצה",
    "MARKETING": "שיווק",
    "MANAGEMENT": "הנהלה",
}

# permission -> roles allowed. Intentionally a flat map, not an IAM engine.
PERMISSIONS: dict[str, set[str]] = {
    "leads.view": {"ADMIN", "SALES", "MARKETING", "MANAGEMENT"},
    "leads.edit": {"ADMIN", "SALES"},
    "leads.delete": {"ADMIN"},
    "courses.view": {"ADMIN", "SALES", "COURSE_MANAGER", "LECTURER", "MANAGEMENT"},
    "courses.edit": {"ADMIN", "COURSE_MANAGER"},
    "students.view": {"ADMIN", "COURSE_MANAGER", "LECTURER", "MANAGEMENT"},
    "students.edit": {"ADMIN", "COURSE_MANAGER"},
    "enrollments.view": {"ADMIN", "COURSE_MANAGER", "MANAGEMENT"},
    "enrollments.edit": {"ADMIN", "COURSE_MANAGER"},
    "ml.view": {"ADMIN", "SALES", "MARKETING", "MANAGEMENT"},
    "reports.view": {"ADMIN", "COURSE_MANAGER", "MARKETING", "MANAGEMENT"},
    "users.manage": {"ADMIN"},
}


def current_user() -> dict | None:
    return session.get("user")


def can(permission: str) -> bool:
    user = current_user()
    if not user:
        return False
    if user["role"] == "ADMIN":
        return True
    return user["role"] in PERMISSIONS.get(permission, set())


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user():
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)

    return wrapped


def permission_required(permission: str):
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if not can(permission):
                flash("אין לך הרשאה לצפות בעמוד זה", "error")
                return redirect(url_for("dashboard.index"))
            return view(*args, **kwargs)

        return wrapped

    return decorator


def demo_users() -> list[dict]:
    return db.query("SELECT * FROM aiakilov_profiles ORDER BY role")


def login_demo(email: str) -> dict | None:
    user = db.query_one("SELECT * FROM aiakilov_profiles WHERE email = ?", (email,))
    if user:
        session["user"] = {
            "id": user["id"], "email": user["email"],
            "full_name": user["full_name"], "role": user["role"],
        }
    return user


def login_supabase(email: str, password: str) -> dict | None:  # pragma: no cover
    """Real Supabase Auth sign-in. Used when demo mode is off."""
    from .supabase_service import get_client

    client = get_client()
    if client is None:
        return None
    res = client.auth.sign_in_with_password({"email": email, "password": password})
    if not res or not res.user:
        return None
    profile = db.query_one("SELECT * FROM aiakilov_profiles WHERE email = ?", (email,))
    role = profile["role"] if profile else "SALES"
    session["user"] = {
        "id": res.user.id, "email": email,
        "full_name": (profile or {}).get("full_name", email), "role": role,
    }
    session["sb_access_token"] = res.session.access_token if res.session else None
    return session["user"]


def logout() -> None:
    session.clear()


def register_template_helpers(app):  # pragma: no cover
    app.jinja_env.globals["can"] = can
