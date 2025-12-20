Output demo-small-storyboard.gif

# Quick, low-friction demo: dry run + export on a small CalTopo-style GeoJSON file.
#
# Generate with:
#   vhs demo/demo_small_storyboard.tape

Set TypingSpeed 75ms
Set PlaybackSpeed 1.3

Set Shell "bash"
Set FontSize 18
Set Width 1800
Set Height 1000

Hide
Type "export PS1='➜ '"
Enter
Type "export TERM=xterm-256color"
Enter
Type "export COLORTERM=truecolor"
Enter
Type "export RICH_FORCE_TERMINAL=1"
Enter
Type "export FORCE_COLOR=1"
Enter
Type 'cd "$(git rev-parse --show-toplevel)"'
Enter
Type "rm -rf demo/onx_ready_demo_small && mkdir -p demo/onx_ready_demo_small"
Enter
Type "clear"
Enter
Show

Type "# Cairn demo: small CalTopo → OnX dataset"
Enter
Sleep 2s

Type "# Step 1: dry run (no files written)"
Enter
Type "uv run cairn convert --dry-run demo/demo_small_caltopo.json"
Enter
Sleep 8s

Type "# Step 2: export OnX-ready GPX/KML"
Enter
Type "uv run cairn convert demo/demo_small_caltopo.json -o demo/onx_ready_demo_small --yes --no-edit"
Enter
Sleep 8s

Type "# Step 3: show outputs"
Enter
Type "ls -1 demo/onx_ready_demo_small | sed -n '1,20p'"
Enter
Sleep 6s
