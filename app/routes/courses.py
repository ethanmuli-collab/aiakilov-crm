"""Course catalogue."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from flask import Blueprint, flash, redirect, render_template, request, url_for

from ..services import db
from ..services.auth_service import permission_required

bp = Blueprint("courses", __name__, url_prefix="/courses")

DIFFICULTIES = ["מתחילים", "בינוני", "מתקדמים"]


@bp.route("/")
@permission_required("courses.view")
def index():
    courses = db.query(
        "SELECT c.*, "
        "(SELECT COUNT(*) FROM aiakilov_enrollments e WHERE e.course_id = c.id) enrolled, "
        "(SELECT COALESCE(SUM(e.price), 0) FROM aiakilov_enrollments e "
        " WHERE e.course_id = c.id AND e.payment_status = 'paid') revenue, "
        "(SELECT COUNT(*) FROM aiakilov_leads l WHERE l.course_interest = c.name) leads "
        "FROM aiakilov_courses c ORDER BY c.name"
    )
    return render_template("courses/index.html", courses=courses)


@bp.route("/new", methods=["GET", "POST"])
@permission_required("courses.edit")
def create():
    if request.method == "POST":
        errors = _validate(request.form)
        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("courses/form.html", course=request.form,
                                   errors=errors, difficulties=DIFFICULTIES), 400
        course_id = str(uuid.uuid4())
        db.execute(
            "INSERT INTO aiakilov_courses (id, name, description, price, start_date,"
            " end_date, lecturer, capacity, hours, difficulty, status, created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (course_id, *_form_values(request.form),
             datetime.now(timezone.utc).isoformat(timespec="seconds")),
        )
        flash("הקורס נוצר בהצלחה", "success")
        return redirect(url_for("courses.detail", course_id=course_id))
    return render_template("courses/form.html", course={}, errors=[], difficulties=DIFFICULTIES)


@bp.route("/<course_id>")
@permission_required("courses.view")
def detail(course_id: str):
    course = db.query_one("SELECT * FROM aiakilov_courses WHERE id = ?", (course_id,))
    if not course:
        return render_template("errors/404.html"), 404
    enrollments = db.query(
        "SELECT e.*, s.first_name, s.last_name, s.email FROM aiakilov_enrollments e "
        "JOIN aiakilov_students s ON s.id = e.student_id WHERE e.course_id = ? "
        "ORDER BY e.enrollment_date DESC LIMIT 50",
        (course_id,),
    )
    stats = db.query_one(
        "SELECT COUNT(*) enrolled, COALESCE(SUM(CASE WHEN payment_status='paid' "
        "THEN price ELSE 0 END), 0) revenue FROM aiakilov_enrollments WHERE course_id = ?",
        (course_id,),
    )
    return render_template(
        "courses/detail.html", course=course, enrollments=enrollments,
        stats=stats, payment_he=db.PAYMENT_HE,
    )


# --------------------------------------------------------------------------- helpers

def _validate(form) -> list[str]:
    errors = []
    if not (form.get("name") or "").strip():
        errors.append("שם הקורס הוא שדה חובה")
    price = (form.get("price") or "").strip()
    if not price:
        errors.append("מחיר הוא שדה חובה")
    else:
        try:
            if float(price) < 0:
                errors.append("מחיר לא יכול להיות שלילי")
        except ValueError:
            errors.append("מחיר חייב להיות מספר")
    for numeric, label in (("capacity", "קיבולת"), ("hours", "שעות")):
        value = (form.get(numeric) or "").strip()
        if value:
            try:
                if int(value) <= 0:
                    errors.append(f"{label} חייבת להיות מספר חיובי")
            except ValueError:
                errors.append(f"{label} חייבת להיות מספר")
    return errors


def _num(value, cast=float):
    try:
        return cast(float(value)) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _form_values(form) -> tuple:
    return (
        form.get("name", "").strip(), form.get("description", "").strip() or None,
        _num(form.get("price")) or 0, form.get("start_date") or None,
        form.get("end_date") or None, form.get("lecturer", "").strip() or None,
        _num(form.get("capacity"), int), _num(form.get("hours"), int),
        form.get("difficulty") or None, form.get("status") or "active",
    )
