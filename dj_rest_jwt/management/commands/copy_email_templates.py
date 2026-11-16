"""
Copy allauth's email templates into your project so you can edit them.

    python manage.py copy_email_templates templates/

Copies ``account/email/*`` and ``mfa/email/*`` (verification, password reset,
sign-in code, "your password was changed", ...) to the given templates
directory. Django loads your copies instead of allauth's as long as that
directory is in ``TEMPLATES["DIRS"]`` (or in an app listed before allauth).

Each email is ``<name>_subject.txt`` + ``<name>_message.txt``. Add a
``<name>_message.html`` next to the .txt to also send an HTML version.
Existing files are never overwritten unless you pass ``--force``.
"""
import shutil
from pathlib import Path

import allauth
from django.core.management.base import BaseCommand, CommandError

SOURCES = ("account/email", "mfa/email")


class Command(BaseCommand):
    help = "Copy allauth's email templates into a templates directory for editing."

    def add_arguments(self, parser):
        parser.add_argument("dest", help="Your templates directory, e.g. templates/")
        parser.add_argument("--only", nargs="*", metavar="NAME",
                            help="Only these emails, e.g. email_confirmation password_reset_code")
        parser.add_argument("--force", action="store_true", help="Overwrite files that already exist.")

    def handle(self, dest, only=None, force=False, **options):
        root = Path(allauth.__file__).parent / "templates"
        dest = Path(dest)
        if dest.exists() and not dest.is_dir():
            raise CommandError(f"{dest} is not a directory.")
        copied = skipped = 0
        for sub in SOURCES:
            for src in sorted((root / sub).glob("*.txt")):
                if only and not any(src.name.startswith(f"{name}_") for name in only):
                    continue
                target = dest / sub / src.name
                if target.exists() and not force:
                    skipped += 1
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(src, target)
                copied += 1
                self.stdout.write(f"  {target}")
        if not copied and only:
            raise CommandError(f"No email templates match {only}.")
        self.stdout.write(self.style.SUCCESS(f"Copied {copied} file(s), skipped {skipped} existing."))
