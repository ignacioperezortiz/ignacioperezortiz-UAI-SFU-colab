# watch_runs.ps1 - environment logger for the controlled-baseline FOR campaign.
#
# Start this ONCE, after the reboot, before the first RunTRn_Base. Leave it
# running for the whole campaign. It records the machine state at the start and
# then samples every 30 s, so each run can be checked against the same base and
# any run that was disturbed can be identified rather than guessed at.
#
#   powershell -ExecutionPolicy Bypass -File scripts\watch_runs.ps1
#
# Stop it with Ctrl+C when the campaign is done. Output goes to
# results\async-performance\baseline\ :
#   env_header.txt   machine state at campaign start
#   env_log.csv      one row per 30 s sample
#   env_events.txt   AIMMS start/exit, with the wall clock of each run
#
# Nothing here touches the model or any result file.

param(
    [int]$IntervalSec = 30,
    [double]$MaxHours = 30
)

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$out  = Join-Path $root 'results\async-performance\baseline'
if (-not (Test-Path $out)) { New-Item -ItemType Directory -Force $out | Out-Null }

$header = Join-Path $out 'env_header.txt'
$log    = Join-Path $out 'env_log.csv'
$events = Join-Path $out 'env_events.txt'

# ------------------------------------------------------------------ header
$os  = Get-CimInstance Win32_OperatingSystem
$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
$plan = (powercfg /getactivescheme) -join ''

$lines = @()
$lines += "Controlled-baseline campaign - machine state at start"
$lines += "captured        : {0}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
$lines += "host            : $env:COMPUTERNAME"
$lines += "cpu             : {0} ({1} cores / {2} logical)" -f $cpu.Name.Trim(), $cpu.NumberOfCores, $cpu.NumberOfLogicalProcessors
$lines += "ram_total_GB    : {0:N1}" -f ($os.TotalVisibleMemorySize/1MB)
$lines += "ram_free_GB     : {0:N1}   <- the baseline every run should start from" -f ($os.FreePhysicalMemory/1MB)
$lines += "uptime          : {0}" -f ((Get-Date) - $os.LastBootUpTime).ToString('d\d\ hh\:mm')
$lines += "power_plan      : $plan"
$lines += ""
$lines += "processes over 100 MB at start (this is the background load being held constant):"
Get-Process | Group-Object ProcessName |
    Where-Object { ($_.Group | Measure-Object WorkingSet64 -Sum).Sum -gt 100MB } |
    Sort-Object { ($_.Group | Measure-Object WorkingSet64 -Sum).Sum } -Descending |
    ForEach-Object {
        $mb = [math]::Round((($_.Group | Measure-Object WorkingSet64 -Sum).Sum)/1MB)
        $lines += ("  {0,-24} {1,3} proc {2,6} MB" -f $_.Name, $_.Count, $mb)
    }
$lines | Set-Content -Encoding utf8 $header

# ------------------------------------------------------------------ log setup
if (-not (Test-Path $log)) {
    "stamp,aimms_running,aimms_RSS_GB,free_GB,commit_GB,cpu_pct" | Set-Content -Encoding utf8 $log
}
Add-Content -Encoding utf8 $events ("=== watcher started {0} ===" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'))

Write-Host "watching. header -> $header"
Write-Host "samples -> $log   (Ctrl+C to stop)"

$deadline = (Get-Date).AddHours($MaxHours)
$wasRunning = $false
$runStart = $null

while ((Get-Date) -lt $deadline) {
    $now = Get-Date
    # Threads.Count -eq 0 filters out zombie process objects: Windows keeps the
    # entry alive while some handle is open, it cannot be killed (access denied),
    # and only a restart clears it. pid 15992 has sat like that since 2026-08-13.
    $p = @(Get-Process aimms* -ErrorAction SilentlyContinue | Where-Object { $_.Threads.Count -gt 0 })
    $running = $p.Count -gt 0

    $rss = 0
    if ($running) { $rss = ($p | Measure-Object WorkingSet64 -Sum).Sum / 1GB }

    $o = Get-CimInstance Win32_OperatingSystem
    $free   = $o.FreePhysicalMemory / 1MB
    $commit = ($o.TotalVisibleMemorySize - $o.FreePhysicalMemory) / 1MB

    $cpuPct = -1
    try {
        $cpuPct = (Get-Counter '\Processor(_Total)\% Processor Time' -ErrorAction Stop).CounterSamples[0].CookedValue
    } catch { }

    "{0},{1},{2:N2},{3:N2},{4:N2},{5:N1}" -f $now.ToString('yyyy-MM-dd HH:mm:ss'), $running, $rss, $free, $commit, $cpuPct |
        Add-Content -Encoding utf8 $log

    # ---- transitions: one AIMMS session = one run, under this protocol
    if ($running -and -not $wasRunning) {
        $runStart = $now
        Add-Content -Encoding utf8 $events ("AIMMS opened  {0}" -f $now.ToString('yyyy-MM-dd HH:mm:ss'))
    }
    if ($wasRunning -and -not $running) {
        $span = $now - $runStart
        Add-Content -Encoding utf8 $events ("AIMMS closed  {0}   session wall {1:hh\:mm\:ss}" -f $now.ToString('yyyy-MM-dd HH:mm:ss'), $span)
        $runStart = $null
    }
    $wasRunning = $running

    Start-Sleep -Seconds $IntervalSec
}

Add-Content -Encoding utf8 $events ("=== watcher stopped {0} (max hours reached) ===" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'))
