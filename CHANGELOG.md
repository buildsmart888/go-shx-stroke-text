# Changelog

## v0.2.0 — 2026-11-01

- Recover actual X/Y/Z of moved native Groups from geometry at Load/Update; preserve float precision when coordinates were not explicitly edited
- Add v0.1 legacy Group migration using the original SHX glyphs and layout rules; persist reference bounds and compact edge statistics in v0.2 metadata
- Guard against externally edited, rotated or scaled geometry instead of silently overwriting
- Add Select-tool-only double-click editing of plugin-owned Groups; preserve default double-click behavior for all other objects; add context menu and toggle
- Add one-pass complete missing-glyph report with codepoints and legacy CP874 candidates, including Show Details and Check all glyphs control
- Fix Thai nonspacing marks with zero Unicode combining class (category Mn) incorrectly advancing the pen; retain legacy layout reconstruction for old Groups
- Expand automated regression tests to 20 including SHX binary, CP874, migrated Group Move, persistence baseline, Undo, selection filter, and DXF export



## v0.1.0 — 2026-10-31

- Direct SHX/SHP glyph decoding through ezdxf shape-file renderer
- Auto/Unicode/CP874 glyph indexing and explicit missing glyph errors
- Model Group creation, selection-based update, tagged layer, Undo
- Paper-space Sheet Composer line shapes, single-step Undo and editable records
- Preview, multiline, XY/XZ/YZ placements, alignment and geometric transform
- Separate export of sheet-owned SHX vectors to standard DXF (millimetres)
- Unit tests and Windows plugin installer in source distribution
