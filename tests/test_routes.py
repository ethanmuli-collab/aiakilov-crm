"""Route and API tests, including lead creation and validation."""

import pytest

PAGES = ["/", "/leads/", "/leads/kanban", "/courses/", "/students/",
         "/enrollments/", "/ml/models", "/ml/predict", "/reports/", "/settings"]


@pytest.mark.parametrize("url", PAGES)
def test_pages_render(auth_client, url):
    res = auth_client.get(url)
    assert res.status_code == 200
    assert 'lang="he"' in res.get_data(as_text=True)


def test_lead_detail_renders(auth_client, sample_lead):
    res = auth_client.get(f"/leads/{sample_lead['id']}")
    assert res.status_code == 200
    assert sample_lead["first_name"] in res.get_data(as_text=True)


def test_lead_detail_unknown_id(auth_client):
    assert auth_client.get("/leads/00000000-0000-0000-0000-000000000000").status_code == 404


def test_create_lead(auth_client):
    res = auth_client.post("/leads/new", data={
        "first_name": "טסט", "last_name": "אוטומציה", "email": "auto@example.com",
        "budget": "4200", "course_interest": "Python for AI",
        "lead_source": "Referral", "status": "New", "interaction_count": "2",
    })
    assert res.status_code == 302
    lead_id = res.headers["Location"].rsplit("/", 1)[-1]
    assert auth_client.get(f"/leads/{lead_id}").status_code == 200


def test_create_lead_validation_rejects_empty_name(auth_client):
    res = auth_client.post("/leads/new", data={"first_name": "", "last_name": ""})
    assert res.status_code == 400


def test_create_lead_validation_rejects_bad_email(auth_client):
    res = auth_client.post("/leads/new",
                           data={"first_name": "א", "last_name": "ב", "email": "not-an-email"})
    assert res.status_code == 400


def test_change_lead_status(auth_client, sample_lead):
    res = auth_client.post(f"/leads/{sample_lead['id']}/status", json={"status": "Contacted"})
    assert res.status_code == 200
    assert res.get_json()["status"] == "Contacted"


def test_change_lead_status_rejects_invalid(auth_client, sample_lead):
    res = auth_client.post(f"/leads/{sample_lead['id']}/status", json={"status": "Nope"})
    assert res.status_code == 400


# ------------------------------------------------------------------ JSON API

def test_api_list_leads(auth_client):
    res = auth_client.get("/api/leads?limit=5")
    assert res.status_code == 200
    body = res.get_json()
    assert len(body["data"]) == 5
    assert body["total"] >= 10_000


def test_api_list_leads_invalid_status(auth_client):
    assert auth_client.get("/api/leads?status=bogus").status_code == 400


def test_api_get_lead_includes_prediction(auth_client, sample_lead):
    res = auth_client.get(f"/api/leads/{sample_lead['id']}")
    assert res.status_code == 200
    assert 0.0 <= res.get_json()["prediction"]["probability"] <= 1.0


def test_api_get_lead_404(auth_client):
    assert auth_client.get("/api/leads/missing").status_code == 404


def test_api_create_lead(auth_client):
    res = auth_client.post("/api/leads", json={
        "first_name": "API", "last_name": "ליד", "email": "api@example.com"})
    assert res.status_code == 201
    assert res.get_json()["first_name"] == "API"


def test_api_create_lead_validation(auth_client):
    res = auth_client.post("/api/leads", json={"first_name": ""})
    assert res.status_code == 422
    assert "details" in res.get_json()


def test_api_courses(auth_client):
    res = auth_client.get("/api/courses")
    assert res.status_code == 200
    assert len(res.get_json()["data"]) == 6


def test_api_requires_auth(client):
    assert client.get("/api/leads").status_code == 302
