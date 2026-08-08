# AdminLTE Shiny Dashboard

A Shiny for Python dashboard scaffold inspired by the AdminLTE layout.
The project includes role-based authentication, SQLite user storage, optional
account expiration, self-service password changes, 12 selectable themes, and
hierarchical RBAC decorators.

## Project Structure

```text
adminlte-shiny-dashboard/
├── app.py                 # Main Shiny application and navigation shell
├── requirements.txt       # Python dependencies
├── auth/
│   ├── __init__.py        # Public auth API re-exports
│   ├── core.py            # Authentication, password hashing, expiration, RBAC
│   └── captcha.py         # Offline image CAPTCHA generator
├── db/
│   └── auth.db            # SQLite database containing user accounts
│                          #   (created automatically on first run; not
│                          #   shipped in the repo/zip, see .gitignore)
├── docker/
│   ├── Dockerfile          # Image build (Python 3.12-slim + deps)
│   ├── entrypoint.sh       # Starts Shiny on 0.0.0.0:$PORT
│   ├── docker-compose.yml  # One-command build + run, port via $PORT
│   ├── .env.example        # Copy to .env to set a default PORT
│   ├── run.sh              # One-command build + run without compose
│   └── README.md           # Docker quick reference
├── static/
│   ├── css/
│   │   └── styles.css     # Dashboard, authentication, and theme styles
│   └── js/
│       └── custom.js      # Sidebar, theme picker, login Enter, user actions
└── tabs/
    ├── tab_01.py          # Dashboard v1 (Superadmin)
    ├── tab_02.py          # Dashboard v2 (Admin+)
    ├── tab_03.py          # Dashboard v3 (User+)
    ├── tab_04.py          # Components (Guest+)
    ├── tab_05.py          # Widgets
    ├── tab_06.py          # Tables
    ├── tab_account.py     # Self-service account and password management
    └── tab_users.py       # Superadmin-only user management
```

## Installation

Install the required packages:

```bash
pip install -r requirements.txt
```

Dependencies: `shiny` and `Pillow` (for offline CAPTCHA images).

## Run the Application

Start the Shiny application with:

```bash
shiny run app.py --reload
```

Then open the address printed by the terminal, usually:

```text
http://127.0.0.1:8000
```

## Docker

The whole project can be built and run in a container with one command --
no local Python install needed. Everything lives in the `docker/` folder.

### Quickest path: docker compose

```bash
cd docker
docker compose up --build -d
```

That builds the image and starts the dashboard on **port 8000**:

```text
http://localhost:8000
```

Want a different port? Set `PORT` -- nothing else to edit, host and
container both pick it up automatically:

```bash
PORT=9000 docker compose up --build -d
# -> http://localhost:9000
```

(Or copy `docker/.env.example` to `docker/.env` and set `PORT` there once,
then just run `docker compose up --build -d` every time.)

Stop it with:

```bash
docker compose down
```

### Alternative: plain `docker`, no compose

If you don't have `docker compose`, run this from the project root instead
-- it builds and starts the container in one step:

```bash
bash docker/run.sh          # port 8000
bash docker/run.sh 9000     # port 9000
```

### What the image does

- Base image: `python:3.12-slim`, with `fonts-dejavu-core` installed so the
  login CAPTCHA renders with a real TrueType font instead of Pillow's tiny
  fallback bitmap font.
- Runs as a non-root user (`appuser`) inside the container.
- `db/` (the SQLite file with all accounts) is mounted as a volume from the
  project root, **not** baked into the image. `auth/core.py` creates and
  seeds it automatically the first time the container starts, and it then
  persists across restarts, rebuilds, and `docker compose down` / `up`.
- A `HEALTHCHECK` pings the dashboard every 30s so `docker ps` and
  orchestrators (Swarm, Kubernetes, etc.) can tell if it's actually serving
  requests, not just that the process is alive.
- The internal port is controlled by a single `PORT` environment variable
  (default `8000`), read by `docker/entrypoint.sh` at startup. Both
  `docker/run.sh` and `docker/docker-compose.yml` publish the host port and
  set this env var together from one value, so you only ever specify the
  port once, in one place.

