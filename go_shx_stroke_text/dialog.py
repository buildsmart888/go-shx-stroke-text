"""IngeTrazo Qt interface. No host imports until a user opens this dialog."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QSettings
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDoubleSpinBox, QFileDialog, QFormLayout, QFrame,
    QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPlainTextEdit,
    QPushButton, QScrollArea, QTabWidget, QVBoxLayout, QWidget, QCheckBox,
)

from .constants import MAX_MODEL_SEGMENTS, MAX_SHEET_SEGMENTS, VERSION
from .engine import (SHXTextError, GlyphCoverageError, build_strokes,
                     check_glyphs, inspect_font)
from .model_host import selected_stroke_group, create_model_group, commit_model
from .pose import effective_parameters, merge_updated_position
from .sheet_host import sheet_entries, sheet_record, commit_sheet, export_sheet_strokes_dxf


class _Preview(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.paths = []
        self.setMinimumHeight(145)
        self.setStyleSheet("background: #fafaf5; border: 1px solid #bec7bd;")

    def set_paths(self, paths):
        self.paths = paths
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.fillRect(self.rect(), QColor("#fafaf5"))
        if not self.paths:
            p.setPen(QColor("#69776c"))
            p.drawText(self.rect(), Qt.AlignCenter,
                       "SHX stroke preview · Select a font and click Preview")
            p.end()
            return
        pts = [pt for poly in self.paths for pt in poly]
        if not pts:
            p.end()
            return
        x0, x1 = min(pt[0] for pt in pts), max(pt[0] for pt in pts)
        y0, y1 = min(pt[1] for pt in pts), max(pt[1] for pt in pts)
        box_w = max(x1-x0, 1e-5)
        box_h = max(y1-y0, 1e-5)
        scale = min((self.width()-32)/box_w, (self.height()-24)/box_h)
        scale = max(scale, 0.01)
        x_mid, y_mid = (x0+x1)*0.5, (y0+y1)*0.5
        pen = QPen(QColor("#2d5954"), 1.35)
        pen.setCosmetic(True)
        p.setPen(pen)
        for poly in self.paths:
            for a, b in zip(poly, poly[1:]):
                p.drawLine(round(self.width()/2 + (a[0]-x_mid)*scale),
                           round(self.height()/2 - (a[1]-y_mid)*scale),
                           round(self.width()/2 + (b[0]-x_mid)*scale),
                           round(self.height()/2 - (b[1]-y_mid)*scale))
        p.end()


def _spin(low, high, value, digits=3, step=0.1, suffix=""):
    w = QDoubleSpinBox()
    w.setRange(low, high)
    w.setDecimals(digits)
    w.setSingleStep(step)
    w.setValue(value)
    if suffix:
        w.setSuffix(suffix)
    return w


class SHXTextDialog(QDialog):
    def __init__(self, app):
        super().__init__(app.window)
        self.app = app
        self.setWindowTitle(f"GO SHX Stroke Text v{VERSION} — IngeTrazo")
        self.resize(800, 830)
        self.setMinimumSize(660, 620)
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        self._loaded_group_uid = None
        self._loaded_visible = {}
        self._build()
        self._load_settings()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 12, 14, 12)
        outer.setSpacing(8)
        title = QLabel("GO SHX STROKE TEXT")
        title.setStyleSheet("font-weight: 700; font-size: 17px; color: #547663;")
        outer.addWidget(title)
        subtitle = QLabel("Load real .shx/.shp strokes (no TTF outline substitution) · Model + Sheet Composer")
        subtitle.setWordWrap(True)
        outer.addWidget(subtitle)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        root = QWidget()
        scroll.setWidget(root)
        form = QVBoxLayout(root)
        form.setSpacing(10)
        outer.addWidget(scroll, 1)

        font_group = QGroupBox("01 · SHX / SHP file")
        fl = QVBoxLayout(font_group)
        line = QHBoxLayout()
        self.font_path = QLineEdit()
        self.font_path.setPlaceholderText(r"C:\CAD\Fonts\thai00.shx")
        line.addWidget(self.font_path, 1)
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse_font)
        line.addWidget(browse)
        fl.addLayout(line)
        self.font_info = QLabel("Font not yet loaded")
        self.font_info.setWordWrap(True)
        self.font_info.setStyleSheet("color: #65766c")
        fl.addWidget(self.font_info)
        form.addWidget(font_group)

        text_group = QGroupBox("02 · Text")
        tl = QVBoxLayout(text_group)
        self.text_box = QPlainTextEdit()
        self.text_box.setPlainText("ABCabc123 ภาษาไทย")
        self.text_box.setMaximumHeight(88)
        tl.addWidget(self.text_box)
        settings = QFormLayout()
        self.encoding = QComboBox()
        self.encoding.addItem("Auto: Unicode, then Thai CP874", "auto")
        self.encoding.addItem("Unicode glyph indices only", "unicode")
        self.encoding.addItem("Legacy CP874 fallback", "cp874")
        settings.addRow("Character mapping", self.encoding)
        self.align = QComboBox()
        for key, label in (("left", "Left"), ("center", "Center"), ("right", "Right")):
            self.align.addItem(label, key)
        settings.addRow("Alignment", self.align)
        self.width_factor = _spin(0.1, 5, 1, 2, 0.1)
        settings.addRow("Width factor", self.width_factor)
        self.tracking = _spin(-0.5, 2, 0, 2, 0.05, " × height")
        settings.addRow("Character tracking", self.tracking)
        self.line_spacing = _spin(0.8, 4, 1.5, 2, 0.1, " × height")
        settings.addRow("Line spacing", self.line_spacing)
        tl.addLayout(settings)
        form.addWidget(text_group)

        self.tabs = QTabWidget()
        model_page = QWidget()
        ml = QFormLayout(model_page)
        self.model_height = _spin(0.001, 100, 0.30, 3, 0.05, " m")
        ml.addRow("Capital height", self.model_height)
        self.model_x = _spin(-1e6, 1e6, 0, 3, 0.1, " m")
        self.model_y = _spin(-1e6, 1e6, 0, 3, 0.1, " m")
        self.model_z = _spin(-1e6, 1e6, 0, 3, 0.1, " m")
        ml.addRow("Insertion X", self.model_x)
        ml.addRow("Insertion Y", self.model_y)
        ml.addRow("Insertion Z", self.model_z)
        self.plane = QComboBox()
        self.plane.addItem("XY · Floor / plan", "XY")
        self.plane.addItem("XZ · Front / elevation", "XZ")
        self.plane.addItem("YZ · Side / elevation", "YZ")
        ml.addRow("Plane", self.plane)
        self.model_angle = _spin(-360, 360, 0, 1, 15, "°")
        ml.addRow("Rotation", self.model_angle)
        model_hint = QLabel("Model output: real loose edges inside ONE named native Group. "
                            "Supports selection, Move, Layer, Save, and Undo.")
        model_hint.setWordWrap(True)
        ml.addRow(model_hint)
        self.double_click_edit = QCheckBox(
            "Double-click GO SHX Group to edit text (other Groups unchanged)")
        self.double_click_edit.toggled.connect(self._store_double_click)
        ml.addRow(self.double_click_edit)
        action_model = QHBoxLayout()
        load_selected = QPushButton("Load selected text")
        load_selected.clicked.connect(self._load_model_selection)
        action_model.addWidget(load_selected)
        btn_model = QPushButton("Create Model Text")
        btn_model.clicked.connect(self._create_model)
        action_model.addWidget(btn_model)
        btn_update = QPushButton("Update Selected")
        btn_update.clicked.connect(lambda: self._create_model(replace=True))
        action_model.addWidget(btn_update)
        ml.addRow(action_model)
        self.tabs.addTab(model_page, "Model · metres")

        sheet_page = QWidget()
        sl = QFormLayout(sheet_page)
        self.sheet_idx = QComboBox()
        self.sheet_idx.currentIndexChanged.connect(self._refresh_sheet_entries)
        sl.addRow("Drawing sheet", self.sheet_idx)
        self.sheet_entry = QComboBox()
        self.sheet_entry.currentIndexChanged.connect(self._load_sheet_entry)
        sl.addRow("Existing stroke text", self.sheet_entry)
        self.sheet_height = _spin(0.5, 50, 3.5, 2, 0.5, " mm")
        sl.addRow("Capital height", self.sheet_height)
        self.paper_x = _spin(-100, 1200, 25, 2, 5, " mm")
        self.paper_y = _spin(-100, 1200, 30, 2, 5, " mm")
        sl.addRow("Baseline X on paper", self.paper_x)
        sl.addRow("Baseline Y on paper", self.paper_y)
        self.paper_angle = _spin(-360, 360, 0, 1, 15, "°")
        sl.addRow("Rotation", self.paper_angle)
        self.pen_mm = _spin(0.05, 2.0, 0.18, 2, 0.05, " mm")
        sl.addRow("Pen width", self.pen_mm)
        sheet_hint = QLabel("Direct paper-space vectors. Each stroke becomes a native "
                            "sheet Line item, combined with one group ID. "
                            "Max 2,500 segments per text for Composer performance.")
        sheet_hint.setWordWrap(True)
        sl.addRow(sheet_hint)
        sheet_action = QHBoxLayout()
        btn_sheet = QPushButton("Create / Update Sheet Text")
        btn_sheet.clicked.connect(self._create_sheet)
        sheet_action.addWidget(btn_sheet)
        btn_delete = QPushButton("Delete Selected Text")
        btn_delete.clicked.connect(self._delete_sheet)
        sheet_action.addWidget(btn_delete)
        export_button = QPushButton("Export Sheet SHX lines to DXF...")
        export_button.setToolTip("Export only GO SHX paper-space strokes to a separate DXF file (mm).")
        export_button.clicked.connect(self._export_sheet_dxf)
        sl.addRow(sheet_action)
        sl.addRow(export_button)
        self.tabs.addTab(sheet_page, "Sheet · millimetres")
        form.addWidget(self.tabs)
        self.preview = _Preview()
        form.addWidget(self.preview)

        bottom = QHBoxLayout()
        self.feedback = QLabel("Ready · select a font file")
        self.feedback.setWordWrap(True)
        bottom.addWidget(self.feedback, 1)
        glyph_button = QPushButton("Check all glyphs")
        glyph_button.setToolTip("List every missing Unicode/CP874 character before rendering.")
        glyph_button.clicked.connect(self._scan_glyphs)
        bottom.addWidget(glyph_button)
        preview_button = QPushButton("Preview strokes")
        preview_button.clicked.connect(self._preview)
        bottom.addWidget(preview_button)
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.close)
        bottom.addWidget(close_button)
        outer.addLayout(bottom)

    def _load_settings(self):
        s = QSettings()
        filename = str(s.value("go_shx_stroke_text/font_path", ""))
        if filename:
            self.font_path.setText(filename)
            self._font_diagnostics()
        idx = int(s.value("go_shx_stroke_text/tab_index", 0) or 0)
        self.tabs.setCurrentIndex(max(0, min(idx, 1)))
        self.double_click_edit.blockSignals(True)
        self.double_click_edit.setChecked(s.value(
            "go_shx_stroke_text/double_click_edit", True, type=bool))
        self.double_click_edit.blockSignals(False)

    def _store_double_click(self, checked):
        QSettings().setValue("go_shx_stroke_text/double_click_edit", bool(checked))

    def _save_settings(self):
        s = QSettings()
        s.setValue("go_shx_stroke_text/font_path", self.font_path.text().strip())
        s.setValue("go_shx_stroke_text/tab_index", self.tabs.currentIndex())

    def closeEvent(self, ev):
        self._save_settings()
        super().closeEvent(ev)

    def _browse_font(self):
        here = self.font_path.text().strip()
        first = str(Path(here).parent) if here else ""
        path, _filter = QFileDialog.getOpenFileName(
            self, "Choose an SHX/SHP font", first,
            "Stroke Fonts (*.shx *.shp);;All Files (*)")
        if path:
            self.font_path.setText(path)
            self._font_diagnostics()
            self._save_settings()

    def _font_diagnostics(self):
        try:
            data = inspect_font(self.font_path.text().strip())
            self.font_info.setText(
                f"{data['name']} · {data['glyph_count']} glyphs · "
                f"Thai Unicode slots: {data['thai_unicode']} · "
                f"Thai legacy candidate slots: {data['thai_cp874_slots']}")
        except SHXTextError as e:
            self.font_info.setText(str(e))

    def refresh_sheet_list(self):
        scene = self.app.scene
        current = self.sheet_idx.currentData()
        self.sheet_idx.blockSignals(True)
        self.sheet_idx.clear()
        for i, s in enumerate(scene.compositions):
            self.sheet_idx.addItem(f"{i+1} · {s.name}", i)
        if current is not None:
            i = self.sheet_idx.findData(current)
            if i >= 0:
                self.sheet_idx.setCurrentIndex(i)
        self.sheet_idx.blockSignals(False)
        self._refresh_sheet_entries()

    def _refresh_sheet_entries(self, *_):
        sheet_no = self.sheet_idx.currentData()
        self.sheet_entry.blockSignals(True)
        self.sheet_entry.clear()
        self.sheet_entry.addItem("< New stroke text >", None)
        if sheet_no is not None:
            for ident, label in sheet_entries(self.app.scene, sheet_no):
                self.sheet_entry.addItem(label + " [" + ident[-5:] + "]", ident)
        self.sheet_entry.blockSignals(False)

    def _load_sheet_entry(self, *_):
        uid = self.sheet_entry.currentData()
        if not uid:
            return
        r = sheet_record(self.app.scene, uid)
        if not r:
            self.feedback.setText("These are existing vector strokes; their source metadata is not available.")
            return
        self.text_box.setPlainText(str(r.get("text", "")))
        self.font_path.setText(str(r.get("font", "")))
        self.sheet_height.setValue(float(r.get("height", 3.5)))
        self.paper_x.setValue(float(r.get("paper_x", 25)))
        self.paper_y.setValue(float(r.get("paper_y", 30)))
        self.paper_angle.setValue(float(r.get("angle", 0)))
        self.pen_mm.setValue(float(r.get("pen_mm", 0.18)))
        self._set_common_params(r)
        self._font_diagnostics()

    def _set_common_params(self, p):
        self.width_factor.setValue(float(p.get("width_factor", 1)))
        self.tracking.setValue(float(p.get("tracking", 0)))
        self.line_spacing.setValue(float(p.get("line_spacing", 1.5)))
        for w, key in ((self.encoding, p.get("encoding", "auto")),
                       (self.align, p.get("alignment", "left"))):
            i = w.findData(key)
            if i >= 0:
                w.setCurrentIndex(i)

    def _common(self):
        return {
            "font": self.font_path.text().strip(),
            "text": self.text_box.toPlainText(),
            "width_factor": self.width_factor.value(),
            "tracking": self.tracking.value(),
            "line_spacing": self.line_spacing.value(),
            "alignment": self.align.currentData(),
            "encoding": self.encoding.currentData(),
        }

    def _params(self, target):
        d = self._common()
        if target == "model":
            d.update(height=self.model_height.value(),
                     x=self.model_x.value(), y=self.model_y.value(), z=self.model_z.value(),
                     angle=self.model_angle.value(), plane=self.plane.currentData())
        else:
            d.update(height=self.sheet_height.value(),
                     paper_x=self.paper_x.value(), paper_y=self.paper_y.value(),
                     angle=self.paper_angle.value(), pen_mm=self.pen_mm.value())
        return d

    def _compile(self, target, params=None):
        d = params if params is not None else self._params(target)
        max_lines = MAX_MODEL_SEGMENTS if target == "model" else MAX_SHEET_SEGMENTS
        strokes = build_strokes(
            d["font"], d["text"], d["height"],
            width_factor=d["width_factor"], tracking=d["tracking"],
            line_spacing=d["line_spacing"], alignment=d["alignment"],
            encoding=d["encoding"], max_segments=max_lines)
        return strokes, d

    def _scan_glyphs(self):
        try:
            report = check_glyphs(self.font_path.text().strip(),
                                  self.text_box.toPlainText(),
                                  encoding=self.encoding.currentData())
            if not report.ok:
                self._error(str(GlyphCoverageError(report)), report.full_report())
            else:
                msg = (f"{report.font_name}: all {report.checked_characters} "
                       f"non-space characters found. "
                       f"{len(report.mapped_legacy)} unique legacy CP874 glyph(s).")
                self.feedback.setText("✓ " + msg)
                QMessageBox.information(self, "GO SHX: glyph scan", msg)
        except SHXTextError as e:
            self._error(str(e))

    def _preview(self):
        try:
            target = "model" if self.tabs.currentIndex() == 0 else "sheet"
            stroke, d = self._compile(target)
            self.preview.set_paths(stroke.paths)
            self._notify_result(stroke)
        except GlyphCoverageError as e:
            self.preview.set_paths([])
            self._error(str(e), e.report.full_report())
        except (SHXTextError, ValueError) as e:
            self.preview.set_paths([])
            self._error(str(e))

    def _notify_result(self, result):
        tail = (" · legacy Thai: " + "".join(result.mapped_legacy)
                if result.mapped_legacy else "")
        self.feedback.setText(
            f"{result.font_name} · {result.segments:,} line segments · "
            f"width ≈ {result.width:.3f} (current units){tail}")

    def _error(self, message, details=None):
        self.feedback.setText("⚠ " + message)
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Warning)
        box.setWindowTitle("GO SHX Stroke Text")
        box.setText(message)
        if details:
            box.setDetailedText(details)
            box.setInformativeText("Click Show Details for the FULL missing-glyph list.")
        box.exec()

    def _load_model_selection(self):
        group = selected_stroke_group(self.app.scene)
        if group is None:
            self._error("Select a GO SHX text Group in the model first.")
            return
        try:
            # Current placement, not stale origin recorded at first Create.
            p = effective_parameters(group)
        except (ValueError, SHXTextError) as e:
            self._loaded_group_uid = None
            self._error(str(e))
            return
        self.font_path.setText(str(p.get("font", "")))
        self.text_box.setPlainText(str(p.get("text", "")))
        self.model_height.setValue(float(p.get("height", 0.3)))
        for key, w in (("x", self.model_x), ("y", self.model_y),
                       ("z", self.model_z), ("angle", self.model_angle)):
            w.setValue(float(p.get(key, 0)))
        i = self.plane.findData(p.get("plane", "XY"))
        if i >= 0:
            self.plane.setCurrentIndex(i)
        self._set_common_params(p)
        self._font_diagnostics()
        self._loaded_group_uid = group.uid
        self._loaded_visible = {"x": self.model_x.value(),
                                "y": self.model_y.value(),
                                "z": self.model_z.value()}
        self.feedback.setText(
            "Loaded selected SHX Group at CURRENT model position · "
            "Edit fields and click Update Selected")

    def _params_for_replacement(self, old):
        if self._loaded_group_uid != old.uid:
            raise ValueError(
                "Select the target Group and click 'Load selected text' first, "
                "or double-click the GO SHX Group. No geometry was changed.")
        current = effective_parameters(old)
        params = self._params("model")
        # If a coordinate has not been changed in the dialog, keep its exact
        # current floating-point value instead of rounding to the 0.001m
        # QDoubleSpinBox display precision. Moving WHILE dialog is open also
        # survives Update. An explicitly edited coordinate always wins.
        return merge_updated_position(
            params, current, self._loaded_visible,
            {"x": self.model_x.value(), "y": self.model_y.value(),
             "z": self.model_z.value()})

    def _create_model(self, replace=False):
        try:
            old = selected_stroke_group(self.app.scene) if replace else None
            if replace and old is None:
                raise ValueError("Select a GO SHX text Group before updating.")
            params = (self._params_for_replacement(old)
                      if replace else self._params("model"))
            strokes, params = self._compile("model", params=params)
            group = create_model_group(strokes, params, previous=old)
            commit_model(self.app, group, old)
            self._save_settings()
            self._load_model_selection()
            self._notify_result(strokes)
            verb = "Updated selected" if replace else "Created"
            self.feedback.setText(f"{verb} native model Group · " + self.feedback.text())
        except GlyphCoverageError as e:
            self._error(str(e), e.report.full_report())
        except (SHXTextError, ValueError, RuntimeError, ImportError) as e:
            self._error(str(e))

    def _create_sheet(self):
        try:
            if self.sheet_idx.currentData() is None:
                raise ValueError("Create a Sheet in Sheet Composer first, then reopen this dialog.")
            strokes, params = self._compile("sheet")
            group_id = self.sheet_entry.currentData()
            uid, count, composer = commit_sheet(
                self.app, self.sheet_idx.currentData(), strokes, params,
                group_id=group_id)
            self._save_settings()
            self._refresh_sheet_entries()
            i = self.sheet_entry.findData(uid)
            if i >= 0:
                self.sheet_entry.setCurrentIndex(i)
            self._notify_result(strokes)
            self.feedback.setText(f"Created {count} Composer stroke lines as ONE Undo step")
            composer.show_sheet(self.sheet_idx.currentData())
        except GlyphCoverageError as e:
            self._error(str(e), e.report.full_report())
        except (SHXTextError, ValueError, RuntimeError, ImportError) as e:
            self._error(str(e))

    def _delete_sheet(self):
        uid = self.sheet_entry.currentData()
        if uid is None:
            self._error("Select an existing stroke text in the Sheet list first.")
            return
        index = self.sheet_idx.currentData()
        try:
            ident, _count, composer = commit_sheet(self.app, index,
                                                  group_id=uid, delete=True)
            self._refresh_sheet_entries()
            self.feedback.setText("Deleted GO SHX sheet text · Composer Undo will restore it")
            composer.show_sheet(index)
        except (ValueError, RuntimeError) as e:
            self._error(str(e))

    def _export_sheet_dxf(self):
        index = self.sheet_idx.currentData()
        if index is None:
            self._error("Create a Sheet in Sheet Composer first.")
            return
        if not sheet_entries(self.app.scene, index):
            self._error("There are no GO SHX stroke texts on this Sheet to export.")
            return
        path, _f = QFileDialog.getSaveFileName(
            self, "Export GO SHX paper-space vectors",
            "GO_SHX_sheet_lines.dxf", "DXF files (*.dxf)")
        if not path:
            return
        if not path.lower().endswith(".dxf"):
            path += ".dxf"
        try:
            n = export_sheet_strokes_dxf(self.app.scene, index, path)
            self.feedback.setText(
                f"Exported {n:,} SHX sheet line segments to {Path(path).name} "
                "(mm, vector DXF; other sheet annotations excluded)")
        except (ValueError, ImportError, OSError) as e:
            self._error(str(e))
