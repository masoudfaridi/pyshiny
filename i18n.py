"""Bilingual (English / Persian) UI strings for the fixed parts of the dashboard.

Covers: the login screen, the main shell (top bar, sidebar group, theme and
font pickers), "My Account", and "User Management". The demo tabs
(tab_01 ... tab_06) are intentionally NOT translated -- they are placeholders
that get replaced by hand.

How to switch language
----------------------
Change ONE line -- ``APP_LANG`` below -- or set the ``APP_LANG`` environment
variable (handy for Docker: ``APP_LANG=fa docker compose up --build -d``).

    APP_LANG = "en"   # English, left-to-right  (default)
    APP_LANG = "fa"   # Persian, right-to-left

Text direction, the Bootstrap stylesheet, the <html lang> attribute, the font
list and every string in ``STRINGS`` follow that single setting. There is no
longer any need to comment/uncomment ``app_ui`` blocks in ``app.py``.

How to add a language
---------------------
Copy the ``"en"`` block inside ``STRINGS``, rename the key (e.g. ``"ar"``),
translate the values, and add the code to ``RTL_LANGS`` if it is right-to-left.

Usage in Python::

    from i18n import t
    t("login_title")                    # -> "Secure Dashboard"  /  "داشبورد امن"
    t("login_locked", remaining=30)     # placeholders use str.format
"""

from __future__ import annotations

import os

# =============================================================================
# >>> THE ONLY SWITCH YOU NEED: "en" (English, LTR)  or  "fa" (Persian, RTL) <<<
# =============================================================================
APP_LANG = "en"

# The environment variable wins, so Docker / CI can choose without editing code.
APP_LANG = os.environ.get("APP_LANG", APP_LANG).strip().lower()

# Languages that are written right-to-left.
RTL_LANGS = {"fa", "ar", "he", "ur"}

