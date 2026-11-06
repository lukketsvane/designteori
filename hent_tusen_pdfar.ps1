param(
    [int]$Limit = 8000,
    [int]$Shards = 1,
    [int]$Shard = 0,
    [double]$MaxCacheGB = 30,
    [double]$MinFreeGB = 2,
    [string]$Email = "",
    [switch]$RetryFailed,
    [switch]$SemanticScholar,
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
    # Default to a private cache OUTSIDE the public Git repository. An
    # existing DESIGNTEORI_PDF_CACHE environment variable takes precedence.
    if (-not $env:DESIGNTEORI_PDF_CACHE) {
        $env:DESIGNTEORI_PDF_CACHE = Join-Path $HOME 'Documents\designteori-pdf-cache'
    }
    Write-Host ("PDF-cache: " + $env:DESIGNTEORI_PDF_CACHE)
    # On the user's original Windows machine, keep the 26 previously
    # collected reading copies without downloading any of them again.
    $older = Join-Path (Split-Path $PSScriptRoot -Parent) 'FORML-RE-datascience\research\nordisk-designforsking\data\oa_fulltexts_private'
    if ((-not $DoiCsvPath) -and (Test-Path -LiteralPath $older)) {
        & $python @prefix 'import_lokale_pdf.py' '--source' $older '--cache' $env:DESIGNTEORI_PDF_CACHE
        if ($LASTEXITCODE -ne 0) { throw 'Import av tidlegare lokale PDF-ar feila.' }
    }
    $inv = [System.Globalization.CultureInfo]::InvariantCulture
    $script = if ($DoiCsvPath) { "hent_doi_csv.py" } else { "hent_oa_pdf.py" }
    $arguments = @($script, "--download", "--limit", "$Limit",
        "--delay", $(if ($DoiCsvPath) { "3.0" } else { "1.0" }),
        "--shards", "$Shards", "--shard", "$Shard",
        "--max-cache-gb", $MaxCacheGB.ToString($inv),
        "--min-free-gb", $MinFreeGB.ToString($inv))
    if ($DoiCsvPath) { $arguments += @("--input", $DoiCsvPath) }
    else { $arguments += "--lookup-openalex" }
    if ($Email) { $arguments += @("--email", $Email) }
    if ($RetryFailed) { $arguments += "--retry-failed" }
    if ($SemanticScholar) { $arguments += "--lookup-semantic-scholar" }
    & $python @prefix @arguments
    if ($LASTEXITCODE -ne 0) { throw "PDF-innsamlinga stoppa med feil $LASTEXITCODE" }
    if (-not $DoiCsvPath) { & $python @prefix "pdf_archive_report.py" }
    if ($LASTEXITCODE -ne 0) { throw "Kontrollen av PDF-arkivet feila" }
} finally {
    Pop-Location
}
