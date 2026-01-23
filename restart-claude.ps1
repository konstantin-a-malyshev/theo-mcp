# Restart-ClaudeDesktop.ps1

# 1. Stop all Claude Desktop processes (main + child processes)
Get-Process -Name "Claude" -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 2

# 2. Start Claude Desktop again
# Adjust the path below if your install location is different
$claudePath = "C:\Users\MALY022\AppData\Local\AnthropicClaude\claude.exe"

if (Test-Path $claudePath) {
    Start-Process $claudePath
} else {
    Write-Error "Claude Desktop not found at: $claudePath"
}
