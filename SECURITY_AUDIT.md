# Security Audit — guitar-scale-generator

Date: 2026-07-14. Scope: full repo at branch `worktree-agent-a608065df867fb560`
(post secrets-to-.env change). Django 5.2.16, Python 3.13, SQLite.

## Critical

### C1. Old SECRET_KEY is in git history — treat as compromised
- **Location:** commit `46c8ffb`, `config/settings.py:23` (`django-insecure-6md!...`).
- **Risk:** anyone with repo access (or a future public push) can read the key
  from history and forge session cookies, CSRF tokens, and password-reset
  tokens for any deployment that ever used it.
- **Recommendation:** the key is now removed from tracked files and replaced by
  `DJANGO_SECRET_KEY` from `.env`, but history still contains it. **Never
  deploy with the old key.** A fresh key has been generated for `.env`; if the
  repo is ever made public, either rewrite history (`git filter-repo`) or
  simply accept the old key as burned — it must not be reused either way.

## High

### H1. Production HTTPS hardening not configured (deploy-blocker)
- **Location:** `config/settings.py` — no `SECURE_SSL_REDIRECT`,
  `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, or `SECURE_HSTS_*`.
- **Evidence:** `manage.py check --deploy` (run with `DJANGO_DEBUG=false`,
  temp key, `DJANGO_ALLOWED_HOSTS=example.com`):
  ```
  ?: (security.W004) You have not set a value for the SECURE_HSTS_SECONDS setting. ...
  ?: (security.W008) Your SECURE_SSL_REDIRECT setting is not set to True. ...
  ?: (security.W012) SESSION_COOKIE_SECURE is not set to True. ...
  ?: (security.W016) You have 'django.middleware.csrf.CsrfViewMiddleware' ... CSRF_COOKIE_SECURE ... not True. ...
  System check identified 4 issues (0 silenced).
  ```
- **Risk:** session/CSRF cookies sent over plaintext HTTP; no forced HTTPS.
- **Recommendation:** before production cutover, add a `if not DEBUG:` block
  setting `SECURE_SSL_REDIRECT = True`, `SESSION_COOKIE_SECURE = True`,
  `CSRF_COOKIE_SECURE = True`, and (once HTTPS is confirmed stable)
  `SECURE_HSTS_SECONDS` with `SECURE_HSTS_INCLUDE_SUBDOMAINS`/`_PRELOAD`.
  If behind a TLS-terminating proxy, also set `SECURE_PROXY_SSL_HEADER`.

## Medium

### M1. `POST /api/log/` is unauthenticated with no rate limiting
- **Location:** `practice/views.py:53-93` (`api_log`), routed at
  `practice/urls.py:10`.
- **Risk:** any visitor can insert unlimited `AttemptLog` rows (CSRF protects
  against cross-site abuse, but a direct client can fetch the page, read the
  token, and flood). Consequences: disk exhaustion on SQLite and poisoning of
  the future spaced-repetition weighting that will consume these rows.
- **Recommendation:** before production, add rate limiting (e.g.
  `django-ratelimit` per-IP on `api_log`) and/or require auth once the planned
  users/auth TODO lands. A row cap or periodic pruning is a cheap stopgap.

### M2. `form_id` accepted unvalidated against known forms (known, fix in flight)
- **Location:** `practice/views.py:76-77` — `form_id` only checked as a
  non-empty string; not checked against `theory.load_fingerings()` and not
  length-bounded, while `AttemptLog.form_id` is `CharField(max_length=64)`
  (`practice/models.py:14`), which SQLite does not enforce.
- **Risk:** arbitrary/oversized junk stored in `form_id`, corrupting future
  spaced-repetition inputs.
- **Status:** known issue; a parallel change is fixing it. Not re-fixed here.

### M3. Django admin enabled and unused
- **Location:** `config/urls.py:6` (`path("admin/", admin.site.urls)`);
  `practice/admin.py` registers no models.
- **Risk:** exposes a login form (credential-stuffing target, framework
  fingerprint) at a well-known URL for zero current benefit.
- **Recommendation:** remove the admin URL + `django.contrib.admin` until
  needed, or move it to a non-default path and restrict access when auth
  arrives.

## Low

### L1. `DEBUG` defaults to true when `DJANGO_DEBUG` is unset
- **Location:** `config/settings.py` (`_env_bool("DJANGO_DEBUG", "true")`).
- **Risk:** a production box missing the env var silently runs with DEBUG on
  (stack traces, settings leakage). Deliberate trade-off so fresh clones/tests
  work; the fail-loud SECRET_KEY check only trips when DEBUG is false.
- **Recommendation:** deployment docs/scripts must set `DJANGO_DEBUG=false`
  explicitly; consider flipping the default to false at production cutover.

### L2. Dependencies are range-pinned, not locked
- **Location:** `requirements.txt` (`Django>=5.2,<6`, `PyYAML>=6.0`,
  `python-dotenv>=1.0`).
- **Evidence:** `pip list --outdated`: `asgiref 3.11.1 -> 3.12.1`,
  `Django 5.2.16 -> 6.0.7` (6.x is outside the pin; 5.2 is LTS, supported to
  April 2028, and the `<6` range keeps pulling 5.2.x security patches).
- **Risk:** non-reproducible installs; a bad upstream release lands silently.
- **Recommendation:** for production, generate a lock file (`pip-compile` or
  `pip freeze > requirements.lock`) and update deliberately; keep the venv's
  Django on the latest 5.2.x patch.

### L3. No `STATIC_ROOT` configured
- **Location:** `config/settings.py` (`STATIC_URL` only).
- **Risk:** `collectstatic` fails in production; teams sometimes "fix" this by
  serving with DEBUG on. Deployment hygiene rather than a direct vuln.
- **Recommendation:** set `STATIC_ROOT` and serve via WhiteNoise or the web
  server at deploy time.

## Verified OK

- Secrets: `git grep -n "django-insecure" -- ':!*.md'` is empty; `.env` and
  `.env.*` (except `.env.example`) gitignored; `db.sqlite3` gitignored; no
  credentials in `practice/configs/` or scripts.
- Fail-loud config: with `DJANGO_DEBUG=false` and no `DJANGO_SECRET_KEY`,
  startup raises `django.core.exceptions.ImproperlyConfigured` (verified).
- YAML: `yaml.safe_load` everywhere (`practice/theory.py:150,336`,
  `scripts/generate_fingerings.py:83`); no `yaml.load`/unsafe loaders.
- No `csrf_exempt`, `mark_safe`, `|safe`, `{% autoescape off %}`, raw SQL,
  `.extra(`, `.raw(`, string-built queries, `eval`/`exec`, `pickle`, or
  `os.system` anywhere in app code; `subprocess.run` appears only in
  `practice/tests/test_generator.py:39` with a fixed argv (no shell).
- CSRF: token is passed via `data-csrf-token` (`templates/practice/index.html:10`)
  and sent as `X-CSRFToken` on the fetch POST (`static/practice/app.js:6,231`);
  `CsrfViewMiddleware` active.
- DOM XSS: the single `innerHTML` write (`app.js:175`) assigns a static string;
  all server-derived round data is set with `textContent`.
- Input surface: `GET /api/round/` takes no user input; `POST /api/log/`
  strictly whitelists `scale`/`key`/`direction`/`correct` against server-side
  enums and rejects non-object/invalid JSON with 400. Request body is bounded
  by Django's default `DATA_UPLOAD_MAX_MEMORY_SIZE` (2.5 MB); oversize bodies
  become 400 via `SuspiciousOperation` handling.
- DB access is ORM-only (one `objects.create` in `views.py:90`) — parameterized.
- Headers: `SECURE_CONTENT_TYPE_NOSNIFF` defaults to `True` and
  `X_FRAME_OPTIONS` defaults to `DENY` in Django 5.2 with the shipped
  middleware stack (`SecurityMiddleware`, `XFrameOptionsMiddleware` present).
- `ALLOWED_HOSTS` now env-driven (`DJANGO_ALLOWED_HOSTS`, comma-separated,
  dev default `localhost,127.0.0.1`) — must be set to the real hostname(s) in
  production; Django refuses other Host headers.
- `manage.py check` (dev mode): "System check identified no issues"; full test
  suite (84 tests) passes under the new env-driven settings.
