# AI video editor for Premiere — one-shot installer for Windows (PowerShell).
# Run from the repo:  powershell -ExecutionPolicy Bypass -File setup\install-windows.ps1 [-EditingRoot PATH] [-Language he|en|auto] [-NoMinecraft] [-ExportVia auto|ame|premiere] [-Yes]
#   -Yes  never prompt (for an AI assistant running the install).
#   Safe to re-run: finished steps are skipped or repeated harmlessly, and existing settings are kept.
param([string]$EditingRoot = "", [string]$Language = "", [switch]$NoMinecraft, [string]$ExportVia = "", [switch]$Yes)
$ErrorActionPreference = "Stop"
# Native tools don't trip ErrorActionPreference: stop on a failed exit code ourselves
function Native { & $args[0] @($args | Select-Object -Skip 1); if ($LASTEXITCODE) { throw "'$($args -join ' ')' failed (exit $LASTEXITCODE). Fix the error above and run the installer again - it is safe to re-run." } }
function Need($cmd, $fix) { if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) { throw "$cmd is still missing after install: $fix, then run the installer again." } }
Set-Location (Join-Path $PSScriptRoot "..")
$Repo = (Get-Location).Path
function Step($t) { Write-Host "`n== $t" -ForegroundColor Magenta }
function Refresh-Path { $env:Path = [Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [Environment]::GetEnvironmentVariable("Path","User") }

Step "1/8 ffmpeg, Node, uv, yt-dlp, Git"
foreach ($id in "Gyan.FFmpeg","OpenJS.NodeJS.LTS","astral-sh.uv","yt-dlp.yt-dlp","Git.Git") {
  winget install --id $id -e --accept-source-agreements --accept-package-agreements --silent
}
Refresh-Path
Need ffmpeg "winget install Gyan.FFmpeg"; Need npm "winget install OpenJS.NodeJS.LTS"; Need uv "winget install astral-sh.uv"; Need git "winget install Git.Git"
# Python prints Hebrew and emoji: make UTF-8 the default for this user's Python (cp1255/cp1252 otherwise)
[Environment]::SetEnvironmentVariable("PYTHONUTF8", "1", "User"); $env:PYTHONUTF8 = "1"

Step "2/8 Claude Code"
if (-not (Get-Command claude -ErrorAction SilentlyContinue)) { irm https://claude.ai/install.ps1 | iex; Refresh-Path }
$Claude = (Get-Command claude -ErrorAction SilentlyContinue).Source
if (-not $Claude) { $Claude = "$env:USERPROFILE\.local\bin\claude.exe" }

Step "3/8 Premiere MCP bridge + panel"
$McpVer = (Select-String -Path mce\config.py -Pattern '^PREMIERE_MCP_VERSION = "(.*)"').Matches[0].Groups[1].Value
Native npm install -g "premiere-pro-mcp@$McpVer"
Refresh-Path
Native premiere-pro-mcp --install-cep
$Panel = Join-Path $env:APPDATA "Adobe\CEP\extensions\MCPBridgeCEP"
Copy-Item panel\index.html, panel\styles.css -Destination $Panel -Force

Step "4/8 Editing tools (Python + Remotion)"
Native uv sync
Push-Location remotion; try { Native npm install } finally { Pop-Location }

Step "5/8 Settings"
$Er = $EditingRoot
if (-not $Er -and -not $Yes -and -not (Test-Path "$env:USERPROFILE\.mce\config.json")) { $Er = Read-Host "Where do you keep your editing projects? [$env:USERPROFILE\Desktop\editing]" }
if (-not $Er -and -not (Test-Path "$env:USERPROFILE\.mce\config.json")) { $Er = "$env:USERPROFILE\Desktop\editing" }
# written by Python: UTF-8 without a BOM, merged into any existing settings
$cfgFile = "$env:USERPROFILE\.mce\config.json"
if (-not $ExportVia -and -not $Yes -and (Test-Path "$env:ProgramFiles\Adobe\Adobe Media Encoder*") -and
    -not ((Test-Path $cfgFile) -and (Select-String -Path $cfgFile -Pattern '"export_via"' -Quiet))) {
  $A = Read-Host "Adobe Media Encoder found. Render exports there (Premiere stays free, and an export crash can't take it down)? [Y/n]"
  $ExportVia = if ($A -match '^[nN]') { "premiere" } else { "ame" }
}
Native uv run python setup\write_config.py --editing-root "$Er" --language "$Language" --minecraft $(if ($NoMinecraft) { "0" } else { "1" }) --export-via "$ExportVia"
if (-not (Test-Path style.md)) { if ($Language -eq "en") { Copy-Item style.template.en.md style.md } else { Copy-Item style.template.md style.md } }
if (-not (Test-Path vocab.txt)) { New-Item vocab.txt | Out-Null }
if (-not (Test-Path brand.json)) { Copy-Item brand.example.json brand.json }

Step "6/8 Skills"
if ($NoMinecraft) { Native uv run python setup\install_skills.py --skip minecraft-edit } else { Native uv run python setup\install_skills.py }
npx -y skills add remotion-dev/skills -g -a claude-code -y
if ($LASTEXITCODE) { Write-Host "Remotion skills not installed (optional) - retry later with the same command" -ForegroundColor Yellow }

Step "7/8 Connect Premiere to Claude"
& $Claude mcp remove premiere -s user 2>$null
Native $Claude mcp add premiere -s user -e PREMIERE_MCP_TOOL_PACKS=essential,inspection,captions -- premiere-pro-mcp

uv run python setup\doctor.py
Step "8/8 Done"
Write-Host "Next: restart Premiere -> Window > Extensions > MCP for Adobe Premiere Pro -> Start." -ForegroundColor Green
Write-Host "Then open a terminal in your project folder and run: claude"
