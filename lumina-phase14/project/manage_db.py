"""Run migrations as a plain script:

    python manage_db.py init
    python manage_db.py migrate "initial schema"
    python manage_db.py upgrade
    python manage_db.py downgrade
"""
import sys

from flask_migrate import downgrade, init, migrate, upgrade

from app import create_app

COMMANDS = ("init", "migrate", "upgrade", "downgrade")


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        sys.exit(f"Usage: python manage_db.py [{'|'.join(COMMANDS)}] [message]")
    cmd = sys.argv[1]
    app = create_app()
    with app.app_context():
        if cmd == "init":
            init()
        elif cmd == "migrate":
            migrate(message=sys.argv[2] if len(sys.argv) > 2 else "migration")
        elif cmd == "upgrade":
            upgrade()
        elif cmd == "downgrade":
            downgrade()


if __name__ == "__main__":
    main()
