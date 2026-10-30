# Python Shiny Dashboard

A customizable Shiny for Python dashboard featuring role-based authentication,
 SQLite user storage, optional account expiration, self-service password changes,
  12 selectable themes, and hierarchical RBAC decorators.

Beyond the basics it also ships with:

- a **password re-confirmation decorator** (`@confirm_with_password`): confirmation
  message + the user's own password before a sensitive callback runs;
- an **audit log** (authentication, navigation and security events in
  `db/audit.db`) with a superadmin-only **Logs** tab: filters, CSV export,
  configurable retention and clean-up buttons;
- an English / Persian (RTL) interface switched by one setting (`APP_LANG`);
- two layers of access control: tabs hidden by role **and** server-side
  decorators that stop callbacks from running.

## Documentation map

| Where | What |
|-------|------|
| this `README.md` | overview, setup, API reference of the `auth` package, decorators, audit log |
| [`tutorial/TUTORIAL.md`](tutorial/TUTORIAL.md) | **complete guide in Persian**: architecture, every function and decorator, building tabs, i18n, tests, security checklist, troubleshooting |
| [`docs/audit-log.md`](docs/audit-log.md) | audit log events, settings, operations |
| [`docs/confirm-with-password.md`](docs/confirm-with-password.md) | `@confirm_with_password` flow and security notes |
| [`tabs/HOW_TO_ADD_A_TAB.md`](tabs/HOW_TO_ADD_A_TAB.md) | every place to edit when adding a tab |
| [`tabs/MODULES.md`](tabs/MODULES.md) | how Shiny modules work |
| [`tabs/examples/`](tabs/examples/README.md) | 15 copy-ready tab examples |
| [`tests/README.md`](tests/README.md) | the test suite |
| [`docker/README.md`](docker/README.md) | Docker quick reference |


