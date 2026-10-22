#!/bin/zsh
# Operator helper for scripts/onx_roundtrip.py: after exporting a test folder from onX as GPX
# and then KML, move the fresh downloads into the set and run verify.
#   scripts/onx_fetch_export.sh <run> <stage> <set> [gpx|kml|both]
# Only downloads under 3 minutes old are taken: a silently failed export must not let an older
# download be verified instead (it did once, r1). Other fresh onX downloads are parked in
# tests/output/stale_downloads/ so a later set cannot pick them up.
set -u
RUN=$1 STAGE=$2 SET=$3 WHICH=${4:-both}
S=tests/fixtures/roundtrip/$RUN/$STAGE/$SET; mkdir -p $S/onx_export
newest() { find ~/Downloads -maxdepth 1 -name "onx-markups-*.$1" -mmin -3 -exec /bin/ls -t {} + 2>/dev/null | head -1 }
if [[ $WHICH != kml ]]; then G=$(newest gpx); [[ -z $G ]] && { echo "no onX GPX download in the last 3 minutes"; exit 2 }; mv "$G" $S/onx_export/onx_export.gpx; fi
if [[ $WHICH != gpx ]]; then K=$(newest kml); [[ -z $K ]] && { echo "no onX KML download in the last 3 minutes"; exit 2 }; mv "$K" $S/onx_export/onx_export.kml; fi
mkdir -p tests/output/stale_downloads
for f in ~/Downloads/onx-markups-*(N.mm-3); do mv "$f" tests/output/stale_downloads/; done
exec uv run python scripts/onx_roundtrip.py verify --run $RUN --stage $STAGE --set $SET \
  --onx $S/onx_export/onx_export.gpx $S/onx_export/onx_export.kml
