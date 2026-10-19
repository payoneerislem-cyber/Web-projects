from datetime import datetime

from app.db.database import get_db


class TransactionRepository:
    @staticmethod
    def list_expenses(user_id):
        return get_db().execute(
            "SELECT id, amount, reason, date, user_id FROM expenses WHERE user_id = ? ORDER BY id DESC",
            (user_id,),
        ).fetchall()

    @staticmethod
    def list_incomes(user_id):
        return get_db().execute(
            "SELECT id, amount, reason, date, user_id FROM incomes WHERE user_id = ? ORDER BY id DESC",
            (user_id,),
        ).fetchall()

    @staticmethod
    def get_totals(user_id):
        db = get_db()
        total_expenses = db.execute(
            "SELECT COALESCE(SUM(amount), 0) AS total FROM expenses WHERE user_id = ?",
            (user_id,),
        ).fetchone()["total"]
        total_incomes = db.execute(
            "SELECT COALESCE(SUM(amount), 0) AS total FROM incomes WHERE user_id = ?",
            (user_id,),
        ).fetchone()["total"]
        return total_expenses, total_incomes

    @staticmethod
    def add_expense(user_id, amount, reason):
        date = datetime.now().strftime("%Y-%m-%d %H:%M")
        db = get_db()
        cursor = db.execute(
            "INSERT INTO expenses (amount, reason, date, user_id) VALUES (?, ?, ?, ?)",
            (amount, reason, date, user_id),
        )
        db.commit()
        return cursor.lastrowid, date

    @staticmethod
    def add_income(user_id, amount, reason):
        date = datetime.now().strftime("%Y-%m-%d %H:%M")
        db = get_db()
        cursor = db.execute(
            "INSERT INTO incomes (amount, reason, date, user_id) VALUES (?, ?, ?, ?)",
            (amount, reason, date, user_id),
        )
        db.commit()
        return cursor.lastrowid, date

    @staticmethod
    def delete_expense(expense_id, user_id):
        db = get_db()
        cursor = db.execute(
            "DELETE FROM expenses WHERE id = ? AND user_id = ?",
            (expense_id, user_id),
        )
        db.commit()
        return cursor.rowcount > 0

    @staticmethod
    def delete_income(income_id, user_id):
        db = get_db()
        cursor = db.execute(
            "DELETE FROM incomes WHERE id = ? AND user_id = ?",
            (income_id, user_id),
        )
        db.commit()
        return cursor.rowcount > 0

    @staticmethod
    def update_expense(expense_id, user_id, amount, reason):
        new_date = datetime.now().strftime("%Y-%m-%d %H:%M")
        db = get_db()
        cursor = db.execute(
            "UPDATE expenses SET amount = ?, reason = ?, date = ? WHERE id = ? AND user_id = ?",
            (amount, reason, new_date, expense_id, user_id),
        )
        db.commit()
        return cursor.rowcount > 0, new_date

    @staticmethod
    def update_income(income_id, user_id, amount, reason):
        new_date = datetime.now().strftime("%Y-%m-%d %H:%M")
        db = get_db()
        cursor = db.execute(
            "UPDATE incomes SET amount = ?, reason = ?, date = ? WHERE id = ? AND user_id = ?",
            (amount, reason, new_date, income_id, user_id),
        )
        db.commit()
        return cursor.rowcount > 0, new_date
