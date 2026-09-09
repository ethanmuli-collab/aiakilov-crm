"""Enrolments and demo invoices."""

from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for

from ..services import db
from ..services.auth_service import permission_required

bp = Blueprint("enrollments", __name__, url_prefix="/enrollments")
PAGE_SIZE = 30


@bp.route("/")
@permission_required("enrollments.view")
def index():
    status = request.args.get("payment_status")
    page = max(1, request.args.get("page", 1, type=int))
    where, params = "1=1", []
    if status in db.PAYMENT_STATUSES:
        where, params = "e.payment_status = ?", [status]

    total = db.query_one(
        f"SELECT COUNT(*) c FROM aiakilov_enrollments e WHERE {where}", tuple(params)
    )["c"]
    rows = db.query(
        "SELECT e.*, s.first_name, s.last_name, c.name course_name, "
        "(SELECT i.id FROM aiakilov_invoices i WHERE i.enrollment_id = e.id) invoice_id "
        "FROM aiakilov_enrollments e "
        "JOIN aiakilov_students s ON s.id = e.student_id "
        "JOIN aiakilov_courses c ON c.id = e.course_id "
        f"WHERE {where} ORDER BY e.enrollment_date DESC LIMIT ? OFFSET ?",
        tuple(params) + (PAGE_SIZE, (page - 1) * PAGE_SIZE),
    )
    totals = db.query_one(
        "SELECT COUNT(*) n, "
        "COALESCE(SUM(CASE WHEN payment_status='paid' THEN price END), 0) paid, "
        "COALESCE(SUM(CASE WHEN payment_status='pending' THEN price END), 0) pending "
        "FROM aiakilov_enrollments"
    )
    return render_template(
        "enrollments/index.html", enrollments=rows, totals=totals, total=total,
        page=page, pages=max(1, -(-total // PAGE_SIZE)),
        payment_statuses=db.PAYMENT_STATUSES, payment_he=db.PAYMENT_HE, selected=status,
    )


@bp.route("/<enrollment_id>/payment", methods=["POST"])
@permission_required("enrollments.edit")
def set_payment(enrollment_id: str):
    status = request.form.get("payment_status")
    if status not in db.PAYMENT_STATUSES:
        flash("סטטוס תשלום לא חוקי", "error")
        return redirect(url_for("enrollments.index"))
    db.execute(
        "UPDATE aiakilov_enrollments SET payment_status = ? WHERE id = ?",
        (status, enrollment_id),
    )
    db.execute(
        "UPDATE aiakilov_invoices SET payment_status = ? WHERE enrollment_id = ?",
        (status, enrollment_id),
    )
    flash("סטטוס התשלום עודכן", "success")
    return redirect(request.referrer or url_for("enrollments.index"))


@bp.route("/invoice/<invoice_id>")
@permission_required("enrollments.view")
def invoice(invoice_id: str):
    inv = db.query_one(
        "SELECT i.*, s.first_name, s.last_name, s.email, s.city, c.name course_name "
        "FROM aiakilov_invoices i "
        "JOIN aiakilov_students s ON s.id = i.student_id "
        "JOIN aiakilov_courses c ON c.id = i.course_id WHERE i.id = ?",
        (invoice_id,),
    )
    if not inv:
        return render_template("errors/404.html"), 404
    return render_template("invoices/invoice.html", inv=inv, payment_he=db.PAYMENT_HE)
