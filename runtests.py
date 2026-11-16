#!/usr/bin/env python
import os
import sys

import django
from django.conf import settings
from django.test.utils import get_runner


def runtests(labels=None):
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dj_rest_jwt.tests.settings")
    django.setup()
    runner = get_runner(settings)(verbosity=1, interactive=False)
    failures = runner.run_tests(labels or ["dj_rest_jwt.tests"])
    sys.exit(bool(failures))


if __name__ == "__main__":
    runtests(sys.argv[1:])
