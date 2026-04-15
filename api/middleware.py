class DevCorsMiddleware:
    """Simple dev CORS middleware for Next.js dashboard integration."""

    ALLOWED_ORIGINS = {
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://geoclimatz.pythonanywhere.com",
        "https://admin-dashboard.geoclimatz.org",
    }

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == "OPTIONS":
            response = self._build_preflight_response()
        else:
            response = self.get_response(request)

        origin = request.headers.get("Origin")
        if origin in self.ALLOWED_ORIGINS:
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
