# Web engine: imported by web/bridge.py and run in the browser via Pyodide.
# Keep it free of terminal/UI imports (tests/test_web_engine_surface.py).
"""Input safety and format detection, run before any reader touches a file.

Two jobs, both cheap and both string-only (no XML parser runs here):

- ``guard_input(text)`` rejects XML that declares a DTD and XML that is too
  large, with a one-sentence message a hiker can read. ``web/app.js``'s
  ``humanError`` shows only the last line of a Python traceback, so the
  message IS the user experience; it is raised as a plain ``ValueError`` so
  that last line reads ``ValueError: <message>`` and the prefix is stripped.
- ``detect(filename, text)`` says what a file is -- ``(kind, dialect)`` -- by
  sniffing its content. The content wins over the extension; a disagreeing
  extension is reported by ``extension_mismatch``, never trusted.

Why a guard at all when stock ElementTree is used: expat >= 2.4 already caps
entity amplification (billion laughs, quadratic blowup) and ElementTree never
resolves external entities. The guard turns those into an immediate, friendly
error instead of a parser error deep in a reader, and it does not depend on
the expat version Pyodide happens to bundle. No exporter of interest (onX
Web Map, CalTopo, Cairn, Google Earth) emits a DTD, so rejecting one costs
nothing. See docs/research/KML_GPX_INPUT_2026-10-22.md section 4.
"""

from __future__ import annotations

import json
import logging
import re

logger = logging.getLogger(__name__)

# 16 MB of XML. onX's own import cap is 4 MB per file, but the input here is
# an onX (or CalTopo) EXPORT, which is not bound by that cap -- a messy account
# of up to 3,000 markups with notes and long tracks is exactly the case this
# tool exists for, and Cairn splits the output back under 4 MB itself. 4x
# headroom covers that. The ceiling exists for the browser tab: Pyodide holds
# the JS string, a Python copy, the file written to its in-memory /tmp and the
# ElementTree, several times the input in total, inside one wasm heap. JSON
# input is not capped here: the CalTopo GeoJSON path predates this guard,
# json.loads has no amplification, and capping it would be a regression.
MAX_XML_INPUT_BYTES = 16 * 1024 * 1024

# Kinds.
GEOJSON = "geojson"
GPX = "gpx"
KML = "kml"
UNKNOWN = "unknown"

# Dialects. Phase 2 dispatches on these, so they are constants, not prose.
CALTOPO = "caltopo"      # CalTopo GeoJSON, or a CalTopo GPX (creator="CALTOPO")
ONX = "onx"              # onX Web Map export (GPX creator "onXmaps ... web"; KML <Data name="id">)
ONX_LIKE = "onx-like"    # GPX declaring an onX namespace but not written by onX's web exporter
CAIRN = "cairn"          # Cairn's own output (GPX creator "Cairn..."; KML generator marker)
GENERIC = "generic"      # anything else of the right kind (Google Earth KML, other GPX, plain GeoJSON)
INVALID = "invalid"      # looked like the kind but could not be parsed (JSON only; XML is sniffed, not parsed)
EMPTY = "empty"          # nothing but whitespace
NOT_A_MAP = "not-a-map"  # XML without a gpx/kml root, or not JSON/XML at all

# Cairn's KML marker. cairn/core/writers.py:_kml_document writes it as a
# Document-level <ExtendedData><Data name="generator"><value>Cairn</value>.
# tests/test_input_check.py ties the two together through a real write.
CAIRN_KML_MARKER_NAME = "generator"
CAIRN_KML_MARKER_VALUE = "Cairn"

_EXTENSIONS = {GEOJSON: (".json", ".geojson"), GPX: (".gpx",), KML: (".kml",)}

_ROOT_RE = re.compile(r"<(?:[A-Za-z_][\w.-]*:)?(gpx|kml)\b([^>]*)>")
_CREATOR_RE = re.compile(r"""\bcreator\s*=\s*(?:"([^"]*)"|'([^']*)')""")
_ONX_ID_RE = re.compile(r"""<Data\s+name\s*=\s*["']id["']""")
_CAIRN_KML_RE = re.compile(
    r"""<Data\s+name\s*=\s*["']%s["']\s*>\s*<value>\s*%s"""
    % (CAIRN_KML_MARKER_NAME, CAIRN_KML_MARKER_VALUE)
)
_WS = " \t\r\n"


def _body(text: str) -> str:
    return text.lstrip("﻿").lstrip(_WS)


def _scan_prolog(body: str) -> tuple[int, bool]:
    """Skip the XML prolog's PIs and comments: returns (offset of the next
    construct, whether that construct is a DTD).

    A DOCTYPE can only appear in the prolog, and a DTD is the only place an
    <!ENTITY> can be declared, so this is where the guard looks -- construct by
    construct rather than searching the whole text, for two reasons. Whole-text
    search would reject a legitimate file whose notes hold pasted HTML
    (`<![CDATA[<!DOCTYPE html>...]]>` in a CalTopo GPX name or description).
    And a naive "text before the first `<tag`" split is bypassable by hiding a
    fake tag in a comment ahead of the DTD. In a prolog only `<?...?>`,
    `<!--...-->` and `<!DOCTYPE` are legal, so any other `<!` before the root
    element is treated as a DTD too.
    """
    pos = 0
    n = len(body)
    while True:
        while pos < n and body[pos] in _WS:
            pos += 1
        if body.startswith("<?", pos):
            end = body.find("?>", pos + 2)
            if end < 0:
                return pos, False  # unterminated PI: malformed, the reader reports it
            pos = end + 2
        elif body.startswith("<!--", pos):
            end = body.find("-->", pos + 4)
            if end < 0:
                return pos, False  # unterminated comment: no root element follows
            pos = end + 3
        else:
            return pos, body.startswith("<!", pos)


