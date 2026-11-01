"""Write paper-space strokes as native Composer FormaItem lines, with Undo."""
from __future__ import annotations

from copy import deepcopy
from uuid import uuid4

from .constants import PLUGIN_KEY, SHEET_GROUP_PREFIX, VERSION
from .geometry import iter_paper_lines, normalise_line


def sheet_entries(scene, index: int) -> list[tuple[str, str]]:
    if not (0 <= index < len(scene.compositions)):
        return []
    comp = scene.compositions[index]
    groups = {s.group_id for s in comp.shapes
              if (getattr(s, "group_id", "") or "").startswith(SHEET_GROUP_PREFIX)}
    meta = (scene.plugin_data or {}).get(PLUGIN_KEY, {}) or {}
    records = meta.get("sheet_texts", {})
    return [(k, records.get(k, {}).get("text", "(stroke text)")[:45])
            for k in sorted(groups)]


def sheet_record(scene, uid):
    return ((scene.plugin_data or {}).get(PLUGIN_KEY, {})
            .get("sheet_texts", {}).get(uid, {}))


def make_sheet_shapes(strokes, params, group_id, *, pen_mm=0.18,
                      color="#203e46"):
    from core.composition import FormaItem
    shapes = []
    for i, (a, b) in enumerate(iter_paper_lines(
        strokes.paths, origin=(params["paper_x"], params["paper_y"]),
        angle=params["angle"]
    )):
        kw = normalise_line(a, b)
        shapes.append(FormaItem(kind="linea", **kw,
                                stroke_mm=pen_mm, color=color,
                                group_id=group_id,
                                list_name=f"SHX {params['text'][:22]} · {i+1:03d}"))
    if not shapes:
        raise ValueError("Font produced no drawable strokes.")
    return shapes


class _SheetCommand:
    """ComposerCommand-compatible reversible bulk operation.

    The command owns only items matching our group_id, so unrelated sheet
    objects, names, frames, and native text cannot be touched by Rebuild.
    """
    def __init__(self, scene, comp, uid, shapes, record=None):
        self.scene = scene
        self.comp = comp
        self.uid = uid
        self.shapes = shapes
        self.record = record
        self.prev_data = deepcopy((scene.plugin_data or {}).get(PLUGIN_KEY))
        self.prev_items = [s for s in comp.shapes
                           if getattr(s, "group_id", "") == uid]

    def do(self):
        self.comp.shapes[:] = [s for s in self.comp.shapes
                              if getattr(s, "group_id", "") != self.uid]
        self.comp.shapes.extend(self.shapes)
        root = deepcopy(self.scene.plugin_data.get(PLUGIN_KEY) or {})
        records = root.setdefault("sheet_texts", {})
        if self.record is None:
            records.pop(self.uid, None)
        else:
            records[self.uid] = dict(self.record, schema=1, version=VERSION)
        self.scene.plugin_data[PLUGIN_KEY] = root

    def undo(self):
        self.comp.shapes[:] = [s for s in self.comp.shapes
                              if getattr(s, "group_id", "") != self.uid]
        self.comp.shapes.extend(self.prev_items)
        if self.prev_data is None:
            self.scene.plugin_data.pop(PLUGIN_KEY, None)
        else:
            self.scene.plugin_data[PLUGIN_KEY] = deepcopy(self.prev_data)


def ensure_composer_for_sheet(app, index: int):
    win = app.window
    if not hasattr(win, "_ensure_composer"):
        raise RuntimeError("This IngeTrazo build has no supported Sheet Composer API.")
    composer = win._ensure_composer()
    if not (0 <= index < len(app.scene.compositions)):
        raise RuntimeError("Choose an existing sheet. Create one in Sheet Composer first.")
    if composer.comp is not app.scene.compositions[index]:
        composer.comp_combo.setCurrentIndex(index)
    if composer.comp is not app.scene.compositions[index]:
        raise RuntimeError("Sheet selection failed; reopen Sheet Composer and try again.")
    return composer


def commit_sheet(app, index, strokes=None, params=None, *, group_id=None,
                 delete=False):
    comp = app.scene.compositions[index]
    if group_id is None:
        group_id = SHEET_GROUP_PREFIX + uuid4().hex[:14]
    if delete:
        shape_items = []
        record = None
    else:
        shape_items = make_sheet_shapes(strokes, params, group_id,
                                       pen_mm=params["pen_mm"])
        record = dict(params)
    composer = ensure_composer_for_sheet(app, index)
    composer.history.execute(_SheetCommand(app.scene, comp, group_id,
                                           shape_items, record))
    return group_id, len(shape_items), composer


def export_sheet_strokes_dxf(scene, index: int, destination: str) -> int:
    """Export plugin-owned paper text to independent paper-space DXF.

    The host's built-in 'Export view as DXF' exports frame model graphics,
    not Sheet annotations. Our separate DXF is in millimetres with Cartesian
    +Y up (paper y-down reflected across the page height). No SHX font is
    embedded; line entities retain the appearance even without the font.
    """
    if not 0 <= index < len(scene.compositions):
        raise ValueError("Invalid sheet index")
    comp = scene.compositions[index]
    lines = [s for s in comp.shapes if
             getattr(s, "kind", "") == "linea" and
             (getattr(s, "group_id", "") or "").startswith(SHEET_GROUP_PREFIX)]
    if not lines:
        raise ValueError("No GO SHX stroke lines found on selected sheet")

    import ezdxf
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4   # millimetres
    msp = doc.modelspace()
    _, paper_height = comp.page_size_mm()
    created = set()
    for line in lines:
        # Group identity persists across edits and undo, and DXF layers make
        # different text objects independently selectable in CAD tools.
        layer = "GO_SHX_" + str(line.group_id)[-14:]
        width = max(0, min(211, round(float(line.stroke_mm) * 100)))
        if layer not in created:
            doc.layers.new(layer, dxfattribs={"color": 7, "lineweight": width})
            created.add(layer)
        x, y = float(line.x_mm), float(line.y_mm)
        w, h = float(line.w_mm), float(line.h_mm)
        if line.invert:
            a, b = (x, y + h), (x + w, y)
        else:
            a, b = (x, y), (x + w, y + h)
        a = (a[0], float(paper_height) - a[1])
        b = (b[0], float(paper_height) - b[1])
        msp.add_line(a, b, dxfattribs={"layer": layer})
    doc.saveas(str(destination))
    return len(lines)
