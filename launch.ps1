<#
.SYNOPSIS
Zero-touch setup and runner for Dialogue Frame Finder (Baseline Audio).
#>

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

Write-Host "=============================================" -ForegroundColor Cyan
Write-Host " Dialogue Frame Finder - Setup & Launch" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan

# Prevent Python from loading global user site-packages
$env:PYTHONNOUSERSITE = "1"

# 1. Python Environment Setup
Write-Host "`n[1/3] Setting up Python Environment..." -ForegroundColor Yellow

$localPythonDir = "$PSScriptRoot\local_python"
$pythonExe = "$localPythonDir\python.exe"

# If local_python doesn't exist, check for existing virtual environment 'que' or download isolated Python
if (Test-Path "$PSScriptRoot\que\Scripts\python.exe") {
    $pythonExe = "$PSScriptRoot\que\Scripts\python.exe"
    Write-Host "Using workspace Python environment: $pythonExe" -ForegroundColor Green
} elseif (-not (Test-Path $pythonExe)) {
    # Check if system Python 3.10+ is installed
    $systemPython = Get-Command "python" -ErrorAction SilentlyContinue
    if ($systemPython) {
        Write-Host "Creating local virtual environment using system Python..."
        & python -m venv "$localPythonDir"
        $pythonExe = "$localPythonDir\Scripts\python.exe"
    } else {
        Write-Host "System Python not found. Downloading portable Python 3.11..."
        $pythonZipPath = "$env:TEMP\python_embed.zip"
        curl.exe -# -L -o $pythonZipPath "https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip"
        Write-Host "Extracting portable Python..."
        New-Item -ItemType Directory -Force -Path $localPythonDir | Out-Null
        tar.exe -xf $pythonZipPath -C $localPythonDir
        
        Write-Host "Enabling site-packages..."
        $pthPath = "$localPythonDir\python311._pth"
        if (Test-Path $pthPath) {
            (Get-Content $pthPath) -replace '#import site', 'import site' | Set-Content $pthPath
        }
        
        Write-Host "Installing pip..."
        curl.exe -# -L -o "$localPythonDir\get-pip.py" "https://bootstrap.pypa.io/get-pip.py"
        Start-Process -FilePath $pythonExe -ArgumentList "get-pip.py", "--no-warn-script-location" -WorkingDirectory $localPythonDir -Wait -NoNewWindow
    }
} else {
    Write-Host "Local Python environment found: $pythonExe" -ForegroundColor Green
}

# 2. Dependency Verification
Write-Host "`n[2/3] Verifying Backend Dependencies..." -ForegroundColor Yellow
if (Test-Path "$PSScriptRoot\requirements.txt") {
    & $pythonExe -m pip install -r "$PSScriptRoot\requirements.txt" --no-warn-script-location --quiet
    Write-Host "Dependencies verified successfully." -ForegroundColor Green
}

# Ensure static_ffmpeg is ready
& $pythonExe -c "import static_ffmpeg; static_ffmpeg.add_paths()" 2>$null

# 3. Find Free Port & Launch Web UI Server
function Get-FreePort {
    param([int]$StartPort = 8000)
    $port = $StartPort
    while ($true) {
        $connection = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
        if ($null -eq $connection) {
            return $port
        }
        $port++
    }
}

Write-Host "`n[3/3] Launching Dialogue Frame Finder..." -ForegroundColor Yellow
$ServerPort = Get-FreePort -StartPort 8000
$outLog = "$PSScriptRoot\server_out.log"
$errLog = "$PSScriptRoot\server_err.log"

# Clean old logs
Remove-Item $outLog, $errLog -Force -ErrorAction SilentlyContinue

# Start server.py in background with log redirection
$serverScript = "$PSScriptRoot\server.py"
$serverProcess = Start-Process -FilePath $pythonExe `
    -ArgumentList "`"$serverScript`"", "--port", "$ServerPort" `
    -WorkingDirectory "$PSScriptRoot" `
    -RedirectStandardOutput "$outLog" `
    -RedirectStandardError "$errLog" `
    -PassThru `
    -WindowStyle Hidden

# Verify server startup with healthcheck
Write-Host "Verifying server startup (Port $ServerPort)..."
$healthy = $false
for ($i = 0; $i -lt 20; $i++) {
    Start-Sleep -Milliseconds 500
    if ($serverProcess.HasExited) {
        break
    }
    try {
        $resp = Invoke-RestMethod -Uri "http://127.0.0.1:$ServerPort/api/health" -TimeoutSec 1 -ErrorAction Stop
        if ($resp.status -eq "ok") {
            $healthy = $true
            break
        }
    } catch {
        # Waiting for server to initialize
    }
}

if (-not $healthy) {
    Write-Host "`n=============================================" -ForegroundColor Red
    Write-Host " [ERROR] Dialogue Frame Finder Failed to Start!" -ForegroundColor Red
    Write-Host "=============================================" -ForegroundColor Red
    if (Test-Path $errLog) {
        $errContent = Get-Content $errLog -Raw
        if ($errContent) {
            Write-Host "`n--- Error Output ($errLog) ---" -ForegroundColor Red
            Write-Host $errContent -ForegroundColor Red
            Write-Host "------------------------------`n" -ForegroundColor Red
        }
    }
    if (Test-Path $outLog) {
        $outContent = Get-Content $outLog -Raw
        if ($outContent) {
            Write-Host "`n--- Standard Output ($outLog) ---" -ForegroundColor Yellow
            Write-Host $outContent -ForegroundColor Yellow
            Write-Host "---------------------------------`n" -ForegroundColor Yellow
        }
    }
    Write-Host "Please check the error details above." -ForegroundColor Yellow
    Read-Host "Press [ENTER] to exit"
    exit 1
}

Write-Host "`n=============================================" -ForegroundColor Cyan
Write-Host " Dialogue Frame Finder is Running!" -ForegroundColor Green
Write-Host " URL: http://localhost:$ServerPort" -ForegroundColor White
Write-Host "=============================================" -ForegroundColor Cyan

# Open default browser
Write-Host "Opening browser in 2 seconds..."
Start-Sleep -Seconds 2
Start-Process "http://localhost:$ServerPort"

# Background watcher to ensure clean shutdown when window is closed
$watcherCode = @"
Wait-Process -Id $PID -ErrorAction SilentlyContinue
taskkill /F /T /PID $($serverProcess.Id) 2>&1 | Out-Null
`$conns = Get-NetTCPConnection -LocalPort $ServerPort -State Listen -ErrorAction SilentlyContinue
if (`$conns) {
    foreach (`$c in `$conns) {
        Stop-Process -Id `$c.OwningProcess -Force -ErrorAction SilentlyContinue
    }
}
"@
$encodedWatcher = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($watcherCode))
Start-Process powershell.exe -WindowStyle Hidden -ArgumentList "-NoProfile", "-EncodedCommand", $encodedWatcher

Write-Host "`nApp is running. Press [ENTER] or close this window to shut down." -ForegroundColor Yellow

try {
    Read-Host
    Write-Host "Stopping server..." -ForegroundColor Cyan
    taskkill /F /T /PID $($serverProcess.Id) 2>&1 | Out-Null
} catch {
    # Handled by watcher
}
