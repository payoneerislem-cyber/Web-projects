"""Entry point: `python run.py` or `flask --app run run --debug`."""
from app import create_app

app = create_app()
with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)
