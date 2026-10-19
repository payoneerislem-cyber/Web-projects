from flask import Blueprint, jsonify, render_template, request, session, url_for

from app.repositories import TransactionRepository
from app.services.budget import get_user_budget_data
from app.utils.decorators import login_required

bp = Blueprint("api", __name__, url_prefix="/api")


def _payload():
    data = request.get_json(silent=True) or {}
    amount = data.get("amount")
    reason = data.get("reason") or data.get("source")

    if amount in (None, "") or reason is None or not str(reason).strip():
        return None, None, (jsonify({"error": "Amount and reason are required."}), 400)

    try:
        amount = float(str(amount).replace(",", ""))
        if amount <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return None, None, (jsonify({"error": "Amount must be a positive number."}), 400)

    if amount.is_integer():
        amount = int(amount)
    return amount, str(reason).strip(), None


@bp.post("/add_expense")
@login_required
def add_expense():
    amount, reason, error = _payload()
    if error:
        return error
    new_id, date = TransactionRepository.add_expense(session["user_id"], amount, reason)
    return jsonify({"message": "New expense added", "date": date, "id": new_id})


@bp.post("/add_income")
@login_required
def add_income():
    amount, reason, error = _payload()
    if error:
        return error
    new_id, date = TransactionRepository.add_income(session["user_id"], amount, reason)
    return jsonify({"message": "New income added", "date": date, "id": new_id})


@bp.post("/delete_expense/<int:expense_id>")
@login_required
def delete_expense(expense_id):
    deleted = TransactionRepository.delete_expense(expense_id, session["user_id"])
    if not deleted:
        return jsonify({"error": "Expense not found."}), 404
    return jsonify({"message": "Expense deleted successfully"})


@bp.post("/delete_income/<int:income_id>")
@login_required
def delete_income(income_id):
    deleted = TransactionRepository.delete_income(income_id, session["user_id"])
    if not deleted:
        return jsonify({"error": "Income not found."}), 404
    return jsonify({"message": "Income deleted successfully"})


@bp.post("/edit_expense/<int:expense_id>")
@login_required
def edit_expense(expense_id):
    amount, reason, error = _payload()
    if error:
        return error
    updated, new_date = TransactionRepository.update_expense(
        expense_id, session["user_id"], amount, reason
    )
    if not updated:
        return jsonify({"error": "Expense not found."}), 404
    return jsonify({"message": "Expense updated successfully", "newdate": new_date})


@bp.post("/edit_income/<int:income_id>")
@login_required
def edit_income(income_id):
    amount, reason, error = _payload()
    if error:
        return error
    updated, new_date = TransactionRepository.update_income(
        income_id, session["user_id"], amount, reason
    )
    if not updated:
        return jsonify({"error": "Income not found."}), 404
    return jsonify({"message": "Income updated successfully", "newdate": new_date})


@bp.get("/get_summary")
@login_required
def get_summary():
    rows = TransactionRepository.list_expenses(session["user_id"])
    return jsonify([dict(row) for row in rows])


@bp.get("/page-data")
@login_required
def page_data():
    page = request.args.get("page", "")
    if page == url_for("auth.change_password_route"):
        return jsonify({"content": render_template("components/change_password.html", fragment=True)})
    if page in {"/", url_for("main.budget")}:  # compatibility with the old client
        data = get_user_budget_data(session["user_id"])
        return jsonify({"content": render_template("dashboard/budget.html", **data)})
    return jsonify({"error": "Page not found"}), 404
