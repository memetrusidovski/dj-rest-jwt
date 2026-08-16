# dj-rest-jwt Demo Architecture

This directory contains a complete demonstration of a modern Single Page Application (SPA) authentication flow using `dj-rest-jwt`.

## Overview

The demo consists of two main components:

1.  **Backend (`demo/backend`)**: A Django project using `dj-rest-jwt`, `django-allauth`, and `djangorestframework-simplejwt`. It exposes REST APIs for registration, login, and Multi-Factor Authentication (MFA).
2.  **Frontend (`demo/spa-client`)**: A Next.js application that consumes the backend APIs. It demonstrates a complete user flow including registration, login, MFA setup (QR code), and MFA verification.
3.  **API tour (`demo/templates`)**: Server-rendered pages the backend serves at
    [http://localhost:8000](http://localhost:8000) - one page per endpoint, driven by
    [Alpine.js](https://alpinejs.dev) and [axios](https://axios-http.com) from a CDN, with no
    build step. Each page submits a real request and shows the raw response beside the form,
    which makes it the quickest way to poke at an endpoint without wiring up a client.

## Architecture Diagram

```mermaid
graph TD
    User[User / Browser]
    subgraph Frontend [Next.js App (Port 3000)]
        Pages[Pages]
        AuthContext[Auth Context]
        ApiClient[Axios Client]
    end
    subgraph Backend [Django API (Port 8000)]
        DjRestAuth[dj-rest-jwt]
        AllAuth[django-allauth]
        MFA[MFA App]
        DB[(SQLite DB)]
    end

    User -->|Interacts| Pages
    Pages -->|Uses| AuthContext
    AuthContext -->|Requests| ApiClient
    ApiClient -->|HTTP Requests| DjRestAuth
    
    DjRestAuth -->|Auth Logic| AllAuth
    DjRestAuth -->|MFA Logic| MFA
    AllAuth -->|Persists| DB
    MFA -->|Persists| DB

    note1[Login Flow]
    User -.->|1. Credentials| Pages
    Pages -.->|2. Login| DjRestAuth
    DjRestAuth -.->|3. MFA Required + Ephemeral Token| Pages
    Pages -.->|4. Verify Code + Token| DjRestAuth
    DjRestAuth -.->|5. Auth Token / Session| User
```

## Running the Demo

The easiest way to run the demo is with Docker Compose:

```bash
cd demo
docker-compose up --build
```
- Frontend (Next.js SPA): [http://localhost:3000](http://localhost:3000)
- Backend + API tour: [http://localhost:8000](http://localhost:8000)

### Backend only

The API tour needs nothing but the Django server, so if you only want to explore the
endpoints:

```bash
cd demo/backend
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Then open [http://localhost:8000](http://localhost:8000) and work down the sidebar:
sign up, log in, load your profile, enrol TOTP, and log in again to meet the second-factor
challenge. The token from a successful login is held in `localStorage` and reused by every
other page, so there is no copying tokens between forms.

Note this project pins `USE_JWT = False` with a `TOKEN_MODEL`, so it demonstrates the classic
token flow; the package's own default is JWT-only. Verification and password-reset emails are
printed to the console the server is running in.
