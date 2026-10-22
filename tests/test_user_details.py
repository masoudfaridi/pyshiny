"""Identification code (unique), e-mail and phone: validation, storage, migration."""
from __future__ import annotations

import sqlite3

import pytest

import auth.core as core
from tests.conftest import contact


class TestValidators:
    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("ab-1234", "AB-1234"),          # upper-cased
            ("  EMP_007 ", "EMP_007"),       # trimmed
            ("۱۲۳۴۵۶", "123456"),            # Persian digits -> ASCII
            ("١٢٣٤٥٦", "123456"),            # Arabic-Indic digits -> ASCII
        ],
    )
    def test_id_code_normalized(self, raw, expected):
        assert core.validate_id_code(raw) == expected

    @pytest.mark.parametrize("raw", ["", "   ", None])
    def test_id_code_required(self, raw):
        with pytest.raises(ValueError, match="required"):
            core.validate_id_code(raw)

    @pytest.mark.parametrize("raw", ["abc", "x" * 21, "bad code", "ab#1234", "-abcd"])
    def test_id_code_format(self, raw):
        with pytest.raises(ValueError, match="Identification code"):
            core.validate_id_code(raw)

    def test_national_mode_checks_the_checksum(self, monkeypatch):
        monkeypatch.setattr(core, "ID_CODE_MODE", "national_ir")
        assert core.validate_id_code("0499370899") == "0499370899"  # valid code
        for bad in ("0499370898", "1111111111", "12345", "ABCDEFGHIJ"):
            with pytest.raises(ValueError, match="national"):
                core.validate_id_code(bad)

    @pytest.mark.parametrize(
        "raw, expected",
        [(" Ali@Example.COM ", "ali@example.com"), ("a.b+c@sub.example.org", "a.b+c@sub.example.org")],
    )
    def test_email_normalized(self, raw, expected):
        assert core.validate_email(raw) == expected

    @pytest.mark.parametrize("raw", ["", "plain", "a@b", "a@@b.com", "a b@c.com", "@c.com", "a@.com"])
    def test_email_invalid(self, raw):
        with pytest.raises(ValueError):
            core.validate_email(raw)

    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("09123456789", "09123456789"),
            ("+98 912 345-6789", "+989123456789"),
            ("0098 (912) 3456789", "+989123456789"),   # 00 -> +
            ("۰۹۱۲۳۴۵۶۷۸۹", "09123456789"),              # Persian digits
        ],
    )
    def test_phone_normalized(self, raw, expected):
        assert core.validate_phone(raw) == expected

    @pytest.mark.parametrize("raw", ["", "12345", "1" * 16, "09a12345678", "+"])
    def test_phone_invalid(self, raw):
        with pytest.raises(ValueError):
            core.validate_phone(raw)


class TestCreateAndUpdate:
    def test_stored_normalized_and_listed(self, superadmin_ctx):
        core.create_user(
            "detailed", "Passw0rd1", "user",
            id_code="emp-42-x", email="Detailed@Example.com", phone="+98 912 000 1111",
        )
        row = next(u for u in core.list_users() if u["username"] == "detailed")
        assert (row["id_code"], row["email"], row["phone"]) == (
            "EMP-42-X", "detailed@example.com", "+989120001111",
        )

    def test_session_carries_the_details(self, superadmin_ctx):
        core.create_user("withsession", "Passw0rd1", "user", **contact("withsession"))
        session = core.authenticate("withsession", "Passw0rd1")
        assert session["id_code"] == "ID-WITHSESSION"
        assert session["email"] == "withsession@example.com"
        assert core.get_user_by_id(session["id"])["phone"] == session["phone"]

    def test_all_three_fields_are_required_to_create(self, superadmin_ctx):
        with pytest.raises(TypeError):
            core.create_user("nofields", "Passw0rd1", "user")  # type: ignore[call-arg]
        for blank in ("id_code", "email", "phone"):
            data = contact("blankfield")
            data[blank] = ""
            with pytest.raises(ValueError, match="required"):
                core.create_user("blankfield", "Passw0rd1", "user", **data)

    def test_id_code_must_be_unique_on_create(self, superadmin_ctx):
        core.create_user("first_one", "Passw0rd1", "user", **contact("first_one"))
        clash = {**contact("second_one"), "id_code": "id-first_one"}  # same code, other case
        with pytest.raises(ValueError, match="already used"):
            core.create_user("second_one", "Passw0rd1", "user", **clash)
        assert not any(u["username"] == "second_one" for u in core.list_users())

    def test_duplicate_username_is_still_an_integrity_error(self, superadmin_ctx):
        core.create_user("same_name", "Passw0rd1", "user", **contact("same_name"))
        with pytest.raises(sqlite3.IntegrityError):
            core.create_user("same_name", "Passw0rd1", "user", **contact("same_name_2"))

    def test_id_code_must_be_unique_on_update(self, superadmin_ctx):
        core.create_user("owner_a", "Passw0rd1", "user", **contact("owner_a"))
        core.create_user("owner_b", "Passw0rd1", "user", **contact("owner_b"))
        b_id = core.authenticate("owner_b", "Passw0rd1")["id"]
        with pytest.raises(ValueError, match="already used"):
            core.update_user(b_id, "owner_b", "user", True, id_code="ID-OWNER_A")

    def test_keeping_own_id_code_is_not_a_clash(self, superadmin_ctx):
        core.create_user("keeper", "Passw0rd1", "user", **contact("keeper"))
        uid = core.authenticate("keeper", "Passw0rd1")["id"]
        core.update_user(uid, "keeper", "user", True, id_code="id-keeper", email="new@example.com")
        row = next(u for u in core.list_users() if u["id"] == uid)
        assert row["id_code"] == "ID-KEEPER" and row["email"] == "new@example.com"

    def test_update_without_details_keeps_them(self, superadmin_ctx):
        core.create_user("untouched", "Passw0rd1", "user", **contact("untouched"))
        uid = core.authenticate("untouched", "Passw0rd1")["id"]
        before = next(u for u in core.list_users() if u["id"] == uid)
        core.update_user(uid, "untouched", "admin", True)
        after = next(u for u in core.list_users() if u["id"] == uid)
        assert (after["id_code"], after["email"], after["phone"]) == (
            before["id_code"], before["email"], before["phone"],
        )

    def test_update_cannot_blank_a_required_field(self, superadmin_ctx):
        core.create_user("noblank", "Passw0rd1", "user", **contact("noblank"))
        uid = core.authenticate("noblank", "Passw0rd1")["id"]
        for field in ("id_code", "email", "phone"):
            with pytest.raises(ValueError, match="required"):
                core.update_user(uid, "noblank", "user", True, **{field: ""})

    def test_audit_records_code_change_but_not_email_or_phone_values(self, superadmin_ctx):
        from auth import audit

        core.create_user("audited", "Passw0rd1", "user", **contact("audited"))
        uid = core.authenticate("audited", "Passw0rd1")["id"]
        core.update_user(
            uid, "audited", "user", True,
            id_code="NEW-CODE-1", email="secret@example.com", phone="09111111111",
        )
        detail = next(
            e["detail"] for e in audit.query_events(category="security")
            if e["event"] == "user_updated"
        )
        assert "NEW-CODE-1" in detail
        assert "secret@example.com" not in detail and "09111111111" not in detail
        assert '"email": "changed"' in detail


