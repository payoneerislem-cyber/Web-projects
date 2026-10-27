"""Image uploads. Validates type, size and content, re-encodes the image (drops metadata) and
stores it under a random name. `get_storage()` is the single place to swap in S3/Cloudinary."""
import io
import uuid
from pathlib import Path

from flask import current_app
from PIL import Image
from werkzeug.utils import secure_filename

Image.MAX_IMAGE_PIXELS = 40_000_000  # refuse decompression bombs

ALLOWED_MIMES = {"image/jpeg", "image/png", "image/webp"}
FORMAT_EXT = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}
MAX_DIMENSION = 1600
URL_PREFIX = "/static/uploads/"


class ImageError(Exception):
    """The uploaded file was rejected (message is shown to the admin)."""


class LocalImageStorage:
    def __init__(self, folder: str):
        self.root = Path(folder)

    def save(self, upload, subfolder: str = "products") -> str:
        name = secure_filename(upload.filename or "")
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        if ext not in current_app.config["ALLOWED_IMAGE_EXTENSIONS"]:
            raise ImageError("Only JPG, PNG or WebP images are allowed.")
        if (upload.mimetype or "").lower() not in ALLOWED_MIMES:
            raise ImageError("That file type isn't a supported image.")
        limit = current_app.config["MAX_CONTENT_LENGTH"]
        raw = upload.read(limit + 1)
        if not raw or len(raw) > limit:
            raise ImageError(f"Images must be smaller than {limit // (1024 * 1024)} MB.")
        try:
            Image.open(io.BytesIO(raw)).verify()  # is it really an image?
            image = Image.open(io.BytesIO(raw))
            fmt = image.format
            image.load()
        except Exception:
            raise ImageError("That file isn't a valid image.") from None
        if fmt not in FORMAT_EXT:
            raise ImageError("Only JPG, PNG or WebP images are allowed.")
        image.thumbnail((MAX_DIMENSION, MAX_DIMENSION))
        if fmt == "JPEG" and image.mode not in ("RGB", "L"):
            image = image.convert("RGB")
        filename = f"{uuid.uuid4().hex}.{FORMAT_EXT[fmt]}"
        target = self.root / subfolder / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        image.save(target, fmt, **({"quality": 85, "optimize": True} if fmt == "JPEG" else {}))
        return f"{URL_PREFIX}{subfolder}/{filename}"

    def delete(self, url: str | None) -> None:
        """Remove a file we stored. Anything else (external URLs, seed art) is left alone."""
        if not url or not url.startswith(URL_PREFIX):
            return
        relative = Path(url[len(URL_PREFIX):])
        target = (self.root / relative).resolve()
        if self.root.resolve() in target.parents and target.is_file():
            target.unlink(missing_ok=True)


def get_storage() -> LocalImageStorage:
    return LocalImageStorage(current_app.config["UPLOAD_FOLDER"])
