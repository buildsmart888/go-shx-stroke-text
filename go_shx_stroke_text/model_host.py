"""Host adapter for native IngeTrazo Groups and transactional model Undo."""
from __future__ import annotations

from .constants import PLUGIN_KEY, LAYER_NAME, VERSION
from .geometry import iter_model_edges


def selected_stroke_group(scene):
    for obj in scene.selection:
        params = getattr(obj, "ext", None)
        if isinstance(params, dict) and PLUGIN_KEY in params and obj in scene.groups:
            return obj
    return None


def create_model_group(strokes, params, previous=None):
    from PySide6.QtGui import QVector3D
    from core.group import Group
    from core.mesh import Mesh

    mesh = Mesh()
    for a, b in iter_model_edges(
            strokes.paths,
            origin=(params["x"], params["y"], params["z"]),
            plane=params["plane"], angle=params["angle"]):
        mesh.add_edge(QVector3D(*a), QVector3D(*b))
    if not mesh.edges:
        raise ValueError("Font produced no drawable strokes.")
    g = Group(mesh=mesh, name=f"GO SHX | {params['text'].splitlines()[0][:35]}")
    g.layer = LAYER_NAME
    from .pose import group_bounds, group_edge_statistics
    # This baseline survives Save/Reload and allows exact translation recovery
    # even if the original font is moved or deleted after generation.
    baseline = group_bounds(g)
    g.ext = {PLUGIN_KEY: dict(params, schema=2, version=VERSION,
                              reference_bounds=[list(v) for v in baseline],
                              reference_edge_stats=list(group_edge_statistics(g)))}
    if previous is not None:
        g.uid = previous.uid  # edit retains identity to sheet/view references
        g.layer = previous.layer or LAYER_NAME
        g.material = previous.material
        g.hidden = previous.hidden
        g.locked = previous.locked
        if previous.ext:
            g.ext = dict(previous.ext, **g.ext)
    return g


def commit_model(app, group, old=None):
    from core.history import Command
    from core.layers import Layer

    class _ModelTextCommand(Command):
        def __init__(self):
            self.created_layer = None
            self.old_index = -1

        def do(self, scene):
            if not any(ly.name == LAYER_NAME for ly in scene.layers):
                if self.created_layer is None:
                    self.created_layer = Layer(LAYER_NAME, color=(0.16, 0.28, 0.32),
                                               lineweight=0.18)
                scene.layers.append(self.created_layer)
            if old is not None and old in scene.groups:
                self.old_index = scene.groups.index(old)
                scene.groups.remove(old)
            if group not in scene.groups:
                i = self.old_index if self.old_index >= 0 else len(scene.groups)
                scene.groups.insert(i, group)
            scene.selection.clear()
            scene.selection.add(group)
            scene.version += 1

        def undo(self, scene):
            if group in scene.groups:
                scene.groups.remove(group)
            scene.selection.discard(group)
            if old is not None and old not in scene.groups:
                scene.groups.insert(max(self.old_index, 0), old)
                scene.selection.add(old)
            if self.created_layer is not None and self.created_layer in scene.layers:
                # The transaction added this layer; don't remove a now-used layer.
                others = [g for g in scene.groups if g.layer == LAYER_NAME]
                if not others:
                    scene.layers.remove(self.created_layer)
            scene.version += 1

    vp = app.viewport
    vp.history.execute(_ModelTextCommand())
    if getattr(vp.history, "last_error", None) is not None:
        raise RuntimeError(str(vp.history.last_error))
    vp.notify_scene_changed()
    return group
