# rhymes_with_soot

**Shared web-service infrastructure: auth, stateless sessions, CSRF, SQLite + WAL, user provisioning.**

rhymes_with_soot is a Python web framework built on Flask that gives you a production-ready internal service in minutes. It handles everything a small team's web app needs: authentication, security, database, error pages, logging, and deployment concerns, so you can focus on your application logic.

## Installation

### Prerequisites

- Python ≥ 3.12
- (Optional) gunicorn ≥ 21.2 for production deployment
- (Optional) nginx for reverse proxy / TLS termination

### Install

```bash
git clone https://github.com/sootleaf/rhymes-with-soot.git
cd rhymes-with-soot
pip install -r requirements.txt
```

The `rhymes_with_soot/` directory is then importable from any site in the same tree.

---

## Configuration

Every site subclasses `BaseConfig` and sets an `ENV_PREFIX`. The framework reads all settings from environment variables using that prefix.

### Required environment variables

| Variable | Description |
|----------|-------------|
| `<PREFIX>_SECRET_KEY` | Signing key for sessions and CSRF tokens. **Required.** The app refuses to start without it. |
| `<PREFIX>_DB_PATH` | Path to the SQLite database file (e.g. `/var/lib/mysite/app.db`). |
| `<PREFIX>_USERS_FILE` | Path to the `users.json` provisioning file. |

### Optional environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `<PREFIX>_SECRET_KEYFILE` | — | Path to a file containing the secret key (alternative to the env var). |
| `LOGIN_REDIRECT` | `/` | Where to redirect after successful login. Set to your dashboard URL. |
| `APP_NAME` | `rhymes_with_soot` | Display name injected into templates. |

### Generating a secret key

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Store the output in your environment (e.g. a `.env` file managed by your process supervisor, or a systemd `EnvironmentFile`).

---

## Plugging in a Site

A "site" is a Python package under `sites/` that provides its own config, blueprints, and models. Here's the minimal structure:

```
sites/mysite/
├── __init__.py
├── config.py          # Your Config class
├── routes.py          # Your blueprints
├── models.py          # Your domain models (on rhymes_with_soot's Base)
├── templates/         # Overrides framework templates by filename
│   └── base.html
├── static/            # Your CSS/JS (shadows framework assets by filename)
│   └── css/
│       └── site.css
└── users.json         # Provisioning file (NOT committed to git)
```

Or copy the template. `site_template/` at the repo root has the structure and wiring already done — the `create_app` call, `base.html` extending `framework_base.html`, the CSS drop-in points. Copy it and rename:

```bash
cp -r site_template sites/mysite
```

Rename every `site_template` reference to your site name (config class, `ENV_PREFIX`, blueprint name, `url_for` targets). Verify nothing is missed:

```bash
grep -rn "site_template" sites/mysite/   # must return nothing
```

Then replace the sample model in `models.py`, the sample routes in `routes.py`, and the templates with your own. The `__init__.py` wiring, `base.html`, and `site.css` stay as-is.

### 1. Define your config

```python
# mysite/config.py
from rhymes_with_soot.config import BaseConfig


class MySiteConfig(BaseConfig):
    ENV_PREFIX = "MYSITE"
    APP_NAME = "My Site"
    LOGIN_REDIRECT = "/dashboard"
    SESSION_COOKIE = "mysite_session"
    CSRF_COOKIE = "mysite_csrf"
```

`ENV_PREFIX`, `SESSION_COOKIE`, and `CSRF_COOKIE` are **required** — the app refuses to start without them. `ENV_PREFIX` names the environment variables the site reads; the two cookie names are your site's identity in the browser. `SECRET_KEY`, `DB_PATH`, and `USERS_FILE` are resolved from `MYSITE_SECRET_KEY`, `MYSITE_DB_PATH`, and `MYSITE_USERS_FILE` automatically.

### 2. Define your models

