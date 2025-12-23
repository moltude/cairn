# Cairn Migrate OnX Demo
# Generate with: vhs demo.tape

Output demo.gif

Set TypingSpeed 200ms
Set PlaybackSpeed 1.0

Set Shell "bash"
Set FontSize 20
Set Width 1800
Set Height 1000

# Setup
Hide
Type "export PS1='➜ '"
Enter
Type "printf '\033[1 q'"
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
Type "clear"
Enter
Show

# Title
Type "# Caltopo to onX"
Enter
Sleep 2s

# Run the migrate command
Type "uv run cairn tui"
Sleep 2s
Enter

# Navigate through TUI interface
# SELECT demo/
Down
Down
Sleep 1s
Down
Down
Down
Sleep 1s
Enter
Sleep 1s

# SELECT bitterroots/
Down
# Sleep 1s
Enter

# SELECT subset.json
Down
Down
Down
Sleep 1s
Enter

# Summary
Sleep 2s
Enter

# Folder
Sleep 2s
Enter

# Routes (none)
Sleep 1s
Enter

# Select and modify waypoints
# Edit campsites
# - Change color
# - Change description
# - Change name
Space
Sleep 1s
Down
Sleep 1s
Space
Sleep 1s
Enter
Sleep 1s
Enter
Sleep 1s
Type "Campsites"
Enter
Sleep 3s
Enter
Sleep 1s
Down
Down
Down
Sleep 2s
Enter

# Change color
Down
Down
Down
Down
Enter
Sleep 8s
Escape

# Edit ski touring
# - Normalize icons
# - Add description
Down
Down
Down
Space
Down
Space
Sleep 1s
Down
Down
Down
Down
Down
Down
Sleep 1s
Enter
Down
Enter
Sleep 1s
Type "Ski touring"
Enter
Down
Down
Sleep 1s
Enter
Tab
Tab
Tab
Type "ski"
Tab
Down
Down
Sleep 2s
Enter
Down
Down
Down
Enter
Down
Sleep 1s
Enter
Down
Down
Down
Down
Sleep 3s
Enter
Sleep 2s



# Edit color for climbing

# Pause for 5s
# Move on to next screen

Sleep 5s
Escape
