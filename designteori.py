#!/usr/bin/env python3
"""DESIGNTEORI — Unified CLI for the Nordic Design Theory & Research Corpus."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _print(data) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def cmd_collect(args: argparse.Namespace) -> int:
    from designteori.collect import harvest_all_nordic_archives, harvest_openalex

    out = {}
    if not args.archives_only:
        out["openalex"] = harvest_openalex(
            pages_en=args.pages_en,
            pages_nordic=args.pages_nordic,
            end_year=args.end_year,
        )
    if not args.openalex_only:
        out["nordic_archives"] = harvest_all_nordic_archives()
    _print(out)
    return 0


def cmd_harvest_pdf(args: argparse.Namespace) -> int:
    from designteori.pdf import (
        audit_private_cache,
        harvest_pdfs,
        merge_local_cache,
        publish_pdf_catalog,
        sync_repo_pdf_folder,
    )

    out = {}
    if args.merge_from:
        out["merged"] = merge_local_cache(Path(args.merge_from))
    if not args.catalog_only:
        out["tried"] = harvest_pdfs(
            limit=args.limit,
            workers=args.workers,
            host_delay=args.host_delay,
            max_mb=args.max_mb,
            max_cache_gb=args.max_cache_gb,
            min_free_gb=args.min_free_gb,
            retry_failed=args.retry_failed,
            lookup_openalex=not args.no_openalex,
        )
    if not args.no_sync_repo:
        out["repo_pdf"] = sync_repo_pdf_folder(max_file_mb=args.max_mb, max_repo_gb=args.max_repo_gb)
    out["audit"] = audit_private_cache()
    out["catalog"] = publish_pdf_catalog(sync_repo_pdfs=False)
    _print(out)
    return 0


def cmd_index_pdf(args: argparse.Namespace) -> int:
    from designteori.fulltext import index_all_pdfs

    _print(index_all_pdfs(force=args.force, limit=args.limit, workers=args.workers))
    return 0


def cmd_embed(args: argparse.Namespace) -> int:
    from designteori import DOCS_DATA_DIR, read_json
    from designteori.embeddings import (
        LOCAL_GEMMA_MODEL,
        embed_corpus_works,
        embed_fulltext_chunks,
        export_public_semantic_index,
    )

    out = {}
    if not args.chunks_only:
        works = (read_json(DOCS_DATA_DIR / "publications.json", []) or [])
        nordic = (read_json(DOCS_DATA_DIR / "nordic_additions.json", []) or [])
        all_works = works + nordic
        vecs, _ = embed_corpus_works(all_works, dims_public=128, dims_local=args.dims)
        out["works"] = export_public_semantic_index(all_works, vecs, dims=128)
    if not args.works_only:
        out["chunks"] = embed_fulltext_chunks(
            model=args.model,
            dims=args.dims,
            limit=args.limit,
            batch=args.batch,
            include_unreviewed=True,
            consent_cloud=args.consent_cloud,
        )
    _print(out)
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    from designteori.build import build_all

    _print(build_all(embed=not args.no_embed, sync_repo_pdfs=not args.no_sync_pdf))
    return 0


def cmd_analyze(_args: argparse.Namespace) -> int:
    from designteori.analysis import build_analysis

    res = build_analysis()
    _print(res.get("overview", {}))
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    from designteori.search import search_corpus

    hits = search_corpus(
        " ".join(args.query),
        mode=args.mode,
        limit=args.limit,
        country=args.country,
        year_min=args.year_min,
        year_max=args.year_max,
        pdf_only=args.pdf_only,
        fulltext=not args.no_fulltext,
    )
    if args.json:
        _print(hits)
        return 0
    for idx, h in enumerate(hits, 1):
        auth = ", ".join((h.get("authors") or [])[:3])
        yr = h.get("year") or "?"
        pdf_tag = " [PDF]" if h.get("pdf") else ""
        cos_tag = f" cos={h['semantic_cosine']:.3f}" if h.get("semantic_cosine") is not None else ""
        print(f"{idx:2d}. [{yr}] {h['title']}{pdf_tag} ({h['id']}{cos_tag})")
        if auth or h.get("source"):
            print(f"    {auth} — {h.get('source') or ''}")
        if h.get("pdf"):
            print(f"    PDF: {h['pdf']}")
        if ex := h.get("excerpt"):
            print(f"    Side {ex['page']}: {ex['snippet']}")
    return 0


def cmd_verify(_args: argparse.Namespace) -> int:
    from designteori.build import verify_all

    _print(verify_all())
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="designteori",
        description="DESIGNTEORI — Open research corpus for Nordic design theory & research (1900–2026).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_col = sub.add_parser("collect", help="Harvest OpenAlex & Nordic national archives")
    p_col.add_argument("--openalex-only", action="store_true")
    p_col.add_argument("--archives-only", action="store_true")
    p_col.add_argument("--pages-en", type=int, default=5)
    p_col.add_argument("--pages-nordic", type=int, default=5)
    p_col.add_argument("--end-year", type=int, default=2026)
    p_col.set_defaults(func=cmd_collect)

    p_pdf = sub.add_parser("harvest-pdf", help="Retrieve Open Access PDFs and sync pdf/ directory")
    p_pdf.add_argument("--limit", type=int, default=8000)
    p_pdf.add_argument("--workers", type=int, default=12)
    p_pdf.add_argument("--host-delay", type=float, default=1.0)
    p_pdf.add_argument("--max-mb", type=int, default=45)
    p_pdf.add_argument("--max-cache-gb", type=float, default=25.0)
    p_pdf.add_argument("--max-repo-gb", type=float, default=50.0)
    p_pdf.add_argument("--min-free-gb", type=float, default=6.0)
    p_pdf.add_argument("--retry-failed", action="store_true")
    p_pdf.add_argument("--no-openalex", action="store_true")
    p_pdf.add_argument("--no-sync-repo", action="store_true")
    p_pdf.add_argument("--catalog-only", action="store_true")
    p_pdf.add_argument("--merge-from", default="")
    p_pdf.set_defaults(func=cmd_harvest_pdf)

    p_idx = sub.add_parser("index-pdf", help="Extract page-level text & FTS5 chunks from all PDFs")
    p_idx.add_argument("--workers", type=int, default=6)
    p_idx.add_argument("--limit", type=int, default=0)
    p_idx.add_argument("--force", action="store_true")
    p_idx.set_defaults(func=cmd_index_pdf)

    p_emb = sub.add_parser("embed", help="Compute Google EmbeddingGemma vectors for works & fulltext chunks")
    p_emb.add_argument("--model", default="embeddinggemma-300m")
    p_emb.add_argument("--dims", type=int, default=256)
    p_emb.add_argument("--batch", type=int, default=64)
    p_emb.add_argument("--limit", type=int, default=0)
    p_emb.add_argument("--works-only", action="store_true")
    p_emb.add_argument("--chunks-only", action="store_true")
    p_emb.add_argument("--consent-cloud", action="store_true")
    p_emb.set_defaults(func=cmd_embed)

    p_bld = sub.add_parser("build", help="Reconcile layers, embed corpus, analyze, pack SQLite, and verify")
    p_bld.add_argument("--no-embed", action="store_true", help="Reuse existing semantic_vectors.bin")
    p_bld.add_argument("--no-sync-pdf", action="store_true")
    p_bld.set_defaults(func=cmd_build)

    p_ana = sub.add_parser("analyze", help="Compute empirical, citation & Google semantic cluster analysis")
    p_ana.set_defaults(func=cmd_analyze)

    p_src = sub.add_parser("search", help="Hybrid FTS5 + Google EmbeddingGemma + PDF chunk search")
    p_src.add_argument("query", nargs="+")
    p_src.add_argument("--mode", choices=("hybrid", "lexical", "semantic"), default="hybrid")
    p_src.add_argument("--country", default="")
    p_src.add_argument("--year-min", type=int, default=None)
    p_src.add_argument("--year-max", type=int, default=None)
    p_src.add_argument("--pdf-only", action="store_true")
    p_src.add_argument("--no-fulltext", action="store_true")
    p_src.add_argument("--limit", type=int, default=15)
    p_src.add_argument("--json", action="store_true")
    p_src.set_defaults(func=cmd_search)

    p_ver = sub.add_parser("verify", help="Verify corpus integrity, provenance, checksums & embeddings")
    p_ver.set_defaults(func=cmd_verify)

    parsed = parser.parse_args(argv)
    return parsed.func(parsed)


if __name__ == "__main__":
    sys.exit(main())

