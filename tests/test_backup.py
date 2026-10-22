"""Accounts database backup and restore (auth/backup.py + the @superadmin wrappers)."""
from __future__ import annotations

import sqlite3

import pytest

import auth.core as core
from auth import audit, backup
from tests.conftest import contact


def _usernames():
    with sqlite3.connect(core.DB_PATH) as con:
        return {row[0] for row in con.execute("SELECT username FROM users")}


class TestNames:
    @pytest.mark.parametrize(
        "name",
        ["auth-20261019-143210.db", "auth-20261019-143210-manual.db",
         "auth-20261019-143210-prerestore.db", "auth-20261019-143210-uploaded.db"],
    )
    def test_generated_names_are_valid(self, name):
        assert backup.is_valid_name(name)

    @pytest.mark.parametrize(
        "name",
        ["../auth.db", "auth.db", "../../etc/passwd", "auth-2026-1.db", "auth-20261019-143210-evil.db",
         "auth-20261019-143210.db/../x", "/auth-20261019-143210.db", "", None, 5, "auth-20261019-143210.db "],
    )
    def test_forged_names_are_rejected(self, name):
        assert not backup.is_valid_name(name)

    def test_format_size(self):
        assert backup.format_size(512) == "512 B"
        assert backup.format_size(2048) == "2.0 KB"
        assert backup.format_size(3 * 1024 * 1024) == "3.00 MB"


class TestCreateAndList:
    def test_create_makes_a_consistent_copy(self, superadmin_ctx):
        info = core.create_backup()
        assert backup.is_valid_name(info["name"]) and info["kind"] == "manual" and info["size"] > 0
        path = core.DB_PATH.parent / "backups" / info["name"]
        with sqlite3.connect(path) as con:
            names = {r[0] for r in con.execute("SELECT username FROM users")}
            assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert {"superadmin", "admin", "user", "guest"} <= names

    def test_two_backups_in_the_same_second_do_not_overwrite(self, superadmin_ctx):
        a, b = core.create_backup(), core.create_backup()
        assert a["name"] != b["name"]
        assert len(core.list_backups()) == 2

    def test_list_is_newest_first_and_ignores_foreign_files(self, superadmin_ctx):
        first, second = core.create_backup(), core.create_backup()
        (core.DB_PATH.parent / "backups" / "notes.txt").write_text("x")
        names = [b["name"] for b in core.list_backups()]
        assert names == sorted([first["name"], second["name"]], reverse=True)

    def test_no_partial_files_left_behind(self, superadmin_ctx):
        core.create_backup()
        leftovers = [p.name for p in (core.DB_PATH.parent / "backups").iterdir() if p.suffix == ".partial"]
        assert leftovers == []


class TestRestore:
    def test_restore_brings_back_deleted_and_changed_accounts(self, superadmin_ctx):
        core.create_user("keepme", "Passw0rd1", "user", **contact("keepme"))
        snapshot = core.create_backup()

        core.create_user("added_later", "Passw0rd1", "user", **contact("added_later"))
        keep_id = core.authenticate("keepme", "Passw0rd1")["id"]
        core.delete_user(keep_id)
        assert "keepme" not in _usernames() and "added_later" in _usernames()

        result = core.restore_backup(snapshot["name"])

        assert "keepme" in _usernames() and "added_later" not in _usernames()
        assert result["users"] == len(_usernames())
        assert core.authenticate("keepme", "Passw0rd1") is not None  # password hash restored too

    def test_restore_makes_a_safety_copy_of_the_current_data(self, superadmin_ctx):
        snapshot = core.create_backup()
        core.create_user("will_be_lost", "Passw0rd1", "user", **contact("will_be_lost"))
        result = core.restore_backup(snapshot["name"])
        assert result["safety"]["kind"] == "prerestore"
        safety_file = core.DB_PATH.parent / "backups" / result["safety"]["name"]
        with sqlite3.connect(safety_file) as con:
            assert con.execute("SELECT 1 FROM users WHERE username='will_be_lost'").fetchone()

    def test_restore_of_an_old_schema_backup_adds_the_new_columns(self, superadmin_ctx):
        old = core.DB_PATH.parent / "backups" / "auth-20200101-000000.db"
        old.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(old) as con:
            con.execute(
                """CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL UNIQUE,
                   password_hash TEXT NOT NULL, role TEXT NOT NULL, is_active INTEGER NOT NULL DEFAULT 1,
                   expire_date TEXT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"""
            )
            con.execute(
                "INSERT INTO users(username,password_hash,role) VALUES('legacy_admin',?, 'superadmin')",
                (core._hash_password("LegacyPass1"),),
            )
            con.commit()
        core.restore_backup(old.name)
        with sqlite3.connect(core.DB_PATH) as con:
            columns = {r[1] for r in con.execute("PRAGMA table_info(users)")}
        assert {"id_code", "email", "phone"} <= columns
        assert core.authenticate("legacy_admin", "LegacyPass1") is not None

    def test_restore_clears_login_lockouts(self, superadmin_ctx):
        snapshot = core.create_backup()
        for _ in range(core.LOGIN_MAX_FAILURES):
            core.register_login_failure("admin")
        assert core.is_login_locked("admin")[0]
        core.restore_backup(snapshot["name"])
        assert not core.is_login_locked("admin")[0]

    def test_unknown_or_forged_name(self, superadmin_ctx):
        with pytest.raises(ValueError, match="Invalid backup"):
            core.restore_backup("../auth.db")
        with pytest.raises(ValueError, match="not found"):
            core.restore_backup("auth-20200101-000000.db")

    def test_corrupt_file_is_refused_and_data_untouched(self, superadmin_ctx):
        bad = core.DB_PATH.parent / "backups" / "auth-20200102-000000.db"
        bad.parent.mkdir(parents=True, exist_ok=True)
        bad.write_bytes(b"this is not a database")
        before = _usernames()
        with pytest.raises(ValueError, match="not a valid"):
            core.restore_backup(bad.name)
        assert _usernames() == before

    def test_backup_without_an_active_superadmin_is_refused(self, superadmin_ctx):
        bad = core.DB_PATH.parent / "backups" / "auth-20200103-000000.db"
        bad.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(bad) as con:
            con.execute(
                """CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, password_hash TEXT,
                   role TEXT, is_active INTEGER, expire_date TEXT)"""
            )
            con.execute("INSERT INTO users VALUES(1,'only_user','x','user',1,NULL)")
            con.commit()
        with pytest.raises(ValueError, match="Superadmin"):
            core.restore_backup(bad.name)
        assert "superadmin" in _usernames()


