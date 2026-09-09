"""JSON API. Returns proper status codes and validates input."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

from ..services import db, ml_service
from ..services.auth_service import login_required

bp = Blueprint("api", __name__, url_prefix="/api")

MAX_LIMIT = 200


@bp.route("/leads")
@login_required
def list_leads():
    limit = min(request.args.get("limit", 50, type=int), MAX_LIMIT)
    offset = max(request.args.get("offset", 0, type=int), 0)
    status = request.args.get("status")

    where, params = "1=1", []
    if status:
        if status not in db.LEAD_STATUSES:
            return jsonify({"error": "invalid status", "allowed": db.LEAD_STATUSES}), 400
        where, params = "status = ?", [status]

    rows = db.query(
        f"SELECT * FROM aiakilov_leads WHERE {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
        tuple(params) + (limit, offset),
    )
    total = db.query_one(f"SELECT COUNT(*) c FROM aiakilov_leads WHERE {where}", tuple(params))["c"]
    return jsonify({"total": total, "limit": limit, "offset": offset, "data": rows}), 200


@bp.route("/leads/<lead_id>")
@login_required
def get_lead(lead_id: str):
    lead = db.query_one("SELECT * FROM aiakilov_leads WHERE id = ?", (lead_id,))
    if not lead:
        return jsonify({"error": "lead not found"}), 404
    lead["prediction"] = ml_service.predict(lead)
    return jsonify(lead), 200


@bp.route("/leads", methods=["POST"])
@login_required
def create_lead():
    payload = request.get_json(silent=True) or {}
    errors = []
    for field in ("first_name", "last_name"):
        if not str(payload.get(field) or "").strip():
            errors.append(f"'{field}' is required")
    email = str(payload.get("email") or "")
    if email and "@" not in email:
        errors.append("'email' is invalid")
    status = payload.get("status", "New")
    if status not in db.LEAD_STATUSES:
        errors.append("'status' is invalid")
    if errors:
        return jsonify({"error": "validation failed", "details": errors}), 422

    lead_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    db.execute(
        "INSERT INTO aiakilov_leads (id, first_name, last_name, email, phone, age, city,"
        " occupation, education, course_interest, lead_source, status, budget,"
        " preferred_schedule, previous_ai_experience, interaction_count,"
        " assigned_sales_rep, notes, purchased, created_at, updated_at)"
        " VALUES (" + ",".join("?" * 21) + ")",
        (
            lead_id, payload["first_name"].strip(), payload["last_name"].strip(),
            payload.get("email"), payload.get("phone"), payload.get("age"),
            payload.get("city"), payload.get("occupation"), payload.get("education"),
            payload.get("course_interest"), payload.get("lead_source"), status,
            payload.get("budget"), payload.get("preferred_schedule"),
            1 if payload.get("previous_ai_experience") else 0,
            payload.get("interaction_count", 0), payload.get("assigned_sales_rep"),
            payload.get("notes"), 0, now, now,
        ),
    )
    return jsonify(db.query_one("SELECT * FROM aiakilov_leads WHERE id = ?", (lead_id,))), 201


@bp.route("/courses")
@login_required
def list_courses():
    return jsonify({"data": db.query("SELECT * FROM aiakilov_courses ORDER BY name")}), 200


@bp.route("/predict", methods=["POST"])
@login_required
def predict():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "JSON body required"}), 400

    model_key = payload.get("model")
    trained = {m["key"] for m in ml_service.available_models()}
    if model_key and model_key not in trained:
        return jsonify({"error": "unknown or untrained model",
                        "available": sorted(trained)}), 400

    result = ml_service.predict(payload, model_key)
    if "error" in result:
        return jsonify(result), 503
    return jsonify(result), 200


@bp.route("/models/metrics")
@login_required
def model_metrics():
    return jsonify(ml_service.load_metrics()), 200