**🔗 Live Demo:** [https://masoudfaridi.shinyapps.io/pyshiny/](https://masoudfaridi.shinyapps.io/pyshiny/)

<p align="center">
  <img src="docs/01.jpg" alt="Dashboard" width="400">
</p>

<p align="center">
  <img src="docs/02.gif" alt="Theme switching" width="800">
</p>

## Project Structure

```text
pyshiny/
├── 00_create_files/           # Step 0 – prepare runtime environment
│   └── bootstrap.py           # Creates db/, cleans auth.db, makes docker/.env
├── 01_requirements/           # Step 1 – auto-update requirements.txt
│   └── update_requirements.py # Scans all .py files and refreshes dependencies
├── app.py                     # Main Shiny application and navigation shell
├── i18n.py                    # English / Persian UI strings + the APP_LANG switch
├── requirements.txt           # Python dependencies (auto-maintained)
├── auth/
│   ├── __init__.py            # Public auth API re-exports
│   ├── core.py                # Authentication, password hashing, expiration, RBAC
│   ├── captcha.py             # Offline image CAPTCHA generator
│   ├── audit.py               # Audit log storage (db/audit.db); see docs/audit-log.md
│   └── confirm.py             # @confirm_with_password; see docs/confirm-with-password.md
├── db/                        # SQLite databases (created on first run; never shipped)
│                              #   auth.db  = users, audit.db = audit log + its settings
├── docs/                      # audit-log.md, confirm-with-password.md, screenshots
├── tutorial/
│   └── TUTORIAL.md            # complete guide (Persian)
├── tests/                     # pytest suite (see tests/README.md)
├── docker/
│   ├── Dockerfile             # Image build (Python 3.12-slim + deps)
│   ├── entrypoint.sh          # Starts Shiny on 0.0.0.0:$PORT
│   ├── docker-compose.yml     # One-command build + run, port via $PORT
│   ├── .env.example           # Copy to .env to set a default PORT
│   ├── run.sh                 # One-command build + run without compose
│   └── README.md              # Docker quick reference
├── static/
│   ├── css/
│   │   └── styles.css         # Dashboard, authentication, and theme styles
│   └── js/
│       └── custom.js          # Sidebar, theme picker, login Enter, user actions
└── tabs/
    ├── tab_01.py              # Dashboard v1 (Superadmin)
    ├── tab_02.py              # Dashboard v2 (Admin+)
    ├── tab_03.py              # Dashboard v3 (User+)
    ├── tab_04.py              # Components (Guest+)
    ├── tab_05.py              # Widgets
    ├── tab_06.py              # Tables
    ├── tab_07.py              # Role-gated buttons + password-protected buttons (demo/test tab)
    ├── tab_account.py         # Self-service account and password management
    ├── tab_users.py           # Superadmin-only user management
    ├── tab_logs.py            # Superadmin-only audit log viewer (last tab); see docs/audit-log.md
    ├── HOW_TO_ADD_A_TAB.md    # Every place to edit when adding a tab
    ├── MODULES.md             # How Shiny modules work (the technique used by the tabs)
    └── examples/              # 15 copy-ready module examples (ex01 ... ex15) + README
```

## Font picker

A **Font** button sits next to the theme control. It exposes three roles:

- **Body / UI** – main interface text
- **Headings** – titles and brand text (`Inherit` = same as Body)
- **Navigation** – sidebar links (`Inherit` = same as Body)

Available families depend on the text direction, which follows `APP_LANG`
(see [Language and direction](#language-and-direction-english--فارسی)):

- **ltr** → Inter, Roboto, IBM Plex Sans, Source Sans 3, System UI  
  (files under `static/fonts/ltr/`)
- **rtl** → Vazirmatn, Shabnam, Samim, Sahel, BYekan, System UI  
  (Farsi-digit variants under `static/fonts/rtl/`)

Choices are stored in `localStorage` and re-applied after refresh.

## Language and direction (English / فارسی)

The fixed texts of the **login screen**, the **main page** (top bar, sidebar,
theme and font pickers), **My Account** and **User Management** exist in two
languages. The demo tabs (`tab_01` … `tab_06`) are placeholders you replace by
hand, so they are deliberately not translated.

All strings live in one dictionary, `STRINGS`, in `i18n.py`:

```python
STRINGS = {
    "en": {"login_title": "Secure Dashboard", "login_button": "Sign in", ...},
    "fa": {"login_title": "داشبورد امن",      "login_button": "ورود",     ...},
}
```

### Switching to Persian (RTL)

Change **one line** – `APP_LANG` in `i18n.py`:

```python
APP_LANG = "fa"   # "en" = English / LTR (default),  "fa" = Persian / RTL
```

…or, without editing any file, set the environment variable (it wins over the
line above):

```bash
APP_LANG=fa shiny run app.py --reload          # Linux / macOS
set APP_LANG=fa && shiny run app.py --reload   # Windows (cmd)
APP_LANG=fa docker compose up --build -d       # Docker
```

That single setting also switches the text direction (`dir="rtl"`), the
Bootstrap stylesheet (`bootstrap.rtl.css`), the `<html lang>` attribute, the
font list (`static/fonts/rtl/`: Vazirmatn, Shabnam, Samim, Sahel, BYekan) and
the messages raised by `auth/core.py`. **Nothing has to be commented or
uncommented in `app.py` any more** (older versions of this project required
swapping two `app_ui` blocks by hand).

Note: the language is chosen when the server starts, so restart the app after
changing it (`--reload` does this for you when `i18n.py` is edited).

### Using the strings in your own code

```python
from i18n import t, role_label

ui.h3(t("account_title"))                 # "My Account"  /  "حساب کاربری من"
t("login_locked", remaining=30)           # placeholders use str.format
role_label("superadmin")                  # "Superadmin"  /  "مدیر کل"
```

A key that is missing in the active language falls back to English; a key
missing everywhere is shown as the key itself, so typos are easy to spot.
Strings used by the browser (theme names, font labels, the delete confirmation)
are passed to `static/js/custom.js` automatically as `window.APP_I18N`.

### Adding another language

1. In `i18n.py`, copy the whole `"en"` block inside `STRINGS` and rename it
   (for example `"ar"`).
2. Translate the values. Keep the `{placeholders}` exactly as they are.
3. If the language is right-to-left, make sure its code is in `RTL_LANGS`.
4. Run it with `APP_LANG=ar`. `tests/test_i18n.py` checks that every language
   has the same keys and placeholders.

### Reference: all translated strings

<details>
<summary>Click to expand the full English ↔ فارسی table (generated from <code>i18n.py</code>)</summary>

**Roles / نقش‌ها**

| Key | English | فارسی |
|---|---|---|
| `role_guest` | Guest | مهمان |
| `role_user` | User | کاربر |
| `role_admin` | Admin | مدیر |
| `role_superadmin` | Superadmin | مدیر کل |

**Common / عمومی**

| Key | English | فارسی |
|---|---|---|
| `yes` | Yes | بله |
| `no` | No | خیر |
| `never` | Never | هرگز |
| `username` | Username | نام کاربری |
| `password` | Password | رمز عبور |
| `access_level` | Access level | سطح دسترسی |
| `confirm_password` | Confirm password | تکرار رمز عبور |
| `confirm_new_password` | Confirm new password | تکرار رمز عبور جدید |
| `set_expiry` | Set an expiration date | تعیین تاریخ انقضا |
| `expiry_date` | Expiration date | تاریخ انقضا |
| `superadmin_no_expiry` | Superadmin accounts do not expire. | حساب مدیر کل منقضی نمی‌شود. |

**Login screen / صفحه‌ی ورود**

| Key | English | فارسی |
|---|---|---|
| `login_title` | Secure Dashboard | داشبورد امن |
| `login_subtitle` | Please sign in to continue. | برای ادامه لطفاً وارد شوید. |
| `login_security_check` | Security check | بررسی امنیتی |
| `login_captcha_placeholder` | Type the characters you see | نویسه‌های داخل تصویر را وارد کنید |
| `login_captcha_alt` | CAPTCHA | کپچا |
| `login_refresh` | Refresh | تازه‌سازی |
| `login_button` | Sign in | ورود |
| `login_hint` | Default accounts are documented in README.md. Change default passwords after first login. | حساب‌های پیش‌فرض در فایل README.md توضیح داده شده‌اند. پس از اولین ورود، رمز عبور پیش‌فرض را تغییر دهید. |
| `login_invalid` | Invalid username or password, inactive account, or expired account. | نام کاربری یا رمز عبور نادرست است، یا حساب غیرفعال یا منقضی شده است. |
| `login_locked` | Too many failed attempts. Try again in {remaining} seconds. | تعداد تلاش‌های ناموفق بیش از حد مجاز است. {remaining} ثانیه دیگر دوباره تلاش کنید. |
| `login_captcha_invalid` | Invalid security check. Please try again. | بررسی امنیتی نادرست بود. لطفاً دوباره تلاش کنید. |

**Main page – top bar / صفحه‌ی اصلی – نوار بالا**

| Key | English | فارسی |
|---|---|---|
| `brand` | Python Shiny Dashboard | داشبورد Python Shiny |
| `logout` | Logout | خروج |
| `font_button` | Font | فونت |
| `font_aria` | Choose fonts | انتخاب فونت |
| `font_menu_title` | Fonts | فونت‌ها |
| `font_body` | Body / UI | متن / رابط کاربری |
| `font_headings` | Headings | عنوان‌ها |
| `font_navigation` | Navigation | منوی ناوبری |
| `font_inherit` | Inherit (Body) | همانند متن اصلی |
| `font_system` | System UI | فونت سیستم |
| `theme_aria` | Choose theme | انتخاب تم |
| `theme_light_title` | Light themes | تم‌های روشن |
| `theme_dark_title` | Dark themes | تم‌های تیره |
| `theme_light_suffix` | Light theme | تم روشن |
| `theme_dark_suffix` | Dark theme | تم تیره |

**Main page – sidebar / صفحه‌ی اصلی – منوی کناری**

| Key | English | فارسی |
|---|---|---|
| `nav_dashboard` | Dashboard | داشبورد |
| `nav_account` | My Account | حساب کاربری من |
| `nav_users` | User Management | مدیریت کاربران |

**Theme names / نام تم‌ها**

| Key | English | فارسی |
|---|---|---|
| `theme_light-blue` | Ocean Blue | آبی اقیانوسی |
| `theme_light-green` | Fresh Green | سبز شاداب |
| `theme_light-purple` | Soft Purple | بنفش ملایم |
| `theme_light-orange` | Warm Orange | نارنجی گرم |
| `theme_light-teal` | Calm Teal | فیروزه‌ای آرام |
| `theme_light-rose` | Elegant Rose | صورتی ظریف |
| `theme_dark-slate` | Midnight Slate | سربی نیمه‌شب |
| `theme_dark-ocean` | Deep Ocean | اقیانوس عمیق |
| `theme_dark-emerald` | Emerald Night | شب زمردی |
| `theme_dark-purple` | Royal Night | شب سلطنتی |
| `theme_dark-amber` | Amber Night | شب کهربایی |
| `theme_dark-rose` | Rose Night | شب رز |

**My Account / حساب کاربری من**

| Key | English | فارسی |
|---|---|---|
| `account_title` | My Account | حساب کاربری من |
| `account_intro` | Change your own password. This is available to every authenticated user. | رمز عبور خود را تغییر دهید. این امکان برای همه کاربرانِ واردشده در دسترس است. |
| `account_change_heading` | Change password | تغییر رمز عبور |
| `account_current_password` | Current password | رمز عبور فعلی |
| `account_new_password` | New password | رمز عبور جدید |
| `account_change_button` | Change password | تغییر رمز عبور |
| `account_tips_heading` | Password tips | نکات رمز عبور |
| `account_tip_length` | Use at least 8 characters. | حداقل ۸ نویسه استفاده کنید. |
| `account_tip_mix` | Mix letters, numbers, and symbols. | ترکیبی از حروف، اعداد و نمادها به کار ببرید. |
| `account_tip_reuse` | Avoid reusing passwords from other sites. | از رمزهای عبور سایت‌های دیگر دوباره استفاده نکنید. |
| `account_mismatch` | New password and confirmation do not match. | رمز عبور جدید و تکرار آن یکسان نیستند. |
| `account_changed` | Password changed successfully. | رمز عبور با موفقیت تغییر کرد. |

**User Management / مدیریت کاربران**

| Key | English | فارسی |
|---|---|---|
| `users_title` | User Management | مدیریت کاربران |
| `users_intro` | Only Superadmin users can create, edit, and delete accounts. | فقط مدیر کل می‌تواند حساب‌ها را ایجاد، ویرایش و حذف کند. |
| `users_create_heading` | Create user | ایجاد کاربر |
| `users_create_button` | Create user | ایجاد کاربر |
| `users_existing_heading` | Existing users | کاربران موجود |
| `users_existing_hint` | Use Change to edit an account in a popup, or Delete to remove it. | برای ویرایش حساب در یک پنجره‌ی بازشو، «ویرایش» و برای حذف آن، «حذف» را بزنید. |
| `users_change` | Change | ویرایش |
| `users_delete` | Delete | حذف |
| `users_col_actions` | Actions | عملیات |
| `users_col_id` | ID | شناسه |
| `users_col_username` | Username | نام کاربری |
| `users_col_role` | Role | نقش |
| `users_col_active` | Active | فعال |
| `users_col_expires` | Expires | انقضا |
| `users_col_created` | Created | تاریخ ایجاد |
| `users_create_mismatch` | Password and confirmation do not match. | رمز عبور و تکرار آن یکسان نیستند. |
| `users_created` | User created successfully. | کاربر با موفقیت ایجاد شد. |
| `users_updated` | User updated successfully. | کاربر با موفقیت ویرایش شد. |
| `users_deleted` | User deleted successfully. | کاربر با موفقیت حذف شد. |
| `users_not_found` | User not found. | کاربر پیدا نشد. |
| `users_exists` | This username already exists. | این نام کاربری از قبل وجود دارد. |
| `users_denied_create` | Access denied: only Superadmin can create users. | دسترسی غیرمجاز: فقط مدیر کل می‌تواند کاربر ایجاد کند. |
| `users_denied_edit` | Access denied: only Superadmin can edit users. | دسترسی غیرمجاز: فقط مدیر کل می‌تواند کاربر را ویرایش کند. |
| `users_denied_delete` | Access denied: only Superadmin can delete users. | دسترسی غیرمجاز: فقط مدیر کل می‌تواند کاربر را حذف کند. |
| `users_confirm_delete` | Delete user "{username}"? This cannot be undone. | کاربر «{username}» حذف شود؟ این کار قابل بازگشت نیست. |

**User Management – edit popup / پنجره‌ی ویرایش**

| Key | English | فارسی |
|---|---|---|
| `edit_title` | Edit user: {username} | ویرایش کاربر: {username} |
| `edit_active` | Active account | حساب فعال |
| `edit_new_password` | New password (leave blank to keep current password) | رمز عبور جدید (برای حفظ رمز فعلی خالی بگذارید) |
| `edit_save` | Save changes | ذخیره تغییرات |
| `edit_delete` | Delete user | حذف کاربر |
| `edit_cancel` | Cancel | انصراف |
| `edit_mismatch` | New password and confirmation do not match. | رمز عبور جدید و تکرار آن یکسان نیستند. |

**Validation errors (auth/core.py) / پیام‌های خطا**

| Key | English | فارسی |
|---|---|---|
| `field_password` | Password | رمز عبور |
| `field_new_password` | New password | رمز عبور جدید |
| `err_username_format` | Username must be 3–32 characters and contain only letters, numbers, underscores, or hyphens. | نام کاربری باید بین ۳ تا ۳۲ نویسه باشد و فقط شامل حروف انگلیسی، اعداد، زیرخط (_) یا خط تیره (-) باشد. |
| `err_password_required` | {field} is required. | {field} الزامی است. |
| `err_password_min` | {field} must contain at least {n} characters. | {field} باید حداقل {n} نویسه داشته باشد. |
| `err_password_max` | {field} must contain at most {n} characters. | {field} باید حداکثر {n} نویسه داشته باشد. |
| `err_password_complexity` | {field} must contain at least one letter and one number. | {field} باید حداقل یک حرف و یک عدد داشته باشد. |
| `err_expiry_format` | Expiration date must use YYYY-MM-DD format. | تاریخ انقضا باید با قالب YYYY-MM-DD وارد شود. |
| `err_invalid_role` | Invalid role. | نقش نامعتبر است. |
| `err_auth_required` | Authentication is required. | ورود به سامانه الزامی است. |
| `err_current_password` | Current password is incorrect. | رمز عبور فعلی نادرست است. |
| `err_user_not_found` | User not found. | کاربر پیدا نشد. |
| `err_last_superadmin` | At least one active Superadmin must remain. | دست‌کم یک مدیر کل فعال باید باقی بماند. |
| `err_delete_self` | You cannot delete the account you are currently using. | نمی‌توانید حسابی را که با آن وارد شده‌اید حذف کنید. |
| `err_delete_last_superadmin` | The last active Superadmin cannot be deleted. | آخرین مدیر کل فعال را نمی‌توان حذف کرد. |

</details>

## Installation


Follow these steps in order after extracting the archive.

### Step 0 – Prepare the runtime environment

```bash
python 00_create_files/bootstrap.py
```

This script:

- Creates the `db/` directory if it does not exist.
- Removes any leftover `db/auth.db` (the database must be generated on first
  run by `auth.core.init_db()`, never shipped).
- Creates `docker/.env` from `docker/.env.example` when missing.
- Performs basic sanity checks on the project layout.
- Prints the next commands you should run.

### Step 1 – Refresh requirements.txt

```bash
python 01_requirements/update_requirements.py
```

What the script does:

- Walks the whole project tree and parses every `.py` file with the AST.
- Detects both `import package` and `from package import ...` statements.
- Maps import names to the correct PyPI package (e.g. `PIL` → `Pillow`).
- Skips the Python standard library and local packages (`auth`, `tabs`, …).
- Never creates duplicate entries.
- Preserves any version pins that are already present.
- Adds newly discovered third-party packages with sensible minimum versions.

Dry-run mode (show changes without writing the file):

```bash
python 01_requirements/update_requirements.py --dry-run
```

After the script finishes, `requirements.txt` typically looks like:

```text
shiny>=1.4
Pillow>=10.0
matplotlib>=3.7
numpy>=1.24
```

### Step 2 – Install the packages

```bash
pip install -r requirements.txt
```

Current core dependencies:

| Package      | Purpose                              |
|--------------|--------------------------------------|
| shiny        | Web application framework            |
| Pillow       | Offline CAPTCHA image generation     |
| numpy        | Numerical arrays used by the charts  |
| matplotlib   | Histogram and plot rendering         |

## Environment variables

| Variable | Default | Meaning |
|----------|---------|---------|
| `APP_LANG` | `en` | `en` (LTR) or `fa` (RTL). Beats the value in `i18n.py`; restart after changing. |
| `PORT` | `8000` | Port inside Docker (`docker compose` publishes the same port). |
| `AUDIT_LOG_SUPERADMIN` | `1` | `0` = do not record the superadmin's own routine activity. Account management, log clean-up and attacks on the `superadmin` account are still recorded. |
| `ID_CODE_MODE` | `generic` | Rule for the user identification code: `generic` = 4-20 letters/digits/`-`/`_`; `national_ir` = valid 10-digit Iranian national code (checksum checked). Either way the code is unique. |
| `TRUST_PROXY_HEADERS` | off | `1` = read the client IP from `X-Forwarded-For`. Only behind a trusted reverse proxy (otherwise spoofable). |

Constants you may tune in code: `LOGIN_MAX_FAILURES` (5) and
`LOGIN_LOCKOUT_SECONDS` (300) in `auth/core.py`, `DEFAULT_TIMEOUT_SECONDS` (120) in
`auth/confirm.py`, `CAPTCHA_LENGTH` / `CAPTCHA_TTL_SECONDS` in `auth/captcha.py`.

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

Persian (RTL) interface instead of English: `APP_LANG=fa docker compose up --build -d`.

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
docker logs -f pyshiny      # follow logs
docker stop pyshiny         # stop (run.sh-started container)
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

The authentication system includes several security protections:

- Session authorization is revalidated against SQLite before protected actions.
- Passwords are hashed with PBKDF2-HMAC-SHA256 and per-password salts.
- Login attempts are rate-limited after repeated failures.
- The SQLite database is generated automatically on first run and `db/auth.db`
  should never be committed to the repository.
- Change all default passwords before using the application in a real environment.
- Role decorators are enforced on the server and are fail-closed; every refusal
  is written to the audit log.
- Sensitive actions can require the user's own password (`@confirm_with_password`),
  sharing the login lockout counters.
- Serve the app over HTTPS (passwords travel over the websocket) and see the
  limits listed in the audit-log section and in `tutorial/TUTORIAL.md` (chapter 14).

For production deployment, additional infrastructure-level protections such as
shared rate limiting and security headers may be required.

## Security controls

The login form includes an **offline image CAPTCHA** (no external network service).

Additional protections:

- Constant-time hash comparison and a dummy verify path for unknown users
- Username format limits and password length limits
- Stronger password rules for self-service password changes
  (Superadmin may still assign simpler passwords when creating/editing users)

## Account Expiration

Superadmin accounts never expire. Admin, User, and Guest accounts can optionally
have an expiration date. The expiration date is inclusive, so the account remains
usable through the specified date and becomes unavailable starting the following day.

Expired accounts cannot log in, and protected backend functions also reject expired
sessions.


## First Run and Accounts

The SQLite database is created automatically on first startup. Accounts are seeded
**only when the users table is empty** -- an account you delete is never re-created
on the next restart (older versions re-inserted the four demo accounts, with their
public passwords, on every start).

| Setting (environment variable) | Effect on the first run |
|---|---|
| *(nothing set)* | One account, `superadmin`, with a **random password**. It is printed to the console (`docker logs pyshiny`) and saved to `db/initial_superadmin_password.txt` (mode 600). The file is deleted automatically once the superadmin password is changed. |
| `INITIAL_SUPERADMIN_PASSWORD=...` | `superadmin` gets this password instead (nothing is written to disk). |
| `DEMO_ACCOUNTS=1` | Also creates the demo accounts below (testing / tutorials only). Without `INITIAL_SUPERADMIN_PASSWORD`, `superadmin` then gets the demo password too. |

Demo accounts (`DEMO_ACCOUNTS=1` only):

| Username | Password | Role | Expiration |
|---|---|---|---|
| `superadmin` | `ChangeMe123!` | Superadmin | Never |
| `admin` | `Admin123!` | Admin | None |
| `user` | `User123!` | User | None |
| `guest` | `Guest123!` | Guest | None |

Passwords are not stored as plaintext. The application uses PBKDF2-HMAC-SHA256
with a per-password random salt. A Superadmin may set any password (length 8-128)
for any account, including their own.

### Security settings

| Variable | Default | Meaning |
|---|---|---|
| `SESSION_MAX_HOURS` | `12` | A signed-in session ends after this many hours even if the tab stays open (`0` = no limit). |
| `TRUST_PROXY_HEADERS` | `0` | `1` only behind your own reverse proxy: the client IP is then taken from the right-most `X-Forwarded-For` entry. |
| `HSTS` | `0` | `1` only when the site is served over HTTPS (adds `Strict-Transport-Security`). |

Built in (no setting): security headers on every response (no framing, `nosniff`,
no referrer, restrictive permissions policy), an upload size cap, sign-out of every
other session of an account when its password is changed or reset, account
lockout after 5 wrong passwords (login form, password dialogs and the change-password
form share it), and a per-page limit on failed sign-in attempts. A wrong CAPTCHA does
**not** count towards the account lockout, so nobody can lock another person's
account by submitting junk.

## User details: identification code, email, phone

Every account now stores three more fields, required when a Superadmin creates or
edits a user (Users page, create form and edit popup):

| Field | Rules |
|-------|-------|
| Identification code | **Unique** (case-insensitive, enforced by a unique index and checked with a friendly error), 4-20 characters. Stored upper-case. See `ID_CODE_MODE`. |
| Email | Valid address, stored lower-case. |
| Phone number | 7-15 digits, optional leading `+`; spaces, dashes and brackets are removed, `00` becomes `+`. |

Persian/Arabic digits are converted to ASCII everywhere. The values appear in the users
table, in the `My Account` page (a user can change their own email and phone there; only a
Superadmin can change the identification code) and in the session user (`current_user()`).
The audit log records the identification-code change, but only *that* email / phone
changed, not their values.

**Existing databases** are upgraded automatically at start-up (`ALTER TABLE` + unique index);
accounts created earlier keep empty details until a Superadmin fills them in (several
empty values are allowed, duplicates of a real code are not).

## Accounts database backup and restore

Users page -> *Accounts database backup* (Superadmin only; logic in `auth/backup.py`,
guarded wrappers `create_backup`, `list_backups`, `restore_backup`, `delete_backup`,
`read_backup`, `import_backup` in `auth/core.py`):

* **Create backup** - consistent copy (SQLite online backup) saved as
  `db/backups/auth-YYYYMMDD-HHMMSS-manual.db`.
* **Restore** - replaces *all* accounts with the chosen backup. A safety copy of the current
  data (`-prerestore`) is made first; backups from an older schema are upgraded; the backup
  must be a healthy database with at least one active Superadmin, otherwise it is refused.
  Login lock-outs are reset. If the account in use no longer exists afterwards, the session ends.
* **Download / Import / Delete** - move backups between machines or tidy up. Imported
  files are validated and stored as `-uploaded`; to restore one, use *Restore*.
* Restore, delete, download and import ask for the user's password
  (`@confirm_with_password`); every operation is written to the Security log.
* Backup files contain password hashes: keep `db/backups/` private. In Docker the folder
  lives inside the mounted `db/` volume. The audit log (`db/audit.db`) is not part of the backup.

## Password-protected management actions

`@confirm_with_password` (see the section below) now guards:

* **Users page:** create user, save changes, delete user (table and popup), restore /
  delete / download / import backup. The browser `confirm()` for deletion was replaced by
  this dialog.
* **Logs page:** saving the retention settings and all four "clear log" buttons.

The password is asked *after* the confirmation dialog; nothing happens before it is correct,
and the form values typed in a popup are kept so a failed save re-opens the popup.

## Log size and top-bar clock

* The Logs page shows the **total size of all logs in MB** at the top (and in
  Settings and clean-up): `db/audit.db` plus its WAL files, 1 MB = 1024*1024 bytes. Clearing logs
  compacts the file so the number really drops. API: `audit_log_size_mb()`.
* The top bar shows a live clock **before the logout button**, taken from the device's system
  clock, **down to the minute (no seconds)**: in Persian the weekday (شنبه، یکشنبه، ...), Jalali
  date and time; in English the weekday, Gregorian date (`YYYY-MM-DD`) and time. It uses the browser's built-in
  `Intl` calendars (`static/js/custom.js`, `startClock`), so no extra package is needed.

## Logs: user behaviour analysis

Logs page -> **User behaviour analysis** (Superadmin only; `auth.audit_analytics`, logic in
`audit.analytics()`):

* **Per user:** logins, failed logins, measured sessions, total / average / longest usage in
  **minutes**, page views, most used page, active days, warning/critical events, last login and
  last activity. Sorted by usage. Export to CSV.
* **Overall:** active users, logins, failed logins (and how many were for unknown names),
  total usage, average session, longest session, average usage per user, page views, events,
  alerts; charts for events by log type, by hour of day, by weekday, per day, most visited
  pages, most frequent events and failed-login reasons.
* **Filters:** period (24 h / 7 / 30 / 90 days / all / custom dates), one user (for an individual
  report) or all, role, log types (authentication / navigation / security), severity.
* Hours, weekdays and days use the **browser's time zone** (shown on the page); the log tables stay in UTC.
* Minutes are counted when a session ends (sign-out, closed browser or revoked session - all
  three now record `duration_s`). A session that is still open is counted once it ends.

## Logs database: backup, restore and automatic backup before clean-up

All logs live in **one** SQLite file, `db/audit.db`. Logs page -> Settings -> *Logs database backup*
(`auth/log_backup.py`; `create_log_backup`, `list_log_backups`, `restore_log_backup`,
`delete_log_backup`, `read_log_backup`, `import_log_backup`):

* **Create backup** -> `db/log_backups/audit-YYYYMMDD-HHMMSS-manual.db`.
* **Restore** replaces all log rows with the backup's rows in one transaction (the retention
  settings are kept); a `-prerestore` safety copy is made first, so a restore can be undone.
* **Download / Load file / Delete**; loaded files are validated first. Restore, delete,
  download and load ask for the password (`@confirm_with_password`).
* **Automatic backup before the automatic clean-up:** right before `purge_old()` deletes expired
  rows it copies the whole log database into the special folder **`db/log_backups/auto/`**
  (`audit-...-auto.db`). If the copy fails, nothing is deleted. Settings (Logs -> Settings):
  switch on/off (default on) and how many automatic backups to keep (default 10, oldest removed).
  Nothing to delete -> no backup is made. The purge itself is logged (`audit_auto_purged`).
* Manual "clear log" buttons are not backed up automatically (take a manual backup first if you
  want one).

## Self-Service Password Change

Every authenticated user can change their own password from the `My Account`
page. The current password must be verified, and the new password must be entered
twice and contain at least 8 characters.

This functionality is available to every authenticated role, including Guest users.

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

### How the decorators work

```python
def require_role(required_role):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not has_role(required_role):
                audit.log_event("security", "access_denied", ...)   # always logged
                raise PermissionError(...)
            return fn(*args, **kwargs)
        return wrapper
    return decorator

superadmin = require_role("superadmin")   # admin, user, guest likewise
```

* The user is **not** a parameter. It comes from `current_user()`, i.e. from
  the surrounding `with user_context(user):` block. Call protected functions
  inside that block.
* **Fail-closed:** outside `user_context` there is no user, so every decorator
  raises `PermissionError`.
* `has_role()` also rejects inactive and expired accounts, whatever their role.
* Every refusal is written to the Security log as `access_denied` (function
  name + required role). The decorator is the single choke point for that.
* `require_role(role)` can be used directly to make your own named decorator;
  an unknown role raises `KeyError` when the function runs.

### Using them inside Shiny callbacks

Put the decorator on the function that does the work, and call it from the
callback inside `user_context` with a **freshly validated** user
(`_ensure_valid_session` in `app.py`, passed to the tab as `get_session_user`):

```python
from auth import admin, user_context

@admin
def export_report(report_id):
    return build(report_id)

@reactive.effect
@reactive.event(input.export)
def _on_export():
    person = get_session_user()          # re-read from SQLite
    if person is None:
        return                           # signed out / revoked
    try:
        with user_context(person):
            export_report(5)
    except PermissionError:
        ui.notification_show("You do not have access to this section.", type="error")
```

`tabs/tab_07.py` contains this pattern as `_attempt()`.

Common mistakes: decorating the reactive handler itself (it runs without a user,
so it always fails); passing the raw `logged_in_user` (a cache: a demoted
account keeps its old role); naming a variable `user` after
`from auth import user` (it shadows the decorator); using `current_role()` for a
security decision (it answers `"guest"` when nobody is signed in).

### Two layers of access control

1. **Hiding (UI):** `NAV_MIN_ROLE` of a tab decides who sees its sidebar link;
   `build_sidebar()` omits it and `active_panel` refuses to render it. Forged
   tab requests are recorded in the Security log.
2. **Decorators (server):** stop a callback from running no matter how its input
   arrived. This matters because every tab's server runs for every session and
   Shiny accepts any input id the browser sends: a hidden button can still be
   "clicked" by a crafted message.

| Tab | Hidden by role | Server-side decorators |
|-----|:--------------:|:----------------------:|
| `tab_01` / `tab_02` / `tab_03` | superadmin / admin / user | **no** (UI only; they only draw random samples) |
| `tab_04`, `tab_05`, `tab_06` | guest | n/a (open to every signed-in user) |
| `tab_07` | guest | yes (every button) |
| `tab_account` | guest | yes (`change_own_password` is `@guest`) |
| `tab_users` | superadmin | yes (`@superadmin` CRUD functions + explicit role checks) |
| `tab_logs` | superadmin | yes (all log functions are `@superadmin`) |

## Public API of the `auth` package

Everything below is importable with `from auth import ...`.

### Roles, context and decorators

| Name | Description |
|------|-------------|
| `ROLE_LEVELS` | `{"guest": 0, "user": 1, "admin": 2, "superadmin": 3}` |
| `superadmin`, `admin`, `user`, `guest` | the four decorators |
| `require_role(role)` | factory behind them |
| `user_context(user)` | context manager binding the current user |
| `current_user()` / `current_role()` | current user dict (or `None`) / role (`"guest"` when anonymous, display only) |
| `has_role(role)` | `True` for an active, non-expired user at or above `role` |

### Accounts and sessions

| Function | Notes |
|----------|-------|
| `init_db()` | schema, migration, default accounts (runs on import) |
| `authenticate(username, password)` | session dict or `None`; always runs a hash check (timing protection); no decorator (called before login) |
| `get_user_by_id(user_id)` | user dict or `None` |
| `refresh_session_user(session_user)` | re-reads the user; `None` if deleted, disabled or expired |
| `is_login_locked(username)` | `(locked, seconds_remaining)` |
| `register_login_failure(username)` | returns `True` only for the failure that causes the lock |
| `clear_login_failures(username)` | reset after a successful login |
| `validate_username(name)` / `validate_password(pw, strict=False)` | raise `ValueError` with a translated message |
| `verify_own_password(password)` | `@guest`; checks the password of the **current** user only |
| `change_own_password(current, new)` | `@guest`; the new password must contain a letter and a digit |
| `create_user(username, password, role, expire_date=None)` | `@superadmin` |
| `list_users()` | `@superadmin`; never returns hashes |
| `update_user(user_id, username, role, is_active, new_password="", expire_date=None)` | `@superadmin`; protects the last active superadmin |
| `delete_user(user_id)` | `@superadmin`; not yourself, not the last active superadmin |

Session dict: `{"id", "username", "role", "is_active", "expire_date"}`
(`app.py` adds `sid`, `ip`, `ua` for the audit log).
Errors: `ValueError` = invalid input / business rule (message is translated);
`PermissionError` = not allowed; `sqlite3.IntegrityError` = e.g. duplicate username.

### CAPTCHA

`generate_captcha()` -> `(png_data_url, answer_hash, expires_at)`;
`verify_captcha(answer, hash, expires_at)` -> `bool`.

### Audit log (see the section below)

`audit` (module), `list_audit_events`, `get_audit_settings`,
`update_audit_settings`, `audit_log_counts`, `clear_audit_logs` (all
`@superadmin`).

### Password re-confirmation

`confirm_with_password` (next section).

## Password re-confirmation: `@confirm_with_password`

Runs a callback only after a confirmation dialog with **your message** and then
the signed-in user's **own account password**. Place it directly above the
callback:

```python
from auth import confirm_with_password

@reactive.effect
@reactive.event(input.btn_delete)
@confirm_with_password(
    input,                          # the module server's input
    get_session_user,               # app.py's _ensure_valid_session
    message={"en": "Delete all data?", "fa": "همه داده‌ها حذف شود؟"},
    required_role="admin",          # optional, checked before any dialog
    timeout_seconds=120,            # optional
)
def _on_delete():
    ...                             # runs only after the right password
```

| Parameter | Meaning |
|-----------|---------|
| `message` | first dialog text: string, `{"en": ..., "fa": ...}` dict, or an `i18n.STRINGS` key |
| `title` | optional title (same forms) |
| `required_role` | minimum role, checked **before** any dialog is shown |
| `timeout_seconds` | how long the confirmation stays valid (default 120) |

Flow: click -> role check -> dialog 1 (message, Continue/Cancel) -> dialog 2
(password) -> correct: callback runs; wrong: error inside the dialog; too many
wrong passwords: dialog closes and the account is locked like on the login form;
expired / different user: aborted with a toast. All fixed texts are the
`reauth_*` keys in `i18n.py` (English + Persian). Details and security notes:
[`docs/confirm-with-password.md`](docs/confirm-with-password.md).

Keep in mind: the callback function name must be unique inside its module (it
builds the dialog ids); the password travels over the websocket, so serve the app
over HTTPS; and keep the role decorator on the functions the callback calls
(defence in depth).

## Role-gated buttons demo (`tab_07`)

Eight buttons, all visible to everyone; the server decides.

* Superadmin / Admin / User / Guest buttons: each calls a function wrapped by
  `@superadmin` / `@admin` / `@user` / `@guest`. A too-low role gets the toast
  "You do not have access to this section." (Persian: «دسترسی به این بخش برای شما مقدور نیست.»).
* Four **Secure ...** buttons: the same roles, but behind `@confirm_with_password`
  (message dialog, then the account password). The guest one expires after 30 s
  so the expiry message can be tested.

## Audit log

Events are stored in `db/audit.db` (SQLite, WAL), separate from the user
database, and shown in the superadmin-only **Logs** tab (always the last tab).

| Category | Events |
|----------|--------|
| `auth` | `login_success`, `login_failed` (`bad_credentials` / `captcha`), `logout`, `password_changed`, `password_change_failed` |
| `navigation` | `tab_opened`, `session_ended` |
| `security` | `access_denied`, `unauthorized_tab_request`, `unknown_tab_request`, `account_locked`, `login_blocked_locked`, `session_revoked`, `user_created`, `user_updated`, `role_changed`, `user_deleted`, `audit_settings_changed`, `audit_cleared`, `reauth_failed`, `reauth_blocked_locked`, `sensitive_action_confirmed` |

Each row: UTC time, category, event, severity (`info` / `warning` / `critical`),
user id / name / role, session id, IP, user agent and a JSON `detail`.

* **Never logged:** passwords and CAPTCHA answers. Inputs are sanitised
  (control characters removed, lengths capped).
* **Logging never breaks the app:** `audit.log_event()` swallows its own errors.
* **Logs tab -> Events:** three sub-tabs, filters (severity, username, rows),
  refresh and CSV export (formula-injection safe).
* **Logs tab -> Settings:** retention per category (defaults: navigation 30 days,
  authentication 180, security 365), the minimum interval between automatic
  clean-ups (default 1 hour), and buttons to clear the navigation,
  authentication or security log separately or all logs at once (each asks for
  confirmation). Clearing is itself recorded afterwards as `audit_cleared`.
* **Superadmin:** recorded like everyone else (default). `AUDIT_LOG_SUPERADMIN=0`
  skips the superadmin's own routine activity, but account management, log
  settings/clean-up and attacks on the `superadmin` account are still recorded.
* **Adding an event:** `audit.log_event("security", "my_event", user=current_user(), detail={...})`.

Limits: the automatic clean-up is checked when a new browser session starts (so
it needs some traffic); the file can be edited by anyone with write access to
`db/audit.db` (ship logs elsewhere if you need tamper-evidence). Full reference:
[`docs/audit-log.md`](docs/audit-log.md) and the tutorial.

## Testing

```bash
pip install -r requirements-dev.txt
pytest
```

Mutating tests use a temporary SQLite file (`isolated_db`) and a temporary audit
database (`isolated_audit_db`, autouse), never the real `db/*.db`. Role fixtures:
`superadmin_ctx`, `admin_ctx`, `user_ctx`, `guest_ctx`, `anonymous_ctx`. Overview
of every test file: [`tests/README.md`](tests/README.md).

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

A second file, `db/audit.db`, holds the audit log (`audit_log` table) and its
retention settings (`audit_settings` table). It is created on first use and is
git-ignored like `auth.db`.

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

### How widgets follow the theme

Shiny and Bootstrap ship widgets with hard-coded light colours. Two things make
**every** widget follow the selected theme:

1. `static/js/custom.js` sets `data-bs-theme="light|dark"` on `<html>` together
   with `data-theme`, so Bootstrap 5.3's own dark palette applies to anything
   not styled by hand. Dark themes also set `color-scheme: dark` (native
   scrollbars, spin buttons, date inputs, `<select>` popups).
2. The **THEME BRIDGE** section at the end of `static/css/styles.css` maps the
   widget classes to the theme variables (`--surface`, `--text`, `--border`,
   `--accent` ...). It covers text / number / password / textarea inputs
   (`.shiny-input-number`, `.form-control` ...), `select` and selectize,
   checkbox / radio / switch, sliders (`.irs--shiny`), the date picker, file
   input, buttons (`.btn-default`, `.btn-primary`, `.action-label`, download
   links), cards, accordion, nav tabs / pills, tables, modals, notifications,
   dropdowns, popovers, tooltips, list groups, progress bars, code output,
   scrollbars and browser autofill.

If a new widget looks wrong in a theme, inspect its class in the browser and add
one rule to the THEME BRIDGE using the theme variables (never a fixed colour).
`tests/test_theme_coverage.py` checks that all 12 themes define the required
variables and that the widget selectors above stay styled. Note that matplotlib
figures are images and keep their own (white) background.

### Sidebar toggle

The top bar has a large menu button (`#sidebar-toggle-btn`, 44 px). The layout
is plain HTML/CSS (`<aside id="app-sidebar">` + `<main class="app-main">`, no
bslib `layout_sidebar`): `setupSidebarToggle` in `custom.js` only adds or removes
the class `sidebar-collapsed` on `.app-shell`, and keeps `aria-expanded` in sync.

* Desktop: the choice (open / closed) is remembered in `localStorage`.
* Phones (< 768 px): the menu starts closed, slides over the content, and closes
  when you tap outside it or pick a page.
* RTL/LTR work automatically (logical CSS properties).
* The content (`.app-main`) uses all remaining space; `.tab-pane-content` is
  full-width and fills the available height.

### Login CAPTCHA

The CAPTCHA image is drawn at 2x resolution with a bundled font
(`auth/fonts/DejaVuSans-Bold.ttf`, Bitstream Vera / DejaVu licence in
`auth/fonts/DejaVu-LICENSE.txt`), so the characters are large and identical on
Windows, Linux and slim Docker images. Size is set by `CAPTCHA_WIDTH` /
`CAPTCHA_HEIGHT` in `auth/captcha.py` and must match `.login-captcha-image` in
`styles.css`.

## Adding a New Tab

Detailed guides live in `tabs/`: [`HOW_TO_ADD_A_TAB.md`](tabs/HOW_TO_ADD_A_TAB.md)
(every place to edit), [`MODULES.md`](tabs/MODULES.md) (how Shiny modules work)
and [`tabs/examples/`](tabs/examples/README.md) (15 copy-ready module examples).

Quick version:

1. Copy an existing module from `tabs/`.
2. Give the new module a unique `NAV_ID`.
3. Set `NAV_LABEL` to the text shown in the sidebar (or `t("some_key")` after
   adding the key to both languages in `i18n.py`, if the tab should be bilingual).
4. Set `NAV_ICON` to a Bootstrap Icons class for top-level items.
5. Set `NAV_GROUP` to `dashboard` to place the tab inside the Dashboard group,
   or use `None` for a top-level item.
6. Set `NAV_MIN_ROLE` to the minimum role required to see the page.
7. In `app.py`: import the module, add it to the `TABS` list, **and call its
   `server()` once inside `def server(...)`** (e.g. `tab_08.server()`).

Example:

```python
NAV_ID = "tab_08"
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

## Next Steps

Done since the first release: user/security activity logging (the **Logs** tab) and
password re-confirmation for sensitive actions.

Ideas for future releases:

- **Session timeout / idle auto-logout**  
  Automatically log the user out after a period of inactivity (e.g. 10 minutes)
  to improve security on shared or unattended workstations.

- **Server-side decorators for `tab_01` ... `tab_03`**  
  Today these demo tabs are only hidden by role; their callbacks should use the
  pattern from `tab_07` before they are replaced by real, sensitive tabs.

- **Shared rate limiting**  
  The login lockout counter lives in process memory; use a shared store (e.g.
  Redis) when running several workers.

- **Scheduled log clean-up**  
  Run the retention purge from a cron job instead of at session start.
