"""Pure geometry conversions for IngeTrazo metres and Composer paper mm."""
from __future__ import annotations
from math import cos, sin, radians


def iter_model_edges(paths, origin=(0.0, 0.0, 0.0), plane="XY", angle=0.0):
    """World-space 3D edges, one segment per stroke segment (model metres)."""
    if plane not in ("XY", "XZ", "YZ"):
        raise ValueError("Unknown text plane")
    ox, oy, oz = map(float, origin)
    c, s = cos(radians(angle)), sin(radians(angle))

    def transform(v):
        x, y = v
        a, b = c*x - s*y, s*x + c*y
        if plane == "XY":
            return ox+a, oy+b, oz
        if plane == "XZ":
            return ox+a, oy, oz+b
        return ox, oy+a, oz+b

    for poly in paths:
        for a, b in zip(poly, poly[1:]):
            p, q = transform(a), transform(b)
            if any(abs(u-v)>1e-9 for u, v in zip(p, q)):
                yield p, q


def iter_paper_lines(paths, origin=(20.0, 20.0), angle=0.0):
    """Sheet-local lines: X right, Y DOWN (sheet millimetres)."""
    ox, oy = map(float, origin)
    c, s = cos(radians(angle)), sin(radians(angle))

    def transform(v):
        x, y = v
        return (ox + c*x - s*y, oy - (s*x + c*y))

    for poly in paths:
        for a, b in zip(poly, poly[1:]):
            p, q = transform(a), transform(b)
            if abs(p[0]-q[0]) + abs(p[1]-q[1]) > 1e-8:
                yield p, q


def normalise_line(p, q):
    """Map a pair of arbitrary endpoints to a positive-size FormaItem box."""
    dx, dy = q[0] - p[0], q[1] - p[1]
    return {
        "x_mm": min(p[0], q[0]), "y_mm": min(p[1], q[1]),
        "w_mm": max(abs(dx), 0.001),
        "h_mm": max(abs(dy), 0.001),
        "invert": dx * dy < 0.0,
    }
