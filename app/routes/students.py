"""Students - business records converted from won leads."""

from __future__ import annotations

from flask import Blueprint, render_template, request

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
