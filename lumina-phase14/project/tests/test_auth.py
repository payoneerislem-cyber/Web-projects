import re

import pytest

from app.extensions import db
from app.models import Notification, User
from app.services import auth_service

PASSWORD = "Secret123!"


def make_user(email="user@example.com", role="customer", **kw):
    user = User(email=email, name=kw.pop("name", "Test User"), role=role, **kw)
    user.set_password(PASSWORD)
    db.session.add(user)
    db.session.commit()
    return user


def login(client, email="user@example.com", password=PASSWORD, **extra):
    return client.post("/login", data={"email": email, "password": password, **extra})


def test_register_creates_hashed_user_and_logs_in(client):
    r = client.post("/register", data={
        "name": "Ada Lovelace", "email": "Ada@Example.com",
        "password": PASSWORD, "confirm_password": PASSWORD,
    }, follow_redirects=True)
    assert r.status_code == 200
    user = User.query.filter_by(email="ada@example.com").one()  # normalised
    assert user.password_hash != PASSWORD and user.role == "customer"
    assert client.get("/account").status_code == 200  # logged in


def test_register_rejects_duplicate_email(client):
    make_user()
    r = client.post("/register", data={
        "name": "Other", "email": "USER@example.com",
        "password": PASSWORD, "confirm_password": PASSWORD,
    })
    assert b"already exists" in r.data
    assert User.query.count() == 1


@pytest.mark.parametrize("password", ["short1", "onlyletters", "12345678"])
def test_register_rejects_weak_password(client, password):
    r = client.post("/register", data={
        "name": "Weak", "email": "weak@example.com",
        "password": password, "confirm_password": password,
    })
    assert User.query.count() == 0
    assert r.status_code == 200


def test_register_password_mismatch(client):
    r = client.post("/register", data={
        "name": "Mismatch", "email": "m@example.com",
        "password": PASSWORD, "confirm_password": PASSWORD + "x",
    })
    assert b"Passwords must match" in r.data
    assert User.query.count() == 0


def test_login_success_and_wrong_password(client):
    make_user()
    r = login(client, password="wrong-pass-1")
    assert b"Invalid email or password." in r.data
    r = login(client)
    assert r.status_code == 302
    assert client.get("/account").status_code == 200


def test_login_unknown_email_gives_same_message(client):
    r = login(client, email="nobody@example.com")
    assert b"Invalid email or password." in r.data


def test_inactive_user_cannot_login(client):
    make_user(is_active=False)
    r = login(client)
    assert b"disabled" in r.data
    assert client.get("/account").status_code == 302


def test_logout_requires_post(client):
    make_user()
    login(client)
    assert client.get("/logout").status_code == 405
    assert client.post("/logout").status_code == 302
    assert client.get("/account").status_code == 302


def test_open_redirect_is_blocked(client):
    make_user()
    r = client.post("/login?next=https://evil.example.org/x",
                    data={"email": "user@example.com", "password": PASSWORD})
    assert "evil" not in r.headers["Location"]
    client.post("/logout")
    r = client.post("/login?next=//evil.example.org",
                    data={"email": "user@example.com", "password": PASSWORD})
    assert "evil" not in r.headers["Location"]


def test_next_redirect_to_local_path_works(client):
    make_user()
    r = client.post("/login?next=/account",
                    data={"email": "user@example.com", "password": PASSWORD})
    assert r.headers["Location"].endswith("/account")


def test_account_requires_login(client):
    r = client.get("/account")
    assert r.status_code == 302
    assert "/login" in r.headers["Location"] and "next=" in r.headers["Location"]


def test_admin_authorization(client):
    # anonymous -> redirected to login
    assert client.get("/admin").status_code == 302
    # customer -> 403
    make_user()
    login(client)
    assert client.get("/admin").status_code == 403
    client.post("/logout")
    # admin -> 200
    make_user(email="boss@example.com", role="admin")
    login(client, email="boss@example.com")
    assert client.get("/admin").status_code == 200


def test_admin_redirects_to_dashboard_after_login(client):
    make_user(email="boss@example.com", role="admin")
    r = login(client, email="boss@example.com")
    assert r.headers["Location"].endswith("/admin")


@pytest.fixture()
def sent_emails(monkeypatch):
    sent = []
    monkeypatch.setattr(auth_service, "send_email",
                        lambda to, subject, body: sent.append((to, subject, body)) or True)
    return sent


def test_forgot_password_does_not_reveal_accounts(client, sent_emails):
    make_user()
    known = client.post("/forgot-password", data={"email": "user@example.com"},
                        follow_redirects=True)
    unknown = client.post("/forgot-password", data={"email": "ghost@example.com"},
                          follow_redirects=True)
    msg = b"If an account exists"
    assert msg in known.data and msg in unknown.data
    assert len(sent_emails) == 1 and sent_emails[0][0] == "user@example.com"


def test_full_password_reset_flow(client, sent_emails):
    user = make_user()
    client.post("/forgot-password", data={"email": "user@example.com"})
    token = re.search(r"/reset-password/(\S+)", sent_emails[0][2]).group(1)

    assert client.get(f"/reset-password/{token}").status_code == 200
    r = client.post(f"/reset-password/{token}", data={
        "password": "NewSecret456", "confirm_password": "NewSecret456"})
    assert r.status_code == 302

    assert b"Invalid email or password." in login(client, password=PASSWORD).data
    assert login(client, password="NewSecret456").status_code == 302
    assert Notification.query.filter_by(user_id=user.id, type="security").count() == 1

    # token is single-use
    client.post("/logout")
    assert client.get(f"/reset-password/{token}").status_code == 302


def test_invalid_and_expired_reset_tokens(client):
    user = make_user()
    assert client.get("/reset-password/garbage").status_code == 302
    token = auth_service.generate_reset_token(user)
    assert auth_service.verify_reset_token(token) is not None
    assert auth_service.verify_reset_token(token, max_age=-1) is None


def test_csrf_failure_is_friendly(app):
    app.config["WTF_CSRF_ENABLED"] = True
    client = app.test_client()
    r = client.post("/login", data={"email": "a@example.com", "password": "x"})
    assert r.status_code == 400
    assert b"refresh the page" in r.data
