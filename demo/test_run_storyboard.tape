Output test-run-storyboard.gif

# Record a deterministic test run as a GIF so users can “see” the workflow and results.
#
# Generate with:
#   vhs demo/test_run_storyboard.tape

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
Type 'cd "$(git rev-parse --show-toplevel)"'
Enter
Type "clear"
Enter
Show

Type "# Cairn: run a focused regression test (Bitterroots Complete)"
Enter
Sleep 2s

Type "uv run --with pytest pytest -q tests/test_caltopo_to_onx_bitterroots_complete.py"
Enter
Sleep 12s
