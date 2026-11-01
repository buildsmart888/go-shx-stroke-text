"""Convert REAL SHX/SHP glyphs to stroke paths using ezdxf, not TTF outlines.

Pure Python + ezdxf; no PySide6 or IngeTrazo imports. Model units and sheet
units are supplied by the caller and must not be mixed. The source font is
opened by its full filesystem path -- no font-manager mapping or TTF fallback.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from math import isfinite
from pathlib import Path
import unicodedata

from .constants import MAX_FONT_BYTES, MAX_TEXT_LENGTH


class SHXTextError(ValueError):
    """Missing/unsupported font, unavailable glyph, or invalid input."""


@dataclass(frozen=True)
class GlyphCoverage:
    """A complete one-pass report, not only the first missing glyph."""
    font_name: str
    total_characters: int
    checked_characters: int
    missing: tuple[str, ...]
    mapped_legacy: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.missing

    @staticmethod
    def describe(ch: str) -> str:
        code = f"U+{ord(ch):04X}"
        try:
            raw = ch.encode("cp874")
            legacy = f", CP874 0x{raw[0]:02X}" if len(raw) == 1 else ""
        except UnicodeEncodeError:
            legacy = ""
        label = {"\t": "TAB", "\n": "NEWLINE"}.get(ch, ch)
        return f"{label} ({code}{legacy})"

    def full_report(self) -> str:
        lines = [f"Font: {self.font_name}",
                 f"Characters checked: {self.checked_characters}",
                 f"Missing glyphs: {len(self.missing)} unique character(s)"]
        lines.extend(f"  {i:02d}. {self.describe(ch)}"
                     for i, ch in enumerate(self.missing, 1))
        if self.mapped_legacy:
            lines.append(f"Legacy CP874 mapped: {len(self.mapped_legacy)} unique character(s)")
        if self.missing:
            lines.append("The SHX may lack the glyph, or use a private character map. "
                         "Select a compatible font or remap at the source; no TTF fallback is used.")
        return "\n".join(lines)


class GlyphCoverageError(SHXTextError):
    def __init__(self, report: GlyphCoverage):
        self.report = report
        samples = ", ".join(report.describe(ch) for ch in report.missing[:8])
        extra = (f", +{len(report.missing) - 8} more" if len(report.missing) > 8 else "")
        super().__init__(f"Glyph missing from {report.font_name}: "
                         f"{len(report.missing)} unique character(s): {samples}{extra}. "
                         "View the full glyph report for all characters.")


@dataclass
class StrokeText:
    paths: list[list[tuple[float, float]]]
    width: float
    height: float
    segments: int
    font_name: str
    mapped_legacy: tuple[str, ...]


def _font_stat(filename: str) -> tuple[str, int, int]:
    path = Path(filename).expanduser().resolve()
    if path.suffix.lower() not in (".shx", ".shp"):
        raise SHXTextError("Choose a .shx or .shp stroke font, not a .ttf or .otf file.")
    try:
        stat = path.stat()
    except OSError as e:
        raise SHXTextError(f"Cannot open font: {path} ({e})") from e
    if not (0 < stat.st_size <= MAX_FONT_BYTES):
        raise SHXTextError("Font file is empty or larger than 12 MB.")
    return str(path), stat.st_size, stat.st_mtime_ns


@lru_cache(maxsize=5)
def _open_font(path: str, _size: int, _mtime_ns: int):
    try:
        from ezdxf.fonts import shapefile
    except ImportError as e:
        raise SHXTextError(
            "This IngeTrazo Python environment needs ezdxf >= 1.1."
        ) from e
    try:
        font = shapefile.readfile(path)
        cache = shapefile.GlyphCache(font)
        if not font.shapes:
            raise SHXTextError("No glyphs found in the SHX/SHP font.")
        return font, cache
    except SHXTextError:
        raise
    except Exception as e:
        # E.g. ezdxf currently does not support AutoCAD BIGFONT SHX.
        raise SHXTextError(f"Could not decode the font as SHX/SHP: {e}") from e


def inspect_font(filename: str) -> dict:
    path, size, stamp = _font_stat(filename)
    font, _cache = _open_font(path, size, stamp)
    codes = font.shapes
    return {
        "name": Path(path).name,
        "glyph_count": len(codes),
        "thai_unicode": sum(0x0E00 <= n <= 0x0E7F for n in codes),
        "thai_cp874_slots": sum(0xA1 <= n <= 0xFB for n in codes),
        "file_bytes": size,
    }


def _glyph_number(ch: str, shapes: dict, encoding: str) -> tuple[int | None, bool]:
    cp = ord(ch)
    legacy_cp = None
    if encoding in ("auto", "cp874"):
        try:
            data = ch.encode("cp874")
            if len(data) == 1:
                legacy_cp = data[0]
        except (UnicodeEncodeError, LookupError):
            pass
    if encoding == "cp874" and legacy_cp is not None and legacy_cp in shapes:
        return legacy_cp, legacy_cp != cp
    if cp in shapes:
        return cp, False
    if legacy_cp is not None and legacy_cp in shapes:
        return legacy_cp, True
    return None, False


def _coverage_from_shapes(font_name: str, text: str, shapes: dict,
                          encoding: str) -> GlyphCoverage:
    missing, mapped = [], []
    seen_missing, seen_mapped = set(), set()
    checked = 0
    for ch in text:
        if ch.isspace():
            continue
        checked += 1
        code, legacy = _glyph_number(ch, shapes, encoding)
        if code is None and ch not in seen_missing:
            missing.append(ch)
            seen_missing.add(ch)
        if code is not None and legacy and ch not in seen_mapped:
            mapped.append(ch)
            seen_mapped.add(ch)
    return GlyphCoverage(font_name, len(text), checked, tuple(missing),
                         tuple(mapped))


def check_glyphs(filename: str, text: str, *, encoding: str = "auto") -> GlyphCoverage:
    """Inspect ALL characters without constructing geometry, useful for Thai fonts.

    Does not report glyphs as supported merely because the codepoint is in a
    Thai-looking range: it checks every character against actual SHX slots.
    """
    if encoding not in ("auto", "unicode", "cp874"):
        raise SHXTextError("Encoding must be auto, unicode, or cp874.")
    if not isinstance(text, str) or not text.strip():
        raise SHXTextError("Enter some text.")
    if len(text) > MAX_TEXT_LENGTH:
        raise SHXTextError(f"Text is longer than {MAX_TEXT_LENGTH} characters.")
    path, size, stamp = _font_stat(filename)
    font, _cache = _open_font(path, size, stamp)
    return _coverage_from_shapes(Path(path).name, text, font.shapes, encoding)


def build_strokes(
    filename: str,
    text: str,
    height: float,
    *,
    width_factor: float = 1.0,
    tracking: float = 0.0,
    line_spacing: float = 1.5,
    alignment: str = "left",
    encoding: str = "auto",
    flatten_tolerance: float | None = None,
    max_segments: int = 16000,
    legacy_mark_positions: bool = False,
) -> StrokeText:
    """Stroke geometry in local XY; origin is the FIRST LINE's baseline.

    +Y is UP. Height, tracking and tolerance use the SAME units as output.
    Both shape-file Unicode glyph numbers and legacy CP874 slots are supported.
    Missing non-whitespace glyphs cause an error instead of silent tofu/TTF.
    Thai vowel/tone combining marks have a basic anchor approximation; exact
    shaping cannot be promised for legacy SHX fonts.
    """
    if not isinstance(text, str) or not text.strip():
        raise SHXTextError("Enter some text.")
    if len(text) > MAX_TEXT_LENGTH:
        raise SHXTextError(f"Text is longer than {MAX_TEXT_LENGTH} characters.")
    if alignment not in ("left", "center", "right"):
        raise SHXTextError("Alignment must be left, center, or right.")
    if encoding not in ("auto", "unicode", "cp874"):
        raise SHXTextError("Encoding must be auto, unicode, or cp874.")
    for x, name, lo, hi in ((height, "height", 1e-5, 1e5),
                            (width_factor, "width_factor", 0.1, 10.0),
                            (line_spacing, "line_spacing", 0.8, 10.0)):
        if not isfinite(x) or not lo <= x <= hi:
            raise SHXTextError(f"Invalid {name}.")
    if not isfinite(tracking) or not -0.5 <= tracking <= 2.0:
        raise SHXTextError("Tracking must be between -0.5 and 2.0 of text height.")
    path, size, stamp = _font_stat(filename)
    font, cache = _open_font(path, size, stamp)
    coverage = _coverage_from_shapes(Path(path).name, text, font.shapes, encoding)
    if not coverage.ok:
        raise GlyphCoverageError(coverage)
    try:
        scale_y = cache.get_scaling_factor(height)
        if not isfinite(scale_y) or scale_y <= 0:
            raise SHXTextError("The font has invalid cap height information.")
        scale_x = scale_y * width_factor
        # A tiny fraction of cap height, adjusted to the requested output size.
        tolerance = (height * 0.004 if flatten_tolerance is None
                     else float(flatten_tolerance))
        if not isfinite(tolerance) or tolerance <= 0:
            raise SHXTextError("Invalid arc flattening tolerance.")

        all_lines = []
        widest = 0.0
        mapped = set()
        n_segments = 0
        lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        for row, line in enumerate(lines):
            x = 0.0
            y = -row * height * line_spacing
            strokes = []
            last_base_x = None
            last_base_advance = 0.0
            for ch in line:
                if ch == "\t":
                    x += 4.0 * cache.space_width * scale_x
                    last_base_x = None
                    continue
                if ch.isspace():
                    x += cache.space_width * scale_x
                    last_base_x = None
                    continue
                code, legacy = _glyph_number(ch, font.shapes, encoding)
                # All missing glyphs were reported before any geometry work.
                if code is None:
                    raise GlyphCoverageError(coverage)
                if legacy:
                    mapped.add(ch)
                glyph = cache.get_shape(code)
                # A few fonts return an incorrect width; reject NaN and use
                # spacing only when an actual non-combining glyph was drawn.
                adv = float(cache.get_advance_width(code)) * scale_x
                if not isfinite(adv):
                    raise SHXTextError("Font contains a non-finite glyph width.")
                # Thai combining marks have Unicode category Mn but combining
                # class zero. Checking combining() alone wrongly advances the
                # pen for many Thai above/below vowels and tone marks.
                is_mark = (unicodedata.combining(ch) != 0 if legacy_mark_positions
                           else unicodedata.category(ch) in ("Mn", "Me"))
                place_x = x
                if is_mark and last_base_x is not None:
                    # SHX doesn't encode complex text shaping. Position a
                    # combining mark near the middle of the preceding letter.
                    place_x = last_base_x + last_base_advance * 0.35
                for sub in glyph.to_path().sub_paths():
                    pts = list(sub.flattening(distance=tolerance / max(scale_y, 1e-12),
                                              segments=4))
                    if len(pts) < 2:
                        continue
                    out = [(float(v.x) * scale_x + place_x,
                            float(v.y) * scale_y + y) for v in pts]
                    dedup = []
                    for v in out:
                        if not dedup or (abs(v[0]-dedup[-1][0]) +
                                         abs(v[1]-dedup[-1][1]) > 1e-11):
                            dedup.append(v)
                    out = dedup
                    if len(out) < 2:
                        continue
                    n_segments += len(out) - 1
                    if n_segments > max_segments:
                        raise SHXTextError(
                            f"Too many stroke segments ({n_segments} > {max_segments}). "
                            "Use shorter text or fewer details."
                        )
                    strokes.append(out)
                if not is_mark or last_base_x is None:
                    last_base_x = x
                    last_base_advance = adv
                    x += adv + (height * tracking)
            actual_width = max(0.0, x - (height * tracking if line else 0.0))
            widest = max(widest, actual_width)
            all_lines.append((strokes, actual_width))

        # Align each line independently, not the entire bounding box.
        aligned = []
        for strokes, line_width in all_lines:
            shift = {"left": 0.0, "center": -line_width / 2.0,
                     "right": -line_width}[alignment]
            aligned.extend([[(px + shift, py) for px, py in poly]
                            for poly in strokes])
        return StrokeText(
            paths=aligned, width=widest,
            height=height * (1 + (len(lines)-1) * line_spacing),
            segments=n_segments, font_name=Path(path).name,
            mapped_legacy=tuple(sorted(mapped)),
        )
    except SHXTextError:
        raise
    except Exception as e:
        raise SHXTextError(f"SHX glyph rendering failed: {e}") from e
