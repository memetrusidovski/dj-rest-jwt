# Contributing

## Setup

```bash
git clone https://github.com/memetrusidovski/dj-rest-jwt.git
cd dj-rest-jwt
python -m venv .venv && source .venv/bin/activate     # Python 3.12+
pip install -e . -r dj_rest_jwt/tests/requirements.txt
```

## Python tests

```bash
python runtests.py                                  # all
python runtests.py dj_rest_jwt.tests.test_tokens    # one module
coverage run ./runtests.py && coverage report
flake8 dj_rest_jwt/
tox                                                 # Python 3.12–3.14 × Django 6.0/6.1
```

Tests are end-to-end over HTTP. A change to a security-relevant code path needs a test that fails
when the protection is removed.

## JavaScript client

```bash
cd js
npm install
npm test                       # unit tests
```

End-to-end against the demo backend, both transports:

```bash
mkdir -p /tmp/mails
cd demo/backend && python manage.py migrate
EMAIL_FILE_PATH=/tmp/mails python manage.py runserver 8765 &
cd ../../js && E2E_URL=http://localhost:8765 E2E_MAILS=/tmp/mails npx vitest run test/e2e.test.ts
```

## Docs

```bash
pip install -r docs/requirements.txt
zensical serve                 # http://localhost:8000
```

Pushes to `main` publish the site to GitHub Pages.

## Principles

- Prefer an allauth feature or setting over new code here. Add code only where allauth has no
  hook, and keep it small.
- Secure by default: a new option that weakens security defaults to off and gets a system check.
