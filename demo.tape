# Cairn Migrate OnX Demo
# Generate with: vhs demo.tape

Output demo.gif

Set TypingSpeed 100ms
Set PlaybackSpeed 1.2

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
Type "# Migrate OnX waypoints with interactive editing"
Enter
Sleep 2s

# Run the migrate command
Type "cairn migrate onx"
Sleep 2s
Enter

# Input: demo/bitterroots/
Sleep 2s
Type "demo/bitterroots/"
Sleep 3s
Enter

# Input: 2
Sleep 2s
Type "2"
Sleep 3s
Enter
Sleep 4s

# Input: y
Sleep 4s
Type "y"
Sleep 3s
Enter

# Input: y
Sleep 2s
Type "y"
Sleep 3s
Enter

# Input: 3
Sleep 2s
Type "3"
Sleep 3s
Enter

# Input: Cool chute
Sleep 2s
Type "Cool chute"
Sleep 3s
Enter

# Input: let it rip
Sleep 2s
Type "let it rip"
Sleep 3s
Enter

# Input: browse
Sleep 2s
Type "browse"
Sleep 3s
Enter

# Input: Clour
Sleep 2s
Type "Clour"
Sleep 3s
Enter

# Input: ski touring
Sleep 2s
Type "ski touring"
Sleep 3s
Enter

# Input: purple
Sleep 2s
Type "purple"
Sleep 3s
Enter

# Input: y
Sleep 2s
Type "y"
Sleep 3s
Enter

# Input: 10,4
Sleep 2s
Type "10,4"
Sleep 3s
Enter

# Input: enter (just press enter)
Sleep 2s
Enter

# Input: enter (just press enter)
Sleep 2s
Enter

# Input: ski touring
Sleep 2s
Type "ski touring"
Sleep 3s
Enter

# Input: 7
Sleep 2s
Type "7"
Sleep 3s
Enter

# Input: n
Sleep 2s
Type "n"
Sleep 3s
Enter

# Input: y
Sleep 2s
Type "y"
Sleep 3s
Enter

# Input: y
Sleep 2s
Type "y"
Sleep 3s
Enter

# Final pause to show completion
Sleep 10s
