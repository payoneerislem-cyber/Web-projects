import sqlite3
from pathlib import Path


def test_missing_csrf_is_rejected(logged_client):
    response = logged_client.post("/logout")
    assert response.status_code == 400


def test_invalid_csrf_is_rejected(logged_client):
    response = logged_client.post("/logout", data={"_csrf_token": "invalid-token"})
    assert response.status_code == 400


def test_database_is_outside_static_directory(app):
    database = Path(app.config["DATABASE_PATH"]).resolve()
    static = (Path(app.root_path) / "static").resolve()
    assert static not in database.parents


def test_foreign_keys_are_enabled(app):
    from app.db.database import get_db
    with app.app_context():
        assert get_db().execute("PRAGMA foreign_keys").fetchone()[0] == 1
