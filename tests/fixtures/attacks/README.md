# Hostile XML fixtures

Every file here must be **rejected** by `cairn/io/input_check.guard_input` before any reader
runs (`tests/test_input_check.py`). None is a valid map. Do not glob this directory into an
"every fixture parses" test.

| File | Attack |
|---|---|
| `billion_laughs.gpx` | 10 levels of 10x nested entities (10^9 expansion) |
| `quadratic_blowup.kml` | one 5 KB entity referenced 5,000 times (~25 MB expanded) |
| `external_entity.gpx` | external general entity `SYSTEM "file:///etc/passwd"` |
| `external_parameter_entity.kml` | external parameter entity `%p;` |

Without the guard, stock ElementTree already refuses or neutralises all four (expat >= 2.4's
amplification limit; no external entity resolution) -- see
`docs/research/KML_GPX_INPUT_2026-10-22.md` section 4. The guard makes them fail fast with a
user-facing message, independent of the expat version Pyodide bundles.
