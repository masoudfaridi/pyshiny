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
| `conftest.py` | Isolated temp SQLite DBs (`isolated_db`, autouse `isolated_audit_db`), role fixtures |
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
| `test_examples.py` | Every module in `tabs/examples/` follows the tab contract |
| `test_theme_coverage.py` | All 12 themes define the variables; widget selectors, sidebar toggle wiring, CAPTCHA size/font |
| `test_i18n.py` | English/Persian dictionary parity, `APP_LANG` selection, JS theme names |
| `test_auth_package.py` | Context manager / constants smoke |
| `test_tab_07.py` | The four role-gated buttons follow the role hierarchy (fail-closed) |
| `test_audit.py` | Audit log: superadmin policy, hooks in `auth.core`, input sanitising, retention settings, clear/purge, single `@guest` wrapping, Logs-tab helpers |
| `test_confirm.py` | `@confirm_with_password`: dialog flow, wrong password, lockout sharing, expiry, forged inputs, logging |

All mutating tests use a **temporary database** (`isolated_db`); the real `db/auth.db` is never modified.
