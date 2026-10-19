from app.services.auth import generate_otp, is_otp_valid, normalize_email, otp_expiration, validate_registration
from app.services.budget import get_user_budget_data
from app.repositories import TransactionRepository, UserRepository
from werkzeug.security import generate_password_hash


def test_auth_service_validation():
    assert normalize_email("  USER@Example.COM ") == "user@example.com"
    assert validate_registration("abc", "Strong123", "a@example.com")[0]
    assert not validate_registration("ab", "Strong123", "a@example.com")[0]
    assert not validate_registration("abc", "short", "a@example.com")[0]
    assert not validate_registration("abc", "Strong123", "invalid")[0]


def test_otp_generation_and_expiration():
    otp = generate_otp()
    assert otp.isdigit() and len(otp) == 6
    expires = otp_expiration(60)
    assert is_otp_valid(otp, otp, expires)
    assert not is_otp_valid(otp, "000000", expires)
    assert not is_otp_valid(otp, otp, "not-a-number")


def test_budget_service_calculates_balance(app):
    with app.app_context():
        user_id = UserRepository.create("budget", generate_password_hash("password123"), "budget@example.com")
        TransactionRepository.add_income(user_id, 500, "Income")
        TransactionRepository.add_expense(user_id, 125, "Expense")
        data = get_user_budget_data(user_id)
        assert data["user_budget"] == 375
        assert len(data["user_expenses"]) == 1
        assert len(data["user_incomes"]) == 1
