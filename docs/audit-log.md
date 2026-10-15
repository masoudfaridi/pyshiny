# Audit log

Events are stored in `db/audit.db` (SQLite, WAL), separate from `db/auth.db`.
`db/` is already a Docker volume, so the log survives restarts.
Only a superadmin can read it: sidebar tab **Logs** (last tab).

## Categories

| Category | Events |
|----------|--------|
| `auth` | `login_success`, `login_failed` (reason: `bad_credentials` / `captcha`), `logout`, `password_changed`, `password_change_failed` |
| `navigation` | `tab_opened` (one row per tab change), `session_ended` (browser closed while signed in) |
| `security` | `access_denied` (any `@superadmin/@admin/@user/@guest` refusal), `unauthorized_tab_request`, `unknown_tab_request`, `account_locked`, `login_blocked_locked`, `session_revoked` (account deleted / disabled / expired), `user_created`, `user_updated`, `role_changed`, `user_deleted` |

Severity is `info`, `warning` or `critical` (e.g. a role change that touches a
superadmin is `critical`).

## Superadmin policy

Every account is logged, **superadmin included** (default). To skip a
superadmin's own routine activity (login, logout, navigation, session end) set
the environment variable `AUDIT_LOG_SUPERADMIN=0`. Even then two things are
still recorded:

1. account / role management done by a superadmin (`ALWAYS_LOG_EVENTS` in
   `auth/audit.py`), and
2. attacks on the `superadmin` account by anonymous visitors (failed logins,
   lockout) -- the actor is anonymous, so the policy does not apply.

## Where things happen

* `auth/audit.py` -- `log_event()` (never raises), `query_events()`, `purge_old()`.
* `auth/core.py` -- the decorator logs every denial; `create_user`,
  `update_user`, `delete_user`, `change_own_password` log themselves;
  `list_audit_events()` is `@superadmin`.
* `app.py` -- login / logout / navigation / session end / revoked session.
* `tabs/tab_logs.py` -- viewer (3 sub-tabs, filters, CSV export).

## Operations

* **Retention** (purged automatically, at most once an hour): navigation 30
  days, auth 180 days, security 365 days -- `RETENTION_DAYS` in `auth/audit.py`.
* **Client IP:** the direct peer address. Behind a trusted reverse proxy set the
  env var `TRUST_PROXY_HEADERS=1` to use `X-Forwarded-For` instead (it is
  spoofable when no trusted proxy sets it, so it is off by default).
* **Never logged:** passwords, CAPTCHA answers. The typed login name is stored
  (control characters removed, max 64 chars) -- be aware people sometimes type
  a password into that field.
* **Not tamper-proof:** the application has no edit/delete function for the
  log, but anyone who can write the file `db/audit.db` can change it. Ship the
  log to external storage if you need that guarantee.
