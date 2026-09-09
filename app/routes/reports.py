"""Business reports: sources, courses, sales reps, revenue."""

from __future__ import annotations

from flask import Blueprint, render_template

from ..services import db
from ..services.auth_service import permission_required

bp = Blueprint("reports", __name__, url_prefix="/reports")


@bp.route("/")
@permission_required("reports.view")
def index():
    by_source = db.query(
        "SELECT lead_source src, COUNT(*) total, "
        "SUM(CASE WHEN status='Won' THEN 1 ELSE 0 END) won, "
        "ROUND(AVG(budget), 0) avg_budget FROM aiakilov_leads "
        "GROUP BY src ORDER BY total DESC"
    )
    by_rep = db.query(
        "SELECT assigned_sales_rep rep, COUNT(*) total, "
        "SUM(CASE WHEN status='Won' THEN 1 ELSE 0 END) won FROM aiakilov_leads "
        "WHERE assigned_sales_rep IS NOT NULL GROUP BY rep ORDER BY won DESC"
    )
    by_course = db.query(
        "SELECT c.name, c.price, "
        "(SELECT COUNT(*) FROM aiakilov_leads l WHERE l.course_interest = c.name) leads, "
        "(SELECT COUNT(*) FROM aiakilov_enrollments e WHERE e.course_id = c.id) enrolled, "
        "(SELECT COALESCE(SUM(e.price), 0) FROM aiakilov_enrollments e "
        " WHERE e.course_id = c.id AND e.payment_status='paid') revenue "
        "FROM aiakilov_courses c ORDER BY revenue DESC"
    )
    payments = db.query(
        "SELECT payment_status ps, COUNT(*) n, COALESCE(SUM(price), 0) amount "
        "FROM aiakilov_enrollments GROUP BY ps"
    )

    for row in by_source + by_rep:
        row["rate"] = (row["won"] / row["total"]) if row["total"] else 0

    charts = {
        "source_conversion": {
            "labels": [db.SOURCE_HE.get(r["src"], r["src"]) for r in by_source],
            "values": [round(r["rate"] * 100, 1) for r in by_source],
        },
        "course_revenue": {
            "labels": [r["name"] for r in by_course],
            "values": [round(r["revenue"]) for r in by_course],
        },
    }
    return render_template(
        "reports/index.html", by_source=by_source, by_rep=by_rep,
        by_course=by_course, payments=payments, charts=charts,
        source_he=db.SOURCE_HE, payment_he=db.PAYMENT_HE,
    )
