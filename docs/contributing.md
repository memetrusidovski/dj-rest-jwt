# Contributing

## Setup

```bash
git clone https://github.com/memetrusidovski/dj-rest-jwt.git
cd dj-rest-jwt
uv sync          # creates .venv (Python 3.13) with the package and the test + lint tools
```

[uv](https://docs.astral.sh/uv/) manages the Python version, the virtualenv and the locked dev
tools (`uv.lock`). Users of the package are unaffected; they install it with pip or anything
else.

## Python tests

```bash
uv run python runtests.py                                  # all
uv run python runtests.py dj_rest_jwt.tests.test_tokens    # one module
uv run coverage run runtests.py && uv run coverage report
uv run ruff check dj_rest_jwt runtests.py
uv run --python 3.12 --with "django~=6.0.0" python runtests.py   # another Python/Django combination
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
cd demo/backend && uv run python manage.py migrate
EMAIL_FILE_PATH=/tmp/mails uv run python manage.py runserver 8765 &
cd ../../js && E2E_URL=http://localhost:8765 E2E_MAILS=/tmp/mails npx vitest run test/e2e.test.ts
```

## Docs

```bash
uv run --group docs zensical serve     # http://localhost:8000
```

Pushes to `main` publish the site to GitHub Pages.

## Principles

- Prefer an allauth feature or setting over new code here. Add code only where allauth has no
  hook, and keep it small.
- Secure by default: a new option that weakens security defaults to off and gets a system check.