class TestImportAndDelete:
    def test_import_stores_a_validated_file(self, superadmin_ctx):
        source = core.create_backup()
        data = (core.DB_PATH.parent / "backups" / source["name"]).read_bytes()
        info = core.import_backup(data)
        assert info["kind"] == "uploaded" and info["name"] != source["name"]
        assert info["name"] in [b["name"] for b in core.list_backups()]

    @pytest.mark.parametrize("data", [b"", b"hello world", b"SQLite format 3\x00" + b"\x00" * 50])
    def test_import_rejects_garbage(self, superadmin_ctx, data):
        with pytest.raises(ValueError):
            core.import_backup(data)
        assert core.list_backups() == []

    def test_import_size_limit(self, superadmin_ctx, monkeypatch):
        monkeypatch.setattr(backup, "MAX_IMPORT_BYTES", 10)
        with pytest.raises(ValueError, match="too large"):
            core.import_backup(b"SQLite format 3\x00" + b"x" * 100)

    def test_delete(self, superadmin_ctx):
        info = core.create_backup()
        core.delete_backup(info["name"])
        assert core.list_backups() == []
        with pytest.raises(ValueError, match="not found"):
            core.delete_backup(info["name"])

    def test_delete_refuses_path_tricks(self, superadmin_ctx):
        with pytest.raises(ValueError, match="Invalid backup"):
            core.delete_backup("../auth.db")
        assert core.DB_PATH.exists()

    def test_read_backup_returns_a_sqlite_file(self, superadmin_ctx):
        info = core.create_backup()
        assert core.read_backup(info["name"]).startswith(b"SQLite format 3\x00")


class TestAccessControl:
    @pytest.mark.parametrize("ctx", ["admin_ctx", "user_ctx", "guest_ctx", "anonymous_ctx"])
    def test_only_superadmin(self, ctx, request):
        request.getfixturevalue(ctx)
        for call in (
            core.create_backup,
            core.list_backups,
            lambda: core.restore_backup("auth-20200101-000000.db"),
            lambda: core.delete_backup("auth-20200101-000000.db"),
            lambda: core.read_backup("auth-20200101-000000.db"),
            lambda: core.import_backup(b"SQLite format 3\x00"),
        ):
            with pytest.raises(PermissionError):
                call()
        assert not (core.DB_PATH.parent / "backups").exists()  # nothing was created

    def test_denied_attempt_is_written_to_the_security_log(self, admin_ctx):
        with pytest.raises(PermissionError):
            core.create_backup()
        assert any(e["event"] == "access_denied" for e in audit.query_events(category="security"))


class TestAuditTrail:
    def test_every_operation_is_logged(self, superadmin_ctx):
        info = core.create_backup()
        core.restore_backup(info["name"])
        core.read_backup(info["name"])
        core.delete_backup(info["name"])
        events = {e["event"]: e for e in audit.query_events(category="security", limit=50)}
        for name in ("accounts_backup_created", "accounts_backup_restored",
                     "accounts_backup_downloaded", "accounts_backup_deleted"):
            assert name in events, name
        assert events["accounts_backup_restored"]["severity"] == "critical"