```python
# mysite/models.py
from rhymes_with_soot.models import Base, uuid4, now
from sqlalchemy import Column, String, Integer, DateTime


class Document(Base):
    __tablename__ = "documents"

    id = Column(String(36), primary_key=True, default=uuid4)
    title = Column(String(256), nullable=False)
    owner = Column(String(64), nullable=False)
    created_at = Column(DateTime, default=now)
```

All models share rhymes_with_soot's single `Base`, and `create_all` is called automatically at startup after your blueprints are registered.

### 3. Define your routes

```python
# mysite/routes.py
from flask import Blueprint, render_template, redirect, url_for
from rhymes_with_soot.auth.session import get_current_user, login_required
from rhymes_with_soot.db import get_session
from mysite.models import Document

site_bp = Blueprint("site", __name__)


@site_bp.route("/")
def index():
    return render_template("index.html")


@site_bp.route("/dashboard")
@login_required
def dashboard():
    session = get_session()
    docs = session.query(Document).all()
    return render_template("dashboard.html", docs=docs)
```

### 4. Create the app

```python
# mysite/__init__.py
from rhymes_with_soot import create_app
from mysite.config import MySiteConfig
from mysite.routes import site_bp


def create():
    app = create_app(MySiteConfig, blueprints=[site_bp])

    # Provision users at startup. Must come after create_app, which creates
    # the database tables that provision_users inserts into.
    from rhymes_with_soot.provisioning import provision_users
    provision_users(app)

    return app


app = create()
```

### 5. Run it

```bash
# Development
export MYSITE_SECRET_KEY="your-64-char-hex-key"
export MYSITE_DB_PATH="/tmp/mysite.db"
export MYSITE_USERS_FILE="/tmp/mysite-users.json"

PYTHONPATH=sites python -m flask --app mysite run

# Production
PYTHONPATH=sites gunicorn -w 4 -b 127.0.0.1:8000 "mysite:app"
```

### Template and static asset shadowing

The framework ships with `base.html`, `login.html`, and error page templates. To customize any of them, place a file with the **same name** in your site's `templates/` directory. Your version takes priority; the framework's is the fallback.

**Important:** your site's `base.html` must extend `framework_base.html`, not `base.html`. Because your file shadows the framework's `base.html` by name, extending `"base.html"` would resolve to your own file and recurse infinitely.

The same applies to static assets: a `static/css/framework.css` in your site directory shadows the framework's.

### The `users.json` file

```json
{
  "alice": "s3cur3-p@ssw0rd-h3r3",
  "bob": "an0th3r-l0ng-p@ssw0rd"
}
```

- Existing users are **never overwritten** (safe to re-run on every boot).
- The file is read once at startup and accounts are created idempotently.
- The password is hashed with PBKDF2 on import; the file is the only place plaintext exists.
- These are seed passwords for initial account creation only. Users can change their password later.
- **Do not commit this file to version control.** Add it to your `.gitignore`.

---

## Security Model

| Mechanism | How it works |
|-----------|-------------|
| Sessions | Stateless. The cookie is a signed, expiring `itsdangerous` payload. Valid on any worker. |
| CSRF | Synchronizer token in a signed HttpOnly cookie + hidden form field / `X-CSRF-Token` header. Token is **bound to the user's identity**: a token issued for user A is rejected if the session is user B. |
| Passwords | Hashed with `werkzeug.security` (PBKDF2). Plaintext never stored. |
| HSTS | `max-age=31536000; includeSubDomains` on all HTTPS responses. |
| Cookies | `HttpOnly`, `SameSite=Lax`, `Secure` (when HTTPS). |
| Open redirects | `safe_referrer()` only allows same-host or relative-path redirects. |
| Static assets | SHA-256 query-param versioning prevents stale cache after deploys. |

---

## Optional: nginx Configuration

A typical production setup puts nginx in front of gunicorn for TLS termination and static file serving.

