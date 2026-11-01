"""Recover a translated native Group's actual insertion from live edges.

IngeTrazo Move translates classic Group mesh vertices but never updates the
extension's group.ext parameters. Before editing, compare the current world
bounds with the bounds AT GENERATION. Persist the latter in v0.2; reproduce
it once using the original SHX parameters for v0.1 documents.

Only a pure translation is recoverable here. Edited/rotated/scaled geometry is
rejected rather than silently replacing the user's geometry with stale text.
"""
from __future__ import annotations

from math import isfinite, sqrt


def _xyz(p):
    if hasattr(p, "x") and callable(p.x):
        return (float(p.x()), float(p.y()), float(p.z()))
    return tuple(float(v) for v in p[:3])


def bounds_from_pairs(pairs):
    lo = [float("inf")] * 3
    hi = [float("-inf")] * 3
    count = 0
    for a, b in pairs:
        for p in (a, b):
            xyz = _xyz(p)
            if not all(isfinite(k) for k in xyz):
                raise ValueError("Group contains non-finite coordinates.")
            for i, v in enumerate(xyz):
                lo[i] = min(lo[i], v)
                hi[i] = max(hi[i], v)
        count += 1
    if not count:
        raise ValueError("This SHX Group has no edges to update.")
    return (tuple(lo), tuple(hi))


def group_bounds(group):
    if getattr(group, "xform", None) is not None:
        raise ValueError("This SHX Group was converted into a transformed Component. "
                         "Make it a regular Group before editing its stroke text.")
    return bounds_from_pairs((e if isinstance(e, tuple) and len(e) == 2
                              else (e.a, e.b)) for e in group.mesh.edges)


def edge_statistics(pairs):
    """Compact translation-invariant geometry signature (count and norms).

    Used along with bounds to catch externally edited edges that happen not
    to affect the Group's overall bounding box.
    """
    n, total, squared = 0, 0.0, 0.0
    axial = [0.0, 0.0, 0.0]
    for a, b in pairs:
        v = [b1 - a1 for a1, b1 in zip(_xyz(a), _xyz(b))]
        d2 = sum(x * x for x in v)
        total += sqrt(d2)
        squared += d2
        for i in range(3):
            axial[i] += abs(v[i])
        n += 1
    return (n, total, squared, *axial)


def group_edge_statistics(group):
    return edge_statistics((e if isinstance(e, tuple) and len(e) == 2
                            else (e.a, e.b)) for e in group.mesh.edges)


def reference_geometry(group):
    from .constants import PLUGIN_KEY, MAX_MODEL_SEGMENTS
    from .engine import build_strokes
    from .geometry import iter_model_edges

    p = (getattr(group, "ext", None) or {}).get(PLUGIN_KEY, {})
    ref = p.get("reference_bounds")
    if isinstance(ref, (list, tuple)) and len(ref) == 2:
        try:
            lo, hi = tuple(_xyz(v) for v in ref)
            if all(isfinite(k) for pair in (lo, hi) for k in pair):
                return (lo, hi), p.get("reference_edge_stats")
        except (TypeError, ValueError, IndexError):
            pass
    # Compatibility with v0.1.0 groups (no reference bounds in metadata).
    # Reconstruct only the OLD text, old font and original parameters. New
    # text/height/font typed into the dialog must not affect the recovery.
    old_version = str(p.get("version", "0.1.0"))
    try:
        strokes = build_strokes(
            p["font"], p["text"], float(p["height"]),
            width_factor=float(p.get("width_factor", 1)),
            tracking=float(p.get("tracking", 0)),
            line_spacing=float(p.get("line_spacing", 1.5)),
            alignment=p.get("alignment", "left"),
            encoding=p.get("encoding", "auto"),
            max_segments=MAX_MODEL_SEGMENTS,
            legacy_mark_positions=old_version.startswith("0.1."),
        )
        # Use the host's own weld/dedup semantics to reconstruct a legacy
        # Group, not just raw stroke segments (which can repeat).
        from PySide6.QtGui import QVector3D
        from core.mesh import Mesh
        mesh = Mesh()
        for a, b in iter_model_edges(
                strokes.paths, origin=(p["x"], p["y"], p["z"]),
                plane=p.get("plane", "XY"), angle=float(p.get("angle", 0))):
            mesh.add_edge(QVector3D(*a), QVector3D(*b))
        edges = ((e if isinstance(e, tuple) and len(e) == 2
                  else (e.a, e.b)) for e in mesh.edges)
        ref = bounds_from_pairs(edges)
        pairs = ((e if isinstance(e, tuple) and len(e) == 2
                  else (e.a, e.b)) for e in mesh.edges)
        return ref, edge_statistics(pairs)
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(
            "Cannot recover the position of this v0.1 SHX text. "
            "Its original SHX font and parameters must be readable. "
            f"Details: {exc}") from exc


def effective_parameters(group):
    """Copy saved text parameters but use actual current world insertion.

    A strict extents check detects common external Rotate/Scale/Edit actions.
    """
    from .constants import PLUGIN_KEY
    p = dict((getattr(group, "ext", None) or {}).get(PLUGIN_KEY, {}))
    if not p:
        raise ValueError("Selected object is not a GO SHX Stroke Text Group.")
    ((before_lo, before_hi), baseline_stats) = reference_geometry(group)
    after_lo, after_hi = group_bounds(group)
    extent_before = [b - a for a, b in zip(before_lo, before_hi)]
    extent_after = [b - a for a, b in zip(after_lo, after_hi)]
    height = max(float(p.get("height", 0.3)), 0.001)
    # Do not use just machine epsilon: QVector3D uses float32 and large
    # model coordinates accumulate small round-off during Move.
    tol = max(height * 0.0005, 2e-5,
              max(abs(v) for v in after_lo + after_hi) * 3e-7)
    if any(abs(a - b) > tol for a, b in zip(extent_before, extent_after)):
        raise ValueError(
            "This SHX Group was rotated, scaled or its edges were modified "
            "after creation. Automatic Update preserves moved Groups only; "
            "the geometry was not changed. Make a backup and create a new text "
            "object, or undo the external geometry edit.")
    if baseline_stats:
        current_stats = group_edge_statistics(group)
        if int(current_stats[0]) != int(baseline_stats[0]):
            raise ValueError("This SHX Group's edges were modified after creation. "
                             "Automatic Update can preserve translation only.")
        # Tolerate float32 mesh roundoff from native Move, not real edits.
        epsilon = max(height * 0.002, 1e-4,
                      max(abs(v) for v in after_lo + after_hi) * 2e-6)
        if any(abs(float(a) - float(b)) > epsilon
               for a, b in zip(current_stats[1:], baseline_stats[1:])):
            raise ValueError("This SHX Group was rotated, scaled or its edges "
                             "were modified after creation. The original "
                             "geometry was left untouched.")
    delta = [((cur_lo + cur_hi) - (base_lo + base_hi)) * 0.5
             for cur_lo, cur_hi, base_lo, base_hi
             in zip(after_lo, after_hi, before_lo, before_hi)]
    for key, change in zip(("x", "y", "z"), delta):
        p[key] = float(p.get(key, 0.0)) + change
    return p


def merge_updated_position(form_params, current_params, loaded_visible,
                           shown_values):
    """Preserve exact moved coordinates unless user explicitly edited an axis."""
    result = dict(form_params)
    for key in ("x", "y", "z"):
        if shown_values.get(key) == loaded_visible.get(key):
            result[key] = current_params[key]
    return result
