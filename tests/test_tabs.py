"""Tab module metadata contracts."""
from __future__ import annotations

import importlib

import pytest

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

REQUIRED_ATTRS = ("NAV_ID", "NAV_LABEL", "NAV_ICON", "NAV_GROUP", "NAV_MIN_ROLE")
VALID_ROLES = {"guest", "user", "admin", "superadmin"}


@pytest.fixture(params=TAB_MODULES)
def tab_mod(request):
    return importlib.import_module(request.param)


class TestTabMetadata:
    def test_required_attributes(self, tab_mod):
        for attr in REQUIRED_ATTRS:
            assert hasattr(tab_mod, attr), f"{tab_mod.__name__} missing {attr}"

    def test_panel_callable(self, tab_mod):
        assert callable(getattr(tab_mod, "panel", None))

    def test_nav_id_format(self, tab_mod):
        assert isinstance(tab_mod.NAV_ID, str)
        assert tab_mod.NAV_ID
        assert " " not in tab_mod.NAV_ID

    def test_nav_label_nonempty(self, tab_mod):
        assert isinstance(tab_mod.NAV_LABEL, str)
        assert tab_mod.NAV_LABEL.strip()

    def test_nav_icon_bootstrap(self, tab_mod):
        # Grouped child tabs may set NAV_ICON to None (icon only on group header).
        if tab_mod.NAV_ICON is None:
            assert tab_mod.NAV_GROUP is not None
            return
        assert isinstance(tab_mod.NAV_ICON, str)
        assert tab_mod.NAV_ICON.startswith("bi-")

    def test_min_role_valid(self, tab_mod):
        assert tab_mod.NAV_MIN_ROLE in VALID_ROLES

    def test_nav_group_type(self, tab_mod):
        assert tab_mod.NAV_GROUP is None or isinstance(tab_mod.NAV_GROUP, str)


class TestTabUniqueness:
    def test_unique_nav_ids(self):
        ids = []
        for name in TAB_MODULES:
            mod = importlib.import_module(name)
            ids.append(mod.NAV_ID)
        assert len(ids) == len(set(ids))

    def test_users_tab_superadmin_only(self):
        mod = importlib.import_module("tabs.tab_users")
        assert mod.NAV_MIN_ROLE == "superadmin"

    def test_default_tab_is_guest_accessible(self):
        # DEFAULT_TAB_ID in app is tab_04; it must be guest-visible
        mod = importlib.import_module("tabs.tab_04")
        assert mod.NAV_MIN_ROLE == "guest"