STRINGS: dict[str, dict[str, str]] = {
    # ------------------------------------------------------------------ English
    "en": {
        # ---- Roles ----
        "role_guest": "Guest",
        "role_user": "User",
        "role_admin": "Admin",
        "role_superadmin": "Superadmin",

        # ---- Common ----
        "yes": "Yes",
        "no": "No",
        "never": "Never",
        "username": "Username",
        "password": "Password",
        "access_level": "Access level",
        "confirm_password": "Confirm password",
        "confirm_new_password": "Confirm new password",
        "set_expiry": "Set an expiration date",
        "expiry_date": "Expiration date",
        "superadmin_no_expiry": "Superadmin accounts do not expire.",

        # ---- Login screen ----
        "login_title": "Secure Dashboard",
        "login_subtitle": "Please sign in to continue.",
        "login_security_check": "Security check",
        "login_captcha_placeholder": "Type the characters you see",
        "login_captcha_alt": "CAPTCHA",
        "login_refresh": "Refresh",
        "login_button": "Sign in",
        "login_hint": (
            "Default accounts are documented in README.md. "
            "Change default passwords after first login."
        ),
        "login_invalid": (
            "Invalid username or password, inactive account, or expired account."
        ),
        "login_locked": "Too many failed attempts. Try again in {remaining} seconds.",
        "login_captcha_invalid": "Invalid security check. Please try again.",

        # ---- Main page: top bar ----
        "brand": "Python Shiny Dashboard",
        "logout": "Logout",
        "font_button": "Font",
        "font_aria": "Choose fonts",
        "font_menu_title": "Fonts",
        "font_body": "Body / UI",
        "font_headings": "Headings",
        "font_navigation": "Navigation",
        "font_inherit": "Inherit (Body)",
        "font_system": "System UI",
        "theme_aria": "Choose theme",
        "theme_light_title": "Light themes",
        "theme_dark_title": "Dark themes",
        "theme_light_suffix": "Light theme",
        "theme_dark_suffix": "Dark theme",

        # ---- Main page: sidebar ----
        "sidebar_toggle": "Show / hide the menu",
        "nav_dashboard": "Dashboard",
        "nav_account": "My Account",
        "nav_users": "User Management",

        # ---- Theme names (keys match static/js/custom.js) ----
        "theme_light-blue": "Ocean Blue",
        "theme_light-green": "Fresh Green",
        "theme_light-purple": "Soft Purple",
        "theme_light-orange": "Warm Orange",
        "theme_light-teal": "Calm Teal",
        "theme_light-rose": "Elegant Rose",
        "theme_dark-slate": "Midnight Slate",
        "theme_dark-ocean": "Deep Ocean",
        "theme_dark-emerald": "Emerald Night",
        "theme_dark-purple": "Royal Night",
        "theme_dark-amber": "Amber Night",
        "theme_dark-rose": "Rose Night",

        # ---- My Account page ----
        "account_title": "My Account",
        "account_intro": (
            "Change your own password. "
            "This is available to every authenticated user."
        ),
        "account_change_heading": "Change password",
        "account_current_password": "Current password",
        "account_new_password": "New password",
        "account_change_button": "Change password",
        "account_tips_heading": "Password tips",
        "account_tip_length": "Use at least 8 characters.",
        "account_tip_mix": "Mix letters, numbers, and symbols.",
        "account_tip_reuse": "Avoid reusing passwords from other sites.",
        "account_mismatch": "New password and confirmation do not match.",
        "account_changed": "Password changed successfully.",

        # ---- User Management page ----
        "users_title": "User Management",
        "users_intro": "Only Superadmin users can create, edit, and delete accounts.",
        "users_create_heading": "Create user",
        "users_create_button": "Create user",
        "users_existing_heading": "Existing users",
        "users_existing_hint": (
            "Use Change to edit an account in a popup, or Delete to remove it."
        ),
        "users_change": "Change",
        "users_delete": "Delete",
        "users_col_actions": "Actions",
        "users_col_id": "ID",
        "users_col_username": "Username",
        "users_col_role": "Role",
        "users_col_active": "Active",
        "users_col_expires": "Expires",
        "users_col_created": "Created",
        "users_create_mismatch": "Password and confirmation do not match.",
        "users_created": "User created successfully.",
        "users_updated": "User updated successfully.",
        "users_deleted": "User deleted successfully.",
        "users_not_found": "User not found.",
        "users_exists": "This username already exists.",
        "users_denied_create": "Access denied: only Superadmin can create users.",
        "users_denied_edit": "Access denied: only Superadmin can edit users.",
        "users_denied_delete": "Access denied: only Superadmin can delete users.",
        "users_confirm_delete": (
            'Delete user "{username}"? This cannot be undone.'
        ),

        # ---- User Management: edit popup ----
        "edit_title": "Edit user: {username}",
        "edit_active": "Active account",
        "edit_new_password": "New password (leave blank to keep current password)",
        "edit_save": "Save changes",
        "edit_delete": "Delete user",
        "edit_cancel": "Cancel",
        "edit_mismatch": "New password and confirmation do not match.",

        # ---- Validation / error messages raised by auth/core.py ----
        "field_password": "Password",
        "field_new_password": "New password",
        "err_username_format": (
            "Username must be 3–32 characters and contain only letters, "
            "numbers, underscores, or hyphens."
        ),
        "err_password_required": "{field} is required.",
        "err_password_min": "{field} must contain at least {n} characters.",
        "err_password_max": "{field} must contain at most {n} characters.",
        "err_password_complexity": (
            "{field} must contain at least one letter and one number."
        ),
        "err_expiry_format": "Expiration date must use YYYY-MM-DD format.",
        "err_invalid_role": "Invalid role.",
        "err_auth_required": "Authentication is required.",
        "err_current_password": "Current password is incorrect.",
        "err_user_not_found": "User not found.",
        "err_last_superadmin": "At least one active Superadmin must remain.",
        "err_delete_self": "You cannot delete the account you are currently using.",
        "err_delete_last_superadmin": "The last active Superadmin cannot be deleted.",
    },

    # ------------------------------------------------------------------ Persian
    "fa": {
        # ---- Roles ----
        "role_guest": "مهمان",
        "role_user": "کاربر",
        "role_admin": "مدیر",
        "role_superadmin": "مدیر کل",

        # ---- Common ----
        "yes": "بله",
        "no": "خیر",
        "never": "هرگز",
        "username": "نام کاربری",
        "password": "رمز عبور",
        "access_level": "سطح دسترسی",
        "confirm_password": "تکرار رمز عبور",
        "confirm_new_password": "تکرار رمز عبور جدید",
        "set_expiry": "تعیین تاریخ انقضا",
        "expiry_date": "تاریخ انقضا",
        "superadmin_no_expiry": "حساب مدیر کل منقضی نمی‌شود.",

        # ---- Login screen ----
        "login_title": "داشبورد امن",
        "login_subtitle": "برای ادامه لطفاً وارد شوید.",
        "login_security_check": "بررسی امنیتی",
        "login_captcha_placeholder": "نویسه‌های داخل تصویر را وارد کنید",
        "login_captcha_alt": "کپچا",
        "login_refresh": "تازه‌سازی",
        "login_button": "ورود",
        "login_hint": (
            "حساب‌های پیش‌فرض در فایل README.md توضیح داده شده‌اند. "
            "پس از اولین ورود، رمز عبور پیش‌فرض را تغییر دهید."
        ),
        "login_invalid": (
            "نام کاربری یا رمز عبور نادرست است، یا حساب غیرفعال یا منقضی شده است."
        ),
        "login_locked": (
            "تعداد تلاش‌های ناموفق بیش از حد مجاز است. "
            "{remaining} ثانیه دیگر دوباره تلاش کنید."
        ),
        "login_captcha_invalid": "بررسی امنیتی نادرست بود. لطفاً دوباره تلاش کنید.",

        # ---- Main page: top bar ----
        "brand": "داشبورد Python Shiny",
        "logout": "خروج",
        "font_button": "فونت",
        "font_aria": "انتخاب فونت",
        "font_menu_title": "فونت‌ها",
        "font_body": "متن / رابط کاربری",
        "font_headings": "عنوان‌ها",
        "font_navigation": "منوی ناوبری",
        "font_inherit": "همانند متن اصلی",
        "font_system": "فونت سیستم",
        "theme_aria": "انتخاب تم",
        "theme_light_title": "تم‌های روشن",
        "theme_dark_title": "تم‌های تیره",
        "theme_light_suffix": "تم روشن",
        "theme_dark_suffix": "تم تیره",

        # ---- Main page: sidebar ----
        "sidebar_toggle": "نمایش / پنهان کردن منو",
        "nav_dashboard": "داشبورد",
        "nav_account": "حساب کاربری من",
        "nav_users": "مدیریت کاربران",

        # ---- Theme names ----
        "theme_light-blue": "آبی اقیانوسی",
        "theme_light-green": "سبز شاداب",
        "theme_light-purple": "بنفش ملایم",
        "theme_light-orange": "نارنجی گرم",
        "theme_light-teal": "فیروزه‌ای آرام",
        "theme_light-rose": "صورتی ظریف",
        "theme_dark-slate": "سربی نیمه‌شب",
        "theme_dark-ocean": "اقیانوس عمیق",
        "theme_dark-emerald": "شب زمردی",
        "theme_dark-purple": "شب سلطنتی",
        "theme_dark-amber": "شب کهربایی",
        "theme_dark-rose": "شب رز",

        # ---- My Account page ----
        "account_title": "حساب کاربری من",
        "account_intro": (
            "رمز عبور خود را تغییر دهید. "
            "این امکان برای همه کاربرانِ واردشده در دسترس است."
        ),
        "account_change_heading": "تغییر رمز عبور",
        "account_current_password": "رمز عبور فعلی",
        "account_new_password": "رمز عبور جدید",
        "account_change_button": "تغییر رمز عبور",
        "account_tips_heading": "نکات رمز عبور",
        "account_tip_length": "حداقل ۸ نویسه استفاده کنید.",
        "account_tip_mix": "ترکیبی از حروف، اعداد و نمادها به کار ببرید.",
        "account_tip_reuse": "از رمزهای عبور سایت‌های دیگر دوباره استفاده نکنید.",
        "account_mismatch": "رمز عبور جدید و تکرار آن یکسان نیستند.",
        "account_changed": "رمز عبور با موفقیت تغییر کرد.",

        # ---- User Management page ----
        "users_title": "مدیریت کاربران",
        "users_intro": "فقط مدیر کل می‌تواند حساب‌ها را ایجاد، ویرایش و حذف کند.",
        "users_create_heading": "ایجاد کاربر",
        "users_create_button": "ایجاد کاربر",
        "users_existing_heading": "کاربران موجود",
        "users_existing_hint": (
            "برای ویرایش حساب در یک پنجره‌ی بازشو، «ویرایش» و برای حذف آن، "
            "«حذف» را بزنید."
        ),
        "users_change": "ویرایش",
        "users_delete": "حذف",
        "users_col_actions": "عملیات",
        "users_col_id": "شناسه",
        "users_col_username": "نام کاربری",
        "users_col_role": "نقش",
        "users_col_active": "فعال",
        "users_col_expires": "انقضا",
        "users_col_created": "تاریخ ایجاد",
        "users_create_mismatch": "رمز عبور و تکرار آن یکسان نیستند.",
        "users_created": "کاربر با موفقیت ایجاد شد.",
        "users_updated": "کاربر با موفقیت ویرایش شد.",
        "users_deleted": "کاربر با موفقیت حذف شد.",
        "users_not_found": "کاربر پیدا نشد.",
        "users_exists": "این نام کاربری از قبل وجود دارد.",
        "users_denied_create": "دسترسی غیرمجاز: فقط مدیر کل می‌تواند کاربر ایجاد کند.",
        "users_denied_edit": "دسترسی غیرمجاز: فقط مدیر کل می‌تواند کاربر را ویرایش کند.",
        "users_denied_delete": "دسترسی غیرمجاز: فقط مدیر کل می‌تواند کاربر را حذف کند.",
        "users_confirm_delete": (
            "کاربر «{username}» حذف شود؟ این کار قابل بازگشت نیست."
        ),

        # ---- User Management: edit popup ----
        "edit_title": "ویرایش کاربر: {username}",
        "edit_active": "حساب فعال",
        "edit_new_password": "رمز عبور جدید (برای حفظ رمز فعلی خالی بگذارید)",
        "edit_save": "ذخیره تغییرات",
        "edit_delete": "حذف کاربر",
        "edit_cancel": "انصراف",
        "edit_mismatch": "رمز عبور جدید و تکرار آن یکسان نیستند.",

        # ---- Validation / error messages raised by auth/core.py ----
        "field_password": "رمز عبور",
        "field_new_password": "رمز عبور جدید",
        "err_username_format": (
            "نام کاربری باید بین ۳ تا ۳۲ نویسه باشد و فقط شامل حروف انگلیسی، "
            "اعداد، زیرخط (_) یا خط تیره (-) باشد."
        ),
        "err_password_required": "{field} الزامی است.",
        "err_password_min": "{field} باید حداقل {n} نویسه داشته باشد.",
        "err_password_max": "{field} باید حداکثر {n} نویسه داشته باشد.",
        "err_password_complexity": (
            "{field} باید حداقل یک حرف و یک عدد داشته باشد."
        ),
        "err_expiry_format": "تاریخ انقضا باید با قالب YYYY-MM-DD وارد شود.",
        "err_invalid_role": "نقش نامعتبر است.",
        "err_auth_required": "ورود به سامانه الزامی است.",
        "err_current_password": "رمز عبور فعلی نادرست است.",
        "err_user_not_found": "کاربر پیدا نشد.",
        "err_last_superadmin": "دست‌کم یک مدیر کل فعال باید باقی بماند.",
        "err_delete_self": "نمی‌توانید حسابی را که با آن وارد شده‌اید حذف کنید.",
        "err_delete_last_superadmin": "آخرین مدیر کل فعال را نمی‌توان حذف کرد.",
    },
}

