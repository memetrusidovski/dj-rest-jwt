# DJ-REST-JWT

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A modern, JWT-first authentication package for Django Rest Framework. Built to address the limitations of dj-rest-auth with better defaults, enhanced security features, and a focus on developer experience.

## Why DJ-REST-JWT?

DJ-REST-JWT is a reimagining of dj-rest-auth with JWT authentication as the primary focus. While dj-rest-auth requires extensive configuration and has limited support for modern authentication patterns, DJ-REST-JWT provides:

- **JWT by default** - No configuration needed for secure, stateless authentication
- **Enhanced security** - Built-in reCAPTCHA support and rate limiting
- **Better email verification** - Reliable, token-based email verification flows
- **Starter project included** - Get up and running in minutes with working examples
- **Modern tooling** - Built with `uv` for faster dependency management

## Requirements

- Django >= 4.2
- Python >= 3.8
- djangorestframework >= 3.14

## Quick Setup

Install package using `uv`:
```bash
uv pip install dj-rest-jwt
```

Or with pip:
```bash
pip install dj-rest-jwt
```

Add `dj_rest_jwt` to your `INSTALLED_APPS`:
```python
INSTALLED_APPS = [
    ...,
    'rest_framework',
    'dj_rest_jwt',
]
```

Add URL patterns:
```python
from django.urls import path, include

urlpatterns = [
    path('api/auth/', include('dj_rest_jwt.urls')),
]
```

That's it! JWT authentication is enabled by default with secure http-only cookies.

## Features

### 🔐 JWT Authentication (Default)
- Automatic JWT token generation and refresh
- Secure http-only cookie support out of the box
- Configurable token expiration and refresh strategies

### 🛡️ Enhanced Security
- **reCAPTCHA Integration** - Protect registration and login endpoints from bots
- **Rate Limiting** - Built-in throttling for authentication endpoints
- **CORS Support** - Proper CORS configuration for SPA applications
- **Secure Password Reset** - Token-based password reset with expiration

### ✉️ Reliable Email Verification
- Token-based email verification that actually works
- Customizable email templates
- Magic link support for passwordless authentication
- Resend verification email endpoint

### 🚀 Developer Experience
- **Starter Project** - Complete example project with React frontend
- **Comprehensive Documentation** - Clear examples and troubleshooting guides
- **Type Hints** - Full type annotation support
- **Modern Testing** - Fast test suite with pytest

### 📱 OAuth & Social Authentication
Essential OAuth providers built-in:
- Google OAuth 2.0
- GitHub OAuth
- Microsoft Azure AD
- Custom OAuth provider support

### 🎯 Production-Ready Features
- **Multi-factor Authentication (MFA)** - TOTP support via authenticator apps
- **Session Management** - View and revoke active sessions
- **Audit Logging** - Track authentication events
- **Account Deactivation** - Soft delete user accounts

## Configuration

DJ-REST-JWT works out of the box with sensible defaults. Customize as needed:
```python
# settings.py
DJ_REST_JWT = {
    # JWT Settings
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=15),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    
    # Cookie Settings
    'JWT_AUTH_COOKIE': 'jwt-access',
    'JWT_AUTH_REFRESH_COOKIE': 'jwt-refresh',
    'JWT_AUTH_SECURE': True,  # HTTPS only in production
    'JWT_AUTH_SAMESITE': 'Lax',
    
    # Email Verification
    'EMAIL_VERIFICATION': 'mandatory',  # or 'optional', 'none'
    'EMAIL_VERIFICATION_TOKEN_LIFETIME': timedelta(days=3),
    
    # Security Features
    'ENABLE_RECAPTCHA': True,
    'RECAPTCHA_SITE_KEY': env('RECAPTCHA_SITE_KEY'),
    'RECAPTCHA_SECRET_KEY': env('RECAPTCHA_SECRET_KEY'),
    
    # MFA
    'ENABLE_MFA': True,
    
    # Rate Limiting
    'ENABLE_RATE_LIMITING': True,
    'RATE_LIMIT_REGISTRATION': '5/hour',
    'RATE_LIMIT_LOGIN': '10/hour',
}
```

## Development

This project uses `uv` for dependency management:
```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone the repository
git clone https://github.com/yourusername/dj-rest-jwt.git
cd dj-rest-jwt

# Install dependencies
uv sync

# Run tests
uv run pytest

# Run the example project
cd example_project
uv run python manage.py migrate
uv run python manage.py runserver
```

### Testing
```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=dj_rest_jwt

# Run specific test file
uv run pytest tests/test_authentication.py

# Run linting
uv run ruff check .
uv run mypy dj_rest_jwt
```

## Starter Project

The included starter project demonstrates:
- Complete authentication flow (register, login, logout, refresh)
- Email verification with resend functionality
- Password reset flow
- Protected API endpoints
- React frontend with authentication hooks
- reCAPTCHA integration
```bash
cd example_project
uv run python manage.py migrate
uv run python manage.py runserver
```

Visit `http://localhost:3000` to see the demo.

## Documentation

Full documentation available at: https://dj-rest-jwt.readthedocs.io

## Roadmap

- [ ] WebAuthn / Passkey support
- [ ] OAuth 2.1 compliance
- [ ] GraphQL authentication support
- [ ] Admin dashboard for user management
- [ ] Webhook notifications for auth events

## Contributing

Contributions are welcome! Please read our [Contributing Guide](CONTRIBUTING.md) for details.

## Why Not dj-rest-auth?

While dj-rest-auth is a solid package, it has some limitations:

- Requires extensive configuration for JWT
- Limited django-allauth integration with unclear boundaries
- Email verification can be unreliable
- Lacks modern security features like reCAPTCHA
- No starter project or comprehensive examples

DJ-REST-JWT addresses these issues while maintaining a focused scope and excellent developer experience.

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Acknowledgements

Inspired by dj-rest-auth and django-allauth. Thanks to all contributors to those projects for paving the way!