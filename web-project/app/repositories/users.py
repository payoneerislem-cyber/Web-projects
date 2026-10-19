from app.db.database import get_db


class UserRepository:
    @staticmethod
    def get_by_id(user_id):
        return get_db().execute(
            "SELECT id, username, password, email, profile_pic FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()

    @staticmethod
    def get_by_username(username):
        return get_db().execute(
            "SELECT id, username, password, email, profile_pic FROM users WHERE username = ?",
            (username,),
        ).fetchone()

    @staticmethod
    def get_by_email(email):
        return get_db().execute(
            "SELECT id, username, password, email, profile_pic FROM users WHERE email = ?",
            (email,),
        ).fetchone()

    @staticmethod
    def create(username, password_hash, email):
        db = get_db()
        cursor = db.execute(
            "INSERT INTO users (username, password, email) VALUES (?, ?, ?)",
            (username, password_hash, email),
        )
        db.commit()
        return cursor.lastrowid

    @staticmethod
    def update_password(user_id, password_hash):
        db = get_db()
        db.execute("UPDATE users SET password = ? WHERE id = ?", (password_hash, user_id))
        db.commit()

    @staticmethod
    def update_profile_picture(user_id, filename):
        db = get_db()
        db.execute("UPDATE users SET profile_pic = ? WHERE id = ?", (filename, user_id))
        db.commit()

    @staticmethod
    def get_profile_picture(user_id):
        row = get_db().execute(
            "SELECT profile_pic FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        return row["profile_pic"] if row else "default.png"
