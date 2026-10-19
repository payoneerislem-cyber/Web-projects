import io
import re

import pytest


def extract_csrf(response):
    match = re.search(r'name="_csrf_token" value="([^"]+)"', response.get_data(as_text=True))
    assert match, "CSRF token was not found in the response"
    return match.group(1)


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("UPLOAD_FOLDER", str(tmp_path / "uploads"))
    monkeypatch.setenv("MAIL_USERNAME", "")
    monkeypatch.setenv("MAIL_PASSWORD", "")
    monkeypatch.setenv("MAIL_SENDER", "")

    from app import create_app

    application = create_app()
    application.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    return application


@pytest.fixture
def client(app):
    return app.test_client()


def register(client, username="tester", email="tester@example.com", password="StrongPass123"):
    response = client.get("/register")
    token = extract_csrf(response)
    return client.post(
        "/register",
        data={
            "_csrf_token": token,
            "username": username,
            "email": email,
            "password": password,
        },
    )


def login(client, username="tester", password="StrongPass123"):
    response = client.get("/login")
    token = extract_csrf(response)
    return client.post(
        "/login",
        data={
            "_csrf_token": token,
            "username": username,
            "password": password,
        },
    )


@pytest.fixture
def logged_client(client):
    register(client)
    response = login(client)
    assert response.status_code == 302
    return client


@pytest.fixture
def csrf_token(logged_client):
    return extract_csrf(logged_client.get("/budget"))


@pytest.fixture
def image_file():
    return (io.BytesIO(b"fake-image-content"), "avatar.png")
