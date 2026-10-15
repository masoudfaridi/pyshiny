"""tabs/examples: every example must follow the tab contract (see tabs/HOW_TO_ADD_A_TAB.md)."""
from __future__ import annotations

import importlib
import inspect
import pkgutil

import pytest

import tabs.examples as examples_pkg
from auth.core import ROLE_LEVELS

EXAMPLE_NAMES = sorted(
    m.name for m in pkgutil.iter_modules(examples_pkg.__path__) if m.name.startswith("ex")
)


def _load(name: str):
    return importlib.import_module(f"tabs.examples.{name}")


def test_there_are_fifteen_examples():
    assert len(EXAMPLE_NAMES) == 15


@pytest.mark.parametrize("name", EXAMPLE_NAMES)
class TestExampleContract:
    def test_metadata(self, name):
        mod = _load(name)
        assert mod.NAV_ID and mod.NAV_LABEL
        assert mod.MODULE_ID == mod.NAV_ID
        assert mod.NAV_MIN_ROLE in ROLE_LEVELS
        if mod.NAV_GROUP is None:
            assert mod.NAV_ICON, "top-level sidebar links need an icon"

    def test_panel_and_server_exist(self, name):
        mod = _load(name)
        assert callable(mod.panel)
        assert callable(mod.server)

    def test_panel_builds(self, name):
        assert _load(name).panel() is not None

    def test_ids_are_unique_and_do_not_clash_with_real_tabs(self, name):
        assert _load(name).NAV_ID.startswith("tab_ex")


def test_nav_ids_are_unique():
    ids = [_load(n).NAV_ID for n in EXAMPLE_NAMES]
    assert len(ids) == len(set(ids))


def test_only_example_14_needs_the_session_user():
    needing = [
        n for n in EXAMPLE_NAMES if len(inspect.signature(_load(n).server).parameters) > 0
    ]
    assert needing == ["ex14_role_aware"]
