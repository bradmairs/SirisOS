from starlette.middleware.cors import CORSMiddleware

from app.main import app


def _cors_options() -> dict:
    for middleware in app.user_middleware:
        if middleware.cls is CORSMiddleware:
            return middleware.kwargs
    raise AssertionError("CORSMiddleware is not registered on the app.")


def test_cors_allows_every_http_method_the_api_actually_uses() -> None:
    # Regression test: allow_methods previously only listed GET/POST, silently
    # breaking every DELETE/PATCH/PUT endpoint from a browser (preflight
    # OPTIONS requests were rejected with 400) while curl/pytest calls -
    # which skip CORS preflight entirely - looked completely fine.
    allowed = set(_cors_options()["allow_methods"])
    for method in ("GET", "POST", "PUT", "PATCH", "DELETE"):
        assert method in allowed, f"{method} is used by the API but not CORS-allowed."
