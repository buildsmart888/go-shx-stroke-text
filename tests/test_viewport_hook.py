"""Event interception tests. Full installed Windows UI remains a smoke test."""
from __future__ import annotations

import importlib
import sys
import types
from types import SimpleNamespace

from go_shx_stroke_text.constants import PLUGIN_KEY


def test_only_double_click_owned_model_group_opens_builder(monkeypatch):
    qt = types.ModuleType("PySide6")
    qt.__path__ = []
    core = types.ModuleType("PySide6.QtCore")
    class QObject:
        def __init__(self, parent=None):
            self.parent = parent
    core.QObject = QObject
    core.QEvent = SimpleNamespace(MouseButtonDblClick=7)
    core.Qt = SimpleNamespace(LeftButton=1, NoModifier=0)
    class Settings:
        enabled = True
        def value(self, _key, _default=None, type=None):
            return self.enabled
    core.QSettings = Settings
    callbacks = []
    core.QTimer = SimpleNamespace(singleShot=lambda ms, fn: callbacks.append(fn))
    monkeypatch.setitem(sys.modules, "PySide6", qt)
    monkeypatch.setitem(sys.modules, "PySide6.QtCore", core)
    sys.modules.pop("go_shx_stroke_text.viewport_hook", None)
    hook = importlib.import_module("go_shx_stroke_text.viewport_hook")

    good = SimpleNamespace(ext={PLUGIN_KEY: {}}, locked=False)
    other = SimpleNamespace(ext={"other_extension": {}}, locked=False)
    # SimpleNamespace is intentionally unhashable; scene.select is a stub.
    scene = SimpleNamespace(groups=[good, other], edit_group=None, selection=[])
    def select(objs, mode=None):
        scene.selection = objs
    scene.select = select
    picked = [good]
    picked_at = []
    vp = SimpleNamespace(
        active_tool=SimpleNamespace(name="Select"), nav_mode=None,
        pick_group=lambda x, y: (picked_at.append((x, y)) or picked[0]),
        update=lambda: None)
    events = []
    dlg = SimpleNamespace(tabs=SimpleNamespace(setCurrentIndex=lambda i: events.append(("tab", i))),
                          _load_model_selection=lambda: events.append("load"))
    window = SimpleNamespace(_go_shx_stroke_dialog=dlg)
    app = SimpleNamespace(viewport=vp, scene=scene, window=window)
    filt = hook.SHXDoubleClickFilter(app, lambda: events.append("open"))

    class Event:
        def __init__(self, kind=7, button=1, modifiers=0):
            self.kind, self.left, self.mods = kind, button, modifiers
            self.accepted = False
        def type(self): return self.kind
        def button(self): return self.left
        def modifiers(self): return self.mods
        def position(self): return SimpleNamespace(x=lambda: 12.5, y=lambda: 42.0)
        def accept(self): self.accepted = True

    ev = Event()
    assert filt.eventFilter(vp, ev) is True
    assert ev.accepted
    assert scene.selection == [good]
    assert picked_at == [(12.5, 42.0)]
    assert not events  # dialog is opened after Qt finishes the click
    callbacks.pop(0)()
    assert events == ["open", ("tab", 0), "load"]
    events.clear()

    picked[0] = other
    assert filt.eventFilter(vp, Event()) is False
    assert not callbacks
    picked[0] = good
    vp.active_tool.name = "Line"
    assert filt.eventFilter(vp, Event()) is False
    vp.active_tool.name = "Select"
    assert filt.eventFilter(vp, Event(button=2)) is False
    assert filt.eventFilter(vp, Event(modifiers=1)) is False
    assert filt.eventFilter(vp, Event(kind=3)) is False
    scene.edit_group = other
    assert filt.eventFilter(vp, Event()) is False
    scene.edit_group = None
    Settings.enabled = False
    assert filt.eventFilter(vp, Event()) is False
    assert not events
    # Do not retain imported fake Qt module for subsequent tests.
    monkeypatch.delitem(sys.modules, "go_shx_stroke_text.viewport_hook")
