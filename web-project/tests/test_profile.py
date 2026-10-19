from pathlib import Path

from app.repositories import UserRepository
from app.services.profile import save_profile_picture
from werkzeug.security import generate_password_hash


def test_profile_picture_upload_and_replacement(app, image_file):
    with app.app_context():
        user_id = UserRepository.create("photo", generate_password_hash("password123"), "photo@example.com")
        first = image_file
        success, _ = save_profile_picture(user_id, type("Upload", (), {
            "filename": first[1],
            "save": lambda self, path: Path(path).write_bytes(first[0].getvalue()),
        })())
        assert success
        first_name = UserRepository.get_profile_picture(user_id)
        assert first_name != "default.png"
        assert (Path(app.config["UPLOAD_FOLDER"]) / first_name).exists()


def test_profile_rejects_bad_extension(app):
    from io import BytesIO
    from werkzeug.datastructures import FileStorage
    with app.app_context():
        user_id = UserRepository.create("photo2", generate_password_hash("password123"), "photo2@example.com")
        storage = FileStorage(stream=BytesIO(b"bad"), filename="malware.exe")
        success, message = __import__("app.services.profile", fromlist=["save_profile_picture"]).save_profile_picture(user_id, storage)
        assert not success
        assert "PNG" in message