class TestOwnProfile:
    def test_user_updates_own_email_and_phone(self, user_ctx):
        core.update_own_profile("Me@Example.com", "+98 912 111 2222")
        row = core.get_user_by_id(user_ctx["id"])
        assert row["email"] == "me@example.com" and row["phone"] == "+989121112222"

    def test_invalid_values_rejected(self, user_ctx):
        with pytest.raises(ValueError):
            core.update_own_profile("nope", "09123456789")
        with pytest.raises(ValueError):
            core.update_own_profile("ok@example.com", "12")

    def test_cannot_change_the_id_code(self, user_ctx):
        import inspect

        assert "id_code" not in inspect.signature(core.update_own_profile).parameters

    def test_requires_a_signed_in_user(self, anonymous_ctx):
        with pytest.raises(PermissionError):
            core.update_own_profile("a@example.com", "09123456789")


class TestMigration:
    def _legacy_db(self, path):
        with sqlite3.connect(path) as con:
            con.execute(
                """CREATE TABLE users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('superadmin','admin','user','guest')),
                    is_active INTEGER NOT NULL DEFAULT 1,
                    expire_date TEXT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"""
            )
            con.execute(
                "INSERT INTO users(username,password_hash,role) VALUES('old1',?, 'user')",
                (core._hash_password("OldPass123"),),
            )
            con.execute(
                "INSERT INTO users(username,password_hash,role) VALUES('old2',?, 'user')",
                (core._hash_password("OldPass456"),),
            )
            con.commit()

    def test_old_database_gets_the_new_columns(self, tmp_path, monkeypatch):
        db = tmp_path / "legacy.db"
        self._legacy_db(db)
        monkeypatch.setattr(core, "DB_PATH", db)
        core.init_db()
        with sqlite3.connect(db) as con:
            columns = {r[1] for r in con.execute("PRAGMA table_info(users)")}
            old = con.execute("SELECT id_code, email, phone FROM users WHERE username='old1'").fetchone()
        assert {"id_code", "email", "phone"} <= columns
        assert old == (None, None, None)                       # nothing invented
        assert core.authenticate("old1", "OldPass123") is not None  # logins keep working

    def test_many_accounts_may_still_lack_a_code(self, tmp_path, monkeypatch):
        db = tmp_path / "legacy2.db"
        self._legacy_db(db)
        monkeypatch.setattr(core, "DB_PATH", db)
        core.init_db()  # two NULL codes must not violate the unique index
        with sqlite3.connect(db) as con:
            assert con.execute("SELECT COUNT(*) FROM users WHERE id_code IS NULL").fetchone()[0] >= 2

    def test_database_level_uniqueness(self, isolated_db):
        with sqlite3.connect(isolated_db) as con:
            con.execute("UPDATE users SET id_code='SAME' WHERE username='admin'")
            with pytest.raises(sqlite3.IntegrityError):
                con.execute("UPDATE users SET id_code='SAME' WHERE username='user'")
