from app.extensions import db
from sqlalchemy import text


def test_home_page(client):
    r = client.get("/")
    assert r.status_code == 200
    assert b"Lumina" in r.data


def test_health(client):
    r = client.get("/health")
    assert r.get_json() == {"status": "ok"}


def test_404_page(client):
    r = client.get("/does-not-exist")
    assert r.status_code == 404
    assert b"doesn't exist" in r.data or b"doesn&#39;t exist" in r.data


def test_404_json_for_api(client):
    r = client.get("/api/nope")
    assert r.status_code == 404
    assert r.get_json()["ok"] is False


def test_security_headers(client):
    r = client.get("/")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
    assert "default-src 'self'" in r.headers["Content-Security-Policy"]


def test_sqlite_foreign_keys_enabled(app):
    value = db.session.execute(text("PRAGMA foreign_keys")).scalar()
    assert value == 1
