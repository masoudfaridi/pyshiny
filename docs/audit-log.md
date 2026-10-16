# Audit log

Events are stored in `db/audit.db` (SQLite, WAL), separate from `db/auth.db`.
`db/` is already a Docker volume, so the log survives restarts.
Only a superadmin can read it: sidebar tab **Logs** (last tab).

## Categories

| Category | Events |
|----------|--------|
| `auth` | `login_success`, `login_failed` (reason: `bad_credentials` / `captcha`), `logout`, `password_changed`, `password_change_failed` |
| `navigation` | `tab_opened` (one row per tab change), `session_ended` (browser closed while signed in) |
| `security` | `access_denied` (any `@superadmin/@admin/@user/@guest` refusal), `unauthorized_tab_request`, `unknown_tab_request`, `account_locked`, `login_blocked_locked`, `session_revoked` (account deleted / disabled / expired), `user_created`, `user_updated`, `role_changed`, `user_deleted`, `audit_settings_changed`, `audit_cleared`, `reauth_failed`, `reauth_blocked_locked`, `sensitive_action_confirmed` (see `docs/confirm-with-password.md`) |

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

* `auth/audit.py` -- `log_event()` (never raises), `query_events()`, settings
  (`get_settings()` / `save_settings()`), `purge_old()`, `clear()`, `counts()`.
* `auth/core.py` -- the decorator logs every denial; `create_user`,
  `update_user`, `delete_user`, `change_own_password` log themselves.
  `@superadmin`-only: `list_audit_events()`, `get_audit_settings()`,
  `update_audit_settings()`, `audit_log_counts()`, `clear_audit_logs()`.
* `app.py` -- login / logout / navigation / session end / revoked session.
* `tabs/tab_logs.py` -- two sections: **Events** (3 sub-tabs, filters, CSV
  export) and **Settings** (retention, clean-up buttons).

## Operations

* **Retention settings** (Logs tab -> Settings, saved in `audit.db`, superadmin
  only). Defaults: navigation 30 days, authentication 180 days, security 365
  days, and the automatic clean-up runs at most once every 1 hour. Allowed
  range: 1-3650 days, 1-168 hours. The automatic purge is triggered when a new
  browser session starts (at most once per configured interval), so on a server
  nobody visits it simply waits for the next visit.
* **Manual clean-up** (Logs tab -> Settings): buttons to clear the navigation,
  authentication or security log separately, and one to clear everything. Each
  asks for confirmation. The deletion is recorded *afterwards* as an
  `audit_cleared` event (critical, with the scope and the number of deleted
  rows), so even "clear all" leaves one row saying who wiped the log. Saving
  changed settings records `audit_settings_changed` with the old and new values.
* **Client IP:** the direct peer address. Behind a trusted reverse proxy set the
  env var `TRUST_PROXY_HEADERS=1` to use `X-Forwarded-For` instead (it is
  spoofable when no trusted proxy sets it, so it is off by default).
* **Never logged:** passwords, CAPTCHA answers. The typed login name is stored
  (control characters removed, max 64 chars) -- be aware people sometimes type
  a password into that field.
* **Not tamper-proof:** the application has no edit/delete function for the
  log, but anyone who can write the file `db/audit.db` can change it. Ship the
  log to external storage if you need that guarantee.
