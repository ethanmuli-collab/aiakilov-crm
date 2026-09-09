"""Lead pipeline: table view, kanban board, detail page and CRUD."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for

from ..services import db, ml_service
from ..services.auth_service import permission_required

bp = Blueprint("leads", __name__, url_prefix="/leads")

PAGE_SIZE = 25
REQUIRED_FIELDS = ("first_name", "last_name")


def _filters_from_request() -> tuple[str, list]:
    """Build a parameterised WHERE clause - no string interpolation of values."""
    clauses, params = ["1=1"], []
    q = (request.args.get("q") or "").strip()
    if q:
        clauses.append("(first_name LIKE ? OR last_name LIKE ? OR email LIKE ? OR phone LIKE ?)")
        params += [f"%{q}%"] * 4
    for field, arg in (
        ("status", "status"),
        ("course_interest", "course"),
        ("lead_source", "source"),
        ("assigned_sales_rep", "rep"),
    ):
        value = request.args.get(arg)
        if value:
            clauses.append(f"{field} = ?")
            params.append(value)
    date_from = request.args.get("from")
    if date_from:
        clauses.append("created_at >= ?")
        params.append(date_from)
    return " AND ".join(clauses), params


def _filter_options() -> dict:
    return {
        "statuses": db.LEAD_STATUSES,
        "status_he": db.STATUS_HE,
        "sources": db.LEAD_SOURCES,
        "source_he": db.SOURCE_HE,
        "courses": [r["name"] for r in db.query("SELECT name FROM aiakilov_courses ORDER BY name")],
        "reps": [r["assigned_sales_rep"] for r in db.query(
            "SELECT DISTINCT assigned_sales_rep FROM aiakilov_leads "
            "WHERE assigned_sales_rep IS NOT NULL ORDER BY 1")],
    }


@bp.route("/")
@permission_required("leads.view")
def index():
    where, params = _filters_from_request()
    page = max(1, request.args.get("page", 1, type=int))
    total = db.query_one(f"SELECT COUNT(*) c FROM aiakilov_leads WHERE {where}", tuple(params))["c"]
    rows = db.query(
        f"SELECT * FROM aiakilov_leads WHERE {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
        tuple(params) + (PAGE_SIZE, (page - 1) * PAGE_SIZE),
    )

    # Score the visible page only - keeps the table fast on 10k leads.
    min_prob = request.args.get("min_prob", type=float)
    if rows:
        for lead, pred in zip(rows, ml_service.predict_batch(rows)):
            lead["prediction"] = pred
        if min_prob is not None:
            rows = [r for r in rows if (r["prediction"].get("percent") or 0) >= min_prob]

    return render_template(
        "leads/index.html",
        leads=rows, page=page, page_size=PAGE_SIZE, total=total,
        pages=max(1, -(-total // PAGE_SIZE)), args=request.args,
        payment_he=db.PAYMENT_HE, **_filter_options(),
    )


@bp.route("/kanban")
@permission_required("leads.view")
def kanban():
    where, params = _filters_from_request()
    columns = {}
    for status in db.LEAD_STATUSES:
        columns[status] = db.query(
            f"SELECT * FROM aiakilov_leads WHERE {where} AND status = ? "
            "ORDER BY created_at DESC LIMIT 20",
            tuple(params) + (status,),
        )
    counts = {
        r["status"]: r["c"]
        for r in db.query(
            f"SELECT status, COUNT(*) c FROM aiakilov_leads WHERE {where} GROUP BY status",
            tuple(params),
        )
    }
    return render_template(
        "leads/kanban.html", columns=columns, counts=counts,
        args=request.args, **_filter_options(),
    )


@bp.route("/<lead_id>")
@permission_required("leads.view")
def detail(lead_id: str):
    lead = db.query_one("SELECT * FROM aiakilov_leads WHERE id = ?", (lead_id,))
    if not lead:
        return render_template("errors/404.html"), 404

    model_key = request.args.get("model") or ml_service.best_model_key()
    prediction = ml_service.predict(lead, model_key)
    activities = db.query(
        "SELECT * FROM aiakilov_lead_activities WHERE lead_id = ? ORDER BY created_at DESC",
        (lead_id,),
    )
    followups = db.query(
        "SELECT * FROM aiakilov_followups WHERE lead_id = ? ORDER BY due_date", (lead_id,)
    )
    student = db.query_one("SELECT * FROM aiakilov_students WHERE lead_id = ?", (lead_id,))
    return render_template(
        "leads/detail.html", lead=lead, prediction=prediction,
        activities=activities, followups=followups, student=student,
        models=ml_service.available_models(), selected_model=model_key,
        statuses=db.LEAD_STATUSES, status_he=db.STATUS_HE, source_he=db.SOURCE_HE,
    )


@bp.route("/new", methods=["GET", "POST"])
@permission_required("leads.edit")
def create():
    if request.method == "POST":
        errors = _validate(request.form)
        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("leads/form.html", lead=request.form,
                                   errors=errors, **_filter_options()), 400
        lead_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        db.execute(
            "INSERT INTO aiakilov_leads (id, first_name, last_name, email, phone, age, city,"
            " occupation, education, course_interest, lead_source, status, budget,"
            " preferred_schedule, previous_ai_experience, interaction_count,"
            " assigned_sales_rep, notes, purchased, created_at, updated_at)"
            " VALUES (" + ",".join("?" * 21) + ")",
            (lead_id, *_form_values(request.form), 0, now, now),
        )
        _log_activity(lead_id, "created", "הליד נוצר במערכת")
        flash("הליד נוצר בהצלחה", "success")
        return redirect(url_for("leads.detail", lead_id=lead_id))
    return render_template("leads/form.html", lead={}, errors=[], **_filter_options())


@bp.route("/<lead_id>/edit", methods=["GET", "POST"])
@permission_required("leads.edit")
def edit(lead_id: str):
    lead = db.query_one("SELECT * FROM aiakilov_leads WHERE id = ?", (lead_id,))
    if not lead:
        return render_template("errors/404.html"), 404
    if request.method == "POST":
        errors = _validate(request.form)
        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("leads/form.html", lead=request.form,
                                   errors=errors, **_filter_options()), 400
        db.execute(
            "UPDATE aiakilov_leads SET first_name=?, last_name=?, email=?, phone=?, age=?,"
            " city=?, occupation=?, education=?, course_interest=?, lead_source=?, status=?,"
            " budget=?, preferred_schedule=?, previous_ai_experience=?, interaction_count=?,"
            " assigned_sales_rep=?, notes=?, updated_at=? WHERE id=?",
            (*_form_values(request.form),
             datetime.now(timezone.utc).isoformat(timespec="seconds"), lead_id),
        )
        flash("הליד עודכן", "success")
        return redirect(url_for("leads.detail", lead_id=lead_id))
    return render_template("leads/form.html", lead=lead, errors=[], **_filter_options())


@bp.route("/<lead_id>/status", methods=["POST"])
@permission_required("leads.edit")
def change_status(lead_id: str):
    status = (request.form.get("status") or request.json.get("status") if request.is_json
              else request.form.get("status"))
    if status not in db.LEAD_STATUSES:
        msg = "סטטוס לא חוקי"
        if request.is_json:
            return jsonify({"error": msg}), 400
        flash(msg, "error")
        return redirect(url_for("leads.detail", lead_id=lead_id))

    lead = db.query_one("SELECT id FROM aiakilov_leads WHERE id = ?", (lead_id,))
    if not lead:
        return (jsonify({"error": "lead not found"}), 404) if request.is_json else (
            render_template("errors/404.html"), 404)

    db.execute(
        "UPDATE aiakilov_leads SET status = ?, purchased = ?, updated_at = ? WHERE id = ?",
        (status, 1 if status == "Won" else 0,
         datetime.now(timezone.utc).isoformat(timespec="seconds"), lead_id),
    )
    _log_activity(lead_id, "status_change", f"סטטוס שונה ל-{db.STATUS_HE.get(status, status)}")
    if request.is_json:
        return jsonify({"ok": True, "id": lead_id, "status": status})
    flash(f"הסטטוס שונה ל{db.STATUS_HE.get(status, status)}", "success")
    return redirect(request.referrer or url_for("leads.detail", lead_id=lead_id))


@bp.route("/<lead_id>/note", methods=["POST"])
@permission_required("leads.edit")
def add_note(lead_id: str):
    text = (request.form.get("note") or "").strip()
    if not text:
        flash("לא ניתן להוסיף הערה ריקה", "error")
    else:
        _log_activity(lead_id, "note", text)
        flash("ההערה נוספה", "success")
    return redirect(url_for("leads.detail", lead_id=lead_id))


@bp.route("/<lead_id>/convert", methods=["POST"])
@permission_required("leads.edit")
def convert(lead_id: str):
    """Turn a Won lead into a student + enrolment + demo invoice."""
    lead = db.query_one("SELECT * FROM aiakilov_leads WHERE id = ?", (lead_id,))
    if not lead:
        return render_template("errors/404.html"), 404
    if db.query_one("SELECT id FROM aiakilov_students WHERE lead_id = ?", (lead_id,)):
        flash("הליד כבר הומר לתלמיד", "error")
        return redirect(url_for("leads.detail", lead_id=lead_id))

    course = db.query_one("SELECT * FROM aiakilov_courses WHERE name = ?",
                          (lead["course_interest"],))
    if not course:
        flash("לא נמצא קורס מתאים להמרה", "error")
        return redirect(url_for("leads.detail", lead_id=lead_id))

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    today = datetime.now(timezone.utc).date().isoformat()
    student_id, enr_id = str(uuid.uuid4()), str(uuid.uuid4())
    db.execute("INSERT INTO aiakilov_students VALUES (?,?,?,?,?,?,?,?)",
               (student_id, lead_id, lead["first_name"], lead["last_name"],
                lead["email"], lead["phone"], lead["city"], now))
    db.execute("INSERT INTO aiakilov_enrollments VALUES (?,?,?,?,?,?,?,?)",
               (enr_id, student_id, course["id"], today, "active",
                course["price"], "pending", now))
    count = db.query_one("SELECT COUNT(*) c FROM aiakilov_invoices")["c"]
    db.execute("INSERT INTO aiakilov_invoices VALUES (?,?,?,?,?,?,?,?,?)",
               (str(uuid.uuid4()), f"AIA-{datetime.now(timezone.utc).year}-{count + 1000}",
                enr_id, student_id, course["id"], course["price"], today, "pending", now))
    db.execute("UPDATE aiakilov_leads SET status='Won', purchased=1, updated_at=? WHERE id=?",
               (now, lead_id))
    _log_activity(lead_id, "converted", "הליד הומר לתלמיד ונרשם לקורס")
    flash("הליד הומר לתלמיד, נוצרה הרשמה וחשבונית הדגמה", "success")
    return redirect(url_for("students.detail", student_id=student_id))


@bp.route("/<lead_id>/delete", methods=["POST"])
@permission_required("leads.delete")
def delete(lead_id: str):
    db.execute("DELETE FROM aiakilov_lead_activities WHERE lead_id = ?", (lead_id,))
    db.execute("DELETE FROM aiakilov_followups WHERE lead_id = ?", (lead_id,))
    db.execute("DELETE FROM aiakilov_leads WHERE id = ?", (lead_id,))
    flash("הליד נמחק", "success")
    return redirect(url_for("leads.index"))


# --------------------------------------------------------------------------- helpers

def _validate(form) -> list[str]:
    errors = []
    for field in REQUIRED_FIELDS:
        if not (form.get(field) or "").strip():
            errors.append("שם פרטי ושם משפחה הם שדות חובה")
            break
    email = (form.get("email") or "").strip()
    if email and "@" not in email:
        errors.append("כתובת אימייל אינה תקינה")
    for numeric, label in (("age", "גיל"), ("budget", "תקציב"),
                           ("interaction_count", "מספר אינטראקציות")):
        value = (form.get(numeric) or "").strip()
        if value:
            try:
                if float(value) < 0:
                    errors.append(f"{label} לא יכול להיות שלילי")
            except ValueError:
                errors.append(f"{label} חייב להיות מספר")
    status = form.get("status")
    if status and status not in db.LEAD_STATUSES:
        errors.append("סטטוס לא חוקי")
    return errors


def _num(value, cast=float):
    try:
        return cast(float(value)) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _form_values(form) -> tuple:
    return (
        form.get("first_name", "").strip(), form.get("last_name", "").strip(),
        form.get("email", "").strip() or None, form.get("phone", "").strip() or None,
        _num(form.get("age"), int), form.get("city") or None,
        form.get("occupation") or None, form.get("education") or None,
        form.get("course_interest") or None, form.get("lead_source") or None,
        form.get("status") or "New", _num(form.get("budget")),
        form.get("preferred_schedule") or None,
        1 if form.get("previous_ai_experience") else 0,
        _num(form.get("interaction_count"), int) or 0,
        form.get("assigned_sales_rep") or None, form.get("notes") or None,
    )


def _log_activity(lead_id: str, activity_type: str, description: str) -> None:
    from ..services.auth_service import current_user

    user = current_user() or {}
    db.execute(
        "INSERT INTO aiakilov_lead_activities VALUES (?,?,?,?,?,?)",
        (str(uuid.uuid4()), lead_id, activity_type, description,
         user.get("full_name", "מערכת"), datetime.now(timezone.utc).isoformat(timespec="seconds")),
    )
