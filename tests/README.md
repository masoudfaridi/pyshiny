# Test suite

Automated tests for the Python Shiny Dashboard (auth, CAPTCHA, tabs, sidebar RBAC, assets).

## Run

From the project root (`pyshiny/`):

```bash
pip install -r requirements.txt pytest
pytest -v
```

Or:

```bash
python -m pytest -v
```

## Layout

| File | Covers |
|------|--------|
| `conftest.py` | Isolated temp SQLite DB, role fixtures |
| `test_password.py` | PBKDF2 hash/verify, change_own_password |
| `test_validation.py` | Username/password rules, expiry helpers |
| `test_authenticate.py` | Login, inactive/expired accounts, seed users |
| `test_lockout.py` | Brute-force lockout |
| `test_rbac.py` | ROLE_LEVELS, has_role, require_role |
| `test_users_crud.py` | create/list/update/delete + last-superadmin guards |
| `test_session.py` | get_user_by_id, refresh_session_user |
| `test_captcha.py` | Offline image CAPTCHA |
| `test_tabs.py` | Tab module metadata contracts |
| `test_sidebar.py` | Sidebar visibility by role |
| `test_assets.py` | Static files, exports, APP_DIR_MODE |
| `test_auth_package.py` | Context manager / constants smoke |

All mutating tests use a **temporary database** (`isolated_db`); the real `db/auth.db` is never modified.
