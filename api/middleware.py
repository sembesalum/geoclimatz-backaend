import ipaddress
from urllib.parse import urlparse

from django.conf import settings

# POST endpoints that accept anonymous JSON from arbitrary marketing origins (no session cookie).
_PUBLIC_FORM_TAIL_SEGMENTS = frozenset({"newsletter", "donations"})


def _parse_ip_host(hostname: str | None):
    if not hostname:
        return None
    h = hostname.strip().strip("[]")
    try:
        return ipaddress.ip_address(h)
    except ValueError:
        return None


def _is_loopback_browser_origin(origin: str) -> bool:
    """True for localhost / 127.0.0.1 / ::1 / other loopback IPs (any port). Next may use IPv6."""
    try:
        parsed = urlparse(origin)
        if parsed.scheme not in ("http", "https"):
            return False
        host = (parsed.hostname or "").strip().lower()
        if host in ("localhost", "127.0.0.1"):
            return True
        addr = _parse_ip_host(parsed.hostname)
        return bool(addr and addr.is_loopback)
    except Exception:
        return False


def _private_lan_style_origin(origin: str) -> bool:
    """*.local or RFC1918 host — opens dashboard via LAN IP / mDNS, not loopback hostname."""
    try:
        parsed = urlparse(origin)
        if parsed.scheme not in ("http", "https"):
            return False
        host = parsed.hostname
        if not host:
            return False
        if host in ("localhost", "127.0.0.1"):
            return False
        if host.endswith(".local"):
            return True
        addr = _parse_ip_host(host)
        if not addr:
            return False
        if addr.is_loopback:
            return False
        return bool(addr.is_private)
    except ValueError:
        return False
    except Exception:
        return False


def _allow_credentialed_localhost_loopback_cors() -> bool:
    return bool(getattr(settings, "DEBUG", False) or getattr(settings, "TRUST_LOCALHOST_LOOPBACK_CORS", False))


def _allow_credentialed_lan_dashboard_cors() -> bool:
    return bool(getattr(settings, "DEBUG", False) or getattr(settings, "TRUST_LAN_DASHBOARD_CORS", False))


def _origin_hostname_matches_suffix(hostname: str, suffix: str) -> bool:
    """suffix like 'vercel.app' or '.vercel.app' — avoid spoofing (e.g. evilvercel.app)."""
    suf = suffix.strip().lower().lstrip(".")
    if not suf:
        return False
    host = hostname.strip().lower()
    return host == suf or host.endswith("." + suf)


def _credentialed_origin_allowed_by_suffix(origin: str, suffixes: tuple[str, ...]) -> bool:
    if not suffixes:
        return False
    try:
        parsed = urlparse(origin)
        if parsed.scheme not in ("http", "https"):
            return False
        host = parsed.hostname
        if not host:
            return False
        return any(_origin_hostname_matches_suffix(host, s) for s in suffixes)
    except Exception:
        return False


class DevCorsMiddleware:
    """CORS for dashboard allowlist + dev/LAN + open signup POST for newsletter/donations."""

    BASE_ORIGINS = frozenset(
        {
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://[::1]:3000",
            "http://localhost:8080",
            "http://127.0.0.1:8080",
            "http://[::1]:8080",
            "https://geoclimatz.pythonanywhere.com",
            "https://admin-dashboard.geoclimatz.org",
        }
    )

    def __init__(self, get_response):
        self.get_response = get_response
        extra = frozenset(getattr(settings, "CORS_EXTRA_ORIGINS", []) or [])
        self.allowed_origins = self.BASE_ORIGINS | extra
        self.origin_suffixes: tuple[str, ...] = tuple(getattr(settings, "CORS_ORIGIN_SUFFIXES", ()) or ())

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
        elif origin and self.origin_suffixes and _credentialed_origin_allowed_by_suffix(origin, self.origin_suffixes):
            self._apply_credentialed_cors(response, origin)
        elif origin and _allow_credentialed_localhost_loopback_cors() and _is_loopback_browser_origin(origin):
            self._apply_credentialed_cors(response, origin)
        elif origin and _allow_credentialed_lan_dashboard_cors() and (
            _private_lan_style_origin(origin) or _is_loopback_browser_origin(origin)
        ):
            self._apply_credentialed_cors(response, origin)

        return response

    @staticmethod
    def _build_preflight_response():
        from django.http import HttpResponse

        return HttpResponse(status=204)
