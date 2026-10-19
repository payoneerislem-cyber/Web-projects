from pathlib import Path


def test_required_project_files_exist():
    root = Path(__file__).resolve().parents[1]
    required = [
        "run.py", "wsgi.py", "requirements.txt", "app/__init__.py",
        "app/config.py", "app/db/database.py", "app/blueprints/main/routes.py",
        "app/blueprints/auth/routes.py", "app/blueprints/api/routes.py",
        "app/blueprints/profile/routes.py", "app/repositories/users.py",
        "app/repositories/transactions.py", "app/services/auth.py",
        "app/services/budget.py", "app/services/email.py", "app/services/profile.py",
        "app/utils/csrf.py", "app/utils/decorators.py",
    ]
    for relative in required:
        assert (root / relative).is_file(), relative


def test_no_old_monolithic_entrypoint_or_legacy_database_reference():
    root = Path(__file__).resolve().parents[1]
    assert not (root / "web_site.py").exists()
    assert not (root / "init_db.py").exists()


def test_no_nonexistent_budget_blueprint_is_registered():
    root = Path(__file__).resolve().parents[1]
    text = (root / "app/__init__.py").read_text()
    assert "blueprints.budget" not in text


def test_dynamic_transaction_amount_markup_keeps_sign_outside_amount_span():
    root = Path(__file__).resolve().parents[1]
    text = (root / "app/static/js/budget.js").read_text()
    assert '${sign}<span class="amount">${formatAmount(amount)}</span>' in text
    assert '<span class="amount">${sign}${formatAmount(amount)}</span>' not in text