```nginx
# /etc/nginx/sites-available/mysite
upstream mysite {
    server 127.0.0.1:8000;
    keepalive 32;
}

server {
    listen 80;
    server_name internal.example.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name internal.example.com;

    ssl_certificate     /etc/letsencrypt/live/internal.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/internal.example.com/privkey.pem;
    ssl_protocols       TLSv1.2 TLSv1.3;

    # Security headers (HSTS is also set by the app, but nginx is defense-in-depth)
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options nosniff always;
    add_header X-Frame-Options DENY always;
    add_header Referrer-Policy strict-origin-when-cross-origin always;

    # Static files served directly by nginx (bypasses the app)
    location /static/ {
        alias /home/deploy/mysite/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # Everything else goes to gunicorn
    location / {
        proxy_pass http://mysite;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
    }

    # Limit upload size (matches the 413 error page)
    client_max_body_size 50m;
}
```

> **Note:** If nginx serves `/static/` directly, the app's built-in static route is redundant but harmless. The app's versioning query params (`?v=abc123`) will still work because the files on disk are the same.

---

## Optional: fail2ban Configuration

rhymes_with_soot logs failed logins to the `rhymes_with_soot` logger. You can use fail2ban to ban IPs that repeatedly fail authentication.

### Log format

The app logs failed logins as:

```
2025-01-15 10:23:45,123 WARNING rhymes_with_soot: Login failed user='badactor' ip=203.0.113.42
```

### jail.local

```ini
# /etc/fail2ban/jail.local

[mysite_login]
enabled  = true
filter   = mysite_login
backend  = systemd
journal_match_cmd = _COMM=python
maxretry = 5
bantime  = 1h
findtime = 10m
```

### Filter

```ini
# /etc/fail2ban/filter.d/mysite_login.conf

[Definition]
failregex = ^\S+ \S+ WARNING rhymes_with_soot: Login failed user='.*' ip=(?P<ip>\S+)$
ignoreregex =
```

### Alternative: file-based log

If you're not using systemd journal, redirect the app's stderr to a file and adjust:

```ini
[mysite_login]
enabled  = true
filter   = mysite_login
logpath  = /var/log/mysite/error.log
maxretry = 5
bantime  = 1h
findtime = 10m
```

---

## Deployment Checklist

- [ ] `SECRET_KEY` is a random 64+ hex character string, stored in an env file (not in git)
- [ ] `DB_PATH` points to a persistent volume with adequate disk space
- [ ] `USERS_FILE` is on disk, contains your initial users, and is in `.gitignore`
- [ ] gunicorn worker count matches your CPU cores (or slightly more for I/O-bound workloads)
- [ ] nginx terminates TLS and forwards to gunicorn
- [ ] `users.json` is never committed to version control
- [ ] The SQLite `.db`, `.db-wal`, and `.db-shm` files are not in a web-accessible directory
- [ ] fail2ban (or equivalent) is active on the login endpoint
- [ ] Log output is shipped to your central log aggregator

---

## Project Structure

```
rhymes_with_soot/
├── __init__.py          # Application factory (create_app)
├── config.py            # BaseConfig with env-var resolution
├── csrf.py              # Identity-bound CSRF protection
├── db.py                # SQLAlchemy engine, WAL pragmas, session management
├── errors.py            # Error handlers (JSON + themed HTML)
├── logging.py           # Structured 4xx/5xx logging
├── models.py            # Shared Base + User model
├── provisioning.py      # Startup user provisioning from users.json
├── util.py              # utcnow, safe_referrer, format_size
├── auth/
│   ├── __init__.py
│   ├── routes.py        # /login and /logout
│   └── session.py       # Stateless signed-cookie sessions
├── templates/
│   ├── base.html               # Override point; a site shadows this by name
│   ├── framework_base.html     # Reserved core layout (never overridden)
│   ├── login.html
│   └── errors/
│       ├── 400.html
│       ├── 401.html
│       ├── 403.html
│       ├── 404.html
│       ├── 405.html
│       ├── 410.html
│       ├── 413.html
│       ├── 416.html
│       ├── 418.html
│       └── 500.html
└── static/
    └── css/
        └── framework.css
```

---

## License

All rights reserved. See [LICENSE](LICENSE).
