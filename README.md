# Cairn

## This is a work in progress

### Why I built this

I’m an advocate for open data and being able to exchange map data between platforms. GPX/KML/GeoJSON are meant to be platform-agnostic interchange formats (or at least that’s how I understand them). Cairn is my attempt to make that promise feel real for backcountry mapping: move between onX and CalTopo while taking *all the map customization with you* (icons, colors, notes, and organization), not just raw shapes.

This tool started as an experiment and it surfaced a number of challenges. I’m not an expert — if my assumptions are wrong, I want to find out and correct them. The goal is a faithful migration, not “a file that happens to import.”

### What this tool is for

In theory, these formats should make it easy to move between map platforms. In practice, each platform:

- supports only a subset of each format
- adds proprietary fields or extensions
- rewrites data during import/export (sometimes subtly)

I built Cairn to make migration between **onX Backcountry** and **CalTopo** easier *without losing the customization that makes a map valuable* (names, notes, colors, icons, and organizational intent) — not just the raw shapes.

Right now, the most reliable direction is **onX → CalTopo**.

---

## Quick start (onX → CalTopo)

### 1) Export from onX (export both files)

Export the same map from onX in **both** formats:

- **GPX**: best source for waypoint metadata (name/notes) plus onX-specific icon/color extensions
- **KML**: best source for areas/polygons (onX often exports areas as polygons in KML but as tracks/routes in GPX)

You want both files from the same export session so they represent the same content.

### 2) Convert with Cairn

```bash
uv run cairn migrate onx-to-caltopo --gpx onx-export.gpx \
  --kml onx-export.kml \
  --output-dir ./caltopo_ready \
  --name most_usable
```

If you run `uv run cairn migrate onx-to-caltopo` with no arguments, Cairn will prompt you for the file paths and output settings.

### 3) Import into CalTopo

Import `./caltopo_ready/most_usable.json` into CalTopo using CalTopo’s GeoJSON import.

---

## What Cairn writes (onX → CalTopo)

For the example above, Cairn writes:

- **`most_usable.json`**: primary CalTopo-importable GeoJSON (deduped by default)
- **`most_usable_dropped_shapes.json`**: everything that was removed by shape dedup (so nothing is lost)
- **`most_usable_SUMMARY.md`**: human-readable explanation of dedup decisions
- **`trace.jsonl`** (optional): machine-parseable trace events for debugging and replay

---

## Why dedup exists (and what it means)

During this experiment I found cases where onX exports include many distinct objects (different IDs) with identical names and identical geometry. CalTopo will happily import them all, which can look like “duplicates everywhere”.

By default, Cairn produces a **“most usable”** CalTopo file by:

- **preferring polygons** (from KML) over track/route representations (from GPX) when they refer to the same onX object
- **deduplicating shapes** using a fuzzy geometry match (rotation/direction tolerant, coordinate rounding tolerant)

Nothing is deleted permanently: every dropped duplicate is preserved in the secondary GeoJSON, and the summary explains the choices.

---

## Known quirks / blockers I ran into (straightforward, not blame-y)

- **onX export variance**: similar “linework” can export as `<trk>` vs `<rte>`. Areas/polygons often only appear as polygons in KML.
- **CalTopo’s exported “GeoJSON” is CalTopo-flavored**: it may include extra properties and 4D coordinate arrays like `[lon, lat, ele, time]`. I treat this as normal normalization, not automatically a bug.
- **Standards aren’t fully standard in practice**: GPX/KML/GeoJSON are interchange formats, but platform behavior still matters more than file validity.

If any of my assumptions are wrong, I want to know — the goal is a faithful migration, not “a file that happens to import”.

---

## Challenges I found migrating from CalTopo → onX (secondary)

I still care about proving out migration in both directions, but in practice **CalTopo → onX** is harder to make “high fidelity” because of how onX behaves on import and in the UI.

Here are the blockers I ran into (stated plainly, not as criticism):

- **Ordering is not reliable after import**: even if I carefully write GPX/KML in a particular order, onX may re-order items in folders after import and there isn’t a stable user-visible “sort by name” / “sort by import order” workflow that guarantees the same outcome every time.
- **Waypoints and tracks don’t share a single color model**: onX uses different palettes/expectations for waypoint colors vs track colors, so “preserve the exact color” can require quantization or remapping.
- **KML round-trip fidelity is limited**: styles, structure, and metadata may be reduced when moving through onX import/export cycles.

These constraints don’t make the direction impossible — they just make it easier to lose “polish” compared to onX → CalTopo.

---

## Demo

There’s a recorded CLI demo script at `demo.tape` using:

- `demo/onx-to-caltopo/onx-export/` (source exports)
- `demo/onx-to-caltopo/caltopo-ready/` (generated outputs)

---

## CalTopo → onX (secondary / experimental)

Cairn also contains an older CalTopo → onX conversion path (`cairn convert`) which focuses on icon mapping, ordering, and onX import constraints. It’s still useful, but it’s not the main focus of the README anymore.

To explore it:

```bash
uv run cairn convert --help
```

---

## Development

### Running tests

```bash
uv run --with pytest pytest -q
```

---

## License

MIT License - see [LICENSE](LICENSE)
