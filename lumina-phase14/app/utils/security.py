"""HTTP security headers and redirect safety."""
from urllib.parse import urlparse

from flask import Flask

CSP = "; ".join(
    [
        "default-src 'self'",
        "img-src 'self' data: https:",
        "style-src 'self'",
        "script-src 'self'",
        "font-src 'self'",
        "connect-src 'self'",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        "frame-ancestors 'none'",
    ]
)


def register_security_headers(app: Flask) -> None:
    @app.after_request
    def add_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy", "geolocation=(), microphone=(), camera=()"
        )
        response.headers.setdefault("Content-Security-Policy", CSP)
        if app.config.get("ENV_NAME") == "production":
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        return response


def is_safe_redirect_url(target: str | None) -> bool:
    """Allow only same-site relative paths (blocks open-redirect attacks)."""
    if not target or not target.startswith("/"):
        return False
    if target.startswith("//") or "\\" in target:
        return False
    if any(ord(ch) < 32 for ch in target):
        return False
    parsed = urlparse(target)
    return not parsed.scheme and not parsed.netloc
