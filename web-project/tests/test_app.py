from pathlib import Path


def test_app_factory_and_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok", "service": "budget-tracker"}


def test_home_redirects_to_login_when_anonymous(client):
    response = client.get("/")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_protected_budget_redirects_when_anonymous(client):
    response = client.get("/budget")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_static_assets_are_reachable(client):
    for path in (
        "/static/css/base.css",
        "/static/css/dashboard.css",
        "/static/js/main.js",
        "/static/js/budget.js",
    ):
        response = client.get(path)
        assert response.status_code == 200, path


def test_environment_configuration_is_loaded(app, tmp_path):
    assert Path(app.config["DATABASE_PATH"]).resolve() == (tmp_path / "test.db").resolve()
    assert Path(app.config["UPLOAD_FOLDER"]).resolve() == (tmp_path / "uploads").resolve()
    assert app.config["SECRET_KEY"] == "test-secret"

