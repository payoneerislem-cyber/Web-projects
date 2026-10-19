import shutil
import sqlite3
from pathlib import Path

from flask import current_app, g

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    email TEXT,
    profile_pic TEXT NOT NULL DEFAULT 'default.png'
);

CREATE TABLE IF NOT EXISTS expenses(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    amount INTEGER NOT NULL,
    reason TEXT NOT NULL,
    date TEXT NOT NULL,
    user_id INTEGER,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS incomes(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    amount INTEGER NOT NULL,
    reason TEXT NOT NULL,
    date TEXT NOT NULL,
    user_id INTEGER,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_expenses_user_id ON expenses(user_id);
CREATE INDEX IF NOT EXISTS idx_incomes_user_id ON incomes(user_id);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
"""


def _migrate_legacy_database(target: Path):
    if target.exists():
        return

    project_root = Path(__file__).resolve().parents[2]
    legacy_candidates = [
        project_root / "datebase.db",
        project_root / "instance" / "datebase.db",
    ]
    for legacy in legacy_candidates:
        if legacy.exists() and legacy.resolve() != target.resolve():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(legacy, target)
            break


def get_db():
    if "db" not in g:
        database_path = Path(current_app.config["DATABASE_PATH"])
        database_path.parent.mkdir(parents=True, exist_ok=True)
        g.db = sqlite3.connect(database_path)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
        g.db.execute("PRAGMA journal_mode = WAL")
    return g.db


def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_database(app):
    database_path = Path(app.config["DATABASE_PATH"])
    database_path.parent.mkdir(parents=True, exist_ok=True)
    _migrate_legacy_database(database_path)

    with sqlite3.connect(database_path) as db:
        db.execute("PRAGMA foreign_keys = ON")
        db.executescript(SCHEMA)

        # Compatibility with the original database if it predates the current schema.
        columns = {row[1] for row in db.execute("PRAGMA table_info(users)").fetchall()}
        if "email" not in columns:
            db.execute("ALTER TABLE users ADD COLUMN email TEXT")
        if "profile_pic" not in columns:
            db.execute("ALTER TABLE users ADD COLUMN profile_pic TEXT NOT NULL DEFAULT 'default.png'")
        db.commit()

    app.teardown_appcontext(close_db)
