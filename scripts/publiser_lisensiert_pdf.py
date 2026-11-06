#!/usr/bin/env python3
"""Manually approve a downloaded PDF for redistribution in the public archive.

Downloading an accessible document is NOT enough for republication. A human must
verify the exact PDF, publication identity and license; this tool never infers
rights from 'open access', a DOI, a publisher or an unrelated Creative Commons note.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from hent_oa_pdf import ROOT, PRIVATE, LOG, allowed_url, read_json, write_json

LICENSES = {
    "CC0 1.0": "https://creativecommons.org/publicdomain/zero/1.0/",
    "CC BY 2.0": "https://creativecommons.org/licenses/by/2.0/",
    "CC BY 3.0": "https://creativecommons.org/licenses/by/3.0/",
    "CC BY 4.0": "https://creativecommons.org/licenses/by/4.0/",
    "CC BY-SA 4.0": "https://creativecommons.org/licenses/by-sa/4.0/",
    "CC BY-NC 4.0": "https://creativecommons.org/licenses/by-nc/4.0/",
    "CC BY-NC-SA 4.0": "https://creativecommons.org/licenses/by-nc-sa/4.0/",
    "CC BY-ND 4.0": "https://creativecommons.org/licenses/by-nd/4.0/",
    "CC BY-NC-ND 4.0": "https://creativecommons.org/licenses/by-nc-nd/4.0/",
}


def path_for_work(work_id):
    return PRIVATE / "pdf" / (hashlib.sha256(work_id.encode()).hexdigest()[:24] + ".pdf")


def record_for_work(ident):
    for filename in ("publications.json", "nordic_additions.json"):
        records = read_json(ROOT / "docs" / "data" / filename, [])
        for r in records:
            if r.get("id") == ident:
                return r
    return None


def prepare_entry(work_id, lic, evidence):
    progress = read_json(LOG, {})
    item = progress.get(work_id)
    if not item or item.get("status") != "pdf-confirmed":
        raise ValueError("PDF must first be downloaded from a lawful source into the private cache")
    record = record_for_work(work_id)
    if not record:
        raise ValueError("Unknown publication ID")
    url = item.get("url", "")
    if not allowed_url(url):
        raise ValueError("Original source URL is not approved")
    pdf = path_for_work(work_id)
    if not pdf.is_file() or not pdf.read_bytes().lstrip().startswith(b"%PDF"):
        raise ValueError("No valid cached PDF for this ID")
    digest = hashlib.sha256(pdf.read_bytes()).hexdigest()
    if digest != item["sha256"]:
        raise ValueError("Private PDF checksum does not match the recorded download")
    if not evidence or len(evidence.strip()) < 16:
        raise ValueError("Describe the exact license statement and PDF page/section")
    if lic not in LICENSES:
        raise ValueError("Unsupported license; inspect the original terms manually")
    return {
        "id": work_id,
        "title": record["title"],
        "authors": record.get("authors", []),
        "year": record.get("year"),
        "doi": record.get("doi", ""),
        "journal_or_source": record.get("source", ""),
        "original_fulltext_url": url,
        "license": lic,
        "license_url": LICENSES[lic],
        "rights_basis": "Manually checked exact source PDF: " + evidence.strip(),
        "pdf": "pdf/" + hashlib.sha256(work_id.encode()).hexdigest()[:24] + ".pdf",
        "text": None,
        "sha256": digest,
        "bytes": pdf.stat().st_size,
        "verification_status": "checked-document-licence",
        "reviewed_on": datetime.now(timezone.utc).date().isoformat(),
    }


def publish(work_id, license_name, evidence, *, confirm):
    if not confirm:
        raise ValueError("Require --confirm-rights after checking the actual PDF")
    entry = prepare_entry(work_id, license_name, evidence)
    path = ROOT / "fulltekst" / "manifest.json"
    manifest = read_json(path)
    if any(item["id"] == work_id for item in manifest["items"]):
        raise ValueError("PDF is already in the public archive")
    from_pdf = path_for_work(work_id)
    destination = ROOT / "fulltekst" / entry["pdf"]
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(from_pdf, destination)
    assert hashlib.sha256(destination.read_bytes()).hexdigest() == entry["sha256"]
    manifest["items"].append(entry)
    manifest["items"].sort(key=lambda item: item["id"])
    manifest["count"] = len(manifest["items"])
    manifest["generated_at"] = datetime.now(timezone.utc).isoformat()
    write_json(path, manifest)
    with (ROOT / "fulltekst" / "manifest.csv").open("w", encoding="utf-8", newline="") as fh:
        fields = ["id", "year", "title", "authors", "doi", "journal_or_source",
                  "original_fulltext_url", "license", "license_url", "pdf",
                  "text", "sha256", "bytes", "verification_status"]
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in manifest["items"]:
            writer.writerow(dict(row, authors="; ".join(row["authors"])))
    print("PUBLICATION_ADDED", work_id, license_name, entry["sha256"], destination)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--id", required=True)
    p.add_argument("--license", required=True, choices=sorted(LICENSES))
    p.add_argument("--evidence", required=True, help="Where the actual PDF states the license")
    p.add_argument("--confirm-rights", action="store_true",
                   help="Confirm publication identity and redistribution license of this exact PDF")
    args = p.parse_args()
    publish(args.id, args.license, args.evidence, confirm=args.confirm_rights)


if __name__ == "__main__":
    main()
