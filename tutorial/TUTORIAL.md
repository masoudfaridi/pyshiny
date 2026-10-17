# راهنمای کامل پروژه (Python Shiny Dashboard)

این سند همه‌چیزِ داخل پروژه را توضیح می‌دهد: ساختار فایل‌ها، نحوه کار برنامه، تک‌تک
توابع و دکوریتورها، سیستم لاگ، سیستم دو‌زبانه، ساخت تب‌های جدید، تست‌ها و نکات امنیتی.
کد و نام توابع به انگلیسی نوشته شده‌اند و توضیح‌ها فارسی است.

> **نسخه کوتاه‌تر انگلیسی** در `README.md` ریشه پروژه هست. راهنمای‌های تخصصی‌تر در
> `docs/` (لاگ و دکوریتور تأیید با رمز) و `tabs/` (ساخت تب و ماژول‌های Shiny) قرار دارند.

## فهرست

1. [نقشه پروژه](#s1)
2. [نصب، اجرا و تنظیمات](#s2)
3. [معماری: از باز شدن صفحه تا نمایش یک تب](#s3)
4. [سیستم احراز هویت (`auth/core.py`)](#s4)
5. [نقش‌ها و دکوریتورهای RBAC](#s5)
6. [دو لایه محافظت: مخفی کردن و دکوریتور](#s6)
7. [دکوریتور تأیید با رمز عبور (`@confirm_with_password`)](#s7)
8. [لاگ ممیزی (Audit Log)](#s8)
9. [دو‌زبانه بودن (`i18n.py`)](#s9)
10. [ساخت تب جدید](#s10)
11. [تب‌های موجود یکی‌یکی](#s11)
12. [ظاهر: تم، فونت، CSS، جاوااسکریپت، CAPTCHA](#s12)
13. [تست‌ها](#s13)
14. [امنیت: چه چیزی تضمین می‌شود و چه چیزی نه](#s14)
15. [عیب‌یابی و سؤال‌های رایج](#s15)
16. [واژه‌نامه](#s16)

---

<a id="s1"></a>

## 1. نقشه پروژه

```text
pyshiny/
├── app.py                  # قلب برنامه: UI اصلی، ورود، سایدبار، همه handlerهای سراسری
├── i18n.py                 # متن‌های فارسی/انگلیسی + سوئیچ APP_LANG
├── auth/                   # همه‌چیز درباره هویت و دسترسی
│   ├── __init__.py         # API عمومی (همه چیزهایی که باید از `auth` import کنید)
│   ├── core.py             # دیتابیس کاربران، رمز، نقش‌ها، دکوریتورهای RBAC، قفل ورود
│   ├── captcha.py          # CAPTCHA تصویری آفلاین
│   ├── audit.py            # ذخیره و خواندن لاگ ممیزی (db/audit.db)
│   ├── confirm.py          # @confirm_with_password
│   └── fonts/              # فونت DejaVu برای CAPTCHA
├── tabs/                   # هر فایل = یک آیتم سایدبار
│   ├── tab_01..tab_04.py   # نمونه‌های نمودار (Normal, Poisson, Binomial, Negative Binomial)
│   ├── tab_05.py, tab_06.py# Widgets و Tables (جایگزین/Placeholder)
│   ├── tab_07.py           # دکمه‌های وابسته به نقش + دکمه‌های محافظت‌شده با رمز
│   ├── tab_account.py      # «حساب من» (تغییر رمز)
│   ├── tab_users.py        # مدیریت کاربران (فقط superadmin)
│   ├── tab_logs.py         # لاگ‌ها (فقط superadmin، آخرین تب)
│   ├── HOW_TO_ADD_A_TAB.md # چک‌لیست ساخت تب
│   ├── MODULES.md          # توضیح ماژول‌های Shiny
│   └── examples/           # ۱۵ مثال آماده (ex01 ... ex15)
├── static/
│   ├── css/                # bootstrap.css، bootstrap.rtl.css، fonts.css، styles.css
│   ├── js/custom.js        # سایدبار، تم، فونت، Enter در ورود، دکمه‌های جدول کاربران
│   └── fonts/              # فونت‌های LTR و RTL (woff2/ttf)
├── db/                     # فایل‌های SQLite (خودکار ساخته می‌شود؛ هرگز commit نشود)
│   ├── auth.db             #   کاربران
│   └── audit.db            #   لاگ ممیزی + تنظیمات نگهداری
├── tests/                  # تست‌های pytest
├── docs/                   # مستندات تخصصی + تصاویر README
├── docker/                 # Dockerfile، compose، اسکریپت‌ها
├── 00_create_files/bootstrap.py       # آماده‌سازی محیط (db/، docker/.env)
├── 01_requirements/update_requirements.py  # به‌روزرسانی خودکار requirements.txt
└── tutorial/TUTORIAL.md    # همین سند
```

### هر بخش چه کاری می‌کند؟ (خلاصه یک‌خطی)

| فایل | وظیفه |
|------|-------|
| `app.py` | ساخت صفحه (ورود یا داشبورد)، مدیریت نشست، سایدبار، ناوبری، handlerهای ورود/خروج/تغییر رمز/مدیریت کاربران، ثبت لاگ ناوبری |
| `auth/core.py` | رمزها (PBKDF2)، `authenticate`، قفل ورود، نقش‌ها، دکوریتورها، CRUD کاربران، توابع خواندن/تنظیم/پاک‌کردن لاگ (همه با `@superadmin`) |
| `auth/audit.py` | نوشتن/خواندن لاگ، تنظیمات نگهداری، پاکسازی خودکار |
| `auth/confirm.py` | دکوریتور تأیید دو‌مرحله‌ای (پیام + رمز) |
| `auth/captcha.py` | ساخت و بررسی CAPTCHA |
| `i18n.py` | رشته‌های دو‌زبانه و تابع `t()` |
| `tabs/*.py` | محتوای هر صفحه |
| `static/js/custom.js` | رفتار سمت مرورگر (کلیک سایدبار → `sidebar_nav`، تم، فونت) |

---

<a id="s2"></a>

## 2. نصب، اجرا و تنظیمات

### نصب

```bash
python 00_create_files/bootstrap.py          # ساخت db/، حذف auth.db قدیمی، ساخت docker/.env
python 01_requirements/update_requirements.py # (اختیاری) به‌روزرسانی requirements.txt
pip install -r requirements.txt               # shiny>=1.4, Pillow, matplotlib, numpy
pip install -r requirements-dev.txt           # برای اجرای تست‌ها (pytest)
```

### اجرا

```bash
shiny run app.py --reload       # http://127.0.0.1:8000
```

اولین اجرا دیتابیس را می‌سازد و چهار کاربر پیش‌فرض را اضافه می‌کند:

| نام کاربری | رمز | نقش |
|-----------|-----|-----|
| `superadmin` | `ChangeMe123!` | superadmin |
| `admin` | `Admin123!` | admin |
| `user` | `User123!` | user |
| `guest` | `Guest123!` | guest |

> **هشدار:** قبل از استفاده واقعی همه رمزها را عوض کنید.

### Docker

```bash
cd docker
docker compose up --build -d              # پورت ۸۰۰۰
PORT=9000 docker compose up --build -d    # پورت دلخواه
APP_LANG=fa docker compose up --build -d  # رابط فارسی
docker compose down
```

پوشه `db/` به‌صورت volume به کانتینر وصل می‌شود، پس کاربران و لاگ‌ها با ری‌استارت از بین نمی‌روند.

### متغیرهای محیطی

| متغیر | پیش‌فرض | معنی |
|-------|---------|------|
| `APP_LANG` | `en` | زبان و جهت رابط: `en` (چپ‌به‌راست) یا `fa` (راست‌به‌چپ). متغیر محیطی بر مقدار داخل `i18n.py` اولویت دارد. با تغییر آن برنامه را ری‌استارت کنید. |
| `PORT` | `8000` | پورت داخل Docker |
| `AUDIT_LOG_SUPERADMIN` | `1` | اگر `0` باشد فعالیت عادی خود superadmin (ورود، خروج، ناوبری) در لاگ ثبت نمی‌شود. مدیریت حساب‌ها و حمله به حساب `superadmin` همچنان ثبت می‌شوند. |
| `TRUST_PROXY_HEADERS` | خاموش | اگر `1` باشد IP کلاینت از `X-Forwarded-For` خوانده می‌شود. فقط پشت یک reverse proxy قابل اعتماد روشن کنید (در غیر این صورت قابل جعل است). |

### ثابت‌های قابل تنظیم داخل کد

| ثابت | فایل | مقدار | معنی |
|------|------|-------|------|
| `LOGIN_MAX_FAILURES` | `auth/core.py` | 5 | تعداد ورود ناموفق قبل از قفل شدن |
| `LOGIN_LOCKOUT_SECONDS` | `auth/core.py` | 300 | مدت قفل (و پنجره شمارش) |
| `PASSWORD_MIN_LEN` / `PASSWORD_MAX_LEN` | `auth/core.py` | 8 / 128 | محدودیت طول رمز |
| `USERNAME_RE` | `auth/core.py` | `^[A-Za-z0-9_-]{3,32}$` | قالب نام کاربری |
| `CAPTCHA_LENGTH`, `CAPTCHA_TTL_SECONDS` | `auth/captcha.py` | 5, 300 | طول و عمر CAPTCHA |
| `DEFAULT_TIMEOUT_SECONDS` | `auth/confirm.py` | 120 | مهلت پیش‌فرض تأیید با رمز |
| `DEFAULT_SETTINGS` | `auth/audit.py` | ناوبری 30، احراز هویت 180، امنیتی 365 روز؛ پاکسازی هر 1 ساعت | مقدار اولیه تنظیمات نگهداری لاگ (از تب Logs قابل تغییر) |

---

<a id="s3"></a>

## 3. معماری: از باز شدن صفحه تا نمایش یک تب

### 3.1 ساختار کلی

Shiny برای Python یک برنامه واکنشی (reactive) است: مرورگر ورودی‌ها (`input`) را به سرور می‌فرستد،
سرور خروجی‌ها (`output`) را برمی‌گرداند. در `app.py` دو چیز تعریف شده:

* `app_ui`: صفحه ثابت (CSS، جاوااسکریپت و یک «اسلات» به نام `root_ui`).
* `server(input, output, session)`: برای **هر نشست مرورگر** یک بار اجرا می‌شود و همه واکنش‌ها را تعریف می‌کند.

### 3.2 جریان کامل

```text
مرورگر باز می‌شود
   │
   ▼
root_ui (render.ui)            ← _ensure_valid_session() کاربر را بررسی می‌کند
   ├── کاربر ندارد  → login_ui()  (فرم ورود + CAPTCHA)
   └── کاربر دارد   → dashboard_ui(role)  (سایدبار + اسلات محتوا)
                              │
                              ▼
                      کلیک روی لینک سایدبار
                              │   custom.js: Shiny.setInputValue("sidebar_nav", navId)
                              ▼
        active_panel (render.ui) → تب مربوط را از TAB_LOOKUP پیدا می‌کند
                              │   نقش کافی نیست؟ → اولین تب مجاز
                              ▼
                  with user_context(user): tab.panel()
```

### 3.3 مقدارهای واکنشی نشست (داخل `server()`)

| متغیر | کاربرد |
|-------|--------|
| `logged_in_user` | دیکشنری کاربر وارد‌شده یا `None` (`{"id","username","role","is_active","expire_date"}`) |
| `login_error` | پیام خطای فرم ورود |
| `create_message`, `account_message`, `edit_modal_message` | پیام‌های فرم‌ها |
| `users_refresh` | شمارنده برای بازخوانی جدول کاربران |
| `editing_user_id` | شناسه کاربری که در modal ویرایش است |
| `captcha_hash`, `captcha_expires`, `captcha_image`, `captcha_nonce` | وضعیت CAPTCHA |

همچنین دو متغیر ساده (غیر واکنشی) در هر نشست: `meta` (شناسه نشست/IP/User-Agent برای لاگ) و
`state` (زمان ورود و آخرین تب برای لاگ ناوبری).

### 3.4 توابع کمکی سطح بالای `app.py`

| تابع | توضیح |
|------|-------|
| `read_asset(*parts)` | متن یک فایل داخل `static/` را می‌خواند (برای inline کردن CSS/JS). |
| `_flat_link(tab)` | یک لینک سایدبار بدون زیرمنو (آیکن + برچسب، `data-nav-id`). |
| `_group_block(group_key, children)` | هدر گروه تاشو (مثل «Dashboard») + لینک‌های زیرمجموعه. |
| `build_sidebar(role)` | `TABS` را به ترتیب می‌پیماید و تب‌هایی که `NAV_MIN_ROLE` آن‌ها بالاتر از نقش کاربر است **نمایش نمی‌دهد**. گروه‌ها فقط یک‌بار ساخته می‌شوند. |
| `build_main_content()` | اسلات محتوای اصلی (`output_ui("active_panel")`). |
| `login_ui()` | فرم ورود. |
| `dashboard_ui(role)` | قاب برنامه: نوار بالا (دکمه سایدبار، برند، نقش و نام کاربر، انتخاب تم/فونت، خروج) + سایدبار (`build_sidebar(role)`) + اسلات محتوا. |
| `build_app_shell()` | قاب HTML ثابت. |
| `_inline_json(data)` | JSON امن برای قرار دادن داخل `<script>` (جلوگیری از شکستن تگ). |

### 3.5 توابع داخل `server()`

| تابع | نوع | کار |
|------|-----|-----|
| `_log(category, event, user=None, ...)` | helper | نوشتن لاگ با اطلاعات نشست (شناسه، IP، UA) |
| `_session_seconds()` | helper | مدت نشست برای لاگ خروج |
| `_revoke_reason(user)` | helper | دلیل لغو نشست: `account_deleted` / `account_disabled` / `account_expired` |
| `_note_login_failure(username, reason)` | helper | شمارش شکست ورود + لاگ `login_failed` و در صورت قفل `account_locked` |
| `_on_ended()` | callback | با بسته شدن مرورگر، `session_ended` را ثبت می‌کند |
| `_issue_captcha()` | helper | CAPTCHA جدید می‌سازد |
| **`_ensure_valid_session()`** | helper | **مهم‌ترین تابع**: کاربر را دوباره از SQLite می‌خواند؛ حذف/غیرفعال/منقضی → نشست لغو و لاگ `session_revoked`؛ در غیر این صورت دیکشنری تازه (به‌علاوه `sid/ip/ua`) را برمی‌گرداند |
| `root_ui` | render.ui | ورود یا داشبورد |
| `login_captcha_ui`, `login_message` | render.ui | بخش‌های فرم ورود |
| `_login` | effect | بررسی قفل → CAPTCHA → `authenticate` → لاگ → `logged_in_user.set(user)` |
| `_logout` | effect | لاگ `logout` و پاک کردن نشست |
| `active_panel` | render.ui | تب انتخاب‌شده را (با بررسی نقش) نمایش می‌دهد |
| `_log_navigation` | effect | لاگ `tab_opened` یا رویداد امنیتی برای تب جعلی/غیرمجاز |
| `_change_password_event` | effect | تغییر رمز خود کاربر (`change_own_password`) |
| `_create_user_event`, `_open_edit_modal`, `_save_user_event`, `_delete_from_table`, `_delete_user_event`, `users_table`, ... | effect/render | مدیریت کاربران (همه از توابع `@superadmin` داخل `core.py` استفاده می‌کنند) |

### 3.5.1 چرا `_ensure_valid_session()` این‌قدر مهم است؟

`logged_in_user()` یک **کش** است؛ اگر ادمین دیگری نقش شما را کم کند، کش قدیمی می‌ماند.
`_ensure_valid_session()` در هر استفاده حساس دوباره از دیتابیس می‌خواند. به همین دلیل
تب‌هایی که دکمه حساس دارند (`tab_07`, `tab_logs`) **این تابع** را به‌عنوان `get_session_user`
می‌گیرند، نه مقدار خام `logged_in_user`.

### 3.6 رشته (thread) و contextvar

`user_context(user)` با یک `ContextVar` کار می‌کند: فقط داخل بلوک `with` تابع `current_user()`
مقدار دارد. خارج از آن `None` است و دکوریتورها همه‌چیز را **رد می‌کنند** (fail-closed).
تفصیل در [بخش ۵](#s5).

---

<a id="s4"></a>

## 4. سیستم احراز هویت (`auth/core.py`)

همه‌چیز از پکیج `auth` import می‌شود (`from auth import ...`). فایل `auth/__init__.py` فهرست
عمومی را re-export می‌کند.

### 4.1 دیتابیس کاربران

فایل `db/auth.db`، جدول `users`:

| ستون | نوع | توضیح |
|------|-----|-------|
| `id` | INTEGER PK | شناسه |
| `username` | TEXT UNIQUE | نام کاربری |
| `password_hash` | TEXT | `pbkdf2_sha256$<تکرار>$<salt hex>$<digest hex>` |
| `role` | TEXT | فقط یکی از `superadmin`, `admin`, `user`, `guest` (CHECK در دیتابیس) |
| `is_active` | INTEGER | 1 = فعال، 0 = غیرفعال |
| `expire_date` | TEXT NULL | تاریخ انقضا به قالب `YYYY-MM-DD` (شامل خودِ آن روز) |
| `created_at` | TEXT | زمان ساخت |

`init_db()` هنگام import شدن `auth.core` اجرا می‌شود: جدول را می‌سازد، ستون `expire_date` را برای دیتابیس‌های
قدیمی اضافه می‌کند (migration)، انقضای superadmin را `NULL` می‌کند و چهار کاربر پیش‌فرض را
با `INSERT OR IGNORE` اضافه می‌کند (کاربر موجود هرگز بازنویسی نمی‌شود).

### 4.2 ثابت‌ها

| نام | مقدار | کاربرد |
|-----|-------|--------|
| `ROLE_LEVELS` | `{"guest":0,"user":1,"admin":2,"superadmin":3}` | ترتیب نقش‌ها؛ عدد بزرگ‌تر = دسترسی بیشتر |
| `USERNAME_RE` | `^[A-Za-z0-9_-]{3,32}$` | قالب مجاز نام کاربری |
| `PASSWORD_MIN_LEN`, `PASSWORD_MAX_LEN` | 8, 128 | طول رمز |
| `LOGIN_MAX_FAILURES` | 5 | شکست‌های مجاز |
| `LOGIN_LOCKOUT_SECONDS` | 300 | مدت قفل |
| `DB_PATH` | `db/auth.db` | مسیر فایل |

### 4.3 رمز عبور

| تابع | توضیح |
|------|-------|
| `_hash_password(password, salt=None)` | PBKDF2-HMAC-SHA256 با 600000 تکرار و salt تصادفی. خروجی `pbkdf2_sha256$600000$<salt>$<digest>`. (داخلی) |
| `_verify_password(password, encoded)` | مقایسه با `hmac.compare_digest` (زمان ثابت). قالب خراب/ناشناخته → `False`. (داخلی) |
| `_DUMMY_PASSWORD_HASH` | هش ثابت برای وقتی که کاربر وجود ندارد تا زمان پاسخ نام‌های موجود/ناموجود یکی باشد (جلوگیری از شناسایی کاربر از روی زمان). |
| `validate_username(username)` | `strip` و بررسی با `USERNAME_RE`. خطا: `ValueError`. |
| `validate_password(password, *, strict=False, field_name=None)` | طول 8 تا 128. با `strict=True` باید **حداقل یک حرف و یک عدد** هم داشته باشد. رمزی که superadmin می‌دهد `strict=False`؛ تغییر رمز توسط خود کاربر `strict=True`. |

### 4.4 انقضا

* `_normalize_expiry(expire_date, role)`: برای superadmin همیشه `None`؛ برای بقیه تاریخ ISO را اعتبارسنجی می‌کند (`ValueError` اگر قالب خراب باشد).
* `_is_expired(expire_date)`: `True` اگر **امروز بعد از** تاریخ باشد (روز انقضا هنوز معتبر است).
* حساب منقضی نمی‌تواند وارد شود و توابع محافظت‌شده هم نشست منقضی را رد می‌کنند.
* superadmin هرگز منقضی نمی‌شود.

### 4.5 نشست و زمینه کاربر (user context)

دیکشنری کاربر در نشست (خروجی `_session_dict`) همیشه این کلیدها را دارد:

```python
{"id": 3, "username": "user", "role": "user", "is_active": 1, "expire_date": None}
```

(در `app.py` سه کلید `sid`, `ip`, `ua` هم برای لاگ اضافه می‌شود.)

| تابع | توضیح |
|------|-------|
| `user_context(user)` | **context manager**. داخل `with` کاربر «جاری» همان `user` است و بعد از خروج به حالت قبل برمی‌گردد. با `ContextVar` پیاده‌سازی شده، پس بین نشست‌ها/threadها قاطی نمی‌شود. |
| `current_user()` | دیکشنری کاربر جاری یا `None` |
| `current_role()` | نقش کاربر جاری؛ بدون کاربر `"guest"` (فقط برای نمایش، **نه** تصمیم امنیتی) |
| `has_role(required_role)` | `True` فقط اگر: کاربر هست **و** فعال است **و** منقضی نشده **و** سطح نقشش ≥ سطح مورد نیاز. نقش ناشناخته → `KeyError`. |
| `get_user_by_id(user_id)` | کاربر را از دیتابیس می‌خواند؛ نبود → `None` |
| `refresh_session_user(session_user)` | کاربر را دوباره از دیتابیس می‌خواند و در صورت حذف/غیرفعال/منقضی (به‌جز superadmin) `None` می‌دهد. نقش/نام تازه را هم برمی‌گرداند. |

مثال:

```python
from auth import user_context, current_user, has_role

with user_context({"id": 1, "username": "x", "role": "admin", "is_active": 1, "expire_date": None}):
    print(current_user()["username"])   # x
    print(has_role("admin"))            # True
    print(has_role("superadmin"))       # False
print(current_user())                   # None  ← بیرون از with کاربری نیست
```

### 4.6 قفل ورود (Rate limit)

شمارنده شکست‌ها **داخل حافظه‌ی همان پردازش** نگه داشته می‌شود (به‌ازای هر نام کاربری، بدون توجه به حروف بزرگ/کوچک).

| تابع | توضیح |
|------|-------|
| `is_login_locked(username)` | `(قفل؟, ثانیه‌های باقی‌مانده)`. قفل وقتی است که 5 شکست در 300 ثانیه اخیر باشد. |
| `register_login_failure(username)` | یک شکست ثبت می‌کند. **`True` فقط وقتی برمی‌گرداند که همین شکست باعث قفل شد** (تا بتوانید قفل را یک‌بار لاگ کنید). |
| `clear_login_failures(username)` | شمارنده را صفر می‌کند (بعد از ورود موفق). |

> **نکته:** چون شمارنده در حافظه است، با چند worker یا ری‌استارت صفر می‌شود. برای محیط بزرگ باید به یک ذخیره مشترک (مثل Redis) منتقل شود.

### 4.7 `authenticate(username, password)`

`dict` نشست را برمی‌گرداند یا `None`. همیشه یک بررسی رمز انجام می‌دهد (حتی برای کاربر ناموجود/غیرفعال/منقضی، با هش ساختگی) تا زمان پاسخ نشت نکند.
برای موفقیت: کاربر باید باشد، فعال باشد، (غیر superadmin) منقضی نشده باشد و رمز درست باشد. **این تابع دکوریتور ندارد** (قبل از ورود فراخوانی می‌شود).

### 4.8 توابع مخصوص کاربر وارد‌شده

| تابع | دکوریتور | توضیح |
|------|----------|-------|
| `verify_own_password(password)` | `@guest` | `True` اگر رمز، رمز **کاربر جاری** (داخل `user_context`) باشد. هرگز نمی‌تواند حساب دیگری را بسنجد. برای `@confirm_with_password` ساخته شده. |
| `change_own_password(current_password, new_password)` | `@guest` | رمز فعلی را بررسی می‌کند (غلط → `ValueError` + لاگ `password_change_failed`)، رمز جدید را با `strict=True` اعتبارسنجی می‌کند و ذخیره می‌کند (لاگ `password_changed`). |

### 4.9 مدیریت کاربران (همه `@superadmin`)

| تابع | قوانین |
|------|--------|
| `create_user(username, password, role, expire_date=None)` | نام و رمز اعتبارسنجی می‌شوند (رمز: فقط طول). نقش باید در `ROLE_LEVELS` باشد. نام تکراری → خطای SQLite. لاگ `user_created` (اگر نقش superadmin باشد شدت `critical`). |
| `list_users()` | لیست دیکشنری‌ها: `id, username, role, is_active, expire_date, created_at` (هرگز هش رمز را برنمی‌گرداند). |
| `update_user(user_id, username, role, is_active, new_password="", expire_date=None)` | رمز خالی = تغییر نکند. **آخرین superadmin فعال** را نمی‌شود تنزل داد یا غیرفعال کرد (`err_last_superadmin`). لاگ `user_updated` یا `role_changed` (تغییر نقش) با مقدار قبل/بعد. هیچ تغییری → لاگی ثبت نمی‌شود. |
| `delete_user(user_id)` | کاربر **خودش را** نمی‌تواند حذف کند (`err_delete_self`)؛ آخرین superadmin فعال هم حذف نمی‌شود (`err_delete_last_superadmin`). لاگ `user_deleted`. |

### 4.10 توابع لاگ داخل `core.py` (همه `@superadmin`)

`list_audit_events`, `get_audit_settings`, `update_audit_settings`, `audit_log_counts`, `clear_audit_logs`
— جزئیات در [بخش ۸](#s8).

### 4.11 پیام‌های خطا

خطاهای اعتبارسنجی با `i18n.t("err_...")` ساخته می‌شوند، پس به زبان فعال برنامه‌اند. نوع خطاها:

| نوع | چه موقع |
|-----|---------|
| `ValueError` | ورودی نامعتبر یا قانون کسب‌وکار (رمز کوتاه، آخرین superadmin، ...) — پیامش قابل نمایش به کاربر است |
| `PermissionError` | دسترسی کافی نیست (دکوریتور) یا نشست لازم است |
| `sqlite3.IntegrityError` | مثلاً نام کاربری تکراری؛ باید در لایه UI گرفته شود |

---

<a id="s5"></a>

## 5. نقش‌ها و دکوریتورهای RBAC

### 5.1 سلسله‌مراتب

```text
superadmin (3)  ⊃  admin (2)  ⊃  user (1)  ⊃  guest (0)
```

نقش بالاتر همه‌ی دسترسی‌های پایین‌تر را دارد.

### 5.2 چهار دکوریتور

```python
from auth import superadmin, admin, user, guest
```

| دکوریتور | کیست می‌تواند اجرا کند | |
|---------|------------------------|---|
| `@superadmin` | فقط superadmin | مدیریت کاربران، لاگ‌ها |
| `@admin` | admin و superadmin | |
| `@user` | user، admin، superadmin | |
| `@guest` | همه‌ی کاربران **وارد‌شده** | «پایین‌ترین سطح»، نه «ناشناس» |

ماتریس:

| دکوریتور | superadmin | admin | user | guest | بدون نشست |
|----------|:---:|:---:|:---:|:---:|:---:|
| `@superadmin` | ✅ | ❌ | ❌ | ❌ | ❌ |
| `@admin` | ✅ | ✅ | ❌ | ❌ | ❌ |
| `@user` | ✅ | ✅ | ✅ | ❌ | ❌ |
| `@guest` | ✅ | ✅ | ✅ | ✅ | ❌ |

### 5.3 دکوریتور چگونه کار می‌کند

```python
def require_role(required_role):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not has_role(required_role):
                audit.log_event("security", "access_denied", user=current_user(),
                                severity="warning",
                                detail={"function": fn.__name__, "required_role": required_role})
                raise PermissionError(...)
            return fn(*args, **kwargs)
        return wrapper
    return decorator

superadmin = require_role("superadmin")   # و admin, user, guest به همین ترتیب
```

نکات کلیدی:

1. **کاربر از پارامتر تابع نمی‌آید**، از `current_user()` (یعنی از `user_context`) می‌آید. پس تابع محافظت‌شده باید داخل `with user_context(user):` صدا زده شود.
2. **Fail-closed:** بیرون از `user_context` کاربری نیست → `has_role` همیشه `False` → `PermissionError`.
3. حساب غیرفعال یا منقضی هم رد می‌شود، حتی اگر نقش درست باشد.
4. هر رد شدن **خودکار** در لاگ امنیتی (`access_denied`) با نام تابع و نقش لازم ثبت می‌شود.
5. `@wraps` نام و docstring تابع را حفظ می‌کند و `__wrapped__` را می‌گذارد (تست‌ها از آن می‌فهمند دکوریتور دقیقاً یک‌بار اعمال شده).

### 5.4 ساخت دکوریتور دلخواه

```python
from auth import require_role

moderator = require_role("admin")   # یک نام دیگر برای همان سطح
@moderator
def ban_user(user_id): ...
```

نقش باید یکی از چهار نقش باشد (در غیر این صورت `KeyError` هنگام اجرا).

### 5.5 استفاده در برنامه Shiny (الگوی درست)

دکوریتور را **روی تابع کار** بگذارید (نه روی خود handler واکنشی). handler باید کاربر معتبر را بگیرد و تابع را داخل `user_context` صدا بزند:

```python
from auth import admin, user_context

@admin
def export_report(report_id):          # تابع محافظت‌شده: فقط کار واقعی
    return build_report(report_id)

@module.server
def _server(input, output, session, get_session_user):

    @reactive.effect
    @reactive.event(input.btn_export)
    def _on_export():
        person = get_session_user()               # از دیتابیس تازه شده
        if person is None:
            ui.notification_show("Please sign in again.", type="error"); return
        try:
            with user_context(person):             # ← بدون این، همیشه PermissionError
                result = export_report(5)
            ui.notification_show("Done", type="message")
        except PermissionError:
            ui.notification_show("You do not have access.", type="error")
```

این همان الگوی `_attempt()` در `tabs/tab_07.py` است.

### 5.6 اشتباهات رایج

| اشتباه | نتیجه | راه درست |
|--------|-------|----------|
| گذاشتن `@admin` روی خود handler واکنشی و صدا نزدن داخل `user_context` | همیشه `PermissionError` | دکوریتور روی تابع کار + `with user_context(person)` |
| پاس دادن `logged_in_user` خام به ماژول | نقش کش‌شده (بعد از تنزل هنوز قدیمی) | پاس دادن `_ensure_valid_session` |
| `from auth import user` و بعد متغیری به نام `user` | دکوریتور `@user` بازنویسی می‌شود | متغیرها را `person`/`current` بنامید |
| تصمیم امنیتی با `current_role()` | بدون کاربر `"guest"` برمی‌گرداند | از `has_role()` یا دکوریتور استفاده کنید |
| تکیه فقط بر مخفی بودن تب | ورودی جعلی هنوز به سرور می‌رسد | دکوریتور سمت سرور هم بگذارید (بخش ۶) |
| گرفتن `PermissionError` و ادامه دادن بی‌صدا | کاربر نمی‌فهمد چرا کار نشد | توست/پیام نشان بدهید (مثل `tab_07`) |

---

<a id="s6"></a>

## 6. دو لایه محافظت: مخفی کردن و دکوریتور

### 6.1 لایه اول: مخفی کردن (UI)

* `NAV_MIN_ROLE` هر تب مشخص می‌کند چه نقشی آن را ببیند.
* `build_sidebar(role)` لینک تب‌های بالاتر از نقش را **نمی‌سازد**.
* `active_panel` هم بررسی می‌کند: اگر مرورگر `sidebar_nav` جعلی بفرستد و نقش کافی نباشد، اولین تب مجاز نشان داده می‌شود.
* در `_log_navigation` درخواست تب جعلی/غیرمجاز به‌صورت رویداد امنیتی (`unknown_tab_request` / `unauthorized_tab_request`) ثبت می‌شود.

**این لایه فقط ظاهر را کنترل می‌کند.** سرور ماژول هر تب برای همه نشست‌ها (حتی قبل از ورود) اجرا می‌شود و Shiny هر شناسه‌ی ورودی را که مرورگر بفرستد می‌پذیرد. یعنی کسی که ورودی را دستی بفرستد (مثلاً `tab_01-generate`) به callback می‌رسد، حتی اگر دکمه‌اش را هیچ‌وقت ندیده باشد.

### 6.2 لایه دوم: دکوریتور (سرور)

دکوریتورها جلوی **اجرای تابع** را می‌گیرند، فارغ از اینکه ورودی از کجا آمده. بنابراین هر عملیات حساس باید در تابعی با دکوریتور باشد.

### 6.3 وضعیت فعلی تب‌ها

| تب | حداقل نقش (UI) | محافظت سمت سرور |
|----|----------------|-----------------|
| `tab_01` Normal | superadmin | ❌ فقط مخفی بودن (callbackها دکوریتور ندارند؛ فقط نمونه‌گیری تصادفی است، خطر کم) |
| `tab_02` Poisson | admin | ❌ فقط مخفی بودن |
| `tab_03` Binomial | user | ❌ فقط مخفی بودن |
| `tab_04`, `tab_05`, `tab_06` | guest | — (برای همه وارد‌شده‌ها آزاد است) |
| `tab_07` دکمه‌ها | guest | ✅ هر دکمه با دکوریتور؛ دکمه‌های امن با `@confirm_with_password` + دکوریتور |
| `tab_account` | guest | ✅ `change_own_password` با `@guest` |
| `tab_users` | superadmin | ✅ `create_user/list_users/update_user/delete_user` با `@superadmin` + بررسی صریح نقش در رندرها/modalها |
| `tab_logs` | superadmin | ✅ همه‌ی خواندن/تنظیم/پاک‌کردن لاگ با `@superadmin` |

### 6.4 چطور `tab_01` تا `tab_03` را هم محافظت کنیم؟

الگو: ماژول `get_session_user` بگیرد و callback کار را داخل تابع دکوریت‌شده اجرا کند. (مثل `tab_07`.) اگر خواستید، همین کار روی این سه تب هم قابل انجام است.

---

<a id="s7"></a>

## 7. دکوریتور تأیید با رمز عبور (`@confirm_with_password`)

فایل: `auth/confirm.py` — نمونه‌ی زنده: چهار دکمه‌ی «Secure ... button» در `tabs/tab_07.py`.

### 7.1 کار دکوریتور چیست؟

برای عملیات مهم (حذف، تغییر حساس، ...) نمی‌خواهیم کلیک اشتباه یا نشست باز‌مانده‌ی دیگران کار را انجام دهد.
این دکوریتور بین «کلیک» و «اجرای callback» دو مرحله قرار می‌دهد:

1. پنجره‌ی اول با **پیغامی که شما در دکوریتور می‌نویسید** («آیا مطمئن هستید؟») و دکمه‌های ادامه/انصراف.
2. پنجره‌ی دوم: **رمز عبور حساب خودِ کاربر**. فقط اگر درست بود callback اجرا می‌شود.

### 7.2 استفاده

```python
from auth import confirm_with_password

@module.server
def _server(input, output, session, get_session_user):

    @reactive.effect
    @reactive.event(input.btn_delete)                 # ۱) رویداد کلیک
    @confirm_with_password(                           # ۲) دکوریتور تأیید (مستقیماً بالای callback)
        input,
        get_session_user,                             #    همان _ensure_valid_session
        message={"en": "Delete all data?", "fa": "همه داده‌ها حذف شود؟"},
        required_role="admin",
    )
    def _on_delete():                                 # ۳) callback واقعی
        ...                                           #    فقط بعد از رمز درست اجرا می‌شود
```

**ترتیب ثابت است:** `reactive.effect` ← `reactive.event` ← `confirm_with_password` ← تابع.
نام `_on_delete` بعد از دکوریت شدن تابعی می‌شود که **فقط پنجره را باز می‌کند**؛ callback اصلی از هیچ راه دیگری قابل اجرا نیست.

### 7.3 پارامترها

| پارامتر | نوع | توضیح |
|---------|-----|-------|
| `input` | — | `input` همان `@module.server` (برای ساخت شناسه‌های پنجره‌ها) |
| `get_session_user` | callable | تابعی که کاربر **تازه‌شده** یا `None` برمی‌گرداند (`_ensure_valid_session`) |
| `message` | `str` / `dict` / key | متن پنجره‌ی اول. dict به‌شکل `{"en": ..., "fa": ...}` (زبان `APP_LANG`، پیش‌فرض انگلیسی)، یا نام یک کلید در `i18n.STRINGS`، یا متن ساده، یا callable |
| `title` | مثل `message` | اختیاری؛ پیش‌فرض «تأیید عملیات» (`reauth_title`) |
| `required_role` | `str` یا `None` | حداقل نقش؛ **قبل از نمایش هر پنجره** بررسی می‌شود (نقش کم → فقط توست + لاگ `access_denied`) |
| `timeout_seconds` | `int` > 0 | مهلت تأیید (پیش‌فرض 120). مقدار نامعتبر → `ValueError` |

نقش ناشناخته در `required_role` → `ValueError` هنگام ساخت.

### 7.4 جریان و پیام‌ها

```text
کلیک ─► [نقش؟] ─► پنجره ۱: message ─ادامه─► پنجره ۲: رمز ─► درست؟ ─► callback
          │ کم: توست                 │ انصراف        │ غلط: خطا داخل پنجره
          ▼                          ▼                ▼ قفل: پنجره بسته + توست
```

| وضعیت | چه می‌بینید | کلید i18n |
|-------|-------------|-----------|
| نشست نامعتبر هنگام کلیک | توست | `reauth_signin` |
| نقش کافی نیست | توست، پنجره باز نمی‌شود | `reauth_denied` |
| کلیک مجاز | پنجره ۱ با `message` | `reauth_title`, `reauth_continue`, `reauth_cancel` |
| ادامه | پنجره ۲: فیلد رمز | `reauth_password_intro`, `reauth_password_label`, `reauth_submit` |
| رمز خالی | خطا داخل پنجره (شکست شمرده نمی‌شود) | `reauth_empty_password` |
| رمز غلط | خطا داخل پنجره؛ باز می‌ماند | `reauth_wrong_password` |
| شکست‌های زیاد | پنجره بسته، توست قفل (مثل صفحه ورود) | `login_locked` |
| مهلت تمام شد | پنجره بسته + توست | `reauth_expired` |
| کاربر عوض شد / خروج | پنجره بسته + توست | `reauth_signin` |
| رمز درست | پنجره بسته؛ callback اجرا | — |
| `PermissionError` داخل callback | توست | `reauth_denied` |

همه این متن‌ها در `i18n.py` به فارسی و انگلیسی هستند.

### 7.5 امنیت (چرا قابل اعتماد است)

* رمز فقط برای **کاربر جاری نشست** بررسی می‌شود (`verify_own_password`)؛ نام کاربری قابل تایپ نیست.
* شکست‌ها با **همان شمارنده‌ی صفحه ورود** شمرده می‌شوند؛ نشست باز‌مانده را نمی‌شود از این راه brute-force کرد.
* پنجره‌ها `easy_close=False` هستند؛ ورودی‌های جعلی (submit بدون پنجره، continue بعد از انصراف) نادیده گرفته می‌شوند. بعد از موفقیت وضعیت فوراً بسته می‌شود تا دوبار-کلیک callback را دوبار اجرا نکند.
* اگر کاربر بین کلیک و تأیید عوض شود، عملیات لغو می‌شود.
* callback داخل `user_context(<کاربر تأییدشده>)` اجرا می‌شود (پس توابع `@superadmin` داخل آن درست کار می‌کنند).
* رویدادهای لاگ (دسته امنیتی): `reauth_failed`, `reauth_blocked_locked`, `account_locked` (با `source: reauth`) و `sensitive_action_confirmed` (با `action` = نام تابع). **رمز هرگز ثبت نمی‌شود.**
* رمز از websocket عبور می‌کند؛ برنامه را روی **HTTPS** اجرا کنید.

### 7.6 نکات و اشتباهات

| نکته | توضیح |
|------|-------|
| نام تابع یکتا | شناسه‌ی ورودی‌های پنجره از نام تابع ساخته می‌شود (`reauth_<name>_continue/_cancel/_submit/_password`). دو callback با یک نام در یک ماژول تداخل می‌کنند. |
| فقط داخل `server` | دکوریتور هنگام تزئین `effect` می‌سازد؛ پس داخل تابع server ماژول (برای هر نشست) استفاده شود، نه در سطح ماژول. |
| callback آرگومان ندارد | مثل هر handler واکنشی. داده‌های لازم را از `input` بخوانید. |
| نقش را هم بدهید | `required_role` فقط UX و جلوگیری از پرسیدن بی‌جای رمز است؛ **توابع داخل callback باید دکوریتور خودشان را داشته باشند** (دفاع در عمق؛ `tab_07` همین کار را می‌کند). |
| تست | `trigger.flow` منطق (`_Flow`) را در اختیار می‌گذارد. `show_modal`, `remove_modal`, `notify`, `now` را با Fake جایگزین کنید (نمونه: `tests/test_confirm.py`). |

---

<a id="s8"></a>

## 8. لاگ ممیزی (Audit Log)

فایل‌ها: `auth/audit.py` (ذخیره‌سازی)، توابع `@superadmin` در `auth/core.py` (خواندن/تنظیم/پاک‌کردن)، `tabs/tab_logs.py` (نمایش).
مستند کوتاه‌تر: `docs/audit-log.md`.

### 8.1 اصول طراحی

* فایل جدا: `db/audit.db` (حالت WAL) تا نوشتن‌های پرتعداد لاگ با دیتابیس کاربران قفل نشود.
* یک جدول `audit_log` با ستون `category`، به‌علاوه جدول `audit_settings`.
* ثبت لاگ **هرگز** برنامه را خراب نمی‌کند (`log_event` همه‌ی خطاها را می‌خورد).
* **هرگز** رمز یا پاسخ CAPTCHA ثبت نمی‌شود.
* ورودی‌ها پاکسازی می‌شوند: کاراکترهای کنترلی (جلوگیری از log injection) حذف، طول‌ها محدود (نام کاربری 64، مقدارها 200، User-Agent 200، کل `detail` حداکثر 2000؛ بیشتر از آن جایگزین `{"truncated": true}`).

### 8.2 جدول `audit_log`

| ستون | توضیح |
|------|-------|
| `id` | شماره‌ی افزایشی |
| `ts` | زمان UTC (`YYYY-MM-DD HH:MM:SS`) |
| `category` | `auth` / `navigation` / `security` |
| `event` | نام رویداد |
| `severity` | `info` / `warning` / `critical` |
| `user_id`, `username`, `role` | عامل (برای بازدید‌کننده‌ی ناشناس `user_id`/`role` خالی و `username` همان نام تایپ‌شده) |
| `session_id`, `ip`, `user_agent` | اطلاعات نشست |
| `detail` | JSON با جزئیات (مثلاً مقدار قبل/بعد) |

### 8.3 همه‌ی رویدادها

**`auth`**

| رویداد | شدت | کی؟ | detail |
|--------|-----|-----|--------|
| `login_success` | info | ورود موفق | — |
| `login_failed` | warning | رمز یا CAPTCHA غلط | `reason`: `bad_credentials` / `captcha` |
| `logout` | info | خروج با دکمه | `duration_s` |
| `password_changed` | info | تغییر رمز توسط خود کاربر | — |
| `password_change_failed` | warning | رمز فعلی اشتباه | `reason` |

**`navigation`**

| رویداد | شدت | کی؟ | detail |
|--------|-----|-----|--------|
| `tab_opened` | info | تعویض تب (تکرار پشت‌سرهم یک تب ثبت نمی‌شود) | `tab` |
| `session_ended` | info | بسته شدن مرورگر در حالت وارد‌شده | `duration_s` |

**`security`**

| رویداد | شدت | کی؟ | detail |
|--------|-----|-----|--------|
| `access_denied` | warning | هر رد شدن یکی از دکوریتورهای RBAC | `function`, `required_role` |
| `unauthorized_tab_request` | warning | درخواست تبی که نقش اجازه نمی‌دهد | `tab`, `required_role` |
| `unknown_tab_request` | warning | شناسه‌ی تب جعلی | `tab` |
| `account_locked` | critical | همان شکستی که قفل را فعال کرد (فقط یک‌بار) | `lock_seconds` (و `source: reauth` اگر از پنجره‌ی رمز بود) |
| `login_blocked_locked` | warning | تلاش ورود در حین قفل | `remaining_s` |
| `session_revoked` | warning | حساب حذف/غیرفعال/منقضی شد | `reason`: `account_deleted` / `account_disabled` / `account_expired` |
| `user_created` | info (critical برای superadmin) | ساخت کاربر | `target`, `role`, `expire_date` |
| `user_updated` | info (warning اگر رمز ریست شد) | ویرایش | `target`, `changes` |
| `role_changed` | warning (critical اگر superadmin درگیر باشد) | تغییر نقش | `changes` با `[قبل, بعد]` |
| `user_deleted` | warning (critical برای superadmin) | حذف | `target`, `role` |
| `audit_settings_changed` | warning | تغییر تنظیمات نگهداری | `changes` |
| `audit_cleared` | critical | پاک‌کردن لاگ | `scope` (`all`/دسته), `deleted` |
| `reauth_failed` | warning | رمز غلط در پنجره‌ی تأیید | `action` |
| `reauth_blocked_locked` | warning | تلاش تأیید در حین قفل | `action`, `remaining_s` |
| `sensitive_action_confirmed` | info | عملیات محافظت‌شده تأیید و اجرا شد | `action` |

### 8.4 سیاست superadmin

به‌طور پیش‌فرض **همه** ثبت می‌شوند، superadmin هم. اگر `AUDIT_LOG_SUPERADMIN=0` بگذارید، کارهای عادی خود superadmin ثبت نمی‌شود،
ولی رویدادهای `ALWAYS_LOG_EVENTS` (مدیریت حساب‌ها، تنظیمات/پاک‌کردن لاگ، رویدادهای تأیید با رمز) و هر حمله‌ی ناشناس به حساب `superadmin`
(شکست ورود، قفل) باز هم ثبت می‌شود.

### 8.5 API ماژول `auth/audit.py`

| تابع / ثابت | توضیح |
|-------------|-------|
| `log_event(category, event, *, user=None, username=None, severity="info", detail=None, session_id=None, ip=None, user_agent=None)` | ثبت یک رویداد. هرگز استثنا نمی‌اندازد. `user` عامل وارد‌شده است؛ برای ناشناس `username` بدهید. اگر `session_id/ip/user_agent` ندهید از کلیدهای `sid/ip/ua` داخل دیکشنری `user` برداشته می‌شود. |
| `query_events(category=None, severity=None, username=None, limit=200)` | جدیدترین‌ها اول. `username` جستجوی «شامل» است (wildcardهای `%` و `_` escape می‌شوند). `limit` بین 1 و 5000. **بدون بررسی دسترسی** است؛ در برنامه از `list_audit_events` استفاده کنید. |
| `session_meta(session)` | `{"sid","ip","ua"}` یک نشست Shiny (بدون استثنا) |
| `client_ip(http_conn)` | IP کلاینت؛ `X-Forwarded-For` فقط با `TRUST_PROXY_HEADERS=1` |
| `get_settings()` / `save_settings(values)` / `validate_settings(values)` | تنظیمات نگهداری. `save_settings` مقدارهای تغییرکرده را به‌شکل `{کلید: [قبل, بعد]}` برمی‌گرداند. |
| `counts()` | تعداد ردیف هر دسته |
| `clear(category=None)` | حذف یک دسته یا همه؛ تعداد حذف‌شده را برمی‌گرداند. **بدون بررسی دسترسی** (از `clear_audit_logs` استفاده کنید). |
| `purge_old(now=None)` | حذف ردیف‌های قدیمی‌تر از مدت نگهداری هر دسته |
| `CATEGORIES`, `SEVERITIES` | مقدارهای مجاز |
| `ALWAYS_LOG_EVENTS` | رویدادهایی که حتی در حالت خاموش‌بودن لاگ superadmin ثبت می‌شوند |
| `DEFAULT_SETTINGS`, `SETTING_LIMITS` | مقدارهای اولیه و بازه‌ی مجاز |
| `LOG_SUPERADMIN_ACTIVITY` | از `AUDIT_LOG_SUPERADMIN` خوانده می‌شود |

توابع `@superadmin` در `core.py`:

| تابع | توضیح |
|------|-------|
| `list_audit_events(category=None, severity=None, username=None, limit=200)` | خواندن |
| `get_audit_settings()` | تنظیمات فعلی |
| `update_audit_settings(values)` | اعتبارسنجی + ذخیره (+ لاگ `audit_settings_changed`)؛ مقدار بد → `ValueError` |
| `audit_log_counts()` | تعداد ردیف‌ها |
| `clear_audit_logs(category=None)` | حذف و **بعد از آن** ثبت `audit_cleared`؛ پس حتی «پاک کردن همه» یک ردیف باقی می‌گذارد که می‌گوید چه کسی چه چیزی را پاک کرد |

### 8.6 تنظیمات نگهداری (تب Logs ← Settings)

| تنظیم | پیش‌فرض | بازه |
|-------|---------|------|
| `retention_days_navigation` | 30 روز | 1–3650 |
| `retention_days_auth` | 180 روز | 1–3650 |
| `retention_days_security` | 365 روز | 1–3650 |
| `purge_interval_hours` | 1 ساعت | 1–168 |

پاکسازی خودکار **با شروع هر نشست جدید مرورگر** بررسی می‌شود و حداکثر هر `purge_interval_hours` ساعت یک‌بار اجرا می‌شود.
اگر هیچ‌کس سایت را باز نکند اجرا نمی‌شود؛ برای زمان‌بندی دقیق از cron/job جدا استفاده کنید.

### 8.7 تب Logs

* **Events:** سه زیرتب (احراز هویت، ناوبری، امنیتی)، فیلتر شدت/نام کاربری/تعداد ردیف، دکمه‌ی Refresh و لینک دانلود CSV (متن CSV سمت سرور از همان تابع `@superadmin` ساخته می‌شود؛ BOM برای اکسل؛ سلول‌هایی که با `= + - @` شروع شوند خنثی می‌شوند).
* **Settings:** فرم تنظیمات + چهار دکمه‌ی پاکسازی (ناوبری، احراز هویت، امنیتی، همه) که هر کدام ابتدا نوار تأیید نشان می‌دهند. شمارنده‌ی ردیف‌ها بالای دکمه‌ها است.
* مقدارهای جدول به‌صورت متن ساده رندر می‌شوند (escape خودکار)؛ نام کاربری جعلی نمی‌تواند HTML تزریق کند.

### 8.8 افزودن رویداد جدید

```python
from auth import audit, current_user

def export_report(report_id):
    ...
    audit.log_event(
        "security", "report_exported",
        user=current_user(), severity="info",
        detail={"report_id": report_id},
    )
```

اگر می‌خواهید حتی با `AUDIT_LOG_SUPERADMIN=0` هم ثبت شود، نام رویداد را به `ALWAYS_LOG_EVENTS` اضافه کنید.
رویداد را در جدول `docs/audit-log.md` هم مستند کنید.

> **محدودیت:** برنامه تابعی برای ویرایش/حذف دستی ردیف‌ها ندارد، ولی هر کس به فایل `db/audit.db` دسترسی نوشتن داشته باشد می‌تواند آن را عوض کند. اگر ضمانت تغییرناپذیری لازم است لاگ را به محل خارجی بفرستید.

---

<a id="s9"></a>

## 9. دو‌زبانه بودن (`i18n.py`)

### 9.1 سوئیچ زبان

```python
APP_LANG = "en"   # یا "fa"
```

یا متغیر محیطی `APP_LANG` (اولویت دارد). این **یک** تنظیم همه‌چیز را عوض می‌کند: متن‌ها، جهت صفحه (`dir`)، Bootstrap RTL، `<html lang>`، فهرست فونت‌ها و پیام‌های خطای `core.py`.
زبان هنگام شروع سرور انتخاب می‌شود؛ بعد از تغییر ری‌استارت کنید. مقدار نامعتبر به `en` برمی‌گردد.

### 9.2 اجزای ماژول

| نام | توضیح |
|-----|-------|
| `STRINGS` | دیکشنری `{"en": {...}, "fa": {...}}`؛ **کلیدهای دو زبان باید یکسان باشند** (تست `test_i18n.py` بررسی می‌کند) |
| `APP_LANG`, `RTL_LANGS` | زبان فعال، و زبان‌های راست‌به‌چپ (`fa, ar, he, ur`) |
| `IS_RTL`, `DIRECTION` | از زبان فعال محاسبه می‌شوند (`"rtl"`/`"ltr"`) |
| `t(key, **kwargs)` | متن کلید در زبان فعال. اگر کلید در زبان فعال نبود → انگلیسی؛ اگر هیچ‌جا نبود → خود کلید (تا غلط املایی دیده شود، برنامه خراب نشود). `kwargs` جای `{placeholder}` را پر می‌کنند (`str.format`). |
| `role_label(role)` | نام نمایشی نقش (مثلاً «مدیر کل») |
| `js_bundle()` | متن‌های لازم برای `custom.js` (نام تم‌ها، برچسب‌های فونت، تأیید حذف) که به‌صورت `window.APP_I18N` به مرورگر می‌رسد |

### 9.3 استفاده در کد

```python
from i18n import t, role_label

ui.h3(t("account_title"))
t("login_locked", remaining=30)       # placeholder
role_label("superadmin")
```

### 9.4 افزودن متن جدید

۱. کلید را در **هر دو** بلوک `"en"` و `"fa"` اضافه کنید.
۲. با `t("my_key")` استفاده کنید.
۳. `pytest tests/test_i18n.py` را اجرا کنید.

### 9.5 افزودن زبان جدید

بلوک `"en"` را کپی کنید، کلید را عوض کنید (مثلاً `"ar"`)، مقدارها را ترجمه کنید و اگر راست‌به‌چپ است کد را به `RTL_LANGS` اضافه کنید.

### 9.6 متن‌های دو‌زبانه خارج از `i18n.py`

* `confirm_with_password`: `message`/`title` می‌توانند `{"en":..., "fa":...}` باشند.
* تب‌هایی که متن‌های خودشان را دارند (`tab_07`, `tab_logs`): دیکشنری `_TEXTS` داخل خود فایل و تابع `_tx(key)` (با پشتیبانی `APP_LANG`). این کار بدون دست‌زدن به `i18n.py` متن‌های تب را دو‌زبانه می‌کند.
* تب‌های نمونه `tab_01`–`tab_06` عمداً ترجمه نشده‌اند (قرار است جایگزین شوند).

---

<a id="s10"></a>

## 10. ساخت تب جدید

### 10.1 قرارداد یک تب (Tab contract)

هر فایل در `tabs/` باید این‌ها را داشته باشد؛ `app.py` فقط همین‌ها را می‌خواند:

| نام | الزامی | توضیح |
|-----|:------:|-------|
| `NAV_ID` | ✅ | شناسه‌ی یکتا، مثلاً `"tab_08"` (در `data-nav-id` سایدبار و `TAB_LOOKUP` استفاده می‌شود) |
| `NAV_LABEL` | ✅ | متن سایدبار؛ رشته یا `t("key")` برای دو‌زبانه |
| `NAV_ICON` | ✅ | کلاس Bootstrap Icons (مثل `"bi-table"`) برای آیتم‌های بدون گروه؛ برای زیرمجموعه‌ی گروه `None` |
| `NAV_GROUP` | ✅ | `None` (آیتم مستقل) یا کلید یک گروه در `GROUPS` (مثل `"dashboard"`) |
| `NAV_MIN_ROLE` | ✅ | حداقل نقش برای **دیدن** تب: `guest/user/admin/superadmin` |
| `panel()` | ✅ | تابعی که UI تب را برمی‌گرداند؛ هر بار نمایش تب فراخوانی می‌شود |
| `server(...)` | اگر منطق دارد | یک‌بار در `server()` برنامه ثبت می‌شود |
| `MODULE_ID` | قرارداد | همان `NAV_ID` (برای ماژول Shiny) |

### 10.2 ماژول Shiny در یک نگاه

تب‌ها با `@module.ui` و `@module.server` ساخته می‌شوند تا شناسه‌ها با پیشوند تب ساخته شوند
(`"count"` در تب `tab_08` می‌شود `tab_08-count`) و دو تب بتوانند هر دو ورودی‌ای به نام `count` داشته باشند.
جزئیات: `tabs/MODULES.md`.

قالب کامل:

```python
from shiny import module, reactive, render, ui

NAV_ID = "tab_08"
NAV_LABEL = "My Tab"
NAV_ICON = "bi-star"
NAV_GROUP = None
NAV_MIN_ROLE = "user"

MODULE_ID = "tab_08"           # = NAV_ID


@module.ui
def _ui():
    return ui.div(
        ui.h3("My Tab"),
        ui.input_action_button("go", "Go"),     # id کوتاه؛ پیشوند خودکار اضافه می‌شود
        ui.output_text("answer"),
        class_="tab-pane-content",
    )


@module.server
def _server(input, output, session):
    clicks = reactive.Value(0)

    @reactive.effect
    @reactive.event(input.go)
    def _on_go():
        clicks.set(clicks() + 1)

    @render.text
    def answer():
        return f"Clicked {clicks()} times"


def panel():
    return _ui(MODULE_ID)


def server():
    _server(MODULE_ID)
```

### 10.3 مراحل گام‌به‌گام

۱. فایل `tabs/tab_08.py` را بسازید (از قالب بالا یا یکی از `tabs/examples/ex01..ex15`).

۲. در `app.py` import کنید:

```python
from tabs import tab_01, ..., tab_07, tab_08, tab_account, tab_users, tab_logs
```

۳. به `TABS` اضافه کنید. **ترتیب لیست = ترتیب سایدبار.** `tab_logs` عمداً آخر است:

```python
TABS = [tab_01, ..., tab_07, tab_08, tab_account, tab_users, tab_logs]
```

۴. سمت سرور را **یک‌بار** در `server()` ثبت کنید:

```python
tab_08.server()
```

قواعد: فقط یک‌بار و مستقیماً داخل `server()`؛ هرگز داخل `active_panel`، handler ورود یا `reactive.effect` (در غیر این صورت با هر کلیک دوباره ثبت می‌شود).
اگر تب باید بداند چه کسی وارد شده، **بعد از تعریف `_ensure_valid_session`** ثبت کنید و آن را پاس بدهید (مثل `tab_07`/`tab_logs`):

```python
tab_08.server(_ensure_valid_session)     # و در تب:  def server(get_session_user): ...
```

۵. (فقط برای گروه جدید) یک خط به `GROUPS` اضافه کنید و `NAV_GROUP` تب‌ها را برابر همان کلید بگذارید:

```python
GROUPS = {
    "dashboard": {"label": t("nav_dashboard"), "icon": "bi-speedometer2"},
    "reports":   {"label": "Reports", "icon": "bi-file-earmark-text"},   # گروه جدید
}
```

۶. (اختیاری) تب پیش‌فرض بعد از ورود `DEFAULT_TAB_ID = "tab_04"` است؛ باید برای **همه‌ی نقش‌ها** قابل دیدن (`guest`) باشد.

۷. تست‌ها: نام ماژول را به فهرست `TAB_MODULES` در `tests/test_tabs.py` و `tests/test_sidebar.py` اضافه کنید.

۸. (اختیاری) دو‌زبانه کردن: `NAV_LABEL = t("nav_my_tab")` و کلید را در هر دو زبان `i18n.py` بگذارید؛ یا دیکشنری `_TEXTS` محلی (مثل `tab_07`).

### 10.4 حذف یا مخفی کردن تب

* مخفی کردن موقت: `NAV_MIN_ROLE = "superadmin"` یا خط‌اش را از `TABS` بردارید.
* حذف کامل: از `TABS` و import و `server()` برش دارید، فایل و تست را پاک کنید.

### 10.5 مثال‌های کامل

**الف) تب محافظت‌شده با دکوریتور (دکمه‌ی فقط‌ادمین)**

```python
from shiny import module, reactive, ui
from auth import admin, user_context

NAV_ID = "tab_08"; NAV_LABEL = "Reports"; NAV_ICON = "bi-file-earmark-text"
NAV_GROUP = None; NAV_MIN_ROLE = "guest"        # همه ببینند؛ سرور تصمیم می‌گیرد
MODULE_ID = "tab_08"


@admin
def _build_report():
    return "Report ready"


@module.ui
def _ui():
    return ui.div(ui.input_action_button("make", "Build report"), class_="tab-pane-content")


@module.server
def _server(input, output, session, get_session_user):
    @reactive.effect
    @reactive.event(input.make)
    def _on_make():
        person = get_session_user()
        if person is None:
            ui.notification_show("Please sign in again.", type="error"); return
        try:
            with user_context(person):
                message = _build_report()
            ui.notification_show(message, type="message")
        except PermissionError:
            ui.notification_show("You do not have access to this section.", type="error")


def panel():  return _ui(MODULE_ID)
def server(get_session_user):  _server(MODULE_ID, get_session_user=get_session_user)
```

در `app.py`: `tab_08.server(_ensure_valid_session)` (بعد از تعریف `_ensure_valid_session`).

**ب) دکمه‌ی خطرناک با تأیید و رمز**

```python
from auth import admin, confirm_with_password, user_context

@admin
def _wipe():
    ...
    return "Done"

@module.server
def _server(input, output, session, get_session_user):

    @reactive.effect
    @reactive.event(input.wipe)
    @confirm_with_password(
        input, get_session_user,
        message={"en": "This deletes everything. Continue?", "fa": "همه‌چیز حذف می‌شود. ادامه می‌دهید؟"},
        required_role="admin",
    )
    def _on_wipe():
        try:
            ui.notification_show(_wipe(), type="message")     # داخل user_context اجرا می‌شود
        except PermissionError:
            ui.notification_show("Denied", type="error")
```

**ج) نوشتن رویداد در لاگ از داخل تب**

```python
from auth import audit, current_user
audit.log_event("security", "wipe_done", user=current_user(), severity="warning")
```

### 10.6 اشتباهات رایج هنگام ساخت تب

| اشتباه | نشانه | درمان |
|--------|-------|-------|
| `NAV_ID` تکراری | تب اشتباه نمایش داده می‌شود | یکتا |
| `server()` را فراموش کردید | دکمه‌ها کار نمی‌کنند | در `app.py` صدا بزنید |
| `server()` دوبار ثبت شد | handlerها دوبار اجرا می‌شوند | فقط یک‌بار در `server()` |
| `server(get_session_user)` را قبل از `_ensure_valid_session` ثبت کردید | `NameError` | بعد از تعریف آن |
| `NAV_MIN_ROLE` بالا و `DEFAULT_TAB_ID` همان تب | کاربر کم‌دسترسی تب پیش‌فرض ندارد | تب پیش‌فرض `guest` باشد |
| id ورودی با پیشوند نوشته شد | `input.tab_08-x` پیدا نمی‌شود | داخل ماژول فقط id کوتاه |
| فقط `NAV_MIN_ROLE` گذاشتید | callback برای ورودی جعلی باز است | دکوریتور روی تابع کار |

---

<a id="s11"></a>

## 11. تب‌های موجود یکی‌یکی

| تب | `NAV_ID` | گروه | حداقل نقش (دیدن) | محتوا |
|----|----------|------|------------------|-------|
| Normal | `tab_01` | dashboard | superadmin | نمونه‌گیری از توزیع نرمال + هیستوگرام (`numpy`, `matplotlib`). توضیح کامل ماژول‌ها در docstring همین فایل. |
| Poisson | `tab_02` | dashboard | admin | توزیع پواسون |
| Binomial | `tab_03` | dashboard | user | توزیع دوجمله‌ای |
| Negative Binomial | `tab_04` | — | guest | توزیع دوجمله‌ای منفی (تب پیش‌فرض `DEFAULT_TAB_ID`) |
| Widgets | `tab_05` | — | guest | جای‌گزین (Placeholder) برای ویجت‌ها |
| Tables | `tab_06` | — | guest | جای‌گزین برای جدول‌ها |
| Access Buttons | `tab_07` | — | guest | هشت دکمه (جزئیات پایین) |
| حساب من | `tab_account` | — | guest | تغییر رمز خود کاربر |
| مدیریت کاربران | `tab_users` | — | superadmin | ساخت/ویرایش/حذف کاربر |
| Logs | `tab_logs` | — | superadmin | لاگ ممیزی (آخرین تب) |

### 11.1 `tab_07` — دکمه‌های وابسته به نقش

برای آزمایش و نمونه‌ی الگوها ساخته شده. همه‌ی هشت دکمه برای همه دیده می‌شوند؛ **سرور** تصمیم می‌گیرد.

**چهار دکمه‌ی دکوریتوری:**

| دکمه | تابع | چه کسی موفق می‌شود |
|------|------|--------------------|
| Superadmin button | `_superadmin_action` با `@superadmin` | فقط superadmin |
| Admin button | `_admin_action` با `@admin` | admin و superadmin |
| User button | `_user_action` با `@user` | user و بالاتر |
| Guest button | `_guest_action` با `@guest` | همه‌ی وارد‌شده‌ها |

اگر نقش کافی نباشد: توست «دسترسی به این بخش برای شما مقدور نیست.»؛ اگر نشست نامعتبر باشد: «نشست شما دیگر معتبر نیست».

**چهار دکمه‌ی امن (Secure ... button):** همان چهار نقش، ولی هر کدام ابتدا پیام تأیید و بعد رمز حساب را می‌خواهد (`@confirm_with_password`). مهلت تأیید دکمه‌ی مهمان عمداً 30 ثانیه است تا پیام انقضا قابل آزمایش باشد. هر callback بعد از رمز درست، تابع دارای دکوریتور نقش را اجرا می‌کند (`_secure_*_action`).

تابع `_attempt(action, get_session_user)` هسته‌ی الگوست: کاربر را می‌گیرد، داخل `user_context` عمل را اجرا می‌کند و برای `PermissionError`/نشست نامعتبر توست مناسب می‌دهد.

### 11.2 `tab_account` — حساب من

فرم تغییر رمز (رمز فعلی + رمز جدید + تکرار). handler در `app.py` (`_change_password_event`) است و `change_own_password` (با `@guest`) را صدا می‌زند. رمز جدید باید `strict` باشد (حرف + عدد، حداقل 8). برای همه‌ی نقش‌ها (حتی guest) در دسترس است.

### 11.3 `tab_users` — مدیریت کاربران

فقط superadmin (دو لایه). صفحه شامل فرم ساخت کاربر (نام، رمز، تکرار، نقش، تاریخ انقضای اختیاری) و جدول کاربران با دکمه‌های ویرایش/حذف است.

* دکمه‌های جدول با `custom.js` به `input.user_action_edit` / `input.user_action_delete` (شناسه‌ی کاربر) وصل می‌شوند.
* ویرایش در یک modal (`_build_edit_modal`) انجام می‌شود: نام، نقش، فعال/غیرفعال، رمز جدید (اختیاری)، انقضا. ذخیره → `update_user`.
* حذف با پرسش تأیید مرورگر و بعد `delete_user`.
* همه‌ی handlerها ابتدا `_ensure_valid_session()` را می‌گیرند و بعد توابع `@superadmin` را داخل `user_context` صدا می‌زنند؛ پیام خطا به زبان فعال نمایش داده می‌شود.
* قوانین: آخرین superadmin فعال تنزل/غیرفعال/حذف نمی‌شود؛ کاربر خودش را حذف نمی‌کند.

### 11.4 `tab_logs` — لاگ‌ها

شرح کامل در [بخش ۸](#s8). ساختار فایل: `_events_panel()` و `_settings_panel()` (UI)، `_server` (منطق)، توابع کمکی خالص برای تست (`_detail_text`, `_csv_safe`, `_rows_to_csv`, `_csv_href`, `_limit_value`) و متن‌های دو‌زبانه در `_TEXTS`.

### 11.5 مثال‌های آماده (`tabs/examples/`)

۱۵ ماژول کامل و قابل کپی؛ برنامه آن‌ها را پیش‌فرض بارگذاری **نمی‌کند**.

| # | فایل | نشان می‌دهد |
|---|------|-------------|
| 01 | `ex01_layout.py` | تب حداقلی، grid بوت‌استرپ، تب‌های داخلی، accordion |
| 02 | `ex02_text_io.py` | ورودی متن → `render.text` |
| 03 | `ex03_counter.py` | دکمه، `reactive.Value`، `reactive.event` |
| 04 | `ex04_reactive_calc.py` | `reactive.calc` مشترک بین دو خروجی |
| 05 | `ex05_plot.py` | نمودار matplotlib |
| 06 | `ex06_html_table.py` | فیلتر و مرتب‌سازی جدول بدون pandas |
| 07 | `ex07_dynamic_ui.py` | `render.ui` پویا |
| 08 | `ex08_update_inputs.py` | لیست‌های وابسته |
| 09 | `ex09_upload_csv.py` | آپلود CSV |
| 10 | `ex10_download_csv.py` | دانلود CSV (از `render.download` استفاده می‌کند که در Shiny جدید هشدار deprecated می‌دهد؛ برای الگوی بدون هشدار `tab_logs` را ببینید) |
| 11 | `ex11_notify_modal.py` | توست و modal تأیید |
| 12 | `ex12_auto_refresh.py` | `invalidate_later` |
| 13 | `ex13_nested_modules.py` | ماژول تو در تو |
| 14 | `ex14_role_aware.py` | پاس دادن کاربر به ماژول و `@admin` داخل آن |
| 15 | `ex15_bilingual.py` | تب دو‌زبانه |

---

<a id="s12"></a>

## 12. ظاهر: تم، فونت، CSS، جاوااسکریپت، CAPTCHA

### 12.1 تم‌ها

۱۲ تم: ۶ روشن (Ocean Blue، Fresh Green، Soft Purple، Warm Orange، Calm Teal، Elegant Rose) و ۶ تیره (Midnight Slate، Deep Ocean، Emerald Night، Royal Night، Amber Night، Rose Night).
انتخاب در `localStorage` ذخیره می‌شود. `custom.js` دو ویژگی روی `<html>` می‌گذارد: `data-theme` و `data-bs-theme` (`light`/`dark`).

### 12.2 چرا ویجت‌ها از تم پیروی می‌کنند؟

بخش **THEME BRIDGE** انتهای `static/css/styles.css` کلاس‌های ویجت Shiny/Bootstrap را به متغیرهای تم (`--surface`, `--text`, `--border`, `--accent`, ...) وصل می‌کند.
اگر ویجتی در یک تم بد دیده شد: کلاسش را در مرورگر ببینید و **یک** قانون با متغیرهای تم (نه رنگ ثابت) به THEME BRIDGE اضافه کنید.
تست `test_theme_coverage.py` بررسی می‌کند همه‌ی ۱۲ تم متغیرهای لازم را دارند.

### 12.3 فونت‌ها

* LTR: Inter، Roboto، IBM Plex Sans، Source Sans 3، System UI (`static/fonts/ltr/`)
* RTL: Vazirmatn، Shabnam، Samim، Sahel، BYekan، System UI (`static/fonts/rtl/`)
* انتخاب‌ها در `localStorage` می‌مانند. تعریف `@font-face` در `static/css/fonts.css`.

### 12.4 `static/js/custom.js`

| تابع | کار |
|------|-----|
| `i18n(key, fallback)` | خواندن متن از `window.APP_I18N` |
| `themeLabel`, `applyTheme(name)`, `buildThemePicker()` | انتخاب و اعمال تم |
| `setSidebarCollapsed`, `setupSidebarToggle()` | باز/بسته کردن سایدبار (در موبایل روی محتوا می‌لغزد) |
| `submitLoginForm`, `bindLoginEnterKey`, `bindLoginButtonFlush` | ارسال فرم ورود (`login_username/password/captcha/login_submit`) و کلید Enter |
| `currentFontList`, `defaultFonts`, `loadFontSettings`, `saveFontSettings`, `applyFonts`, `fillSelect`, `buildFontPicker` | انتخاب فونت |
| `init()` | اتصال همه چیز؛ کلیک سایدبار → `Shiny.setInputValue("sidebar_nav", navId)`؛ دکمه‌ی CAPTCHA → `captcha_refresh`؛ دکمه‌های جدول کاربران → `user_action_edit/delete` |

### 12.5 CAPTCHA (`auth/captcha.py`)

* `generate_captcha()` → `(data URL تصویر PNG, هش پاسخ, زمان انقضا)`. متن: 5 کاراکتر از الفبای بدون حروف مبهم (`ABCDEFGHJKLMNPQRSTUVWXYZ23456789`).
* `verify_captcha(answer, expected_hash, expires_at)` → `bool`. پاسخ `strip` و بزرگ‌حرف می‌شود، با HMAC (کلید تصادفی هر اجرا) مقایسه می‌شود و مهلت (300 ثانیه) هم بررسی می‌شود.
* کاملاً آفلاین است (Pillow + فونت DejaVu داخل پروژه).
* اندازه‌ی تصویر `CAPTCHA_WIDTH × CAPTCHA_HEIGHT` (230×76) باید با `.login-captcha-image` در `styles.css` هم‌خوان بماند.

---

<a id="s13"></a>

## 13. تست‌ها

```bash
pip install -r requirements-dev.txt
pytest                      # همه
pytest tests/test_audit.py  # یک فایل
pytest -k confirm           # با نام
```

همه‌ی تست‌هایی که دیتابیس را تغییر می‌دهند از دیتابیس موقت استفاده می‌کنند؛ `db/auth.db` و `db/audit.db` واقعی هرگز دست نمی‌خورند.

### 13.1 فیکسچرها (`tests/conftest.py`)

| فیکسچر | کار |
|--------|-----|
| `isolated_audit_db` (autouse) | مسیر `audit.db` را برای هر تست به فایل موقت می‌برد |
| `isolated_db` | دیتابیس موقت کاربران با چهار کاربر پیش‌فرض |
| `superadmin_ctx`, `admin_ctx`, `user_ctx`, `guest_ctx` | داخل `user_context` آن نقش (تا پایان تست) |
| `anonymous_ctx` | `user_context(None)` (بدون نشست) |

### 13.2 فایل‌ها

| فایل | چه چیزی را می‌سنجد |
|------|---------------------|
| `test_password.py` | هش/تأیید PBKDF2، تغییر رمز |
| `test_validation.py` | قوانین نام کاربری/رمز، انقضا |
| `test_authenticate.py` | ورود، کاربر غیرفعال/منقضی، کاربران پیش‌فرض |
| `test_lockout.py` | قفل ورود |
| `test_rbac.py` | سلسله‌مراتب، `has_role`, `require_role` |
| `test_users_crud.py` | ساخت/لیست/ویرایش/حذف و محافظ آخرین superadmin |
| `test_session.py` | `get_user_by_id`, `refresh_session_user` |
| `test_captcha.py` | CAPTCHA |
| `test_tabs.py`, `test_sidebar.py` | قرارداد متادیتای تب‌ها و فیلتر سایدبار |
| `test_tab_07.py` | ماتریس دکوریتورها و fail-closed |
| `test_audit.py` | لاگ: سیاست superadmin، hookهای core، پاکسازی ورودی، نگهداری، تنظیمات، پاک‌کردن، یک‌بار-`@guest` |
| `test_confirm.py` | `@confirm_with_password`: جریان، رمز غلط، قفل، انقضا، لاگ |
| `test_i18n.py` | برابری کلیدهای دو زبان، placeholderها، `APP_LANG` |
| `test_assets.py`, `test_theme_coverage.py` | فایل‌های static، تم‌ها |
| `test_examples.py` | هر مثال از قرارداد تب پیروی می‌کند |
| `test_auth_package.py` | صادرات پکیج `auth` |

### 13.3 نوشتن تست برای کد خودتان

```python
import pytest, auth.core as core

def test_export_needs_admin(user_ctx):              # کاربر «user» داخل context
    with pytest.raises(PermissionError):
        export_report(1)

def test_export_ok_for_admin(admin_ctx):
    assert export_report(1)

def test_denial_is_logged(user_ctx):
    from auth import audit
    with pytest.raises(PermissionError):
        export_report(1)
    assert audit.query_events(category="security")[0]["event"] == "access_denied"
```

برای تست `@confirm_with_password` الگوی `Harness` در `tests/test_confirm.py` را ببینید (hookهای Shiny با Fake جایگزین می‌شوند، نیازی به مرورگر نیست).

---

<a id="s14"></a>

## 14. امنیت: چه چیزی تضمین می‌شود و چه چیزی نه

### 14.1 آنچه پیاده‌سازی شده

* رمزها: PBKDF2-HMAC-SHA256، 600000 تکرار، salt تصادفی، مقایسه‌ی زمان-ثابت، هش ساختگی برای کاربر ناموجود.
* ورود: CAPTCHA آفلاین، قفل بعد از 5 شکست در 5 دقیقه، پیام یکسان برای نام/رمز غلط.
* نشست: در هر استفاده‌ی حساس دوباره از SQLite خوانده می‌شود (حذف/غیرفعال/منقضی/تنزل فوراً اثر می‌کند).
* RBAC سمت سرور با دکوریتور (fail-closed) + مخفی‌سازی UI.
* تأیید با رمز برای عملیات حساس (با قفل مشترک).
* لاگ ممیزی (ورود، دسترسی غیرمجاز، تغییر نقش، قفل، لغو نشست، پاک‌کردن لاگ).
* escape خودکار خروجی HTML و خنثی‌سازی CSV injection در لاگ؛ پاکسازی ورودی لاگ (log injection).
* دیتابیس هرگز همراه پروژه منتشر نمی‌شود (`.gitignore`، `bootstrap.py`).

### 14.2 محدودیت‌های شناخته‌شده

| محدودیت | توضیح / راه‌حل |
|---------|-----------------|
| `tab_01`–`tab_03` فقط پنهان هستند | callbackهایشان دکوریتور ندارد (بخش ۶.۴) |
| شمارنده‌ی قفل ورود در حافظه است | با چند worker/ری‌استارت صفر می‌شود؛ برای تولید بزرگ از ذخیره‌ی مشترک استفاده کنید |
| لاگ تغییرناپذیر نیست | هر کس به فایل `audit.db` دسترسی نوشتن داشته باشد می‌تواند آن را تغییر دهد؛ لاگ را به محل خارجی بفرستید |
| پاکسازی خودکار لاگ وابسته به شروع نشست است | برای زمان‌بندی دقیق، job جدا (cron) |
| رمزهای پیش‌فرض شناخته‌شده‌اند | بلافاصله عوض کنید |
| ترافیک رمز | از HTTPS استفاده کنید |
| IP پشت پروکسی | فقط با `TRUST_PROXY_HEADERS=1` و پروکسی مطمئن |
| نام کاربری ناموفق در لاگ ذخیره می‌شود | ممکن است کاربر رمز را در این فیلد بزند؛ دسترسی به لاگ فقط superadmin است |
| امنیت سطح زیرساخت | rate limit مشترک، هدرهای امنیتی، WAF و ... خارج از این پروژه است |

### 14.3 چک‌لیست قبل از انتشار

- [ ] رمز چهار کاربر پیش‌فرض عوض شد (یا کاربران ساخته و پیش‌فرض‌ها غیرفعال شدند)
- [ ] HTTPS فعال است
- [ ] `db/` روی volume پایدار و بکاپ‌گیری‌شده است
- [ ] `APP_LANG` و `PORT` تنظیم شد
- [ ] تنظیمات نگهداری لاگ در تب Logs بازبینی شد
- [ ] تست‌ها (`pytest`) سبز هستند
- [ ] برای عملیات حساس جدید: دکوریتور نقش روی تابع کار + (در صورت نیاز) `@confirm_with_password`

---

<a id="s15"></a>

## 15. عیب‌یابی و سؤال‌های رایج

| مشکل | علت محتمل | راه‌حل |
|------|-----------|--------|
| `PermissionError` همیشه | تابع دکوریت‌شده بیرون از `user_context` صدا زده شد | `with user_context(person):` |
| تب جدید در سایدبار نیست | `TABS` یا `NAV_MIN_ROLE` | به لیست اضافه کنید؛ نقش را بررسی کنید |
| دکمه‌های تب کار نمی‌کنند | `server()` ثبت نشد | در `app.py` صدا بزنید |
| `NameError: _ensure_valid_session` | ثبت تب قبل از تعریف تابع | ثبت را بعد از تعریف بگذارید |
| متن انگلیسی در رابط فارسی | کلید فقط در `en` است | به `fa` هم اضافه کنید (`test_i18n`) |
| رابط فارسی نشد | `APP_LANG` تنظیم نشد/ری‌استارت نشد | `APP_LANG=fa shiny run app.py` |
| هشدار `render.download is deprecated` | Shiny جدید | لینک data-URI مثل `tab_logs` یا API رسمی نسخه‌ی خودتان |
| لاگ‌ها خالی‌اند | `AUDIT_LOG_SUPERADMIN=0` و کاربر superadmin | مقدار را حذف/`1` کنید |
| IP همیشه `127.0.0.1` یا آدرس پروکسی | پشت reverse proxy | `TRUST_PROXY_HEADERS=1` (فقط با پروکسی مطمئن) |
| قفل شدن بعد از چند بار رمز غلط در پنجره‌ی تأیید | شمارنده‌ی مشترک با ورود | ۵ دقیقه صبر کنید (یا ری‌استارت در محیط تست) |
| CAPTCHA بدون فونت | فونت سیستم پیدا نشد | فونت `auth/fonts/DejaVuSans-Bold.ttf` همراه پروژه است؛ در Docker `fonts-dejavu-core` نصب می‌شود |
| ورود با کاربر منقضی نمی‌شود | تاریخ انقضا گذشته | در «مدیریت کاربران» تاریخ را عوض کنید |

---

<a id="s16"></a>

## 16. واژه‌نامه

| واژه | معنی |
|------|------|
| **RBAC** | کنترل دسترسی بر اساس نقش |
| **Decorator (دکوریتور)** | تابعی که تابع دیگر را می‌پوشاند و قبل از اجرای آن شرط می‌گذارد |
| **`user_context`** | بلوکی که کاربر جاری را برای دکوریتورها مشخص می‌کند |
| **Fail-closed** | در شک (نبود کاربر/خطا) دسترسی **رد** می‌شود |
| **Reactive** | سیستم واکنشی Shiny: وقتی ورودی عوض شد، خروجی‌های وابسته دوباره اجرا می‌شوند |
| **Effect / Event** | `reactive.effect` کاری انجام می‌دهد؛ `reactive.event` آن را به یک ورودی خاص (مثل کلیک دکمه) محدود می‌کند |
| **Module (ماژول)** | واحد قابل‌استفاده‌ی مجدد UI+server با شناسه‌های پیشوندی |
| **Toast / Notification** | پیام کوتاه گوشه‌ی صفحه (`ui.notification_show`) |
| **Modal** | پنجره‌ی شناور (`ui.modal`) |
| **Audit log** | دفتر ثبت رویدادهای مهم برای بررسی بعدی |
| **PBKDF2** | الگوریتم هش رمز با تکرار زیاد (کند عمدی) |
| **Salt** | رشته‌ی تصادفی که با رمز ترکیب می‌شود تا دو رمز یکسان هش یکسان نداشته باشند |
| **WAL** | حالت ژورنال SQLite که خواندن و نوشتن هم‌زمان را بهتر می‌کند |
| **CSV injection** | سلولی که با `=` شروع شود و در اکسل به‌عنوان فرمول اجرا شود |
| **Session (نشست)** | اتصال یک مرورگر به سرور؛ `server()` برای هر نشست یک‌بار اجرا می‌شود |
