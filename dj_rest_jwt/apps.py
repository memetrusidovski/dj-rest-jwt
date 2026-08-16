from django.apps import AppConfig


class DjRestJwtConfig(AppConfig):
    name = 'dj_rest_jwt'
    verbose_name = 'dj-rest-jwt'
    default_auto_field = 'django.db.models.BigAutoField'

    def ready(self):
        from . import checks  # noqa: F401  (registers the deployment checks)
