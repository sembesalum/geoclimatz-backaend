import ipaddress
from urllib.parse import urlparse

from django.conf import settings

# POST endpoints that accept anonymous JSON from arbitrary marketing origins (no session cookie).
_PUBLIC_FORM_TAIL_SEGMENTS = frozenset({"newsletter", "donations"})


def _private_dashboard_browser_origin(origin: str) -> bool:
    """True if Origin looks like local dev (localhost, *.local, private IPv4/IPv6)."""
    try:
        parsed = urlparse(origin)
        if parsed.scheme not in ("http", "https"):
            return False
        host = parsed.hostname
        if not host:
            return False
        if host in ("localhost", "127.0.0.1"):
            return True
        if host.endswith(".local"):
            return True
        addr = ipaddress.ip_address(host)
        return bool(addr.is_private or addr.is_loopback)
    except ValueError:
        return False
    except Exception:
        return False


def _allow_credentialed_private_dashboard_origins() -> bool:
    return bool(getattr(settings, "DEBUG", False) or getattr(settings, "TRUST_LAN_DASHBOARD_CORS", False))


class DevCorsMiddleware:
    """CORS for dashboard allowlist + dev/LAN + open signup POST for newsletter/donations."""

    BASE_ORIGINS = frozenset(
        {
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:8080",
            "http://127.0.0.1:8080",
            "https://geoclimatz.pythonanywhere.com",
            "https://admin-dashboard.geoclimatz.org",
        }
    )

    def __init__(self, get_response):
        self.get_response = get_response
        extra = frozenset(getattr(settings, "CORS_EXTRA_ORIGINS", []) or [])
        self.allowed_origins = self.BASE_ORIGINS | extra

    @staticmethod
    def _is_public_anonymous_post(request) -> bool:
        if request.method not in ("POST", "OPTIONS"):
            return False
        tail = request.path.rstrip("/").split("/")[-1]
        return tail in _PUBLIC_FORM_TAIL_SEGMENTS

    @staticmethod
    def _apply_credentialed_cors(response, origin: str) -> None:
        response["Access-Control-Allow-Origin"] = origin
        response["Access-Control-Allow-Credentials"] = "true"
        response["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-CSRFToken, Accept"
        response["Access-Control-Allow-Methods"] = "GET, POST, PATCH, DELETE, OPTIONS"
        response["Vary"] = "Origin"

    def __call__(self, request):
        if request.method == "OPTIONS":
            response = self._build_preflight_response()
        else:
            response = self.get_response(request)

        origin = request.headers.get("Origin")

        if origin and self._is_public_anonymous_post(request):
            response["Access-Control-Allow-Origin"] = origin
            response["Access-Control-Allow-Methods"] = "POST, OPTIONS"
            response["Access-Control-Allow-Headers"] = "Content-Type, Accept"
            response["Vary"] = "Origin"
            if request.method == "OPTIONS":
                response["Access-Control-Max-Age"] = "86400"
            return response

        if origin and origin in self.allowed_origins:
            self._apply_credentialed_cors(response, origin)
        elif origin and _allow_credentialed_private_dashboard_origins() and _private_dashboard_browser_origin(origin):
            self._apply_credentialed_cors(response, origin)

        return response

    @staticmethod
    def _build_preflight_response():
        from django.http import HttpResponse

        return HttpResponse(status=204)
