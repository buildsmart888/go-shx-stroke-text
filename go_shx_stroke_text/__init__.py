"""GO SHX Stroke Text v0.2.0: native SHX/SHP strokes for IngeTrazo."""
from __future__ import annotations

from .constants import VERSION


def setup(app):
    """Register SHX UI with the IngeTrazo Extension API v2."""
    def show():
        from .dialog import SHXTextDialog
        dlg = getattr(app.window, "_go_shx_stroke_dialog", None)
        if dlg is None:
            dlg = SHXTextDialog(app)
            app.window._go_shx_stroke_dialog = dlg
        dlg.refresh_sheet_list()
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()

    def edit_selected():
        from .model_host import selected_stroke_group
        if selected_stroke_group(app.scene) is None:
            show()
            return
        show()
        dlg = app.window._go_shx_stroke_dialog
        dlg.tabs.setCurrentIndex(0)
        dlg._load_model_selection()

    menu = app.add_menu("GO SHX Stroke Text")
    menu.addAction("Open Stroke Text Builder…", show)
    menu.addAction("Edit Selected Stroke Text…", edit_selected)
    app.add_menu_action("GO SHX Stroke Text…", show,
                        tip="Place real SHX vectors in Model or Sheet Composer.")
    try:
        app.add_context_menu(lambda menu, selection: (
            menu.addAction("Edit GO SHX Stroke Text…", edit_selected)
            if any(getattr(g, "ext", None) and
                   "go_shx_stroke_text" in g.ext
                   for g in selection if g in app.scene.groups)
            else None))
    except (AttributeError, RuntimeError):
        pass
    try:
        from PySide6.QtWidgets import QToolBar
        toolbar = QToolBar("GO SHX Text", app.window)
        toolbar.setObjectName("go_shx_stroke_text_toolbar")
        toolbar.addAction("SHX Text", show)
        app.window.addToolBar(toolbar)
    except (AttributeError, RuntimeError):
        pass
    # The filtered event goes to the ordinary host handler for every other
    # object/tool. Failure only disables this shortcut, never the builder.
    try:
        from .viewport_hook import install_double_click_filter
        install_double_click_filter(app, show)
    except (ImportError, AttributeError, RuntimeError):
        pass
