from __future__ import annotations
import struct
import pytest

from go_shx_stroke_text.engine import build_strokes, inspect_font, SHXTextError
from go_shx_stroke_text.geometry import iter_model_edges, iter_paper_lines, normalise_line


def make_shx(tmp_path, extra_codes=()):
    """Build an original, synthetic SHX test font. No proprietary font copied."""
    # Char data: unsigned shape codes. 0 record carries font metrics.
    records = {
        0: (b"FONT", bytes([10, 2, 0, 0])),
        32: (b"SP", bytes([2, 0x30, 0])),
        65: (b"A", bytes([0x74, 0x70, 0x7C, 2, 0x30, 0])),
        66: (b"B", bytes([0x74, 0x70, 0x7C, 2, 0x30, 0])),
        0xA1: (b"THAI-KO", bytes([0x74, 0x70, 0x7C, 2, 0x30, 0])),
    }
    for c in extra_codes:
        records[int(c)] = (f"EXTRA-{c}".encode("ascii"),
                           bytes([0x74, 0x70, 0x7C, 2, 0x30, 0]))
    ordered = sorted(records.items())
    head = b"AutoCAD-86 shapes 1.0\r\n" + b"\x1a"
    assert len(head) == 24
    header = struct.pack("<HHH", ordered[0][0], ordered[-1][0], len(ordered))
    rows = [(code, len(name) + 1 + len(data))
            for code, (name, data) in ordered]
    index = b"".join(struct.pack("<HH", *row) for row in rows)
    record_bytes = b"".join(name + b"\x00" + data for _code, (name, data) in ordered)
    p = tmp_path / "original_test.shx"
    p.write_bytes(head + header + index + record_bytes + b"EOF")
    return p


def test_real_binary_shx_decodes_stroke_not_outline(tmp_path):
    file = make_shx(tmp_path)
    result = build_strokes(str(file), "AB", 0.3)
    assert result.segments >= 6
    assert len(result.paths) > 0
    assert result.width > 0.3
    assert result.mapped_legacy == ()
    assert inspect_font(str(file))["glyph_count"] == 4


def test_cp874_fallback_reads_thai_from_a_shx_slot(tmp_path):
    file = make_shx(tmp_path)
    result = build_strokes(str(file), "ก A", 0.3, encoding="auto")
    assert result.segments > 0
    assert "ก" in result.mapped_legacy


def test_missing_thai_glyph_is_error_not_ttf_fallback(tmp_path):
    file = make_shx(tmp_path)
    with pytest.raises(SHXTextError, match="Glyph missing"):
        build_strokes(str(file), "ข", 1.0)


def test_multiline_right_alignment_and_spacing(tmp_path):
    file = make_shx(tmp_path)
    result = build_strokes(str(file), "AB\nA", 1.0, alignment="right")
    assert result.height == pytest.approx(2.5)
    assert result.width > 1.0
    assert any(y < 0 for poly in result.paths for _, y in poly)


def test_protect_segment_limit(tmp_path):
    file = make_shx(tmp_path)
    with pytest.raises(SHXTextError, match="Too many"):
        build_strokes(str(file), "AAAA", 1.0, max_segments=4)


def test_coordinate_transform_and_sheet_inverted_y():
    paths = [[(0.0, 0.0), (1.0, 1.0)], [(0.0, 0.0), (0.0, 2.0)]]
    model = list(iter_model_edges(paths, (3, 4, 5), "XZ", 0))
    assert model[0] == ((3, 4, 5), (4, 4, 6))
    paper = list(iter_paper_lines(paths, (20, 30), 0))
    assert paper[0] == ((20, 30), (21, 29))
    assert paper[1] == ((20, 30), (20, 28))
    line = normalise_line(paper[0][0], paper[0][1])
    assert line["invert"] is True
    assert line["w_mm"] > 0 and line["h_mm"] > 0


def test_unsupported_font_is_explicit_error(tmp_path):
    file = tmp_path / "not-shx.shx"
    file.write_bytes(b"not really a font")
    with pytest.raises(SHXTextError, match="Could not decode"):
        build_strokes(str(file), "AB", 0.3)