def guard_input(text: str) -> None:
    """Raise ValueError with a user-facing sentence if `text` is unsafe XML.

    Non-XML input (anything not starting with `<` after a BOM and whitespace)
    passes untouched: the JSON path has its own parser and errors.
    """
    body = _body(text)
    if not body.startswith("<"):
        return
    # len() is characters; UTF-8 bytes are >= characters, so only encode when
    # the cheap check can't already decide.
    size = len(text) if len(text) > MAX_XML_INPUT_BYTES else len(text.encode("utf-8"))
    if size > MAX_XML_INPUT_BYTES:
        raise ValueError(
            f"This file is {size / (1024 * 1024):.1f} MB, and Cairn opens GPX and KML "
            f"files up to {MAX_XML_INPUT_BYTES // (1024 * 1024)} MB. "
            f"Export one folder at a time instead."
        )
    if _scan_prolog(body)[1]:
        raise ValueError(
            "This file contains a <!DOCTYPE> declaration, which map exports from onX, "
            "CalTopo and Google Earth never include, so Cairn won't open it."
        )


def detect(filename: str, text: str) -> tuple[str, str]:
    """Classify a file by its content: returns (kind, dialect).

    kind is GEOJSON, GPX, KML or UNKNOWN; dialect is one of the constants
    above. The filename's extension is never used to decide -- call
    `extension_mismatch` to report a disagreement.

    XML is sniffed (root element within 4 KB of the prolog, then attributes and
    markers), not parsed: a malformed GPX still detects as GPX and its reader
    reports the parse error. JSON is parsed, because CalTopo's marker is a
    property on any feature.
    """
    body = _body(text)
    if not body:
        result = (UNKNOWN, EMPTY)
    elif body[0] in "{[":
        result = _detect_json(body)
    elif body[0] == "<":
        result = _detect_xml(body)
    else:
        result = (UNKNOWN, NOT_A_MAP)
    note = extension_mismatch(filename, result[0])
    if note:
        logger.warning(note)
    return result


def _detect_json(body: str) -> tuple[str, str]:
    try:
        data = json.loads(body)
    except ValueError:
        return (GEOJSON, INVALID)
    feats = data.get("features") if isinstance(data, dict) else None
    if isinstance(feats, list) and any(
        isinstance(f, dict)
        and isinstance(f.get("properties"), dict)
        and f["properties"].get("class") in ("Folder", "Marker", "Shape")
        for f in feats
    ):
        return (GEOJSON, CALTOPO)
    return (GEOJSON, GENERIC)


def _detect_xml(body: str) -> tuple[str, str]:
    # Look for the root in the 4 KB after the prolog's comments and PIs (a
    # DTD, which the guard rejects anyway, gets 64 KB so it can still be named).
    start, dtd = _scan_prolog(body)
    m = _ROOT_RE.search(body, start, start + (65536 if dtd else 4096))
    if not m:
        return (UNKNOWN, NOT_A_MAP)
    root, attrs = m.group(1), m.group(2)
    if root == "gpx":
        cm = _CREATOR_RE.search(attrs)
        creator = (cm.group(1) if cm and cm.group(1) is not None else (cm.group(2) if cm else "")) or ""
        if "onxmaps" in creator.lower():
            return (GPX, ONX)
        if creator.strip().upper() == "CALTOPO":
            return (GPX, CALTOPO)
        if creator.startswith("Cairn"):
            return (GPX, CAIRN)
        if "onxmaps.com" in attrs.lower():
            return (GPX, ONX_LIKE)
        return (GPX, GENERIC)
    # KML. The Cairn marker is checked BEFORE onX's per-placemark id: once
    # Cairn writes onX ids back (roadmap Phase 6) its own KML carries both.
    if _CAIRN_KML_RE.search(body):
        return (KML, CAIRN)
    if _ONX_ID_RE.search(body):
        return (KML, ONX)
    return (KML, GENERIC)


def extension_mismatch(filename: str, kind: str) -> str | None:
    """A user-facing note when the extension disagrees with the content, else None."""
    expected = _EXTENSIONS.get(kind)
    if not expected:
        return None
    name = filename or ""
    dot = name.rfind(".")
    ext = name[dot:].lower() if dot > 0 else ""
    if ext in expected:
        return None
    label = {GEOJSON: "GeoJSON", GPX: "GPX", KML: "KML"}[kind]
    shown = f"“{ext}”" if ext else "no"
    return f"{name or 'This file'} has {shown} extension but contains {label}; reading it as {label}."