# An unknown value (typo in APP_LANG / env var) falls back to English.
if APP_LANG not in STRINGS:
    APP_LANG = "en"

IS_RTL: bool = APP_LANG in RTL_LANGS
DIRECTION: str = "rtl" if IS_RTL else "ltr"


def t(key: str, **kwargs) -> str:
    """Return the string for ``key`` in the active language.

    Falls back to English when a key is missing from the active language, and
    to the key itself when it is missing everywhere (so a typo is visible in
    the UI instead of crashing the app). ``kwargs`` fill ``{placeholders}``.
    """
    text = STRINGS[APP_LANG].get(key)
    if text is None:
        text = STRINGS["en"].get(key, key)
    return text.format(**kwargs) if kwargs else text


def role_label(role: str) -> str:
    """Translated display name of a role id (``"guest"`` ... ``"superadmin"``)."""
    return t(f"role_{role}") if f"role_{role}" in STRINGS["en"] else str(role)


# Keys starting with "theme_" that are labels, not theme names.
_THEME_NON_NAMES = {
    "theme_aria",
    "theme_light_title",
    "theme_dark_title",
    "theme_light_suffix",
    "theme_dark_suffix",
}


def js_bundle() -> dict:
    """Strings that the browser-side script (static/js/custom.js) needs.

    The delete-confirmation keeps its ``{username}`` placeholder; JavaScript
    fills it in.
    """
    return {
        "font_inherit": t("font_inherit"),
        "font_system": t("font_system"),
        "theme_light_suffix": t("theme_light_suffix"),
        "theme_dark_suffix": t("theme_dark_suffix"),
        "users_confirm_delete": STRINGS[APP_LANG].get(
            "users_confirm_delete", STRINGS["en"]["users_confirm_delete"]
        ),
        "themes": {
            key[len("theme_"):]: t(key)
            for key in STRINGS["en"]
            if key.startswith("theme_") and key not in _THEME_NON_NAMES
        },
    }
