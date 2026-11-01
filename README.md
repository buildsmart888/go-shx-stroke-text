# GO SHX Stroke Text — v0.2.0

Native stroke-text extension for IngeTrazo API v2, using ezdxf to read `.shx` / `.shp` glyph paths directly. Windows TrueType font substitution is never used. Supports model Group edges and paper-space Composer shape lines with undo and document persistence. Version 0.2.0 recovers current placement after moving a Group, permits native double-click editing (Select tool only), and reports every missing glyph in one inspection instead of failing on the first character. Includes Thai Unicode and legacy CP874 glyph-index fallback when the font contains them.

Install the `go_shx_stroke_text/` package into **Extensions → Open plugins folder** and restart IngeTrazo. The package requires `ezdxf >= 1.1` in the host Python runtime. Use a licensed SHX file owned by the user; no font files are shipped.

See [README_TH.md](README_TH.md) for full install/test instructions and limitations. In particular, SHX BIGFONT is not supported by ezdxf, Thai combining marks need visual checking, sheet text has a 2,500 segment limit, direct native Sheet PDF supports the lines, and the built-in Export View DXF does NOT include paper-space annotations. Use the extension's dedicated Sheet SHX DXF export instead. Actual IngeTrazo Windows integration tests are still required.

## Architecture

- `engine.py`: pure ezdxf stroke font decoder and glyph validation (no implicit TTF fallback)
- `geometry.py`: model-world and sheet-paper coordinate transformations
- `model_host.py`: Group, layer, metadata, and model Undo
- `pose.py`: recover moved Group insertion from live geometry and saved baseline, with v0.1 compatibility
- `viewport_hook.py`: narrowly scoped Qt event filter for double-click editing of plugin-owned Groups
- `sheet_host.py`: Composer `FormaItem` line batches, sheet-specific Undo and metadata
- `dialog.py`: Qt UI with Model and Sheet modes
- `__init__.py`: IngeTrazo `setup(app)` menu and toolbar

Compatible target: IngeTrazo Extension API v2 based on upstream `docs/plugins.md` (host version must be checked). Not yet smoke-tested in the Windows host. License: MIT for this extension's original source; dependencies carry their own licenses.

## Upgrade and regression coverage (v0.2.0)

1. Backup `.igz`, replace old plugin package, restart IngeTrazo.
2. Select or double-click an existing GO SHX Group (when Select is active); edit and Update Selected.
3. Use **Check all glyphs** to inspect the complete list of missing Unicode and CP874 slots. Missing Thai numerals require a font that actually contains those glyphs; no silent substitution is performed.
4. Verify Move→Update preserves position, including v0.1.0 Group migration, and Undo/Redo works. The source tests include synthetic original SHX bytes and DXF round-trip.

20 automated tests pass. Host-side GUI / Windows smoke tests are **NOT TESTED** here. Rotation, scaling, and external Group geometry edits are not automatically migrated: the editor rejects updates it cannot prove are translation-only.

## GitHub release and Community distribution

The distributable package is `dist/go_shx_stroke_text-v0.2.0.zip` with **one top-level** `go_shx_stroke_text/` package. Do not distribute the source ZIP via the IngeTrazo Community manager. `community/go_shx_stroke_text.toml` is the separate Community catalog entry.

The author provided a live IngeTrazo screenshot on 2026-11-01 showing the v0.2.0 dialog and model Group selection. The 20 automated tests passed; full Windows matrix (sheet exports, save/reload, all font variants) has not been independently verified. The screenshot is provided under `screenshots/` for documentation.
