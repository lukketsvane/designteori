param(
    [int]$Limit = 8000,
    [int]$Shards = 1,
    [int]$Shard = 0,
    [double]$MaxCacheGB = 30,
    [double]$MinFreeGB = 2,
    [string]$Email = "",
    [switch]$RetryFailed,
    [string]$DoiCsvPath = ""
)
$ErrorActionPreference = "Stop"
Push-Location $PSScriptRoot
try {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        $python = "py"
        $prefix = @("-3")
    } elseif (Get-Command python -ErrorAction SilentlyContinue) {
        $python = "python"
        $prefix = @()
    } else {
        throw "Python 3 manglar. Installer Python og køyr skriptet igjen."
    }
    $inv = [System.Globalization.CultureInfo]::InvariantCulture
    $script = if ($DoiCsvPath) { "scripts/hent_doi_csv.py" } else { "scripts/hent_oa_pdf.py" }
    $arguments = @($script, "--download", "--limit", "$Limit",
        "--delay", $(if ($DoiCsvPath) { "3.0" } else { "1.0" }),
        "--shards", "$Shards", "--shard", "$Shard",
        "--max-cache-gb", $MaxCacheGB.ToString($inv),
        "--min-free-gb", $MinFreeGB.ToString($inv))
    if ($DoiCsvPath) { $arguments += @("--input", $DoiCsvPath) }
    else { $arguments += "--lookup-openalex" }
    if ($Email) { $arguments += @("--email", $Email) }
    if ($RetryFailed) { $arguments += "--retry-failed" }
    & $python @prefix @arguments
    if ($LASTEXITCODE -ne 0) { throw "PDF-innsamlinga stoppa med feil $LASTEXITCODE" }
    if (-not $DoiCsvPath) { & $python @prefix "scripts/pdf_archive_report.py" }
    if ($LASTEXITCODE -ne 0) { throw "Kontrollen av PDF-arkivet feila" }
} finally {
    Pop-Location
}
