# Cairn CLI Demo (onX → CalTopo)
# Generate with: vhs demo.tape

Output demo.gif

Set TypingSpeed 45ms
Set PlaybackSpeed 1.2

Set Shell "bash"
Set FontSize 14
Set Width 1500
Set Height 900

# 1) Hide startup noise
Hide
Type "export PS1='➜ '"
Enter
Type "mkdir -p demo/onx-to-caltopo/caltopo-ready"
Enter
Type 'cd "$(git rev-parse --show-toplevel)"'
Enter
Type "clear"
Enter
Show

# Title
Type "# Cairn - Migrate onX → CalTopo"
Enter
Sleep 800ms

# Show migrate help (optional)
# Type "uv run cairn migrate onx-to-caltopo --help"
# Enter
# Sleep 6s

# Run migration using demo exports
Ctrl+L
Type "# Convert onX exports (GPX + KML) into CalTopo-ready GeoJSON"
Enter
Sleep 600ms
Sleep 500ms
Type "rm -rf demo/onx-to-caltopo/caltopo-ready/tape-run && mkdir -p demo/onx-to-caltopo/caltopo-ready/tape-run"
Enter
Sleep 400ms

# Multiline command typed like a human (VHS doesn't support embedded newlines inside one Type)
Type 'uv run cairn migrate onx-to-caltopo \'
Enter
Type '  --gpx demo/onx-to-caltopo/onx-export/onx-export.gpx \'
Enter
Type '  --kml demo/onx-to-caltopo/onx-export/onx-export.kml \'
Enter
Type '  --output-dir demo/onx-to-caltopo/caltopo-ready/tape-run \'
Enter
Type '  --name caltopo-map \'
Enter
Type '  --trace demo/onx-to-caltopo/caltopo-ready/tape-run/trace.jsonl'
Enter
Sleep 4s

# Show summary excerpt
Type "sed -n '1,25p' demo/onx-to-caltopo/caltopo-ready/tape-run/caltopo-map_SUMMARY.md"
Enter
Sleep 4s

# Show outputs
Ctrl+L
Type "ls -lh demo/onx-to-caltopo/caltopo-ready/tape-run/"
Enter
Sleep 3s

# Final message
Ctrl+L
Type "# Next: Import demo/onx-to-caltopo/caltopo-ready/tape-run/caltopo-map.json into CalTopo"
Sleep 5s
