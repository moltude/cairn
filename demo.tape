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
Type "rm -rf demo/onx-to-caltopo/caltopo-ready/tape-run && mkdir -p demo/onx-to-caltopo/caltopo-ready/tape-run"
Enter
Type 'cd "$(git rev-parse --show-toplevel)"'
Enter
Type "clear"
Enter
Show

# Title
Type "# Convert onX exports (GPX + KML) into CalTopo-ready GeoJSON"
Enter
Sleep 400ms

# Run the interactive CLI (prompts for inputs)
Type "uv run cairn migrate onx-to-caltopo"
Enter

# Prompt: GPX path
Type "demo/onx-to-caltopo/onx-export/onx-export.gpx"
Enter

# Prompt: KML path
Type "demo/onx-to-caltopo/onx-export/onx-export.kml"
Enter
Sleep 2s

# Prompt: output directory
Type "demo/onx-to-caltopo/caltopo-ready/tape-run"
Enter
Sleep 2s

# Prompt: base filename
Type "caltopo-map"
Enter
Sleep 2s

# Show summary excerpt
Type "sed -n '1,25p' demo/onx-to-caltopo/caltopo-ready/tape-run/caltopo-map_SUMMARY.md"
Enter
Sleep 5s

# Final message
Type "# Ready to import caltopo-map.json into CalTopo"
Sleep 5s
