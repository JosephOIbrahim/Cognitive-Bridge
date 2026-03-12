# Snapshot file
# Unset all aliases to avoid conflicts with functions
unalias -a 2>/dev/null || true
shopt -s expand_aliases
# Check for rg availability
if ! (unalias rg 2>/dev/null; command -v rg) >/dev/null 2>&1; then
  alias rg=''\''C:\Users\User\.cursor\extensions\anthropic.claude-code-2.1.39-win32-x64\resources\native-binary\claude.exe'\'' --ripgrep'
fi
export PATH=$PATH
