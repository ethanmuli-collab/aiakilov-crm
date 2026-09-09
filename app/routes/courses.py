"""Course catalogue."""

from __future__ import annotations

from flask import Blueprint, render_template

from ..services import db
from ..services.auth_service import permission_required

bp = Blueprint("courses", __name__, url_prefix="/courses")


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
