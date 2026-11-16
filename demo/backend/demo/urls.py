from django.contrib import admin
from django.urls import include, path

from .views import MeView

urlpatterns = [
    path("admin/", include("dj_rest_jwt.admin_login")),     # admin sign-in via allauth (+MFA)
    path("admin/", admin.site.urls),
    path("api/auth/", include("dj_rest_jwt.urls")),          # /api/auth/v1/...
    path("api/me", MeView.as_view()),                          # an example protected API
]
