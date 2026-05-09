from django.conf import settings

# POST endpoints that accept anonymous JSON from arbitrary marketing origins (no session cookie).
_PUBLIC_FORM_TAIL_SEGMENTS = frozenset({"newsletter", "donations"})


class DevCorsMiddleware:
    """CORS for dashboard allowlist + open signup POST for newsletter/donations from any Origin."""

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
        """Newsletter/donation signup POST + OPTIONS preflight — safe to reflect any Origin (no credentialed reads)."""
        if request.method not in ("POST", "OPTIONS"):
            return False
        tail = request.path.rstrip("/").split("/")[-1]
        return tail in _PUBLIC_FORM_TAIL_SEGMENTS

    def __call__(self, request):
        if request.method == "OPTIONS":
            response = self._build_preflight_response()
        else:
            response = self.get_response(request)

        origin = request.headers.get("Origin")

        # Any deployed frontend can POST signup payloads without being added to a whitelist.
        if origin and self._is_public_anonymous_post(request):
            response["Access-Control-Allow-Origin"] = origin
            response["Access-Control-Allow-Methods"] = "POST, OPTIONS"
            response["Access-Control-Allow-Headers"] = "Content-Type, Accept"
            response["Vary"] = "Origin"
            if request.method == "OPTIONS":
                response["Access-Control-Max-Age"] = "86400"
            return response

        if origin in self.allowed_origins:
            response["Access-Control-Allow-Origin"] = origin
            response["Access-Control-Allow-Credentials"] = "true"
            response["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-CSRFToken"
            response["Access-Control-Allow-Methods"] = "GET, POST, PATCH, DELETE, OPTIONS"
            response["Vary"] = "Origin"
        return response

    @staticmethod
    def _build_preflight_response():
        from django.http import HttpResponse

        return HttpResponse(status=204)
