# AI video editor for Premiere — one-shot installer for Windows (PowerShell).
# Run from the repo:  powershell -ExecutionPolicy Bypass -File setup\install-windows.ps1 [-EditingRoot PATH] [-Language he|en|auto] [-ExportVia auto|ame|premiere] [-Yes]
#   -Yes  never prompt (for an AI assistant running the install).
#   Safe to re-run: finished steps are skipped or repeated harmlessly, and existing settings are kept.
param([string]$EditingRoot = "", [string]$Language = "", [string]$ExportVia = "", [switch]$Yes)
$ErrorActionPreference = "Stop"
# Native tools don't trip ErrorActionPreference: stop on a failed exit code ourselves
function Native { & $args[0] @($args | Select-Object -Skip 1); if ($LASTEXITCODE) { throw "'$($args -join ' ')' failed (exit $LASTEXITCODE). Fix the error above and run the installer again - it is safe to re-run." } }
function Need($cmd, $fix) { if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) { throw "$cmd is still missing after install: $fix, then run the installer again." } }
Set-Location (Join-Path $PSScriptRoot "..")
$Repo = (Get-Location).Path
function Step($t) { Write-Host "`n== $t" -ForegroundColor Magenta }
# Every run is logged, so a failure can be read (or sent) after the window closes
$LogDir = Join-Path $env:LOCALAPPDATA "mce\logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$Log = Join-Path $LogDir ("install-" + (Get-Date -Format "yyyyMMdd-HHmmss") + ".log")
try { Start-Transcript -Path $Log -Append | Out-Null } catch { $Log = $null }
trap {
  Write-Host "`nInstall stopped: $_" -ForegroundColor Red
  if ($Log) { Write-Host "Log: $Log" }
  Write-Host "Fix that and run the installer again - finished steps are skipped." -ForegroundColor Yellow
  try { Stop-Transcript | Out-Null } catch {}
  exit 1
}
function Refresh-Path { $env:Path = [Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [Environment]::GetEnvironmentVariable("Path","User") }

Step "1/8 ffmpeg, Node, uv, yt-dlp, Git"
# Only what's missing is installed. winget is the easy way, not the only one: when it is missing or
# blocked (company PCs, sandboxed AI agents) each tool has an official installer to use instead.
$Tools = @(
  @{ Cmd = "ffmpeg"; Id = "Gyan.FFmpeg";       Req = $true;  Url = "https://www.gyan.dev/ffmpeg/builds/ (ffmpeg-release-essentials.zip; add its bin folder to PATH)" },
  @{ Cmd = "npm";    Id = "OpenJS.NodeJS.LTS"; Req = $true;  Url = "https://nodejs.org/en/download (Windows Installer, LTS)" },
  @{ Cmd = "uv";     Id = "astral-sh.uv";      Req = $true;  Url = 'powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"' },
  @{ Cmd = "git";    Id = "Git.Git";           Req = $true;  Url = "https://git-scm.com/download/win" },
  @{ Cmd = "yt-dlp"; Id = "yt-dlp.yt-dlp";     Req = $false; Url = "https://github.com/yt-dlp/yt-dlp/releases/latest (yt-dlp.exe, into a folder on PATH)" }
)
$HaveWinget = [bool](Get-Command winget -ErrorAction SilentlyContinue)
$Missing = @()
foreach ($t in $Tools) {
  if (Get-Command $t.Cmd -ErrorAction SilentlyContinue) { Write-Host "  $($t.Cmd): already installed"; continue }
  if (-not $HaveWinget) { $Missing += $t; continue }
  Write-Host "  $($t.Cmd): installing with winget ($($t.Id))"
  winget install --id $t.Id -e --accept-source-agreements --accept-package-agreements --silent
  $code = $LASTEXITCODE
  Refresh-Path
  # winget's exit code alone isn't trusted either way ("already installed" is non-zero): the command must now exist
  if (-not (Get-Command $t.Cmd -ErrorAction SilentlyContinue)) {
    Write-Host "  $($t.Cmd): winget failed (exit $code)" -ForegroundColor Yellow
    $Missing += $t
  }
}
if (-not $HaveWinget) {
  Write-Host "winget isn't available on this PC (or this shell can't run it)." -ForegroundColor Yellow
}
$Req = @($Missing | Where-Object { $_.Req })
foreach ($t in $Missing) {
  $c = if ($t.Req) { "Red" } else { "Yellow" }
  Write-Host ("  missing: {0}{1}`n    install from: {2}" -f $t.Cmd, $(if ($t.Req) { "" } else { " (optional)" }), $t.Url) -ForegroundColor $c
}
if ($Req.Count) {
  throw ("required tools missing: " + (($Req | ForEach-Object { $_.Cmd }) -join ", ") +
         ". Install them from the links above, open a NEW PowerShell window, and run the installer again." +
         " (Running inside an AI agent's sandbox? winget is often blocked there - run the installer in a normal PowerShell window.)")
}
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
# the real Desktop: often OneDrive\Desktop, not %USERPROFILE%\Desktop (write_config.py uses the same default)
$DefaultRoot = Join-Path ([Environment]::GetFolderPath("Desktop")) "editing"
if (-not $Er -and -not $Yes -and -not (Test-Path "$env:USERPROFILE\.mce\config.json")) { $Er = Read-Host "Where do you keep your editing projects? [$DefaultRoot]" }
if ($Er) { $Er = [IO.Path]::GetFullPath($Er.Trim().Trim('"')) }
# written by Python: UTF-8 without a BOM, merged into any existing settings
$cfgFile = "$env:USERPROFILE\.mce\config.json"
if (-not $ExportVia -and -not $Yes -and (Test-Path "$env:ProgramFiles\Adobe\Adobe Media Encoder*") -and
    -not ((Test-Path $cfgFile) -and (Select-String -Path $cfgFile -Pattern '"export_via"' -Quiet))) {
  $A = Read-Host "Adobe Media Encoder found. Render exports there (Premiere stays free, and an export crash can't take it down)? [Y/n]"
  $ExportVia = if ($A -match '^[nN]') { "premiere" } else { "ame" }
}
Native uv run python setup\write_config.py --editing-root "$Er" --language "$Language" --export-via "$ExportVia"
if (-not (Test-Path style.md)) { if ($Language -eq "en") { Copy-Item style.template.en.md style.md } else { Copy-Item style.template.md style.md } }
if (-not (Test-Path vocab.txt)) { New-Item vocab.txt | Out-Null }
if (-not (Test-Path brand.json)) { Copy-Item brand.example.json brand.json }

Step "6/8 Skills"
Native uv run python setup\install_skills.py
npx -y skills add remotion-dev/skills -g -a claude-code -y
if ($LASTEXITCODE) { Write-Host "Remotion skills not installed (optional) - retry later with the same command" -ForegroundColor Yellow }

Step "7/8 Connect Premiere to Claude"
& $Claude mcp remove premiere -s user 2>$null
Native $Claude mcp add premiere -s user -e PREMIERE_MCP_TOOL_PACKS=essential,inspection,captions -- premiere-pro-mcp

Step "8/8 Check"
uv run python setup\doctor.py
$DoctorOk = ($LASTEXITCODE -eq 0)
if ($Log) { Write-Host "`nInstall log: $Log" }
try { Stop-Transcript | Out-Null } catch {}
if (-not $DoctorOk) {
  Write-Host "Installed, but some required parts are missing (the X lines above). Fix them and run the installer again - finished steps are skipped." -ForegroundColor Yellow
  exit 1
}
Write-Host "Installed. Next: restart Premiere -> Window > Extensions > MCP for Adobe Premiere Pro -> Start." -ForegroundColor Green
Write-Host "Then open a terminal in your project folder and run: claude"
