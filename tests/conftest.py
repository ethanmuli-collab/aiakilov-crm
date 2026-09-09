import pytest

from app import create_app
from app.services import db


@pytest.fixture(scope="session")
def app():
    return create_app({"TESTING": True, "SECRET_KEY": "test", "DEMO_MODE": True})


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def auth_client(app):
    """A client logged in as ADMIN."""
    c = app.test_client()
    c.post("/login", data={"email": "admin@aiakilov.co.il"})
    return c


@pytest.fixture()
def sample_lead():
    return db.query_one("SELECT * FROM aiakilov_leads LIMIT 1")
