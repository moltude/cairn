/* Glyphs for onX's 95 markup icons, drawn as markers.

   Deliberately NOT onX's own artwork: their icon designs are proprietary, and
   bundling them into a third-party tool is a licensing question we don't need to
   take on. The common icons get a simple stroke drawing (24x24 box, drawn with
   round caps at ~2px); the rest show a one- or two-letter abbreviation inside
   the marker. Every icon is always shown next to onX's exact text label, so
   there is never any doubt which onX icon you are actually setting.

   Every name in onX's list must have an entry here -- the e2e suite checks it,
   so a new onX icon can't silently fall back to the default pin. */
const ONX_GLYPHS = (() => {
  const P = {
    pin: "M12 21s-6-6.5-6-11a6 6 0 0 1 12 0c0 4.5-6 11-6 11z M12 10v.01",
    summit: "M3 19 L10 7 L14 13 L16 10 L21 19 Z",
    drop: "M12 3C12 3 6 10 6 14a6 6 0 0 0 12 0C18 10 12 3 12 3Z",
    parking: "M5 3h14v18H5z M10 16V8h3a2.5 2.5 0 0 1 0 5h-3",
    climb: "M7 21l4-7 3 2 2-6 M9 11l3-3 4 2 M13 5.5h.01",
    hazard: "M12 3 L22 20 H2 Z M12 9v5 M12 17v.01",
    tent: "M3 20 L12 5 L21 20 Z M9 20 L12 14 L15 20",
    car: "M2 15v-4l3-5h9l4 5h4v4H2z M5 17a2 2 0 1 0 4 0 2 2 0 1 0-4 0 M15 17a2 2 0 1 0 4 0 2 2 0 1 0-4 0",
    waves: "M2 9c3-2 5 2 8 0s5-2 8 0 4 0 4 0 M2 14c3-2 5 2 8 0s5-2 8 0 4 0 4 0 M2 19c3-2 5 2 8 0s5-2 8 0 4 0 4 0",
    boat: "M2 13c4 4 16 4 20 0z M16 4l-6 13",
    tower: "M8 21l2.5-13h3L16 21 M6 8h12 M8 8l4-4 4 4 M9.5 15h5",
    bike: "M2.5 17a3.5 3.5 0 1 0 7 0 3.5 3.5 0 1 0-7 0 M14.5 17a3.5 3.5 0 1 0 7 0 3.5 3.5 0 1 0-7 0 M6 17l4-7h6l2 7 M9 7h3",
    mushroom: "M3 12a9 7 0 0 1 18 0z M9 12v6a3 3 0 0 0 6 0v-6",
    barrier: "M3 9h18v5H3z M6 14v6 M18 14v6 M7 9l4 5 M13 9l4 5",
    cave: "M2 20h20 M4 20c0-8 3.5-13 8-13s8 5 8 13 M9 20c0-3.5 1.3-6 3-6s3 2.5 3 6",
    steam: "M8 3c-1.5 2 1.5 3 0 5 M12 3c-1.5 2 1.5 3 0 5 M16 3c-1.5 2 1.5 3 0 5 M3 14c3 2 6 2 9 0s6-2 9 0 M3 18c3 2 6 2 9 0s6-2 9 0",
  };
  const G = {
    "Location": P.pin,
    "Summit": P.summit,
    "Water Source": P.drop,
    "Potable Water": P.drop + " M9.5 14.5a2.5 2.5 0 0 0 2.5 2.5",
    "Parking": P.parking,
    "Climbing": P.climb,
    "Hazard": P.hazard,
    "Camp": P.tent,
    "Camp Backcountry": "M4 19 L12 6 L20 19 M2 19h20 M12 6v13",
    "Camp Area": "M4 20 L12 8 L20 20 Z M12 8V3l4 1.5L12 6",
    "Campground": "M2 19 L7 10 L12 19 M12 19 L17 10 L22 19 M2 19h20",
    "Trailhead": "M12 21V3 M12 5h7l2 2.5-2 2.5h-7 M12 12H5l-2 2.5L5 17h7",
    "Shelter": "M3 11 L12 4 L21 11 M5 10v10h14V10 M10 20v-5h4v5",
    // Not one of onX's 95 names, but the engine's keyword map emits it
    // (cairn/core/config.py "cabin"/"hut"/"yurt"); draw it as a shelter.
    "House": "M4 11L12 4l8 7v9H4z M10 20v-6h4v6 M16 7.5V4h2v5",
    "Photo": "M4 8h4l1.5-2h5L16 8h4v11H4z M12 17a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7z",
    "View": "M2 12s4-6 10-6 10 6 10 6-4 6-10 6S2 12 2 12z M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z",
    "Lookout": P.tower,
    "Observation Towers": "M7 21l3.5-15h3L17 21 M5 6h14 M8.5 14h7",
    "Ski": "M5 3l14 18 M19 3L5 21",
    "Ski Touring": "M3 20l18-6 M12 5.5h.01 M8 15l3-6 3 3 3-1",
    "XC Skiing": "M3 18h18 M3 21h18 M8 15l4-8 4 8",
    "Skin Track": "M5 21 L15 17 L7 13 L17 9 L10 5 L14 3",
    "Slide Path": "M3 20L12 5l9 15z M12 9v7 M9.5 13.5L12 16l2.5-2.5",
    "Cornice": "M3 20V9c6 0 12 1 18 5 M21 14c-2 0-3 1-3 2",
    "Couloir": "M3 20L9 4 M21 20L15 4 M9 4c1 6 5 6 6 0 M12 9v11",
    "Snow Pit": "M12 3v18 M4.2 7.5l15.6 9 M4.2 16.5l15.6-9",
    "Gate": "M3 20V5 M21 20V5 M3 8h18 M3 16h18 M3 16L21 8",
    "Open Gate": "M3 20V5 M3 8l11 3 M3 16l11-3 M14 11v6 M21 20V5",
    "Closed Gate": "M3 20V5 M21 20V5 M3 9h18 M3 15h18 M8 9v6 M13 9v6 M18 9v6",
    "Footbridge": "M2 14h20 M2 14c4-6 16-6 20 0 M6 14v-3 M12 14V9.5 M18 14v-3 M4 18h16",
    "Fish": "M3 12c3-5 10-6 14 0-4 6-11 5-14 0z M17 12l4-4v8z M8 11h.01",
    "Waterfall": "M3 4h10 M13 4v3 M9 7v13 M13 7v13 M17 9v11 M3 21h18",
    "Cave": P.cave,
    "Caving": "M5 15a7 7 0 0 1 14 0z M3 15h18 M12 8V5 M10 5h4",
    "Hike": "M6 4h6v7l7 3v5H5z M5 19h14",
    "Backpacker": "M7 8a5 5 0 0 1 10 0v12H7z M9 13h6 M10 4V2.5h4V4",
    "Bike": P.bike,
    "Mountain Biking": P.bike + " M14 4l2-2 2 2",
    "Canoe": P.boat + " M9.5 18.5l-1 2",
    "Kayak": "M2 13c4 4 16 4 20 0z M5 4l14 14 M3 2.5l3 3 M18 17l3 3",
    "Fuel": "M5 21V4h9v17 M3 21h13 M7 8h5 M14 9l4 2v7a1.5 1.5 0 0 0 3 0V8l-2-2",
    "Hot Spring": P.steam,
    "Geyser": "M12 20V9 M9 4c0 2 3 3 3 5 M15 4c0 2-3 3-3 5 M4 20h16",
    "Rapids": P.waves,
    "Washout": "M3 7h7l2 4 2-4h7 M2 15c3-2 5 2 8 0s5-2 8 0 4 0 4 0 M2 19c3-2 5 2 8 0s5-2 8 0 4 0 4 0",
    "Water Crossing": "M2 15c3-2 5 2 8 0s5-2 8 0 4 0 4 0 M2 19c3-2 5 2 8 0s5-2 8 0 4 0 4 0 M5 9h14 M15 6l3 3-3 3",
    "Crossing": "M4 8h16 M16 4l4 4-4 4 M20 16H4 M8 12l-4 4 4 4",
    "Steep Trail": "M3 20L20 5 M3 20h17V5 M8 15l2-2 M12 11l2-2",
    "Webcam": "M4 8h11v8H4z M15 11l5-3v8l-5-3 M8 19h3",
    "Emergency Phone": "M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2",
    "Visitor Center": "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18 M12 8h.01 M11 12h1v5h1",
    "Picnic Area": "M4 9h16 M7 9l-3 11 M17 9l3 11 M3 15h18",
    "Mushroom": P.mushroom,
    "Foraging": P.mushroom + " M18 4l2-2",
    "Ruins": "M4 20h16 M6 20V9 M10 20V7 M14 20v-8 M18 20v-5 M4 7h8",
    "Lighthouses": "M9 21l1.5-13h3L15 21 M8 8h8 M10 8V5h4v3 M12 5V3 M5 21h14",
    "Marina": "M12 8V21 M12 8a2 2 0 1 0 0-4 2 2 0 0 0 0 4z M8 12h8 M5 15c0 3.5 3 6 7 6s7-2.5 7-6",
    "Swimming": "M15 6.5h.01 M5 13l5-4 4 3 M2 17c3-2 5 2 8 0s5-2 8 0 4 0 4 0 M2 21c3-2 5 2 8 0s5-2 8 0 4 0 4 0",
    "Rappel": "M4 4h16 M12 4v17 M12 10c-3 0-4 2-4 4s1 3 2 3",
    "Mountaineer": "M8 4l9 17 M4 6c2-2 6-3 8-2l-1 2",
    "Gear": "M14 6a4 4 0 0 0-5 5L3 17l3 3 6-6a4 4 0 0 0 5-5l-3 3-3-3z",
    "Barrier": P.barrier,
    "Road Barrier": P.barrier + " M2 20h20",
    "Log Obstacle": "M4 13h14 M4 18h14 M18 13a2.5 2.5 0 0 1 0 5 M4 13a2.5 2.5 0 0 0 0 5 M9 13l-2-4",
    "Access Point": "M6 21V3h12v18 M3 21h18 M14 12h.01",
    "Food Storage": "M6 5h12v15H6z M6 9h12 M6 16h12",
    "Food Source": "M12 7c-3-2-8 0-7 6s5 8 7 6c2 2 6 0 7-6s-4-8-7-6z M12 7c0-2 1-3 3-4",
    "Stock Tank": "M3 9h18l-2 11H5z M3 9c0-2 18-2 18 0",
    "Truck": "M2 16V8h11v8z M13 11h5l3 3v2h-8 M5 18a2 2 0 1 0 4 0 2 2 0 1 0-4 0 M15 18a2 2 0 1 0 4 0 2 2 0 1 0-4 0",
    "SUV": P.car,
    "4x4": P.car,
    "Wildflower": "M12 12v9 M12 21c-3 0-5-2-5-4 3 0 5 1 5 4 M12 4a3 3 0 1 0 0 6 3 3 0 0 0 0-6",
    "Wetland": "M2 19c3-2 5 2 8 0s5-2 8 0 4 0 4 0 M7 16V8 M12 16V5 M17 16V9",
  };
  // No drawing yet: a short abbreviation inside the marker.
  const A = {
    "ATV": "AT", "Beach Combing": "Bc", "Dirt Bike": "DB", "Dog Sledding": "DS",
    "Eagle": "Ea", "Feeding Area": "Fd", "Hand Launch": "HL", "Hang Gliding": "HG",
    "Horseback": "Hb", "Kennels": "Kn", "Overland": "Ov", "Put In": "PI", "RV": "RV",
    "Raft": "Rf", "Sasquatch": "Sq", "Ski Areas": "SA", "Snowboarder": "Sb",
    "Snowmobile": "Sm", "Snowpark": "Sp", "Surfing Area": "Sf", "Take Out": "TO",
    "Windsurfing": "Ws",
  };
  const out = {};
  for (const [k, v] of Object.entries(G)) out[k] = { path: v };
  for (const [k, v] of Object.entries(A)) out[k] = { abbr: v };
  return out;
})();

