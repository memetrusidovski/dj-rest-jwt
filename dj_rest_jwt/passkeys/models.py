from django.conf import settings
from django.db import models


class WebAuthnCredential(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='webauthn_credentials',
    )
    name = models.CharField(max_length=255)
    # Stored base64url-encoded rather than as a BinaryField: MySQL and MariaDB
    # can't put a unique index on a BLOB without a prefix length, and the unique
    # constraint is what stops one authenticator being registered to two
    # accounts.
    credential_id = models.CharField(max_length=512, unique=True)
    public_key = models.BinaryField()
    sign_count = models.PositiveIntegerField(default=0)
    transports = models.JSONField(default=list, blank=True)
    discoverable = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'passkeys'

    def __str__(self):
        return f'{self.name} ({self.user})'
