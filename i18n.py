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
            "First run: the superadmin password is in db/initial_superadmin_password.txt "
            "(see README.md). Change it after signing in."
        ),
        "login_session_limit": (
            "Too many failed attempts in this window. Reload the page to try again."
        ),
        "login_session_expired": "Your session has expired. Please sign in again.",
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

        # ---- Account details (identification code, e-mail, phone) ----
        "id_code": "Identification code",
        "email": "Email",
        "phone": "Phone number",
        "users_col_id_code": "Identification code",
        "users_col_email": "Email",
        "users_col_phone": "Phone",
        "users_missing_info": "Not set",
        "users_scroll_hint": "Identification code must be unique.",
        "err_id_code_required": "Identification code is required.",
        "err_id_code_format": (
            "Identification code must be 4-20 characters: letters, numbers, "
            "hyphens or underscores."
        ),
        "err_id_code_national": "Identification code must be a valid 10-digit national code.",
        "err_id_code_exists": "This identification code is already used by another account.",
        "err_email_required": "Email is required.",
        "err_email_format": "Email address is not valid.",
        "err_phone_required": "Phone number is required.",
        "err_phone_format": "Phone number must contain 7-15 digits (a leading + is allowed).",

        # ---- My Account: profile ----
        "account_profile_heading": "My details",
        "account_profile_intro": "Your email and phone can be updated here.",
        "account_profile_save": "Save details",
        "account_profile_saved": "Your details were saved.",
        "account_id_code_note": "Only a Superadmin can change the identification code.",
        "account_not_set": "Not set",

        # ---- User Management: protected actions (password confirmation) ----
        "users_confirm_create": 'Create user "{username}"?',
        "users_confirm_update": 'Save the changes to user "{username}"?',

        # ---- Accounts database backup / restore ----
        "backup_title": "Accounts database backup",
        "backup_intro": (
            "Save a copy of the accounts database (users, roles, password hashes) "
            "and restore it later. Restoring replaces ALL current accounts; a safety "
            "copy of the current database is made first. Backup files are stored in "
            "db/backups/ and contain password hashes: keep them private."
        ),
        "backup_create": "Create backup now",
        "backup_created": "Backup created: {name}",
        "backup_upload_label": "Import a backup file (.db)",
        "backup_import": "Import file",
        "backup_imported": "File imported as backup: {name}",
        "backup_no_file": "Choose a backup file first.",
        "backup_col_name": "File",
        "backup_col_created": "Created (UTC)",
        "backup_col_size": "Size",
        "backup_col_type": "Type",
        "backup_col_actions": "Actions",
        "backup_type_manual": "Manual",
        "backup_type_prerestore": "Before restore",
        "backup_type_uploaded": "Imported",
        "backup_restore": "Restore",
        "backup_download": "Download",
        "backup_delete": "Delete",
        "backup_none": "No backups yet.",
        "backup_restored": (
            "Accounts restored from {name} ({users} accounts). "
            "Safety copy of the previous data: {safety}."
        ),
        "backup_deleted": "Backup deleted.",
        "backup_confirm_restore": (
            'Restore the accounts database from "{name}"? All current accounts will be '
            "replaced (a safety copy is made first)."
        ),
        "backup_confirm_delete": 'Delete the backup "{name}"? This cannot be undone.',
        "backup_confirm_import": "Import the selected file as a new backup?",
        "backup_confirm_download": 'Download the backup "{name}"? It contains password hashes.',
        "backup_download_title": "Download ready",
        "backup_download_text": "Your backup file is ready:",
        "backup_close": "Close",
        "backup_denied": "Access denied: only Superadmin can manage backups.",
        "err_backup_name": "Invalid backup file name.",
        "err_backup_missing": "Backup file not found.",
        "err_backup_invalid": "This file is not a valid backup of this database.",
        "err_backup_no_superadmin": "The backup contains no active Superadmin account.",
        "err_backup_too_large": "The file is too large (maximum {n} MB).",

        # ---- Password re-confirmation (auth/confirm.py: @confirm_with_password) ----
        "reauth_title": "Confirm action",
        "reauth_continue": "Continue",
        "reauth_cancel": "Cancel",
        "reauth_password_intro": "This action is protected. Enter your account password to continue.",
        "reauth_password_label": "Your password",
        "reauth_submit": "Confirm",
        "reauth_wrong_password": "Incorrect password. Please try again.",
        "reauth_empty_password": "Please enter your password.",
        "reauth_expired": "This confirmation has expired. Please click the button again.",
        "reauth_signin": "Your session is no longer valid. Please sign in again.",
        "reauth_denied": "You do not have access to this section.",
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
            "اجرای اول: رمز سوپر ادمین در فایل db/initial_superadmin_password.txt است "
            "(README.md را ببینید). پس از ورود آن را تغییر دهید."
        ),
        "login_session_limit": (
            "تعداد تلاش‌های ناموفق در این صفحه زیاد شد. برای تلاش دوباره صفحه را بارگذاری مجدد کنید."
        ),
        "login_session_expired": "زمان نشست شما به پایان رسید. لطفاً دوباره وارد شوید.",
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

        # ---- اطلاعات حساب (کد شناسایی، ایمیل، تلفن) ----
        "id_code": "کد شناسایی",
        "email": "ایمیل",
        "phone": "شماره تلفن",
        "users_col_id_code": "کد شناسایی",
        "users_col_email": "ایمیل",
        "users_col_phone": "تلفن",
        "users_missing_info": "ثبت نشده",
        "users_scroll_hint": "کد شناسایی باید یکتا باشد.",
        "err_id_code_required": "کد شناسایی الزامی است.",
        "err_id_code_format": (
            "کد شناسایی باید ۴ تا ۲۰ نویسه و شامل حروف انگلیسی، اعداد، "
            "خط تیره یا زیرخط باشد."
        ),
        "err_id_code_national": "کد شناسایی باید یک کد ملی ۱۰ رقمی معتبر باشد.",
        "err_id_code_exists": "این کد شناسایی قبلاً برای حساب دیگری ثبت شده است.",
        "err_email_required": "ایمیل الزامی است.",
        "err_email_format": "نشانی ایمیل معتبر نیست.",
        "err_phone_required": "شماره تلفن الزامی است.",
        "err_phone_format": "شماره تلفن باید شامل ۷ تا ۱۵ رقم باشد (علامت + در ابتدا مجاز است).",

        # ---- حساب کاربری من: اطلاعات شخصی ----
        "account_profile_heading": "اطلاعات من",
        "account_profile_intro": "ایمیل و شماره تلفن خود را می‌توانید از اینجا تغییر دهید.",
        "account_profile_save": "ذخیره اطلاعات",
        "account_profile_saved": "اطلاعات شما ذخیره شد.",
        "account_id_code_note": "فقط مدیر کل می‌تواند کد شناسایی را تغییر دهد.",
        "account_not_set": "ثبت نشده",

        # ---- مدیریت کاربران: عملیات محافظت‌شده (تأیید با رمز عبور) ----
        "users_confirm_create": "کاربر «{username}» ایجاد شود؟",
        "users_confirm_update": "تغییرات کاربر «{username}» ذخیره شود؟",

        # ---- پشتیبان‌گیری و بازنشانی دیتابیس حساب‌ها ----
        "backup_title": "پشتیبان‌گیری از دیتابیس حساب‌ها",
        "backup_intro": (
            "از دیتابیس حساب‌ها (کاربران، نقش‌ها و هش رمزها) نسخه‌ی پشتیبان بگیرید و "
            "بعداً آن را بازنشانی کنید. بازنشانی «همه» حساب‌های فعلی را جایگزین می‌کند؛ "
            "پیش از آن یک نسخه‌ی ایمنی از وضعیت فعلی ساخته می‌شود. فایل‌های پشتیبان در "
            "پوشه‌ی db/backups/ ذخیره می‌شوند و شامل هش رمزها هستند؛ آن‌ها را محرمانه نگه دارید."
        ),
        "backup_create": "ساخت پشتیبان",
        "backup_created": "پشتیبان ساخته شد: {name}",
        "backup_upload_label": "وارد کردن فایل پشتیبان (.db)",
        "backup_import": "وارد کردن فایل",
        "backup_imported": "فایل به‌عنوان پشتیبان وارد شد: {name}",
        "backup_no_file": "ابتدا یک فایل پشتیبان انتخاب کنید.",
        "backup_col_name": "فایل",
        "backup_col_created": "زمان ساخت (UTC)",
        "backup_col_size": "حجم",
        "backup_col_type": "نوع",
        "backup_col_actions": "عملیات",
        "backup_type_manual": "دستی",
        "backup_type_prerestore": "پیش از بازنشانی",
        "backup_type_uploaded": "واردشده",
        "backup_restore": "بازنشانی",
        "backup_download": "دانلود",
        "backup_delete": "حذف",
        "backup_none": "هنوز پشتیبانی وجود ندارد.",
        "backup_restored": (
            "حساب‌ها از {name} بازنشانی شدند ({users} حساب). "
            "نسخه‌ی ایمنی داده‌های قبلی: {safety}."
        ),
        "backup_deleted": "پشتیبان حذف شد.",
        "backup_confirm_restore": (
            "دیتابیس حساب‌ها از «{name}» بازنشانی شود؟ همه‌ی حساب‌های فعلی جایگزین "
            "می‌شوند (پیش از آن نسخه‌ی ایمنی ساخته می‌شود)."
        ),
        "backup_confirm_delete": "پشتیبان «{name}» حذف شود؟ این کار قابل بازگشت نیست.",
        "backup_confirm_import": "فایل انتخاب‌شده به‌عنوان پشتیبان جدید وارد شود؟",
        "backup_confirm_download": "پشتیبان «{name}» دانلود شود؟ این فایل شامل هش رمزهاست.",
        "backup_download_title": "دانلود آماده است",
        "backup_download_text": "فایل پشتیبان شما آماده است:",
        "backup_close": "بستن",
        "backup_denied": "دسترسی غیرمجاز: فقط مدیر کل می‌تواند پشتیبان‌ها را مدیریت کند.",
        "err_backup_name": "نام فایل پشتیبان نامعتبر است.",
        "err_backup_missing": "فایل پشتیبان پیدا نشد.",
        "err_backup_invalid": "این فایل یک پشتیبان معتبر از این دیتابیس نیست.",
        "err_backup_no_superadmin": "این پشتیبان هیچ حساب مدیر کل فعالی ندارد.",
        "err_backup_too_large": "حجم فایل بیش از حد مجاز است (حداکثر {n} مگابایت).",

        # ---- تأیید مجدد با رمز عبور (auth/confirm.py: @confirm_with_password) ----
        "reauth_title": "تأیید عملیات",
        "reauth_continue": "ادامه",
        "reauth_cancel": "انصراف",
        "reauth_password_intro": "این عملیات محافظت‌شده است. برای ادامه، رمز عبور حساب خود را وارد کنید.",
        "reauth_password_label": "رمز عبور شما",
        "reauth_submit": "تأیید",
        "reauth_wrong_password": "رمز عبور نادرست است. لطفاً دوباره تلاش کنید.",
        "reauth_empty_password": "لطفاً رمز عبور را وارد کنید.",
        "reauth_expired": "مهلت این تأیید تمام شد. لطفاً دوباره روی دکمه کلیک کنید.",
        "reauth_signin": "نشست شما دیگر معتبر نیست. لطفاً دوباره وارد شوید.",
        "reauth_denied": "دسترسی به این بخش برای شما مقدور نیست.",
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