/* Marker glyph ink per onX color, from the approved EditMark mockup: dark ink on
   the light colors, white on the rest. Anything else picks by contrast. */
const MARKER_FG = {
  "#FF3300": "#FFFFFF", "#087AFF": "#FFFFFF", "#00FFFF": "#2A241C", "#84D400": "#2A241C",
  "#000000": "#FFFFFF", "#FFFFFF": "#2A241C", "#800080": "#FFFFFF", "#FFFF00": "#2A241C",
  "#FF0000": "#FFFFFF", "#8B4513": "#FFFFFF",
};
function markerFg(hex) {
  const h = String(hex || "").toUpperCase();
  if (Object.hasOwn(MARKER_FG, h)) return MARKER_FG[h];
  const m = /^#([0-9A-F]{6})$/.exec(h);
  if (!m) return "#FFFFFF";
  const lin = c => { c /= 255; return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; };
  const n = parseInt(m[1], 16);
  const L = 0.2126 * lin(n >> 16 & 255) + 0.7152 * lin(n >> 8 & 255) + 0.0722 * lin(n & 255);
  return (1.05 / (L + 0.05)) >= ((L + 0.05) / 0.0592) ? "#FFFFFF" : "#2A241C";
}

const PIN_PATH = "M17 41 C17 41 3 26 3 16 A14 14 0 0 1 31 16 C31 26 17 41 17 41 Z";
const _escAttr = s => String(s ?? "").replace(/[&<>"']/g, c =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

/** Glyph for a name; an unknown name gets its own initials rather than
    masquerading as the default pin. */
function glyphFor(icon) {
  // hasOwn, not ONX_GLYPHS[icon]: an icon name comes from the input file, and
  // "constructor" or "toString" would otherwise find Object.prototype's
  // function and crash the render.
  if (Object.hasOwn(ONX_GLYPHS, icon)) return ONX_GLYPHS[icon];
  const words = String(icon || "").trim().split(/\s+/).filter(Boolean);
  if (!words.length) return ONX_GLYPHS["Location"];
  const abbr = words.length > 1 ? words[0][0] + words[1][0] : words[0].slice(0, 2);
  return { abbr: abbr[0].toUpperCase() + abbr.slice(1) };
}

/** The teardrop map marker: fill = the onX color, icon drawn inside. */
function markerSVG(icon, hex, w = 30, h = 38) {
  const g = glyphFor(icon);
  const fg = markerFg(hex);
  const inner = g.path
    ? `<g transform="translate(8 7) scale(0.75)" fill="none" stroke="${fg}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="${g.path}"/></g>`
    : `<text x="17" y="20.5" text-anchor="middle" font-size="${g.abbr.length > 1 ? 11 : 13}" font-weight="700" fill="${fg}" font-family="'Libre Caslon Text', Georgia, serif">${_escAttr(g.abbr)}</text>`;
  return `<svg class="marker" width="${w}" height="${h}" viewBox="0 0 34 42" aria-hidden="true">` +
    `<path d="${PIN_PATH}" fill="${_escAttr(hex)}" stroke="#2A241C" stroke-width="1"/>${inner}</svg>`;
}

/** The same marker in ink outline on paper, no color: the icon pickers' grids, so
    choosing a color recolors only the item being edited, never every choice. */
function markerOutlineSVG(icon, w = 30, h = 38) {
  const g = glyphFor(icon);
  const inner = g.path
    ? `<g transform="translate(8 7) scale(0.75)" fill="none" stroke="#2A241C" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="${g.path}"/></g>`
    : `<text x="17" y="20.5" text-anchor="middle" font-size="${g.abbr.length > 1 ? 11 : 13}" font-weight="700" fill="#2A241C" font-family="'Libre Caslon Text', Georgia, serif">${_escAttr(g.abbr)}</text>`;
  return `<svg class="marker outline" width="${w}" height="${h}" viewBox="0 0 34 42" aria-hidden="true">` +
    `<path d="${PIN_PATH}" fill="#FFFDF7" stroke="#2A241C" stroke-width="1.6"/>${inner}</svg>`;
}

/** Plain stroke glyph (no marker), for the rail's icon facet. */
function glyphSVG(icon, size = 18) {
  const g = glyphFor(icon);
  if (!g.path)
    return `<svg class="glyph" width="${size}" height="${size}" viewBox="0 0 24 24" aria-hidden="true"><text x="12" y="16" text-anchor="middle" font-size="11" font-weight="700" fill="currentColor" font-family="'Libre Caslon Text', Georgia, serif">${_escAttr(g.abbr)}</text></svg>`;
  return `<svg class="glyph" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${g.path}"/></svg>`;
}

/** onX line styles and weights (bridge LINE_STYLES / LINE_WEIGHTS), drawn.
    Dashes and dots use flat ends so neither the dash nor its dark underlay
    spills into the gaps. Width: [overlay, underlay] in the 30x26 swatch. */
const LINE_DASH = { solid: "", dash: "8 4", dot: "2 3.5" };
const LINE_WIDTH = { "4.0": [3, 5.4], "6.0": [5, 7.4] };
function _lineStroke(style, weight, scale = 1) {
  const dash = (LINE_DASH[style] || "").split(" ").filter(Boolean).map(n => n * scale).join(" ");
  const [w, uw] = (LINE_WIDTH[weight] || [4, 6]).map(n => n * scale);
  const cap = dash ? "butt" : "round";
  return { w, uw, attrs: `${dash ? ` stroke-dasharray="${dash}"` : ""} stroke-linecap="${cap}"` };
}

/** Lines get a drawn line in their color, style and weight; areas a filled
    patch. A dark underlay keeps white and yellow visible on the paper background. */
function lineSVG(hex, kind = "tracks", w = 30, h = 26, style = "solid", weight = "4.0") {
  if (kind === "shapes")
    return `<svg class="lineswatch" width="${w}" height="${h}" viewBox="0 0 30 26" aria-hidden="true">` +
      `<path d="M4 20 L8 6 L20 4 L26 14 L18 22 Z" fill="${_escAttr(hex)}" fill-opacity="0.45" stroke="#2A241C" stroke-width="3.6" stroke-linejoin="round"/>` +
      `<path d="M4 20 L8 6 L20 4 L26 14 L18 22 Z" fill="none" stroke="${_escAttr(hex)}" stroke-width="2" stroke-linejoin="round"/></svg>`;
  const k = _lineStroke(style, weight);
  return `<svg class="lineswatch" width="${w}" height="${h}" viewBox="0 0 30 26" aria-hidden="true">` +
    `<path d="M3 20 C 9 10, 15 22, 27 6" fill="none" stroke="#2A241C" stroke-width="${k.uw}"${k.attrs}/>` +
    `<path d="M3 20 C 9 10, 15 22, 27 6" fill="none" stroke="${_escAttr(hex)}" stroke-width="${k.w}"${k.attrs}/></svg>`;
}

/** A long straight sample in the line's color, style and weight (Line style dialog). */
function lineStripSVG(hex, style = "solid", weight = "4.0", w = 160) {
  const dash = { solid: "", dash: "14 9", dot: "3 6" }[style] || "";
  const [sw, uw] = weight === "6.0" ? [5, 7.4] : [3, 5.4];
  const d = `M3 9 H${w - 3}`, a = `${dash ? ` stroke-dasharray="${dash}"` : ""} stroke-linecap="butt"`;
  return `<svg class="linestrip" width="${w}" height="18" viewBox="0 0 ${w} 18" aria-hidden="true">` +
    `<path d="${d}" stroke="#2A241C" stroke-width="${uw}"${a}/><path d="${d}" stroke="${_escAttr(hex)}" stroke-width="${sw}"${a}/></svg>`;
}

/** Ink-only sample for the style / weight toggles: the drawn line is the label. */
function lineGlyphSVG(style = "solid", weight = null) {
  const dash = { solid: "", dash: "9 8", dot: "3 6" }[style] || "";
  const sw = weight === "6.0" ? 6 : weight === "4.0" ? 2.5 : 3;
  return `<svg class="lineglyph" width="100%" height="14" viewBox="0 0 90 14" preserveAspectRatio="none" aria-hidden="true">` +
    `<path d="M6 7 H84" stroke="#2A241C" stroke-width="${sw}"${dash ? ` stroke-dasharray="${dash}"` : ""} stroke-linecap="butt"/></svg>`;
}

/** The line drawn across a strip of contour paper, roughly as onX shows it. */
function lineMapSVG(hex, style = "solid", weight = "4.0") {
  const dash = { solid: "", dash: "16 13", dot: "4 9" }[style] || "";
  const sw = weight === "6.0" ? 6 : 4;
  const c = "#C9B58C";
  return `<svg class="linemap" width="100%" height="100%" viewBox="0 0 480 150" preserveAspectRatio="xMidYMid slice" aria-hidden="true">` +
    `<path d="M-10 40 C 80 10, 160 70, 260 30 S 420 10, 500 50" fill="none" stroke="${c}" stroke-width="1.2"/>` +
    `<path d="M-10 70 C 90 40, 170 100, 270 60 S 420 40, 500 80" fill="none" stroke="${c}" stroke-width="1.2"/>` +
    `<path d="M-10 100 C 100 70, 180 130, 280 90 S 420 70, 500 110" fill="none" stroke="${c}" stroke-width="1.6"/>` +
    `<path d="M-10 130 C 110 100, 190 160, 290 120 S 420 100, 500 140" fill="none" stroke="${c}" stroke-width="1.2"/>` +
    `<path d="M30 118 C 90 60, 150 120, 220 74 S 360 30, 452 52" fill="none" stroke="#2A241C" stroke-width="${sw + 2}"${dash ? ` stroke-dasharray="${dash}"` : ""} stroke-linecap="butt" stroke-linejoin="round" opacity=".55"/>` +
    `<path d="M30 118 C 90 60, 150 120, 220 74 S 360 30, 452 52" fill="none" stroke="${_escAttr(hex)}" stroke-width="${sw}"${dash ? ` stroke-dasharray="${dash}"` : ""} stroke-linecap="butt" stroke-linejoin="round"/></svg>`;
}

/** Small inline UI icons (chrome, not data). */
const UI_ICON = {
  cairn: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round" aria-hidden="true"><path d="M5 20h14M7 20l2-5h6l2 5M9 15l1.5-4h3L15 15M10.5 11 12 7l1.5 4"/></svg>',
  pencil: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 20h4L19 9l-4-4L4 16z"/></svg>',
  chevron: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M6 9l6 6 6-6"/></svg>',
  close: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg>',
  arrow: '<svg width="24" height="12" viewBox="0 0 24 12" aria-hidden="true"><path d="M2 6h18M15 1l5 5-5 5" fill="none" stroke="#7A4E25" stroke-width="1.6"/></svg>',
};
