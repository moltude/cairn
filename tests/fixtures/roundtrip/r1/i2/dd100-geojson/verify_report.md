# Verify r1 · i2 · dd100-geojson

onX folder: `ZZTEST · r1 · i2 · dd100-geojson`  
onX export read: onx_export.gpx, onx_export.kml  
Expected 21 items, onX export has 21.

**19 PASS · 1 KNOWN_ONX_LIMIT · 1 FAIL**

| Status | Kind | Name | Field | Detail |
|---|---|---|---|---|
| FAIL | waypoint | [r1i2] 02 - Juniper Ridge AS (Used Twice) | notes | expected 512 chars 'JUNIPER RIDGE AS #1:\n\nMile 11.93\nMiles to next AS: 7.92\nElev'…, got 510 chars 'JUNIPER RIDGE AS #1:\n\nMile 11.93\nMiles to next AS: 7.92\nElev'… |
| KNOWN_ONX_LIMIT | track | [r1i2] 2027 Dark Divide 100 Mile Endurance Run | points | thinned by onX: 8089 -> 8088 points, same end points |