### Useful commands

```bash
docker logs -f adminlte-shiny-dashboard      # follow logs
docker stop adminlte-shiny-dashboard         # stop (run.sh-started container)
docker compose down                          # stop (compose-started container)
docker compose up --build -d                 # rebuild after code changes
```

See `docker/README.md` for a short reference to every file in that folder.

## Authentication

Authentication is required before the dashboard can be accessed.
The application uses four hierarchical roles:

```text
Superadmin
    ↓
Admin
    ↓
User
    ↓
Guest
```

A higher role automatically inherits all permissions from lower roles.

## Security Notes

The authentication and RBAC implementation includes the following protections:

1. **Stale-session authorization in three UI renderers.** `users_table()`,
   `edit_expiry_field()`, and `edit_expiry_date_input()` read the cached
   `logged_in_user()` reactive value directly to decide whether to render
   superadmin-only content. If a superadmin was demoted or deactivated from
   *another* session, their own already-open tab could keep showing the full
   user table (usernames, roles, timestamps) until some unrelated input
   happened to trigger a session refresh. All three now call the same
   `_ensure_valid_session()` helper the mutating handlers already used, so
   they re-check the role against SQLite on every render.
2. **PBKDF2 iteration count raised from 310,000 to 600,000** to match current
   OWASP guidance for PBKDF2-HMAC-SHA256. The iteration count is stored
   inside each password hash string, so this is fully backward compatible
   with accounts created under the old count.
3. **The live `db/auth.db` file is no longer shipped in the project
   archive.** Committing/zipping a pre-seeded database means every copy of
   the project carries the same four password hashes at rest indefinitely.
   `auth/core.py` already creates and seeds `db/auth.db` automatically on
   first run, so nothing needs to be done manually — just don't commit the
   generated file (see `.gitignore`).

Residual items worth knowing about (not code bugs, but deployment
considerations if this ever leaves a classroom/demo setting):

- Login rate-limiting is stored in-process and resets on app restart; a
  multi-process deployment would need a shared store (e.g. Redis) instead.
- Shiny itself doesn't set `X-Frame-Options` / CSP headers; put a reverse
  proxy (nginx, Caddy) in front in production and set those there.
- The four default accounts use well-known passwords by design (they're
  documented below) — rotate all of them before any real deployment.

## Security controls

The login form includes an **offline image CAPTCHA** (no external network service).

Additional protections:

- PBKDF2-HMAC-SHA256 password hashing with per-password salt
- Constant-time hash comparison and a dummy verify path for unknown users
- Login rate limiting (temporary lockout after repeated failures)
- Session re-validation against SQLite before protected actions
- Username format limits and password length limits
- Stronger password rules for self-service password changes
  (Superadmin may still assign simpler passwords when creating/editing users)

## Account Expiration

Superadmin accounts never expire.

Admin, User, and Guest accounts can optionally have an expiration date.
On the User Management page, enable the "Set an expiration date" checkbox to
assign a date; leave the checkbox unchecked for accounts that should never expire.

The expiration date is inclusive, meaning the account remains usable on the
specified date and becomes unavailable starting the following day.

For example, an expiration date of `2026-12-31` allows access through December
31, 2026. The account is rejected beginning January 1, 2027.

Expired accounts cannot log in and protected backend functions also reject an
expired session.

## Password confirmation

When creating a user, editing a user password, or changing your own password,
the new password must be entered twice. The two values must match before the
change is accepted.

## Default Accounts

The SQLite database is initialized automatically on first startup.
The following accounts are seeded only when they do not already exist:

| Username | Password | Role | Expiration |
|---|---|---|---|
| `superadmin` | `ChangeMe123!` | Superadmin | Never |
| `admin` | `Admin123!` | Admin | None |
| `user` | `User123!` | User | None |
| `guest` | `Guest123!` | Guest | None |

Passwords are not stored as plaintext. The application uses PBKDF2-HMAC-SHA256
with a per-password random salt.

