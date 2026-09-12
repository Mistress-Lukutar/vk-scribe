<#
.SYNOPSIS
  vk-scribe launcher.

.DESCRIPTION
  Bootstraps the tool end to end: installs uv when missing (winget, with
  the official installer script as a fallback), syncs the project virtual
  environment (.venv) from pyproject.toml / uv.lock — downloading a
  managed Python when needed — then runs the vk-scribe CLI with every
  argument passed through.

.EXAMPLE
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
    # Re-read PATH from the registry so a just-installed uv becomes visible.
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

Set-Location $ProjectRoot
Ensure-Uv

# Create/refresh .venv and install all dependencies (idempotent).
Write-Host 'Syncing dependencies...' -ForegroundColor Cyan
uv sync
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if (-not $CliArgs) { $CliArgs = @('--help') }
uv run --no-sync -- vk-scribe @CliArgs
exit $LASTEXITCODE
