"""Public fulltext and OA-link integrity, no network dependencies."""
from pathlib import Path
import csv,hashlib,json

ROOT=Path(__file__).resolve().parent

def main():
    manifest=json.loads((ROOT/"fulltekst/manifest.json").read_text(encoding="utf-8"))
    rows=manifest["items"]
    assert len(rows)==manifest["count"]==15
    by_id={r["id"]:r for r in rows}
    assert len(by_id)==15
    for id,r in by_id.items():
        path=ROOT/"fulltekst"/r["pdf"]
        assert path.is_file(),id
        assert hashlib.sha256(path.read_bytes()).hexdigest()==r["sha256"],id
        assert r["license_url"].startswith("https://creativecommons.org/"),id
        if r.get("text"):
            assert (ROOT/"fulltekst"/r["text"]).is_file(),id
            assert "ND" not in r["license"],id
    adapted=by_id["W4416250669"]
    assert adapted["license"]=="CC BY 4.0"
    assert adapted.get("derivative_notes")
    assert adapted["source_pdf_sha256"]!=adapted["sha256"]
    assert b"/Subtype /Image" not in (ROOT/"fulltekst"/adapted["pdf"]).read_bytes()

    pub=json.loads((ROOT/"docs/data/publications.json").read_text(encoding="utf-8"))
    assert len(pub)==7300
    w=next(x for x in pub if x["id"]=="W4416250669")
    assert w["pdf"].endswith("/fulltekst/"+adapted["pdf"])
    assert w["text"].endswith("/fulltekst/"+adapted["text"])
    assert w["license"]=="CC BY 4.0"

    with (ROOT/"docs/data/korpus.csv").open(encoding="utf-8",newline="") as f:
        corpus=list(csv.DictReader(f))
    assert len(corpus)==7761
    ids=[r["id"] for r in corpus]
    assert len(ids)==len(set(ids))
    record=next(x for x in corpus if x["id"]=="W4416250669")
    assert record["pdf"].endswith("/fulltekst/"+adapted["pdf"])

    catalog=json.loads((ROOT/"docs/data/pdf_katalog.json").read_text(encoding="utf-8"))
    index=catalog["items"]
    stats=catalog["stats"]
    assert len(index)==stats["total_visible_entries"]==4579
    assert stats["mirrored_licensed_pdf_count"]==15
    assert stats["text_only_adapted_pdf_count"]==1
    assert sum(bool(row["pdf_in_repo"]) for row in index)==15
    assert set(row["id"] for row in index if row["pdf_in_repo"])==set(by_id)
    assert all(r["rights_status"]=="rights_not_reviewed" for r in index if not r["pdf_in_repo"])
    assert all(not r["public_pdf_url"] for r in index if not r["pdf_in_repo"])
    assert (ROOT/"docs/pdf.html").stat().st_size>6000

    with (ROOT/"fulltekst/rettsstatus.csv").open(encoding="utf-8",newline="") as f:
        rights=list(csv.DictReader(f))
    assert len(rights)==26
    assert sum(r["public_mirror_status"]=="licensed_public_file" for r in rights)==15
    assert sum(r["public_mirror_version"]=="text_only_adapted_no_images" for r in rights)==1

    found=json.loads((ROOT/"docs/data/pdf_found.json").read_text(encoding="utf-8"))
    status=json.loads((ROOT/"docs/data/pdf_status.json").read_text(encoding="utf-8"))
    assert len(found)==15
    assert found["W4416250669"]["sha256"]==adapted["sha256"]
    assert status["public_verified_pdf_links"]==status["archived_licensed_pdfs"]==15
    assert status["oa_links_unchecked"]==4564
    print("PASS: 15 verified public PDFs, 1 graphics-free adapted PDF, 4,579 source links, 7,761 corpus rows, 11 unpublished local originals.")
if __name__=="__main__":
    main()
