# Export the network tables of Database.mdb to CSV (for make_aggregators.py).
# Reads a temporary COPY of the database (AIMMS changes Database.mdb on every open, and the original must not change).
# Needs the Microsoft Access Database Driver, as the model does.
#
# Usage (from the repository root, Windows PowerShell):
#   powershell -ExecutionPolicy Bypass -File scripts\paper1\case_study\export_network.ps1 -Out ..\case-study-network
param(
    [string]$Database = "Database.mdb",
    [Parameter(Mandatory = $true)][string]$Out
)
$ErrorActionPreference = "Stop"
$src = (Resolve-Path $Database).Path
New-Item -ItemType Directory -Force $Out | Out-Null
$copy = Join-Path $Out "Database_copy.mdb"
Copy-Item $src $copy -Force
$cn = New-Object System.Data.Odbc.OdbcConnection("Driver={Microsoft Access Driver (*.mdb, *.accdb)};Dbq=$copy;ReadOnly=1")
$cn.Open()
foreach ($t in @("Batteries", "Buses", "Lines", "LoadsAndPV", "Trafos")) {
    $da = New-Object System.Data.Odbc.OdbcDataAdapter("SELECT * FROM [$t]", $cn)
    $dt = New-Object System.Data.DataTable
    [void]$da.Fill($dt)
    $dt | Export-Csv -Path (Join-Path $Out "$t.csv") -NoTypeInformation -Encoding UTF8
    "{0}: {1} rows" -f $t, $dt.Rows.Count
}
$cn.Close()
Remove-Item $copy
$hash = (Get-FileHash $src -Algorithm SHA256).Hash.Substring(0, 16).ToLower()
$line = "Database.mdb sha256 $hash"
$line | Out-File -FilePath (Join-Path $Out "source.txt") -Encoding ascii
$line
