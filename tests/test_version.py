"""Build-version stamping: packaged builds report _build_info, source is dev."""
import sys
import types

import version


def test_dev_when_no_build_info(monkeypatch):
    monkeypatch.delitem(sys.modules, "_build_info", raising=False)
    monkeypatch.setattr(
        "builtins.__import__", _blocking_import("_build_info"))
    assert version.app_version() == "dev"


def test_stamped_version_wins(monkeypatch):
    mod = types.ModuleType("_build_info")
    mod.APP_VERSION = "2026.07.09-1350-abc1234"
    monkeypatch.setitem(sys.modules, "_build_info", mod)
    assert version.app_version() == "2026.07.09-1350-abc1234"


def _blocking_import(blocked):
    real = __import__

    def fake(name, *args, **kwargs):
        if name == blocked:
            raise ImportError(name)
        return real(name, *args, **kwargs)
    return fake
