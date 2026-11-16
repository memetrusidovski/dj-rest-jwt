from django.apps import AppConfig


class DjRestJwtConfig(AppConfig):
    name = "dj_rest_jwt"
    verbose_name = "dj-rest-jwt"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        from django.apps import apps

        from . import checks  # noqa: F401  (registers the system checks)
        from . import conf

        if conf.get("ADMIN_LOGIN") and apps.is_installed("django.contrib.admin"):
            from .admin_login import secure_admin_site
            secure_admin_site()
