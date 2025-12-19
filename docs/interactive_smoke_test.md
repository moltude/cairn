### Interactive picker + bulk edit smoke test (manual)

Run these in a TTY (Terminal/iTerm). Also try once with `--no-interactive` to confirm it stays scriptable.

- **OnX → CalTopo picker**
  - Run `cairn migrate onx-to-caltopo` without args.
  - Verify you can pick an exports directory.
  - Verify you can pick a GPX and optionally skip/pick a KML.

- **CalTopo → OnX picker**
  - Run `cairn migrate caltopo-to-onx` without args.
  - Verify you can pick a CalTopo exports directory.
  - Verify you can pick a `.json`/`.geojson` file.

- **Bulk edit (per-folder)**
  - In `cairn migrate caltopo-to-onx`, answer “yes” to editing.
  - In a folder with items, bulk-select:
    - **Rename prefix/suffix** and confirm preview-before-apply.
    - **Set route color** and confirm preview-before-apply.
    - **Set waypoint color** and confirm preview-before-apply.
    - **Set icon override** (valid icon) and confirm preview-before-apply.
    - **Clear icon override** and confirm preview-before-apply.
  - Verify `--save-session` produces a session file and reruns resume edits.

- **Large list degraded mode**
  - Use a dataset with hundreds+ waypoints/tracks.
  - Confirm it asks for a filter first before showing a huge checklist, and doesn’t hard-fail.
