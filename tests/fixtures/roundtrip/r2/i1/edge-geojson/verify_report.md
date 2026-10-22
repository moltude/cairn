# Verify r2 · i1 · edge-geojson

onX folder: `ZZTEST · r2 · i1 · edge · geojson`  
onX export read: onx_export.gpx, onx_export.kml  
Expected 28 items, onX export has 28.

**16 PASS · 12 KNOWN_ONX_LIMIT · 0 FAIL**

| Status | Kind | Name | Field | Detail |
|---|---|---|---|---|
| KNOWN_ONX_LIMIT | track | [r2i1] ZZTEST dashed line | points | thinned by onX: 12 -> 8 points, same end points |
| KNOWN_ONX_LIMIT | track | [r2i1] ZZTEST line note 3000 | notes | 3000-byte note cut to 512 by onX import |
| KNOWN_ONX_LIMIT | track | [r2i1] ZZTEST line note 3000 | points | thinned by onX: 12 -> 8 points, same end points |
| KNOWN_ONX_LIMIT | track | [r2i1] ZZTEST line note 511 | points | thinned by onX: 12 -> 8 points, same end points |
| KNOWN_ONX_LIMIT | track | [r2i1] ZZTEST line note 512 | points | thinned by onX: 12 -> 8 points, same end points |
| KNOWN_ONX_LIMIT | track | [r2i1] ZZTEST line note 513 | notes | 513-byte note cut to 512 by onX import |
| KNOWN_ONX_LIMIT | track | [r2i1] ZZTEST line note 513 | points | thinned by onX: 12 -> 8 points, same end points |
| KNOWN_ONX_LIMIT | track | [r2i1] ZZTEST wide line | points | thinned by onX: 12 -> 8 points, same end points |
| KNOWN_ONX_LIMIT | waypoint | [r2i1] ZZTEST note 1000 | notes | 1000-byte note cut to 512 by onX import |
| KNOWN_ONX_LIMIT | waypoint | [r2i1] ZZTEST note 3000 | notes | 3000-byte note cut to 512 by onX import |
| KNOWN_ONX_LIMIT | waypoint | [r2i1] ZZTEST note 513 | notes | 513-byte note cut to 512 by onX import |
| KNOWN_ONX_LIMIT | waypoint | [r2i1] ZZTEST note 600 | notes | 600-byte note cut to 512 by onX import |
| KNOWN_ONX_LIMIT | waypoint | [r2i1] ZZTEST utf8 note 513B | notes | 513-byte note cut to 512 by onX import |
| KNOWN_ONX_LIMIT | waypoint | [r2i1] ZZTEST utf8 note mid-char | notes | 514-byte note cut to 511 by onX import |
