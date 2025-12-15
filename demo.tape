# Cairn CLI Demo (OnX → CalTopo)
# Generate with: vhs demo.tape

Output demo.gif

Set TypingSpeed 45ms
Set PlaybackSpeed 1.2

Set Shell "bash"
Set FontSize 14
Set Width 1800
Set Height 1000

# 1) Hide startup noise
Hide
Type "export PS1='➜ '"
Enter
Type "rm -rf demo/OnX-to-caltopo/caltopo-ready/tape-run && mkdir -p demo/OnX-to-caltopo/caltopo-ready/tape-run"
Enter
Type 'cd "$(git rev-parse --show-toplevel)"'
Enter
Type "clear"
Enter
Show

# Title
Type "# Convert OnX exports (GPX + KML) into CalTopo-ready GeoJSON"
Enter
Sleep 400ms

# Run the interactive CLI (prompts for inputs)
Type "uv run cairn migrate OnX-to-caltopo"
Sleep 2s
Enter
# Prompt: GPX path
Sleep 2s
Type "demo/OnX-to-caltopo/OnX-export/OnX-export.gpx"
Sleep 500ms
Enter
# Prompt: KML path
Type "demo/OnX-to-caltopo/OnX-export/OnX-export.kml"
Enter
Sleep 2s
# Prompt: output directory
Type "demo/OnX-to-caltopo/caltopo-ready/tape-run"
Enter
Sleep 2s

# Prompt: base filename
Type "caltopo-map"
Enter
Type "# Ready to import caltopo-map.json into CalTopo"
Sleep 7s
