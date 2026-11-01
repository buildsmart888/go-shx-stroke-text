"""Contract checks for non-Qt adapter logic and real ezdxf round-trip.

These tests intentionally use small API stubs. Installed IngeTrazo smoke tests
are separate and required before a compatibility claim.
"""
from __future__ import annotations

import sys
import types
from types import SimpleNamespace

import ezdxf
import pytest

from go_shx_stroke_text.constants import LAYER_NAME, PLUGIN_KEY, SHEET_GROUP_PREFIX
from go_shx_stroke_text.engine import StrokeText
from go_shx_stroke_text.sheet_host import (
    _SheetCommand, export_sheet_strokes_dxf, make_sheet_shapes,
    sheet_entries, sheet_record,
)
from go_shx_stroke_text.geometry import normalise_line


class FakeFormaItem:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class FakeComp:
    def __init__(self):
        self.shapes = []

    def page_size_mm(self):
        return 297.0, 210.0


@pytest.fixture
def fake_composer(monkeypatch):
    core = types.ModuleType("core")
    core.__path__ = []
    composition = types.ModuleType("core.composition")
    composition.FormaItem = FakeFormaItem
    monkeypatch.setitem(sys.modules, "core", core)
    monkeypatch.setitem(sys.modules, "core.composition", composition)
    comp = FakeComp()
    scene = SimpleNamespace(compositions=[comp], plugin_data={})
    return scene, comp


def test_sheet_geometry_metadata_undo_redo(fake_composer):
    scene, comp = fake_composer
    strokes = StrokeText(
        paths=[[(0.0, 0.0), (5.0, 5.0), (7.0, 5.0)]],
        width=7.0, height=5.0, segments=2, font_name="original.shx", mapped_legacy=(),
    )
    uid = SHEET_GROUP_PREFIX + "abc123"
    param = {"paper_x": 30.0, "paper_y": 40.0, "angle": 0.0,
             "text": "GO", "font": "original.shx", "pen_mm": 0.18}
    untouched = FakeFormaItem(group_id="user_drawing", kind="rect")
    comp.shapes.append(untouched)
    shapes = make_sheet_shapes(strokes, param, uid)
    assert len(shapes) == 2
    command = _SheetCommand(scene, comp, uid, shapes, record=param)
    command.do()
    assert len(sheet_entries(scene, 0)) == 1
    assert sheet_record(scene, uid)["font"] == "original.shx"
    assert untouched in comp.shapes
    assert len(comp.shapes) == 3
    command.undo()
    assert comp.shapes == [untouched]
    assert scene.plugin_data == {}
    command.do()
    assert len(comp.shapes) == 3
    assert scene.plugin_data[PLUGIN_KEY]["sheet_texts"][uid]["schema"] == 1


def test_sheet_replacement_then_restore_previous(fake_composer):
    scene, comp = fake_composer
    uid = SHEET_GROUP_PREFIX + "abcd"
    old = FakeFormaItem(group_id=uid, kind="linea", x_mm=1, y_mm=2,
                        w_mm=3, h_mm=4, invert=False, stroke_mm=0.18)
    comp.shapes = [old]
    scene.plugin_data[PLUGIN_KEY] = {"sheet_texts": {uid: {"text": "OLD"}}}
    new = FakeFormaItem(group_id=uid, kind="linea", x_mm=9, y_mm=9,
                        w_mm=1, h_mm=1, invert=False, stroke_mm=0.18)
    cmd = _SheetCommand(scene, comp, uid, [new], record={"text": "NEW"})
    cmd.do()
    assert comp.shapes == [new]
    cmd.undo()
    assert comp.shapes == [old]
    assert sheet_record(scene, uid)["text"] == "OLD"


