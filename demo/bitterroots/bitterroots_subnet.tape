Output demo-bitterroots-subset-storyboard.gif

# This tape is designed to demonstrate the value of bulk editing Icon + Color
# (OnX can filter waypoints by icon + color), using a small Bitterroots subset.
#
# Generate with:
#   vhs demo/bitterroots_storyboard_subnet.tape

Set TypingSpeed 100ms
Set PlaybackSpeed 1.5

Set Shell "bash"
Set FontSize 18
Set Width 1800
Set Height 1000
Set Theme {"background":"#2A1F1D","black":"#573D26","blue":"#5A86AD","brightBlack":"#9B6C4A","brightBlue":"#B8D3ED","brightCyan":"#93CFD7","brightGreen":"#95D8BA","brightMagenta":"#D19ECB","brightRed":"#E84627","brightWhite":"#FFF9D5","brightYellow":"#D0D150","cursor":"#573D26","cyan":"#74A6AD","foreground":"#E0DBB7","green":"#6BA18A","magenta":"#AC80A6","red":"#BE2D26","selectionBackground":"#563C27","selectionForeground":"#E0DBBB","white":"#E0DBB7","yellow":"#E99D2A"}
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
Type "OPTIONS='demo/bitterroots/Bitterroots__Subset_.json -o demo/bitterroots/onx_ready_subset_storyboard_vhs --interactive'"
Enter
Type 'cd "$(git rev-parse --show-toplevel)"'
Enter
Type "rm -rf demo/bitterroots/onx_ready_subset_storyboard_vhs && mkdir -p demo/bitterroots/onx_ready_subset_storyboard_vhs"
Enter
Type "clear"
Enter
Show
Sleep 3s
Type "uv run cairn migrate onx $OPTIONS"
Enter
Sleep 8000ms

# Edit before export?
Sleep 5000ms
Type "y"
Enter

# Lost Horse Canyon (subset has waypoints only)
Sleep 3s
Type "y"
Enter

# Bulk-select climbing-related waypoints (mostly success with a couple typos)
# After extending the subset, titles sort such that:
#  5-7 are Main Wall-* items, 9 is Pullout boulders
Sleep 1200ms
Type "5-7,9"
Enter

# Name: keep
Sleep 3s
Enter
# Description: set a shared note (shows value of batch edits)
Sleep 3s
Type "Climbing - standardized icon+color for OnX filtering"
Enter

# Icon: typo first, then choose the suggested match
Sleep 3s
Type "Climbng"
Enter
Sleep 3s
Type "1"
Enter

# Color: typo first, then correct (show validation + recovery)
Sleep 3s
Type "BLEU"
Enter
Sleep 3s
Type "RED"
Enter

# Another waypoint edit? yes
Sleep 3s
Type "y"
Enter

# Parking waypoint: set icon+color to Parking+Blue (valid)
Sleep 3s
Type "8"
Enter
Sleep 3s
Enter
Sleep 3s
Enter
Sleep 3s
Type "Parking"
Enter
Sleep 3s
Type "BLUE"
Enter
Sleep 3s

# Another waypoint edit? yes
Sleep 3s
Type "y"
Enter

# Campsites: unify icon+color for quick filtering
Sleep 3s
Type "1-2"
Enter
Sleep 3s
Enter
Sleep 3s
Enter
Sleep 3s
Type "browse"
Enter
Sleep 3000ms
Type "Campground"
Enter

# Done editing
Sleep 3s
Enter
Sleep 3s
Enter

Sleep 6s
# Final gate: Ready to generate new map?
Sleep 3s
Type "y"
Enter

# Capture export + success summary
Sleep 10s
