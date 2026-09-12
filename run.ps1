<#
.SYNOPSIS
  vk-scribe launcher.

.DESCRIPTION
  Bootstraps the tool end to end: installs uv when missing (winget, with
  the official installer script as a fallback), checks ffmpeg before
  anything that may download (and offers to install it via winget when
  absent), syncs the project virtual environment (.venv) from
  pyproject.toml / uv.lock — downloading a managed Python when needed —
  then runs the vk-scribe CLI with every argument passed through.
  Without arguments the CLI opens an interactive menu that asks for
  the playlist, the output folder, and the settings step by step.

.EXAMPLE
  .\run.ps1
  .\run.ps1 run "https://vkvideo.ru/playlist/-169062866_5/season_0" -o vk_course
  .\run.ps1 extract .\vk_course --skip-whisper
  .\run.ps1 --help
#>
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$CliArgs
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = $PSScriptRoot

function Update-SessionPath {
    # Re-read PATH from the registry so a just-installed tool becomes visible.
    $machinePath = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
    $env:Path = "$machinePath;$userPath"
}

function Ensure-Uv {
    if (Get-Command uv -ErrorAction SilentlyContinue) {
        return
    }

    Write-Host 'uv not found — installing it first...' -ForegroundColor Yellow
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        winget install --id astral-sh.uv -e `
            --accept-source-agreements --accept-package-agreements
    }
    else {
        powershell -NoProfile -ExecutionPolicy Bypass -Command `
            "irm https://astral.sh/uv/install.ps1 | iex"
    }

    Update-SessionPath
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        throw 'uv was installed but is still not on PATH. Open a new terminal and run this script again.'
    }
}

function Ensure-Ffmpeg {
    # yt-dlp needs ffmpeg to mux VK streams into mp4; extract works without it.
    if (Get-Command ffmpeg -ErrorAction SilentlyContinue) {
        return
    }

    Write-Warning 'ffmpeg not found on PATH — yt-dlp needs it to mux VK streams into mp4.'
    $answer = Read-Host 'Install ffmpeg now via winget? (Y/n)'
    if ($answer -match '^[Nn]') {
        Write-Host 'Skipped. Downloading will fail until ffmpeg is installed.' -ForegroundColor Yellow
        return
    }

    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        Write-Warning 'winget is not available. Install ffmpeg manually: https://ffmpeg.org/download.html'
        return
    }

    winget install --id Gyan.FFmpeg -e `
        --accept-source-agreements --accept-package-agreements

    Update-SessionPath
    if (Get-Command ffmpeg -ErrorAction SilentlyContinue) {
        Write-Host 'ffmpeg installed successfully.' -ForegroundColor Green
    }
    else {
        Write-Warning 'ffmpeg was installed but is not on PATH yet. Open a new terminal and run this script again.'
    }
}

Set-Location $ProjectRoot
Ensure-Uv

# run/download need ffmpeg, the interactive menu usually downloads too;
# only extract reads local files, so it works without ffmpeg.
$Command = if ($CliArgs) { $CliArgs[0] } else { '' }
if ($Command -notin @('extract', '--help', '-h')) {
    Ensure-Ffmpeg
}

# Create/refresh .venv and install all dependencies (idempotent).
Write-Host 'Syncing dependencies...' -ForegroundColor Cyan
uv sync
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

# No arguments = interactive menu.
if (-not $CliArgs) { $CliArgs = @() }
uv run --no-sync -- vk-scribe @CliArgs
exit $LASTEXITCODE