def test_sheet_dxf_roundtrip_and_selective_export(fake_composer, tmp_path):
    scene, comp = fake_composer
    uid = SHEET_GROUP_PREFIX + "abc123"
    kw = normalise_line((20.0, 30.0), (30.0, 25.0))
    comp.shapes = [
        FakeFormaItem(group_id=uid, kind="linea", stroke_mm=0.18, **kw),
        FakeFormaItem(group_id="NOT_SHX", kind="linea", stroke_mm=0.18, **kw),
    ]
    output = tmp_path / "sheet_vector.dxf"
    n = export_sheet_strokes_dxf(scene, 0, str(output))
    assert n == 1
    doc = ezdxf.readfile(output)
    lines = list(doc.modelspace().query("LINE"))
    assert len(lines) == 1
    assert doc.header["$INSUNITS"] == 4
    p, q = lines[0].dxf.start, lines[0].dxf.end
    assert (p.x, p.y) == pytest.approx((20, 180))
    assert (q.x, q.y) == pytest.approx((30, 185))
    assert lines[0].dxf.layer.startswith("GO_SHX_")


def test_dxf_export_rejects_empty(fake_composer, tmp_path):
    scene, _ = fake_composer
    with pytest.raises(ValueError, match="No GO SHX"):
        export_sheet_strokes_dxf(scene, 0, str(tmp_path / "empty.dxf"))


@pytest.fixture
def fake_model(monkeypatch):
    pyside = types.ModuleType("PySide6")
    pyside.__path__ = []
    qtgui = types.ModuleType("PySide6.QtGui")
    qtgui.QVector3D = lambda *xyz: tuple(xyz)
    monkeypatch.setitem(sys.modules, "PySide6", pyside)
    monkeypatch.setitem(sys.modules, "PySide6.QtGui", qtgui)

    core = types.ModuleType("core")
    core.__path__ = []
    group_mod = types.ModuleType("core.group")
    mesh_mod = types.ModuleType("core.mesh")
    history_mod = types.ModuleType("core.history")
    layers_mod = types.ModuleType("core.layers")

    class Mesh:
        def __init__(self):
            self.edges = []

        def add_edge(self, a, b):
            self.edges.append((a, b))

    class Group:
        def __init__(self, mesh, name):
            self.mesh, self.name = mesh, name
            self.uid = "original_uid"
            self.ext = None
            self.layer = None
            self.material = None
            self.hidden = False
            self.locked = False

    class Layer:
        def __init__(self, name, **kwargs):
            self.name = name

    group_mod.Group = Group
    mesh_mod.Mesh = Mesh
    history_mod.Command = object
    layers_mod.Layer = Layer
    for name, module in (("core", core), ("core.group", group_mod),
                         ("core.mesh", mesh_mod), ("core.history", history_mod),
                         ("core.layers", layers_mod)):
        monkeypatch.setitem(sys.modules, name, module)

    scene = SimpleNamespace(groups=[], layers=[], selection=set(), version=0)

    class History:
        def __init__(self):
            self.cmd = None
            self.last_error = None
        def execute(self, cmd):
            self.cmd = cmd
            cmd.do(scene)

    history = History()
    vp = SimpleNamespace(history=history, notify_scene_changed=lambda: None)
    app = SimpleNamespace(scene=scene, viewport=vp)
    return app, history


def test_model_group_create_and_undo_replace(fake_model):
    from go_shx_stroke_text.model_host import create_model_group, commit_model
    app, history = fake_model
    strokes = StrokeText([[(0, 0), (1, 1)]], 1, 1, 1, "original.shx", ())
    params = {"x": 0, "y": 0, "z": 0, "plane": "XY", "angle": 0,
              "text": "GO", "font": "original.shx"}
    obj = create_model_group(strokes, params)
    commit_model(app, obj)
    assert len(app.scene.groups) == 1
    assert app.scene.layers[0].name == LAYER_NAME
    history.cmd.undo(app.scene)
    assert not app.scene.groups and not app.scene.layers
    history.cmd.do(app.scene)
    assert len(app.scene.groups) == 1
    newer = create_model_group(strokes, dict(params, text="NEW"), previous=obj)
    commit_model(app, newer, old=obj)
    assert app.scene.groups == [newer]
    assert newer.uid == obj.uid
    history.cmd.undo(app.scene)
    assert app.scene.groups == [obj]
