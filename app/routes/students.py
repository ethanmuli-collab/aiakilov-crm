"""Students - business records, either converted from won leads or added directly."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from flask import Blueprint, flash, redirect, render_template, request, url_for

from ..services import db
from ..services.auth_service import permission_required

bp = Blueprint("students", __name__, url_prefix="/students")
PAGE_SIZE = 25


@bp.route("/")
@permission_required("students.view")
def index():
    q = (request.args.get("q") or "").strip()
    page = max(1, request.args.get("page", 1, type=int))
    where, params = "1=1", []
    if q:
        where = "(s.first_name LIKE ? OR s.last_name LIKE ? OR s.email LIKE ?)"
        params = [f"%{q}%"] * 3

    total = db.query_one(
        f"SELECT COUNT(*) c FROM aiakilov_students s WHERE {where}", tuple(params)
    )["c"]
    students = db.query(
        "SELECT s.*, "
        "(SELECT COUNT(*) FROM aiakilov_enrollments e WHERE e.student_id = s.id) courses, "
        "(SELECT COALESCE(SUM(e.price), 0) FROM aiakilov_enrollments e "
        " WHERE e.student_id = s.id AND e.payment_status = 'paid') paid "
        f"FROM aiakilov_students s WHERE {where} ORDER BY s.created_at DESC LIMIT ? OFFSET ?",
        tuple(params) + (PAGE_SIZE, (page - 1) * PAGE_SIZE),
    )
    return render_template(
        "students/index.html", students=students, total=total,
        page=page, pages=max(1, -(-total // PAGE_SIZE)), q=q,
    )


@bp.route("/new", methods=["GET", "POST"])
@permission_required("students.edit")
def create():
    if request.method == "POST":
        errors = _validate(request.form)
        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("students/form.html", student=request.form,
                                   errors=errors), 400
        student_id = str(uuid.uuid4())
        db.execute(
            "INSERT INTO aiakilov_students (id, lead_id, first_name, last_name, email,"
            " phone, city, created_at) VALUES (?,?,?,?,?,?,?,?)",
            (student_id, None, request.form.get("first_name", "").strip(),
             request.form.get("last_name", "").strip(),
             request.form.get("email", "").strip() or None,
             request.form.get("phone", "").strip() or None,
             request.form.get("city", "").strip() or None,
             datetime.now(timezone.utc).isoformat(timespec="seconds")),
        )
        flash("התלמיד נוצר בהצלחה", "success")
        return redirect(url_for("students.detail", student_id=student_id))
    return render_template("students/form.html", student={}, errors=[])


@bp.route("/<student_id>")
@permission_required("students.view")
def detail(student_id: str):
    student = db.query_one("SELECT * FROM aiakilov_students WHERE id = ?", (student_id,))
    if not student:
        return render_template("errors/404.html"), 404
    enrollments = db.query(
        "SELECT e.*, c.name course_name, c.lecturer FROM aiakilov_enrollments e "
        "JOIN aiakilov_courses c ON c.id = e.course_id WHERE e.student_id = ? "
        "ORDER BY e.enrollment_date DESC",
        (student_id,),
    )
    invoices = db.query(
        "SELECT i.*, c.name course_name FROM aiakilov_invoices i "
        "JOIN aiakilov_courses c ON c.id = i.course_id WHERE i.student_id = ? "
        "ORDER BY i.issue_date DESC",
        (student_id,),
    )
    return render_template(
        "students/detail.html", student=student, enrollments=enrollments,
        invoices=invoices, payment_he=db.PAYMENT_HE,
    )


# --------------------------------------------------------------------------- helpers

def _validate(form) -> list[str]:
    errors = []
    if not (form.get("first_name") or "").strip() or not (form.get("last_name") or "").strip():
        errors.append("שם פרטי ושם משפחה הם שדות חובה")
    email = (form.get("email") or "").strip()
    if email and "@" not in email:
        errors.append("כתובת אימייל אינה תקינה")
    return errors
