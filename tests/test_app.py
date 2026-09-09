"""Application bootstrap, auth and permission tests."""

from app.services import auth_service, db


def test_app_starts(app):
    assert app is not None
    assert app.config["TESTING"] is True


def test_seed_data_present():
    assert db.query_one("SELECT COUNT(*) c FROM aiakilov_leads")["c"] >= 10_000
    assert db.query_one("SELECT COUNT(*) c FROM aiakilov_courses")["c"] == 6
    assert db.query_one("SELECT COUNT(*) c FROM aiakilov_profiles")["c"] == 6
    assert db.query_one("SELECT COUNT(*) c FROM aiakilov_students")["c"] > 0
    assert db.query_one("SELECT COUNT(*) c FROM aiakilov_enrollments")["c"] > 0


def test_login_page_renders(client):
    res = client.get("/login")
    assert res.status_code == 200
    assert 'dir="rtl"' in res.get_data(as_text=True)


def test_anonymous_is_redirected(client):
    assert client.get("/").status_code == 302


def test_login_and_logout(client):
    assert client.post("/login", data={"email": "admin@aiakilov.co.il"}).status_code == 302
    assert client.get("/").status_code == 200
    client.get("/logout")
    assert client.get("/").status_code == 302


def test_login_rejects_unknown_user(client):
    assert client.post("/login", data={"email": "nobody@example.com"}).status_code == 401


def test_404_page(auth_client):
    res = auth_client.get("/no-such-page")
    assert res.status_code == 404
    assert "404" in res.get_data(as_text=True)


def test_permission_matrix_denies_lecturer_leads(app):
    c = app.test_client()
    c.post("/login", data={"email": "lecturer@aiakilov.co.il"})
    assert c.get("/leads/").status_code == 302     # not permitted -> redirected
    assert c.get("/courses/").status_code == 200   # permitted


def test_admin_bypasses_permission_map():
    assert "LECTURER" not in auth_service.PERMISSIONS["leads.edit"]
    assert "ADMIN" in auth_service.PERMISSIONS["leads.delete"]
