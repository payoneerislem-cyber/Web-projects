"""Create (or promote) an admin account:  python create_admin.py"""
from getpass import getpass

from app import create_app
from app.extensions import db
from app.models import Role, User
from app.utils.validators import normalize_email, validate_password_strength


def main() -> None:
    app = create_app()
    with app.app_context():
        email = normalize_email(input("Admin email: "))
        name = input("Full name: ").strip() or "Administrator"
        password = getpass("Password (hidden): ")
        problems = validate_password_strength(password)
        if not email or "@" not in email or problems:
            raise SystemExit("Invalid input: " + (" ".join(problems) or "check the email."))

        user = User.query.filter_by(email=email).first()
        if user is None:
            user = User(email=email, name=name)
            db.session.add(user)
        user.name = name
        user.role = Role.ADMIN
        user.is_active = True
        user.set_password(password)
        db.session.commit()
        print(f"Admin ready: {email}")


if __name__ == "__main__":
    main()
