from conftest import extract_csrf


def test_add_expense_and_income(logged_client, csrf_token):
    response = logged_client.post(
        "/api/add_expense",
        json={"amount": "125.50", "reason": "Food"},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert response.status_code == 200
    expense_id = response.get_json()["id"]

    response = logged_client.post(
        "/api/add_income",
        json={"amount": 500, "reason": "Salary"},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert response.status_code == 200
    income_id = response.get_json()["id"]
    assert expense_id > 0 and income_id > 0


def test_api_validates_bad_payloads(logged_client, csrf_token):
    for payload in (
        {},
        {"amount": 0, "reason": "Food"},
        {"amount": -5, "reason": "Food"},
        {"amount": "abc", "reason": "Food"},
        {"amount": 10, "reason": ""},
    ):
        response = logged_client.post(
            "/api/add_expense",
            json=payload,
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 400


def test_api_requires_authentication(client):
    response = client.post("/api/add_expense", json={"amount": 10, "reason": "Food"})
    assert response.status_code == 302


def test_api_requires_csrf(logged_client):
    response = logged_client.post("/api/add_expense", json={"amount": 10, "reason": "Food"})
    assert response.status_code == 400


def test_edit_delete_and_ownership(logged_client, csrf_token, client):
    created = logged_client.post(
        "/api/add_expense",
        json={"amount": 10, "reason": "Food"},
        headers={"X-CSRF-Token": csrf_token},
    ).get_json()
    expense_id = created["id"]

    response = logged_client.post(
        f"/api/edit_expense/{expense_id}",
        json={"amount": 20, "reason": "Dinner"},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert response.status_code == 200

    response = logged_client.get("/api/get_summary")
    assert response.status_code == 200
    assert response.get_json()[0]["amount"] == 20
    assert response.get_json()[0]["reason"] == "Dinner"

    response = logged_client.post(
        f"/api/delete_expense/{expense_id}",
        headers={"X-CSRF-Token": csrf_token},
    )
    assert response.status_code == 200

    response = logged_client.post(
        f"/api/delete_expense/{expense_id}",
        headers={"X-CSRF-Token": csrf_token},
    )
    assert response.status_code == 404


def test_page_data_unknown_page_is_404(logged_client):
    response = logged_client.get("/api/page-data?page=/does-not-exist")
    assert response.status_code == 404
