from flask import redirect, request, url_for

from app.utils.redirects import safe_next_url


def page() -> int:
    return max(request.args.get("page", 1, type=int), 1)


def paginate(query, per_page: int = 20):
    return query.paginate(page=page(), per_page=per_page, error_out=False)


def pagination_args() -> dict:
    return {k: v for k, v in request.args.items() if k != "page" and v}


def like(term: str) -> str:
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def back(default_endpoint: str, **values):
    """Redirect to the page the action came from (validated), else to a default."""
    return redirect(safe_next_url(request.form.get("next")) or url_for(default_endpoint, **values))
