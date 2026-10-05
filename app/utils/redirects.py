"""Open-redirect protection for ?next= parameters."""
from urllib.parse import urljoin, urlparse

from flask import request


def safe_next_url(target: str | None) -> str | None:
    """Return `target` only if it is a same-site relative path, else None."""
    if not target or not target.startswith("/") or target.startswith("//") or "\\" in target:
        return None
    host = urlparse(request.host_url)
    resolved = urlparse(urljoin(request.host_url, target))
    if resolved.scheme in ("http", "https") and resolved.netloc == host.netloc:
        return target
    return None
