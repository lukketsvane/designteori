#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
ARGS=(--download --limit "${LIMIT:-8000}" --lookup-openalex --delay 1.0
      --shards "${SHARDS:-1}" --shard "${SHARD:-0}"
      --max-cache-gb "${MAX_CACHE_GB:-30}" --min-free-gb "${MIN_FREE_GB:-2}")
if [[ -n "${EMAIL:-}" ]]; then ARGS+=(--email "$EMAIL"); fi
if [[ "${RETRY_FAILED:-0}" == "1" ]]; then ARGS+=(--retry-failed); fi
python3 hent_oa_pdf.py "${ARGS[@]}"
python3 pdf_archive_report.py
