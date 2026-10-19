from unittest.mock import patch

from conftest import extract_csrf, login, register


def test_registration_creates_user_and_rejects_duplicate(client):
    first = register(client)
    assert first.status_code == 302

    duplicate = register(client)
    assert duplicate.status_code == 302


def test_registration_validation(client):
    response = client.get("/register")
    token = extract_csrf(response)
    response = client.post(
        "/register",
        data={
            "_csrf_token": token,
            "username": "ab",
            "email": "not-an-email",
            "password": "short",
        },
    )
    assert response.status_code == 302


def test_login_success_and_failure(client):
    register(client)
    bad = login(client, password="WrongPassword")
    assert bad.status_code == 302
    assert bad.headers["Location"].endswith("/login")

    good = login(client)
    assert good.status_code == 302
    assert good.headers["Location"].endswith("/budget")


def test_logout_clears_session(logged_client):
    response = logged_client.get("/budget")
    token = extract_csrf(response)
    response = logged_client.post("/logout", data={"_csrf_token": token})
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")
    assert logged_client.get("/budget").status_code == 302


def test_change_password_invalid_old_password(logged_client):
    response = logged_client.get("/change_password")
    token = extract_csrf(response)
    response = logged_client.post(
        "/change_password",
        data={
            "_csrf_token": token,
            "old_password": "wrong",
            "new_password": "NewStrongPass123",
        },
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/budget")


def test_change_password_success_logs_user_out(logged_client):
    response = logged_client.get("/change_password")
    token = extract_csrf(response)
    response = logged_client.post(
        "/change_password",
        data={
            "_csrf_token": token,
            "old_password": "StrongPass123",
            "new_password": "NewStrongPass123",
        },
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")

    assert login(logged_client, password="NewStrongPass123").status_code == 302


def test_password_reset_flow(client):
    register(client)
    with patch("app.blueprints.auth.routes.send_otp_email", return_value=True):
        response = client.get("/reset_request")
        token = extract_csrf(response)
        response = client.post(
            "/reset_request",
            data={"_csrf_token": token, "email": "tester@example.com"},
        )
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/verify_otp")

    with client.session_transaction() as session:
        otp = session["user_otp_code"]

    response = client.get("/verify_otp")
    token = extract_csrf(response)
    response = client.post(
        "/verify_otp",
        data={"_csrf_token": token, "otp_code": otp},
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/reset_password")

    response = client.get("/reset_password")
    token = extract_csrf(response)
    response = client.post(
        "/reset_password",
        data={"_csrf_token": token, "password": "ResetStrong123"},
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")
    assert login(client, password="ResetStrong123").status_code == 302
