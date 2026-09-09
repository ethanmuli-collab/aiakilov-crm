"""Login / logout. Demo mode by default, Supabase Auth when configured."""

from __future__ import annotations

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for

from ..services import auth_service

bp = Blueprint("auth", __name__)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip()
        if not email:
            flash("יש לבחור משתמש", "error")
            return render_template("login.html", users=auth_service.demo_users(),
                                   role_he=auth_service.ROLE_HE), 400

        if current_app.config["DEMO_MODE"]:
            user = auth_service.login_demo(email)
        else:  # pragma: no cover - requires a live Supabase project
            user = auth_service.login_supabase(email, request.form.get("password", ""))

        if not user:
            flash("ההתחברות נכשלה", "error")
            return render_template("login.html", users=auth_service.demo_users(),
                                   role_he=auth_service.ROLE_HE), 401
        return redirect(url_for("dashboard.index"))

    return render_template("login.html", users=auth_service.demo_users(),
                           role_he=auth_service.ROLE_HE)


@bp.route("/logout", methods=["POST", "GET"])
def logout():
    auth_service.logout()
    return redirect(url_for("auth.login"))