Change the default passwords before using the application in a real environment.

## Self-Service Password Change

Every authenticated user can change their own password from the `My Account`
page.

The user must provide:

- Current password
- New password
- Confirm new password

The backend verifies the current password and checks that the two new password values match before storing the new password.
New passwords must contain at least 8 characters.

This functionality is protected by `@guest`, which means every authenticated
role can use it, including Guest users.

## RBAC Decorators

The project exposes four decorators from the `auth` package (`auth/core.py`):

```python
from auth import superadmin, admin, user, guest

@superadmin
def delete_user(...):
    ...

@admin
def manage_report(...):
    ...

@user
def run_analysis(...):
    ...

@guest
def view_dashboard(...):
    ...
```

### Permission Matrix

| Decorator | Superadmin | Admin | User | Guest |
|---|---:|---:|---:|---:|
| `@superadmin` | Yes | No | No | No |
| `@admin` | Yes | Yes | No | No |
| `@user` | Yes | Yes | Yes | No |
| `@guest` | Yes | Yes | Yes | Yes |

All four decorators require an authenticated user. `@guest` represents the
lowest authenticated permission level; it does not mean anonymous access.

If a user does not have the required permission, the decorator raises
`PermissionError` before the protected function is executed.

## User Management

The `User Management` page is visible only to Superadmin users.
A Superadmin can create, edit, and delete accounts.

### Create User

A Superadmin can provide:

- Username
- Password
- Access level
- Optional expiration date for Admin, User, or Guest accounts

Superadmin accounts always have no expiration date.

### Edit User

A Superadmin can change:

- Username
- Access level
- Active status
- Password
- Optional expiration date

The application prevents the last active Superadmin account from being
demoted, disabled, or deleted.

### Delete User

A Superadmin can delete other accounts.
The currently logged-in account cannot delete itself.
The last active Superadmin account cannot be deleted.

The server-side `create_user()`, `update_user()`, `delete_user()`, and
`list_users()` functions are protected with `@superadmin`.

## SQLite Database

The database file is:

```text
db/auth.db
```

The main table is:

```sql
users
```

Its fields include:

- `id`
- `username`
- `password_hash`
- `role`
- `is_active`
- `expire_date`
- `created_at`

The application automatically migrates an older database file by adding the
`expire_date` column when necessary.

Existing users are never overwritten by the initial seed operation.

## Themes

The dashboard includes 12 selectable themes:

### Light Themes

1. Ocean Blue
2. Fresh Green
3. Soft Purple
4. Warm Orange
5. Calm Teal
6. Elegant Rose

### Dark Themes

1. Midnight Slate
2. Deep Ocean
3. Emerald Night
4. Royal Night
5. Amber Night
6. Rose Night

The theme picker is located in the top-right area of the dashboard.
The selected theme is stored in browser `localStorage`, so it remains selected
after a page refresh.

## Adding a New Tab

1. Copy an existing module from `tabs/`.
2. Give the new module a unique `NAV_ID`.
3. Set `NAV_LABEL` to the text shown in the sidebar.
4. Set `NAV_ICON` to a Bootstrap Icons class for top-level items.
5. Set `NAV_GROUP` to `dashboard` to place the tab inside the Dashboard group,
   or use `None` for a top-level item.
6. Set `NAV_MIN_ROLE` to the minimum role required to see the page.
7. Add the module to the `TABS` list in `app.py`.

Example:

```python
NAV_ID = "tab_07"
NAV_LABEL = "Analytics"
NAV_ICON = "bi-bar-chart"
NAV_GROUP = None
NAV_MIN_ROLE = "user"
```

With `NAV_MIN_ROLE = "user"`, Superadmin, Admin, and User accounts can access
the page, while Guest accounts cannot.

## Adding Protected Functions

Import the appropriate decorator and place it directly above the function:

```python
from auth import admin

@admin
def export_report(report_id):
    # Only Admin and Superadmin users can execute this function.
    return generate_report(report_id)
```

This approach keeps authorization rules close to the functions they protect
and avoids repeating manual role checks throughout the application.
