from pathlib import Path
from uuid import uuid4

from flask import current_app
from werkzeug.utils import secure_filename

from app.repositories import UserRepository

ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


def save_profile_picture(user_id, file_storage):
    if not file_storage or not file_storage.filename or not file_storage.filename.strip():
        return False, "Please choose an image."

    original_filename = secure_filename(file_storage.filename)
    extension = Path(original_filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        return False, "Please upload only PNG, JPG, JPEG or WEBP images."

    upload_folder = Path(current_app.config["UPLOAD_FOLDER"])
    upload_folder.mkdir(parents=True, exist_ok=True)

    filename = f"{uuid4().hex}{extension}"
    file_storage.save(upload_folder / filename)

    old_pic = UserRepository.get_profile_picture(user_id)
    UserRepository.update_profile_picture(user_id, filename)

    if old_pic and old_pic != "default.png":
        old_path = upload_folder / old_pic
        if old_path.exists() and old_path.is_file():
            old_path.unlink()

    return True, "Profile picture updated successfully."
