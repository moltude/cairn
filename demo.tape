# Cairn CLI Demo (onX → CalTopo)
# Generate with: vhs demo.tape

Output demo.gif

Set TypingSpeed 45ms
Set PlaybackSpeed 1.0

Set Shell "bash"
Set FontSize 18
Set Width 1200
Set Height 650

# 1) Hide startup noise
Hide
Type "export PS1='➜ '"
Enter
Type "cd \"$(git rev-parse --show-toplevel)\""
Enter
Type "clear"
Enter
Show

# Title
Type "# Cairn - Migrate onX → CalTopo"
Enter
Sleep 800ms

# Show migrate help
Type "uv run cairn migrate onx-to-caltopo --help"
Enter
Sleep 4s

# Run migration using demo exports
Ctrl+L
Type "# Convert onX exports (GPX + KML) into CalTopo-ready GeoJSON"
Enter
Sleep 600ms
Type "mkdir -p demo/onx-to-caltopo/caltopo-ready"
Enter
Sleep 500ms
Type "uv run cairn migrate onx-to-caltopo demo/onx-to-caltopo/onx-export/onx-export.gpx --kml demo/onx-to-caltopo/onx-export/onx-export.kml --output-dir demo/onx-to-caltopo/caltopo-ready --name most_usable --trace demo/onx-to-caltopo/caltopo-ready/trace.jsonl"
Enter
Sleep 4s

# Show outputs
Ctrl+L
Type "ls -lh demo/onx-to-caltopo/caltopo-ready/"
Enter
Sleep 3s

# Show summary excerpt
Type "sed -n '1,80p' demo/onx-to-caltopo/caltopo-ready/most_usable_SUMMARY.md"
Enter
Sleep 4s

# Final message
Ctrl+L
Type "# Next: Import demo/onx-to-caltopo/caltopo-ready/most_usable.json into CalTopo"
Enter
Sleep 3s
