# Real onX Backcountry exports

Unedited files exported from the onX Backcountry **Web Map** on 2026-10-22 (My Content →
folder menu → Export Folder Contents → GPX / KML). The folder held two test waypoints that
Cairn had just imported ("ZZTEST A" Summit/red, "ZZTEST B" Camp/blue). Both markups were deleted
from the account afterwards, so the ids are dead.

What they confirm (previously inferred from onX's shipped JS):

- GPX: `creator="onXmaps backcountry web"`; `<desc>` is onX's key=value block
  (`name=`, `notes=`, `id=<uuid>`, `color=`, `icon=`) plus `onx:color` / `onx:icon` extensions.
  Colors are written with spaces: `rgba(255, 0, 0, 1)`.
- KML: one `<Document>` with no `<Folder>`; each Placemark carries the same fields as
  `<ExtendedData><Data name="...">`; points have a `0` altitude.
- A Cairn GPX `<desc>` arrives in onX as the markup's notes.

Re-importing the GPX export (which carries the ids) created **two new markups** in a new
folder: onX import does not update existing markups by id. See
`docs/research/ONX_REIMPORT_AND_SHARING_2026-10-22.md`.

Do not edit these files; add new real exports alongside them.
