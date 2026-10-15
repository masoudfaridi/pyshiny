"""Sidebar RBAC filtering (mirrors app.build_sidebar rules without requiring Shiny UI render)."""
from __future__ import annotations

import importlib

import pytest

from auth.core import ROLE_LEVELS

TAB_MODULES = [
    "tabs.tab_01",
    "tabs.tab_02",
    "tabs.tab_03",
    "tabs.tab_04",
    "tabs.tab_05",
    "tabs.tab_06",
    "tabs.tab_07",
    "tabs.tab_account",
    "tabs.tab_users",
]


def _load_tabs():
    return [importlib.import_module(name) for name in TAB_MODULES]


def visible_tabs_for_role(role: str):
    """Same visibility rule as app.build_sidebar."""
    tabs = _load_tabs()

    def allowed(tab):
        return ROLE_LEVELS.get(role, 0) >= ROLE_LEVELS.get(
            getattr(tab, "NAV_MIN_ROLE", "guest"), 0
        )

    return [t for t in tabs if allowed(t)]


class TestSidebarRoleFiltering:
    def test_guest_sees_only_guest_tabs(self):
        visible_ids = {t.NAV_ID for t in visible_tabs_for_role("guest")}
        for tab in _load_tabs():
            if tab.NAV_MIN_ROLE == "guest":
                assert tab.NAV_ID in visible_ids
            else:
                assert tab.NAV_ID not in visible_ids

    def test_user_sees_user_and_below(self):
        visible_ids = {t.NAV_ID for t in visible_tabs_for_role("user")}
        for tab in _load_tabs():
            if ROLE_LEVELS[tab.NAV_MIN_ROLE] <= ROLE_LEVELS["user"]:
                assert tab.NAV_ID in visible_ids
            else:
                assert tab.NAV_ID not in visible_ids

    def test_admin_hides_superadmin_only(self):
        visible_ids = {t.NAV_ID for t in visible_tabs_for_role("admin")}
        assert "tab_users" not in visible_ids
        assert "tab_01" not in visible_ids  # superadmin dashboard
        assert "tab_04" in visible_ids

    def test_superadmin_sees_everything(self):
        visible_ids = {t.NAV_ID for t in visible_tabs_for_role("superadmin")}
        for tab in _load_tabs():
            assert tab.NAV_ID in visible_ids

    def test_unknown_role_treated_as_level_zero(self):
        visible_ids = {t.NAV_ID for t in visible_tabs_for_role("not-a-role")}
        for tab in _load_tabs():
            if tab.NAV_MIN_ROLE == "guest":
                assert tab.NAV_ID in visible_ids
            else:
                assert tab.NAV_ID not in visible_ids


class TestAppConstantsOptional:
    def test_default_tab_guest_accessible(self):
        tab_04 = importlib.import_module("tabs.tab_04")
        assert tab_04.NAV_MIN_ROLE == "guest"
        assert tab_04.NAV_ID == "tab_04"
