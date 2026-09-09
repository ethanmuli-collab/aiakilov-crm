"""ML models comparison page and the interactive prediction sandbox."""

from __future__ import annotations

from flask import Blueprint, render_template, request

from ..services import db, ml_service
from ..services.auth_service import permission_required

bp = Blueprint("predictions", __name__, url_prefix="/ml")


@bp.route("/models")
@permission_required("ml.view")
def models():
    metrics = ml_service.load_metrics()
    selected = request.args.get("model") or metrics.get("best_model")
    model_list = list(metrics.get("models", {}).values())
    order = {"trained": 0, "failed": 1, "unavailable": 2}
    model_list.sort(key=lambda m: (order.get(m.get("status"), 3), m["label"]))
    return render_template(
        "ml/models.html", metrics=metrics, models=model_list,
        selected=metrics.get("models", {}).get(selected), selected_key=selected,
        best=metrics.get("best_model"),
    )


@bp.route("/predict", methods=["GET", "POST"])
@permission_required("ml.view")
def predict():
    """Score an ad-hoc lead profile without saving it."""
    courses = [r["name"] for r in db.query("SELECT name FROM aiakilov_courses ORDER BY name")]
    cities = [r["city"] for r in db.query(
        "SELECT DISTINCT city FROM aiakilov_leads WHERE city IS NOT NULL ORDER BY 1")]
    result, form = None, {}
    if request.method == "POST":
        form = request.form.to_dict()
        payload = {
            "age": _num(form.get("age"), int),
            "budget": _num(form.get("budget")),
            "interaction_count": _num(form.get("interaction_count"), int) or 0,
            "previous_ai_experience": 1 if form.get("previous_ai_experience") else 0,
            "city": form.get("city"),
            "occupation": form.get("occupation"),
            "education": form.get("education"),
            "course_interest": form.get("course_interest"),
            "lead_source": form.get("lead_source"),
            "preferred_schedule": form.get("preferred_schedule"),
        }
        result = ml_service.predict(payload, form.get("model") or None)

    return render_template(
        "ml/predict.html", courses=courses, cities=cities,
        sources=db.LEAD_SOURCES, source_he=db.SOURCE_HE,
        models=ml_service.available_models(), result=result, form=form,
        best=ml_service.best_model_key(),
    )


def _num(value, cast=float):
    try:
        return cast(float(value)) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None
