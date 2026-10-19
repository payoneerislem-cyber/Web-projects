from app.db.database import get_db
from app.repositories import TransactionRepository, UserRepository
from werkzeug.security import generate_password_hash


def test_database_schema_exists(app):
    with app.app_context():
        tables = {
            row["name"]
            for row in get_db().execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
    assert {"users", "expenses", "incomes"}.issubset(tables)


def test_transaction_totals_and_cascade(app):
    with app.app_context():
        user_id = UserRepository.create("dbuser", generate_password_hash("password123"), "db@example.com")
        TransactionRepository.add_income(user_id, 1000, "Salary")
        TransactionRepository.add_expense(user_id, 250, "Food")
        expenses, incomes = TransactionRepository.get_totals(user_id)
        assert expenses == 250
        assert incomes == 1000

        db = get_db()
        db.execute("DELETE FROM users WHERE id = ?", (user_id,))
        db.commit()
        assert TransactionRepository.list_expenses(user_id) == []
        assert TransactionRepository.list_incomes(user_id) == []


def test_transaction_ownership(app):
    with app.app_context():
        first = UserRepository.create("one", generate_password_hash("password123"), "one@example.com")
        second = UserRepository.create("two", generate_password_hash("password123"), "two@example.com")
        expense_id, _ = TransactionRepository.add_expense(first, 100, "Private")
        assert not TransactionRepository.delete_expense(expense_id, second)
        assert TransactionRepository.list_expenses(first)[0]["id"] == expense_id
