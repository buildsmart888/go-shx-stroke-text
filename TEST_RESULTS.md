# v0.2.0 QA results

- Python syntax: PASS (compileall)
- Unit/contract regressions: PASS, 20/20 (pytest)
- SHX binary decoding and CP874 fallback: PASS with synthetic, original SHX test font
- Missing glyphs full report: PASS
- Thai category-Mn mark advance fix: PASS
- Group translation recovery for v0.1 and v0.2 metadata: PASS (stub host)
- Group edit retains UID, Undo/Redo behavior: PASS (stub host)
- Qt double-click event-filter decision logic: PASS (stub Qt)
- Sheet vector DXF round-trip: PASS (ezdxf)
- Installed IngeTrazo 0.x on Windows: **NOT TESTED**
- Real ZWCAD THAISIMP.SHX glyph coverage and shaping: **NOT TESTED**, font not provided
- Windows offscreen Qt GUI test: **NOT TESTED**, PySide6 not present in this container

QA baseline: source-backed API inspection based on public IngeTrazo Extension API v2.
The user should run the Windows host smoke tests described in README_TH.md before production use.
