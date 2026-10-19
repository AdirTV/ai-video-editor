# AI video editor for Premiere — one-shot installer for Windows (PowerShell).
# Run from the repo:  powershell -ExecutionPolicy Bypass -File setup\install-windows.ps1 [-EditingRoot PATH] [-Language he|en|auto] [-NoMinecraft] [-Yes]
#   -Yes  never prompt (for an AI assistant running the install).
param([string]$EditingRoot = "", [string]$Language = "auto", [switch]$NoMinecraft, [switch]$Yes)
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
$Repo = (Get-Location).Path
function Step($t) { Write-Host "`n== $t" -ForegroundColor Magenta }
function Refresh-Path { $env:Path = [Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [Environment]::GetEnvironmentVariable("Path","User") }

Step "1/8 ffmpeg, Node, uv, yt-dlp, Git"
foreach ($id in "Gyan.FFmpeg","OpenJS.NodeJS.LTS","astral-sh.uv","yt-dlp.yt-dlp","Git.Git") {
  winget install --id $id -e --accept-source-agreements --accept-package-agreements --silent
}
Refresh-Path

Step "2/8 Claude Code"
if (-not (Get-Command claude -ErrorAction SilentlyContinue)) { irm https://claude.ai/install.ps1 | iex; Refresh-Path }
$Claude = (Get-Command claude -ErrorAction SilentlyContinue).Source
if (-not $Claude) { $Claude = "$env:USERPROFILE\.local\bin\claude.exe" }

Step "3/8 Premiere MCP bridge + panel"
npm install -g premiere-pro-mcp@1.24.1
Refresh-Path
premiere-pro-mcp --install-cep
$Panel = Join-Path $env:APPDATA "Adobe\CEP\extensions\MCPBridgeCEP"
Copy-Item panel\index.html, panel\styles.css -Destination $Panel -Force

Step "4/8 Editing tools (Python + Remotion)"
uv sync
Push-Location remotion; npm install; Pop-Location

Step "5/8 Settings"
$Er = $EditingRoot
if (-not $Er -and -not $Yes) { $Er = Read-Host "Where do you keep your editing projects? [$env:USERPROFILE\Desktop\editing]" }
if (-not $Er) { $Er = "$env:USERPROFILE\Desktop\editing" }
New-Item -ItemType Directory -Force "$env:USERPROFILE\.mce" | Out-Null
@{ editing_root = $Er; sfx_lib = (Join-Path $Er "SFX"); language = $Language; profile = "general"; minecraft = (-not $NoMinecraft) } | ConvertTo-Json | Set-Content -Encoding UTF8 "$env:USERPROFILE\.mce\config.json"
$kinds = @("whoosh","pop","beep","click","shutter","typing","riser","impact","ding","magic","glitch"); if (-not $NoMinecraft) { $kinds += "minecraft" }
foreach ($k in $kinds) { New-Item -ItemType Directory -Force (Join-Path $Er "SFX\$k") | Out-Null }
if (-not (Test-Path style.md)) { if ($Language -eq "en") { Copy-Item style.template.en.md style.md } else { Copy-Item style.template.md style.md } }
if (-not (Test-Path vocab.txt)) { New-Item vocab.txt | Out-Null }

Step "6/8 Skills"
if ($NoMinecraft) { uv run python setup\install_skills.py --skip minecraft-edit } else { uv run python setup\install_skills.py }
npx -y skills add remotion-dev/skills -g -a claude-code -y

Step "7/8 Connect Premiere to Claude"
& $Claude mcp remove premiere -s user 2>$null
& $Claude mcp add premiere -s user -e PREMIERE_MCP_TOOL_PACKS=essential,inspection,captions -- premiere-pro-mcp

uv run python setup\doctor.py
Step "8/8 Done"
Write-Host "Next: restart Premiere -> Window > Extensions > MCP for Adobe Premiere Pro -> Start." -ForegroundColor Green
Write-Host "Then open a terminal in your project folder and run: claude"
