"""Management dashboard: KPIs and chart data."""

from __future__ import annotations

from flask import Blueprint, render_template

from ..services import db, ml_service
from ..services.auth_service import login_required

bp = Blueprint("dashboard", __name__)


@bp.route("/")
@login_required
def index():
    total_leads = db.query_one("SELECT COUNT(*) c FROM aiakilov_leads")["c"]
    new_leads = db.query_one(
        "SELECT COUNT(*) c FROM aiakilov_leads WHERE status = 'New'")["c"]
    won_leads = db.query_one(
        "SELECT COUNT(*) c FROM aiakilov_leads WHERE status = 'Won'")["c"]
    students = db.query_one("SELECT COUNT(*) c FROM aiakilov_students")["c"]
    revenue = db.query_one(
        "SELECT COALESCE(SUM(price), 0) s FROM aiakilov_enrollments "
        "WHERE payment_status = 'paid'")["s"]
    avg_price = db.query_one("SELECT COALESCE(AVG(price), 0) a FROM aiakilov_courses")["a"]
    open_followups = db.query_one(
        "SELECT COUNT(*) c FROM aiakilov_followups WHERE done = 0")["c"]

    kpis = {
        "total_leads": total_leads,
        "new_leads": new_leads,
        "conversion_rate": (won_leads / total_leads) if total_leads else 0,
        "students": students,
        "revenue": revenue,
        "avg_course_price": avg_price,
        "open_followups": open_followups,
    }

    leads_over_time = db.query(
        "SELECT substr(created_at, 1, 7) m, COUNT(*) c FROM aiakilov_leads "
        "GROUP BY m ORDER BY m")
    revenue_over_time = db.query(
        "SELECT substr(enrollment_date, 1, 7) m, COALESCE(SUM(price), 0) s "
        "FROM aiakilov_enrollments WHERE payment_status = 'paid' GROUP BY m ORDER BY m")
    by_source = db.query(
        "SELECT lead_source src, COUNT(*) total, "
        "SUM(CASE WHEN status = 'Won' THEN 1 ELSE 0 END) won "
        "FROM aiakilov_leads GROUP BY src ORDER BY total DESC")
    by_status = db.query(
        "SELECT status, COUNT(*) c FROM aiakilov_leads GROUP BY status")
    by_course = db.query(
        "SELECT course_interest name, COUNT(*) c FROM aiakilov_leads "
        "GROUP BY name ORDER BY c DESC")

    status_order = {s: i for i, s in enumerate(db.LEAD_STATUSES)}
    by_status.sort(key=lambda r: status_order.get(r["status"], 99))

    # ML probability distribution over a fixed sample - keeps the page fast.
    sample = db.query("SELECT * FROM aiakilov_leads ORDER BY created_at DESC LIMIT 500")
    buckets = [0] * 10
    preds = ml_service.predict_batch(sample) if sample else []
    for p in preds:
        if "percent" in p:
            buckets[min(9, int(p["percent"] // 10))] += 1

    charts = {
        "leads_over_time": {
            "labels": [r["m"] for r in leads_over_time],
            "values": [r["c"] for r in leads_over_time],
        },
        "revenue_over_time": {
            "labels": [r["m"] for r in revenue_over_time],
            "values": [round(r["s"]) for r in revenue_over_time],
        },
        "conversion_by_source": {
            "labels": [db.SOURCE_HE.get(r["src"], r["src"]) for r in by_source],
            "values": [round(100 * r["won"] / r["total"], 1) if r["total"] else 0
                       for r in by_source],
        },
        "leads_by_status": {
            "labels": [db.STATUS_HE.get(r["status"], r["status"]) for r in by_status],
            "values": [r["c"] for r in by_status],
        },
        "leads_by_course": {
            "labels": [r["name"] for r in by_course],
            "values": [r["c"] for r in by_course],
        },
        "ml_distribution": {
            "labels": [f"{i * 10}-{i * 10 + 10}%" for i in range(10)],
            "values": buckets,
        },
    }

    pipeline = [
        {"status": s, "label": db.STATUS_HE.get(s, s),
         "count": next((r["c"] for r in by_status if r["status"] == s), 0)}
        for s in db.LEAD_STATUSES
    ]

    return render_template(
        "dashboard.html", kpis=kpis, charts=charts, pipeline=pipeline,
        best_model=ml_service.best_model_key(),
        metrics=ml_service.load_metrics(),
    )


@bp.route("/settings")
@login_required
def settings():
    from ..services import supabase_service
    from ..services.auth_service import ROLE_HE

    return render_template(
        "settings.html",
        supabase=supabase_service.status(),
        profiles=db.query("SELECT * FROM aiakilov_profiles ORDER BY role"),
        role_he=ROLE_HE,
        metrics=ml_service.load_metrics(),
    )
