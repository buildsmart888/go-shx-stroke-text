"""Regressions reported by Windows user on the original v0.1.0 extension."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from tests.test_engine import make_shx
from tests.test_sheet_and_model import fake_model
from go_shx_stroke_text.constants import PLUGIN_KEY
from go_shx_stroke_text.engine import (GlyphCoverageError, build_strokes,
                                       check_glyphs)
from go_shx_stroke_text.model_host import create_model_group, commit_model
from go_shx_stroke_text.pose import effective_parameters, merge_updated_position


def _params(font, text="AB"):
    return dict(font=str(font), text=text, x=1.2, y=-2.3, z=0.4,
                height=0.3, plane="XY", angle=0.0, alignment="left",
                encoding="auto", tracking=0.0, line_spacing=1.5,
                width_factor=1.0)


def _move_group(group, dx, dy, dz):
    def move(p):
        return tuple(v + delta for v, delta in zip(p, (dx, dy, dz)))
    group.mesh.edges = [(move(a), move(b)) for a, b in group.mesh.edges]


def test_one_pass_all_missing_thai_glyphs_report(tmp_path):
    font = make_shx(tmp_path)
    report = check_glyphs(str(font), "ABC ขฃ๑ ข๑ ก", encoding="cp874")
    assert report.missing == ("C", "ข", "ฃ", "๑")
    assert report.mapped_legacy == ("ก",)
    assert "U+0E51" in report.full_report()
    assert "0xF1" in report.full_report()
    assert len(report.full_report().splitlines()) > 5
    with pytest.raises(GlyphCoverageError) as ex:
        build_strokes(str(font), "๑ขฃ๑", 0.3)
    assert ex.value.report.missing == ("๑", "ข", "ฃ")
    assert "U+0E51" in str(ex.value)


def test_old_and_new_move_then_update_preserve_absolute_geometry(tmp_path, fake_model):
    font = make_shx(tmp_path)
    app, history = fake_model
    p = _params(font)
    strokes = build_strokes(str(font), "AB", 0.3)
    for old_version in (False, True):
        group = create_model_group(strokes, p)
        if old_version:
            # Simulate an object that already exists in a v0.1.0 .igz.
            meta = group.ext[PLUGIN_KEY]
            meta.pop("reference_bounds")
            meta["version"], meta["schema"] = "0.1.0", 1
        commit_model(app, group)
        dx, dy, dz = 1.234567, -0.876543, 0.123456
        _move_group(group, dx, dy, dz)
        recovered = effective_parameters(group)
        assert recovered["x"] == pytest.approx(p["x"] + dx)
        assert recovered["y"] == pytest.approx(p["y"] + dy)
        assert recovered["z"] == pytest.approx(p["z"] + dz)
        updated = dict(recovered, text="A")
        new_strokes = build_strokes(str(font), "A", 0.3)
        replacement = create_model_group(new_strokes, updated, previous=group)
        old_uid = group.uid
        commit_model(app, replacement, old=group)
        assert replacement.uid == old_uid
        assert replacement.layer == group.layer
        assert replacement.ext[PLUGIN_KEY]["schema"] == 2
        assert len(replacement.mesh.edges) > 0
        assert effective_parameters(replacement)["x"] == pytest.approx(p["x"] + dx)
        # Replacing is one undo operation; user-created Group comes back.
        history.cmd.undo(app.scene)
        assert group in app.scene.groups
        assert replacement not in app.scene.groups
        history.cmd.do(app.scene)
        assert replacement in app.scene.groups
        app.scene.groups.clear()


def test_legacy_unicode_mark_metrics_reconstruction(tmp_path, fake_model):
    font = make_shx(tmp_path)
    # All listed chars have glyph slots in the synthetic font; the old
    # kerning algorithm must be selected for a saved v0.1 text.
    app, _ = fake_model
    p = _params(font, "กA")
    strokes = build_strokes(str(font), p["text"], 0.3,
                            legacy_mark_positions=True)
    group = create_model_group(strokes, p)
    group.ext[PLUGIN_KEY].pop("reference_bounds")
    group.ext[PLUGIN_KEY]["version"] = "0.1.0"
    commit_model(app, group)
    _move_group(group, 0.25, 0.1, 0.0)
    assert effective_parameters(group)["x"] == pytest.approx(1.45)


def test_move_after_load_keeps_precision_but_explicit_edits_win():
    current = {"x": 0.123456789, "y": 4.123456789, "z": -2.000012345}
    form = {"text": "changed", "x": 0.123, "y": 4.125, "z": -2.0}
    loaded = {"x": 0.123, "y": 4.123, "z": -2.0}
    shown = {"x": 0.123, "y": 4.125, "z": -2.0}
    got = merge_updated_position(form, current, loaded, shown)
    assert got["x"] == current["x"]
    assert got["y"] == 4.125
    assert got["z"] == current["z"]


def test_update_rejects_nontranslation_geometry(tmp_path, fake_model):
    font = make_shx(tmp_path)
    group = create_model_group(build_strokes(str(font), "AB", 0.3), _params(font))
    # Changing one edge rather than translating all of them must not be
    # mistaken for a move: leave the saved, valid text untouched.
    a, b = group.mesh.edges[0]
    group.mesh.edges[0] = (a, (b[0] + 0.1, b[1], b[2]))
    with pytest.raises(ValueError, match="rotated, scaled or its edges"):
        effective_parameters(group)


def test_v02_position_metadata_works_without_source_font(tmp_path, fake_model):
    font = make_shx(tmp_path)
    g = create_model_group(build_strokes(str(font), "AB", 0.3), _params(font))
    font.unlink()
    _move_group(g, 7.5, -1.5, 0.2)
    actual = effective_parameters(g)
    assert actual["x"] == pytest.approx(8.7)
    assert actual["y"] == pytest.approx(-3.8)
    assert actual["z"] == pytest.approx(0.6)


def test_thai_vowel_with_zero_combining_class_no_longer_advances_pen(tmp_path):
    import unicodedata
    mark = "ิ"   # U+0E34, category Mn, combining class 0
    assert unicodedata.category(mark) == "Mn"
    assert unicodedata.combining(mark) == 0
    font = make_shx(tmp_path, extra_codes=(mark.encode("cp874")[0],))
    base = build_strokes(str(font), "ก", 0.3)
    fixed = build_strokes(str(font), "กิ", 0.3)
    legacy = build_strokes(str(font), "กิ", 0.3,
                           legacy_mark_positions=True)
    assert fixed.width == pytest.approx(base.width)
    assert legacy.width > fixed.width
    assert fixed.segments > base.segments
