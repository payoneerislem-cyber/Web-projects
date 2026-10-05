"""Custom `flask` CLI commands."""
import click
from flask import Flask

from app.extensions import db


def register_cli(app: Flask) -> None:
    @app.cli.command("init-db")
    def init_db():
        """Create all tables directly (quick start without migrations)."""
        db.create_all()
        click.echo("Database tables created.")

    @app.cli.command("reset-db")
    @click.confirmation_option(prompt="This DELETES all data. Continue?")
    def reset_db():
        """Drop and recreate all tables (development only)."""
        db.drop_all()
        db.create_all()
        click.echo("Database reset.")

    @app.cli.command("create-admin")
    @click.option("--email", prompt=True)
    @click.option("--name", prompt=True)
    @click.password_option()
    def create_admin(email, name, password):
        """Create an admin user."""
        from app.models import User
        from app.models.user import ROLE_ADMIN

        email = email.strip().lower()
        if len(password) < 8:
            raise click.ClickException("Password must be at least 8 characters.")
        if db.session.execute(db.select(User).filter_by(email=email)).scalar_one_or_none():
            raise click.ClickException("A user with this email already exists.")
        user = User(email=email, name=name, role=ROLE_ADMIN)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        click.echo(f"Admin created: {email}")
