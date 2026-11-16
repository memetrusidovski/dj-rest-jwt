from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "Print a new RSA private key (PEM) for HEADLESS_JWT_PRIVATE_KEY. Store it in "
        "your secrets manager or environment, never in source control."
    )

    def add_arguments(self, parser):
        parser.add_argument("--bits", type=int, default=3072, choices=[2048, 3072, 4096])

    def handle(self, *args, bits, **options):
        key = rsa.generate_private_key(public_exponent=65537, key_size=bits)
        pem = key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ).decode()
        self.stdout.write(pem, ending="")
