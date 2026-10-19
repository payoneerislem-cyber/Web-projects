# Budget Tracker

A structured Flask budget-tracking application with authentication, password reset by OTP email, profile image upload, income/expense management, and a small AJAX dashboard.

## Architecture

```text
budget_tracker/
├── run.py                         # Local entry point
├── wsgi.py                        # Production WSGI entry point
├── Procfile                      # Gunicorn process definition
├── requirements.txt
├── .env.example
├── instance/
│   └── budget_tracker.db         # Runtime SQLite database (gitignored)
├── app/
│   ├── __init__.py               # Application factory
│   ├── config.py                 # Environment-driven configuration
│   ├── db/
│   │   └── database.py           # SQLite connection, schema and compatibility migration
│   ├── repositories/             # Database access only
│   ├── services/                 # Business logic
│   ├── utils/                    # Cross-cutting helpers (CSRF, auth decorator)
│   ├── blueprints/               # HTTP routes grouped by responsibility
│   │   ├── main/
│   │   ├── auth/
│   │   ├── api/
│   │   └── profile/
│   ├── templates/
│   │   ├── auth/
│   │   ├── dashboard/
│   │   └── components/
│   └── static/
│       ├── css/
│       ├── js/
│       └── uploads/
```

## Run locally

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# Linux/macOS/Termux: source .venv/bin/activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and set a real `SECRET_KEY`.

Start the app:

```bash
python run.py
```

For production WSGI hosting:

```bash
gunicorn --workers 2 --threads 4 --timeout 120 wsgi:app
```

## Existing database compatibility

The application stores runtime data in `instance/budget_tracker.db`. On first startup, when the new database file does not exist but a legacy `datebase.db` is still present in the project root (or `instance/`), it is copied to the new location automatically before schema initialization.

## Important deployment notes

- Never commit `.env`, the SQLite database, uploaded user files, or email credentials.
- Use HTTPS and set `SESSION_COOKIE_SECURE=1` in production.
- Set `APP_ENV=production` for production configuration.
- For a small single-instance deployment, SQLite is acceptable. For multiple application instances or heavier concurrent writes, move the repository layer to PostgreSQL/MySQL.
- Gunicorn is intended for Linux-style production hosting. `run.py` is the simple local/dev entry point.
