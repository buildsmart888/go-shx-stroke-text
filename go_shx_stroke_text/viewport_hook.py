"""Narrow native double-click integration for plugin-owned SHX Groups only.

IngeTrazo normally enters *any* Group's geometry on double-click. The public
extension API has no double-click hook, so use a small Qt event filter that
intercepts only the Select tool clicking one of our top-level Groups.
Everything else passes unchanged to the host's normal mouse handling.
"""
from __future__ import annotations

import logging

from PySide6.QtCore import QObject, QEvent, Qt, QSettings, QTimer

from .constants import PLUGIN_KEY

log = logging.getLogger("ingetrazo.plugins")


class SHXDoubleClickFilter(QObject):
    def __init__(self, app, open_editor):
        super().__init__(app.viewport)
        self.app = app
        self.open_editor = open_editor

    def eventFilter(self, obj, event):
        vp = self.app.viewport
        if obj is not vp or event.type() != QEvent.MouseButtonDblClick:
            return False
        if (event.button() != Qt.LeftButton
                or event.modifiers() != Qt.NoModifier
                or getattr(getattr(vp, "active_tool", None), "name", None) != "Select"
                or getattr(vp, "nav_mode", None) is not None
                or getattr(self.app.scene, "edit_group", None) is not None
                or not QSettings().value("go_shx_stroke_text/double_click_edit",
                                         True, type=bool)):
            return False
        try:
            pos = event.position()
            obj = vp.pick_group(float(pos.x()), float(pos.y()))
            if obj is None or obj not in self.app.scene.groups:
                return False
            meta = getattr(obj, "ext", None)
            if (not isinstance(meta, dict) or PLUGIN_KEY not in meta
                    or getattr(obj, "locked", False)):
                return False
            # Synchronize the native Select tool / Properties selection.
            self.app.scene.select([obj], mode="replace")
            vp.update()
            # Defer opening the non-modal dialog until Qt finishes this event.
            QTimer.singleShot(0, lambda group=obj: self._launch(group))
            event.accept()
            return True
        except (AttributeError, RuntimeError, ValueError) as exc:
            log.warning("GO SHX double-click was not handled: %s", exc)
            return False

    def _launch(self, group):
        if group in self.app.scene.groups:
            self.open_editor()
            dlg = getattr(self.app.window, "_go_shx_stroke_dialog", None)
            if dlg is not None:
                dlg.tabs.setCurrentIndex(0)
                dlg._load_model_selection()


def install_double_click_filter(app, open_editor):
    old = getattr(app.window, "_go_shx_doubleclick_filter", None)
    if old is not None:
        return old
    flt = SHXDoubleClickFilter(app, open_editor)
    app.viewport.installEventFilter(flt)
    app.window._go_shx_doubleclick_filter = flt
    return flt
