from app.repositories import TransactionRepository, UserRepository


def get_user_budget_data(user_id):
    expenses = TransactionRepository.list_expenses(user_id)
    incomes = TransactionRepository.list_incomes(user_id)
    total_expenses, total_incomes = TransactionRepository.get_totals(user_id)
    profile_pic = UserRepository.get_profile_picture(user_id)

    current_balance = total_incomes - total_expenses
    return {
        "user_expenses": expenses,
        "user_incomes": incomes,
        "user_budget": current_balance,
        "box_color": "#e74c3c" if current_balance < 0 else "#2ecc71",
        "user_pic": profile_pic,
    }
