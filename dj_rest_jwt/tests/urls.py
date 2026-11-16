from django.contrib import admin
from django.urls import include, path
from rest_framework.response import Response
from rest_framework.views import APIView


class MeView(APIView):
    """Stands in for the project's own DRF API."""

    def get(self, request):
        return Response({"id": request.user.pk, "email": request.user.email})

    def post(self, request):
        return Response({"ok": True})


urlpatterns = [
    path("admin/", include("dj_rest_jwt.admin_login")),
    path("admin/", admin.site.urls),
    path("api/auth/", include("dj_rest_jwt.urls")),
    path("api/me", MeView.as_view(), name="me"),
]
