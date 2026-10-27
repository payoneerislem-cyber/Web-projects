import pytest
from flask import g

from app import create_app
from app.extensions import db


@pytest.fixture()
def app():
    app = create_app("testing")

    # The fixture keeps one app context open for the whole test, so Flask-Login's
    # per-request cache on `g` would leak between requests. Reset it each request.
    @app.before_request
    def _reset_login_cache():
        g.pop("_login_user", None)

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()
