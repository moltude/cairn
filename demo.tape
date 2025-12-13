# Cairn CLI Demo
# Generate with: vhs demo.tape

Output demo.gif

Set TypingSpeed 50ms
Set PlaybackSpeed 1.0

Set Shell "bash"
Set FontSize 18
Set Width 1200
Set Height 600

# 1. Hide the startup noise
Hide
Type "export PS1='➜ '"
Enter
Type "clear"
Enter
Show


# Title screen
Type "# Cairn - CalTopo to OnX Migration Tool"
Sleep 2s
Enter
Sleep 500ms

# Show main help
Type "uv run cairn --help"
Sleep 500ms
Enter
Sleep 3s

# Clear and show dry-run preview
Ctrl+L
Type "# Preview conversion with --dry-run"
Enter
Sleep 500ms
Type "uv run cairn convert sample-maps/Dark_Divide_100_Miler.json --dry-run"
Sleep 500ms
Enter
Sleep 5s

# Actual conversion
Ctrl+L
Type "# Convert CalTopo export to OnX"
Enter
Sleep 500ms
Type "uv run cairn convert sample-maps/Dark_Divide_100_Miler.json --output demo_output"
Sleep 500ms
Enter
Sleep 2s
# Respond to prompt with option 5
Type "5"
Sleep 1s
Enter
Sleep 4s

# Show output files
Sleep 1s
Type "ls -lh demo_output/"
Sleep 500ms
Enter
Sleep 3s

# Final message
Sleep 1s
Type "# ✨ Ready to import your maps!"
Enter
Sleep 3s
