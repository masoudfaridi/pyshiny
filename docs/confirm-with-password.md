# `@confirm_with_password`

Runs a callback only after (1) a confirmation dialog with your own message and
(2) the signed-in user's **own account password**. Code: `auth/confirm.py`.
Demo: the four "Secure ... button" buttons in `tabs/tab_07.py`.

```python
from auth import confirm_with_password

@reactive.effect
@reactive.event(input.btn_delete)
@confirm_with_password(
    input,                      # the module server's input
    get_session_user,           # app.py's _ensure_valid_session
    message={"en": "Delete all data?", "fa": "همه داده‌ها حذف شود؟"},
    required_role="admin",      # optional: checked BEFORE any dialog
    timeout_seconds=120,        # optional: how long the confirmation stays valid
)
def _on_delete():
    ...                         # runs only after the right password
```

Order is fixed: `reactive.effect` -> `reactive.event` -> `confirm_with_password` ->
your callback. The decorated name is replaced by a function that only opens the
dialog; the callback is reachable from nowhere else.

## Flow and messages

| Situation | What the user sees |
|-----------|--------------------|
| Click, role too low | toast `reauth_denied`, no dialog (logged as `access_denied`) |
| Click, session invalid | toast `reauth_signin` |
| Click, allowed | dialog 1: your `message` + Continue / Cancel |
| Continue | dialog 2: password field + Confirm / Cancel |
| Empty password | error in the dialog (`reauth_empty_password`), not counted as a failure |
| Wrong password | error in the dialog (`reauth_wrong_password`), dialog stays open |
| Too many wrong passwords | dialog closes, toast `login_locked`, account locked like on the login form |
| Right password | dialog closes, callback runs as the validated user |
| Confirmation older than `timeout_seconds` | dialog closes, toast `reauth_expired` |
| User changed / signed out meanwhile | dialog closes, toast `reauth_signin` |

`message` and `title` can be a string, a `{"en": ..., "fa": ...}` dict (the
`APP_LANG` entry, English as fallback) or an `i18n.STRINGS` key. All fixed
texts are the `reauth_*` keys in `i18n.py` (English + Persian).

## Security notes

* The password is verified for the account of the user in the current session
  (`auth.core.verify_own_password`, `@guest`); no username can be typed and no
  other account can be tested.
* Wrong passwords share the login lockout counters (`LOGIN_MAX_FAILURES` /
  `LOGIN_LOCKOUT_SECONDS`), so a hijacked session cannot brute-force the
  password through the dialog.
* Audit events (Security log): `reauth_failed`, `reauth_blocked_locked`,
  `account_locked` (detail `source: reauth`), `sensitive_action_confirmed`
  (detail `action`: the callback name). The password is never logged.
* Stray inputs (submit without the dialog, continue after cancel, replay after
  success) are ignored.
* The password travels through the websocket: serve the app over HTTPS.
* The callback function name must be unique inside its module server (it
  builds the dialog's input ids).
