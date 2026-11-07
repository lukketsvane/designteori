"""Empirical, citation-network, and Google-embedding semantic analysis for DESIGNTEORI."""
from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from . import (
    DOCS_DATA_DIR,
    NORDIC_COUNTRIES,
    PDF_DIR,
    PRIVATE_CORPUS_DB,
    now_iso,
    read_json,
    write_json,
)
from .embeddings import dequantize_int8

THEME_LABELS_NN = {
    "participatory-design": "Deltakande design og arbeidsplassdemokrati",
    "codesign": "Samskaping og co-design",
    "research-through-design": "Research through Design og praksisbasert forsking",
    "design-theory-epistemology": "Designteori, epistemologi og designerkunnskap",
    "service-systemic-design": "Tenestedesign, systemisk design og offentleg sektor",
    "sustainable-circular": "Berekraftig, sirkulær og økologisk design",
    "critical-speculative": "Kritisk, spekulativ og diskursiv design",
    "interaction-hci-ai": "Interaksjonsdesign, HCI og kunstig intelligens",
    "design-history-nordic": "Nordisk designhistorie og materiell kultur",
    "craft-materiality-textile": "Handverk, materialitet og tekstildesign",
    "aesthetics-form": "Estetikk, formgjeving og sansing",
    "design-education-pedagogy": "Designutdanning, studiodidaktikk og læring",
    "design-ethics-justice": "Designetikk, universell utforming og rettferd",
    "design-anthropology": "Designantropologi og kvardagspraksis",
    "industrial-product": "Industridesign, produktutvikling og ingeniørdesign",
    "urban-architecture": "Arkitekturteori, byrom og landskap",
}

STOPWORDS = {
    "the", "and", "for", "with", "from", "into", "through", "toward", "towards",
    "between", "using", "based", "study", "studies", "case", "new", "approach",
    "approaches", "perspectives", "perspective", "exploring", "understanding",
    "making", "design", "designing", "research", "nordic", "scandinavian", "norwegian",
    "swedish", "danish", "finnish", "icelandic", "how", "what", "when", "where",
    "their", "this", "that", "over", "under", "within", "across", "among", "beyond",
    "role", "use", "used", "analysis", "review", "framework", "model", "models",
    "paper", "article", "chapter", "book", "introduction", "editorial", "issue",
    "och", "att", "för", "med", "som", "til", "fra", "frå", "ved", "hos", "eller",
    "ikke", "ikkje", "den", "det", "dei", "een", "ett", "af", "på", "av", "om", "i",
}

WORD_RE = re.compile(r"[A-Za-zÆØÅæøåÄÖÜäöüÞÐþð]{4,}")


def _spherical_kmeans(X: np.ndarray, k: int = 10, iters: int = 25, seed: int = 42) -> tuple[np.ndarray, np.ndarray]:
    n, d = X.shape
    if n == 0:
        return np.zeros((0,), dtype=np.int32), np.zeros((0, d), dtype=np.float32)
    k = min(k, n)
    rng = np.random.default_rng(seed)
    # Deterministic k-means++ initialization using cosine distance (1 - X @ c)
    centroids = np.zeros((k, d), dtype=np.float32)
    first = int(rng.integers(0, n))
    centroids[0] = X[first]
    closest_dist = np.maximum(0.0, 1.0 - (X @ centroids[0]))
    for c_idx in range(1, k):
        total = float(closest_dist.sum())
        if total <= 1e-9:
            pick = int(rng.integers(0, n))
        else:
            probs = closest_dist / total
            pick = int(rng.choice(n, p=probs))
        centroids[c_idx] = X[pick]
        new_dist = np.maximum(0.0, 1.0 - (X @ centroids[c_idx]))
        closest_dist = np.minimum(closest_dist, new_dist)

    labels = np.zeros((n,), dtype=np.int32)
    for _ in range(iters):
        sims = X @ centroids.T
        new_labels = np.argmax(sims, axis=1).astype(np.int32)
        if np.array_equal(new_labels, labels) and _ > 0:
            break
        labels = new_labels
        for c_idx in range(k):
            mask = labels == c_idx
            if np.any(mask):
                mean_vec = X[mask].mean(axis=0)
                norm = float(np.linalg.norm(mean_vec))
                if norm > 1e-12:
                    centroids[c_idx] = mean_vec / norm
    return labels, centroids


def _svd_2d(X: np.ndarray) -> np.ndarray:
    if X.shape[0] <= 2:
        return np.zeros((X.shape[0], 2), dtype=np.float32)
    centered = X - X.mean(axis=0, keepdims=True)
    # Compute covariance d x d (128x128 is tiny and instantaneous!)
    cov = (centered.T @ centered) / max(1, X.shape[0] - 1)
    eigvals, eigvecs = np.linalg.eigh(cov.astype(np.float64))
    top2 = eigvecs[:, -2:][:, ::-1].astype(np.float32)
    # Deterministic sign convention so maps don't flip across builds
    for col in range(2):
        max_idx = int(np.argmax(np.abs(top2[:, col])))
        if top2[max_idx, col] < 0:
            top2[:, col] *= -1.0
    coords = centered @ top2
    scale = np.percentile(np.abs(coords), 98, axis=0)
    scale = np.maximum(scale, 1e-6)
    return np.clip(coords / scale, -1.5, 1.5)


def _cluster_keywords(titles: list[str], global_df: Counter, total_docs: int, top_n: int = 7) -> list[str]:
    tf = Counter()
    for t in titles:
        seen = {w.lower() for w in WORD_RE.findall(t or "")}
        for w in seen:
            if w not in STOPWORDS:
                tf[w] += 1
    scored = []
    n_cluster = max(1, len(titles))
    for w, cnt in tf.items():
        if cnt < 2:
            continue
        idf = math.log(1.0 + total_docs / (1.0 + global_df[w]))
        scored.append(((cnt / n_cluster) * idf, w))
    scored.sort(reverse=True)
    return [w for _, w in scored[:top_n]]


def build_analysis(*, out_dir: Path = DOCS_DATA_DIR, n_clusters: int = 10, map_limit: int = 5000) -> dict:
    works = read_json(out_dir / "publications.json", []) or []
    nordic = read_json(out_dir / "nordic_additions.json", []) or []
    context = read_json(out_dir / "work_context.json", {}) or {}
    authors_data = (read_json(out_dir / "authors.json", {}) or {}).get("items", [])
    inst_data = (read_json(out_dir / "institutions.json", {}) or {}).get("items", [])
    canon_data = (read_json(out_dir / "cited_canon.json", {}) or {}).get("items", [])
    pdf_kat = read_json(out_dir / "pdf_katalog.json", {}) or {}
    repo_manifest = (read_json(PDF_DIR / "manifest.json", {}) or {}).get("items", {}) or {}

    all_works = works + nordic
    works_by_id = {w["id"]: w for w in all_works}

    # Fulltext chunk & embedding stats from local corpus DB if available
    fulltext_chunks_count = 0
    fulltext_embedded_chunks = 0
    fulltext_extracted_docs = 0
    if PRIVATE_CORPUS_DB.is_file():
        import sqlite3
        try:
            cdb = sqlite3.connect(f"file:{PRIVATE_CORPUS_DB.as_posix()}?mode=ro", uri=True)
            valid_shas = set()
            for wid, sha in cdb.execute("SELECT work_id, sha256 FROM work_documents"):
                if wid in works_by_id and sha:
                    valid_shas.add(sha)
            if valid_shas:
                q_marks = ",".join("?" for _ in valid_shas)
                sha_params = tuple(valid_shas)
                fulltext_extracted_docs = cdb.execute(
                    f"SELECT COUNT(*) FROM documents WHERE quality='extracted' AND sha256 IN ({q_marks})",
                    sha_params,
                ).fetchone()[0]
                fulltext_chunks_count = cdb.execute(
                    f"SELECT COUNT(*) FROM chunks WHERE sha256 IN ({q_marks})",
                    sha_params,
                ).fetchone()[0]
                fulltext_embedded_chunks = cdb.execute(
                    f"SELECT COUNT(DISTINCT e.chunk_id) FROM embeddings e JOIN chunks c ON c.chunk_id=e.chunk_id WHERE c.sha256 IN ({q_marks})",
                    sha_params,
                ).fetchone()[0]
            cdb.close()
        except Exception:
            pass

    # 1. Temporal trajectories (1900–2026)
    decades = defaultdict(lambda: {"decade": "", "total": 0, "auto_included": 0, "nordic_archives": 0, "pdfs": 0})
    yearly = defaultdict(lambda: {"year": 0, "total": 0, "auto_included": 0, "open_access": 0, "pdfs": 0})
    pre_2000_count = 0

    for w in works:
        y = w.get("year")
        if not isinstance(y, int) or y < 1900 or y > 2030:
            continue
        if y < 2000:
            pre_2000_count += 1
        dec_key = f"{(y // 10) * 10}s"
        drec = decades[dec_key]
        drec["decade"] = dec_key
        drec["total"] += 1
        is_inc = w.get("scope") == "automatic-title-inclusion"
        if is_inc:
            drec["auto_included"] += 1
        has_pdf = bool(w.get("pdf") or w["id"] in repo_manifest)
        if has_pdf:
            drec["pdfs"] += 1
        if y >= 1970:
            yrec = yearly[y]
            yrec["year"] = y
            yrec["total"] += 1
            if is_inc:
                yrec["auto_included"] += 1
            if w.get("oa_url") or has_pdf:
                yrec["open_access"] += 1
            if has_pdf:
                yrec["pdfs"] += 1

    for w in nordic:
        y = w.get("year")
        if isinstance(y, int) and 1900 <= y <= 2030:
            dec_key = f"{(y // 10) * 10}s"
            decades[dec_key]["decade"] = dec_key
            decades[dec_key]["nordic_archives"] += 1
            if w.get("pdf") or w["id"] in repo_manifest:
                decades[dec_key]["pdfs"] += 1

    # 2. Country statistics & 5x5 Cross-Nordic Collaboration Matrix
    country_stats = {
        c: {"country": c, "openalex_works": 0, "auto_included": 0, "nordic_archive_records": 0,
            "pdfs": 0, "oa_works": 0, "citations_sum": 0, "top_venues": []}
        for c in NORDIC_COUNTRIES
    }
    country_venues: dict[str, Counter] = {c: Counter() for c in NORDIC_COUNTRIES}
    co_matrix = {c1: {c2: 0 for c2 in NORDIC_COUNTRIES} for c1 in NORDIC_COUNTRIES}
    cross_nordic_works = 0

    for w in works:
        cs = [c for c in (w.get("countries") or []) if c in country_stats]
        if len(cs) >= 2:
            cross_nordic_works += 1
        is_inc = w.get("scope") == "automatic-title-inclusion"
        has_pdf = bool(w.get("pdf") or w["id"] in repo_manifest)
        has_oa = bool(w.get("oa_url") or has_pdf)
        cits = int(w.get("citations") or 0)
        src = str(w.get("source") or "").strip()
        for c in cs:
            st = country_stats[c]
            st["openalex_works"] += 1
            if is_inc:
                st["auto_included"] += 1
                if src:
                    country_venues[c][src] += 1
            if has_pdf:
                st["pdfs"] += 1
            if has_oa:
                st["oa_works"] += 1
            st["citations_sum"] += cits
        for i, c1 in enumerate(cs):
            for c2 in cs[i:]:
                co_matrix[c1][c2] += 1
                if c1 != c2:
                    co_matrix[c2][c1] += 1

    for w in nordic:
        sc = w.get("source_country") or ""
        if sc in country_stats:
            country_stats[sc]["nordic_archive_records"] += 1
            if w.get("pdf") or w["id"] in repo_manifest:
                country_stats[sc]["pdfs"] += 1

    for c in NORDIC_COUNTRIES:
        st = country_stats[c]
        st["oa_share"] = round(st["oa_works"] / max(1, st["openalex_works"]), 4)
        st["top_venues"] = [{"venue": v, "count": n} for v, n in country_venues[c].most_common(5)]

    # 3. Top Venues
    venue_acc = defaultdict(lambda: {"venue": "", "works": 0, "auto_included": 0, "pdfs": 0, "citations": 0})
    for w in works:
        src = str(w.get("source") or "").strip()
        if not src:
            continue
        vr = venue_acc[src]
        vr["venue"] = src
        vr["works"] += 1
        if w.get("scope") == "automatic-title-inclusion":
            vr["auto_included"] += 1
        if w.get("pdf") or w["id"] in repo_manifest:
            vr["pdfs"] += 1
        vr["citations"] += int(w.get("citations") or 0)
    top_venues = sorted(venue_acc.values(), key=lambda x: (-x["auto_included"], -x["works"], x["venue"]))[:35]

    # 4. Citation Network & Canon
    internal_ranked = []
    bridge_ranked = []
    total_internal_edges = 0
    for wid, ctx in context.items():
        w = works_by_id.get(wid)
        if not w:
            continue
        in_deg = len(ctx.get("cited_by") or [])
        out_deg = len(ctx.get("cites") or [])
        total_internal_edges += out_deg
        if in_deg > 0:
            internal_ranked.append({
                "id": wid,
                "title": w.get("title", ""),
                "year": w.get("year"),
                "authors": (w.get("authors") or [])[:4],
                "source": w.get("source", ""),
                "countries": w.get("countries") or [],
                "internal_citations": in_deg,
                "internal_references": out_deg,
                "global_citations": w.get("citations") or 0,
                "pdf": w.get("pdf", ""),
            })
        if in_deg >= 3 and out_deg >= 3:
            bridge_score = round(math.sqrt(in_deg * out_deg), 2)
            bridge_ranked.append({
                "id": wid,
                "title": w.get("title", ""),
                "year": w.get("year"),
                "authors": (w.get("authors") or [])[:4],
                "source": w.get("source", ""),
                "internal_citations": in_deg,
                "internal_references": out_deg,
                "bridge_score": bridge_score,
                "pdf": w.get("pdf", ""),
            })
    internal_ranked.sort(key=lambda x: (-x["internal_citations"], -x["global_citations"], x["id"]))
    bridge_ranked.sort(key=lambda x: (-x["bridge_score"], -x["internal_citations"], x["id"]))

    global_cited = sorted(
        [w for w in works if w.get("scope") == "automatic-title-inclusion"],
        key=lambda w: (-(w.get("citations") or 0), w["id"]),
    )[:40]
    top_global_cited = [{
        "id": w["id"], "title": w.get("title", ""), "year": w.get("year"),
        "authors": (w.get("authors") or [])[:4], "source": w.get("source", ""),
        "countries": w.get("countries") or [], "citations": w.get("citations") or 0,
        "pdf": w.get("pdf", ""),
    } for w in global_cited]

    # 5. Google EmbeddingGemma-300M Semantic Cluster & 2D Map Analysis
    sem_meta = read_json(out_dir / "semantic_index.json", {}) or {}
    vec_bin_path = out_dir / "semantic_vectors.bin"
    clusters_out = []
    map_points = []
    embedded_total = 0

    if sem_meta and vec_bin_path.is_file():
        dims = int(sem_meta.get("dimensions") or 128)
        ids = sem_meta.get("ids") or []
        raw_bytes = vec_bin_path.read_bytes()
        if len(raw_bytes) == len(ids) * dims and len(ids) > 0:
            embedded_total = len(ids)
            vecs = dequantize_int8(raw_bytes, dims)
            id_to_idx = {wid: i for i, wid in enumerate(ids)}

            # Fit k-means centroids on core design works (`automatic-title-inclusion` + `nordic_additions`),
            # then assign all embedded works to their nearest research cluster!
            core_indices = [
                i for i, wid in enumerate(ids)
                if wid in works_by_id and (
                    works_by_id[wid].get("scope") in ("automatic-title-inclusion", "editorial-candidate", "repository-candidate")
                )
            ]
            if len(core_indices) < n_clusters:
                core_indices = list(range(len(ids)))
            _, centroids = _spherical_kmeans(vecs[core_indices], k=n_clusters, iters=25, seed=42)
            all_labels = np.argmax(vecs @ centroids.T, axis=1).astype(np.int32)

            # Match each centroid to closest bilingual research theme preset
            presets = sem_meta.get("presets") or {}
            preset_keys = list(presets.keys())
            preset_mat = np.asarray([presets[k] for k in preset_keys], dtype=np.float32) if preset_keys else np.zeros((0, dims), dtype=np.float32)
            if preset_mat.shape[0] > 0:
                p_norms = np.linalg.norm(preset_mat, axis=1, keepdims=True)
                preset_mat = preset_mat / np.maximum(p_norms, 1e-12)

            global_df: Counter = Counter()
            for idx in core_indices:
                t = works_by_id.get(ids[idx], {}).get("title") or ""
                for word in {w.lower() for w in WORD_RE.findall(t)}:
                    if word not in STOPWORDS:
                        global_df[word] += 1

            used_themes: set[str] = set()
            for c_id in range(centroids.shape[0]):
                c_vec = centroids[c_id]
                theme_key = f"cluster-{c_id + 1}"
                theme_label = f" Klynge {c_id + 1}"
                if preset_mat.shape[0] > 0:
                    sims = preset_mat @ c_vec
                    ranked_p = np.argsort(-sims)
                    chosen = int(ranked_p[0])
                    for cand_p in ranked_p:
                        if preset_keys[int(cand_p)] not in used_themes:
                            chosen = int(cand_p)
                            break
                    theme_key = preset_keys[chosen]
                    used_themes.add(theme_key)
                    theme_label = THEME_LABELS_NN.get(theme_key, theme_key)

                member_indices = [i for i in core_indices if int(all_labels[i]) == c_id]
                member_titles = [works_by_id[ids[i]].get("title", "") for i in member_indices if ids[i] in works_by_id]
                keywords = _cluster_keywords(member_titles, global_df, len(core_indices), top_n=6)

                c_countries = Counter()
                c_pdfs = 0
                exemplar_cands = []
                for i in member_indices:
                    w = works_by_id.get(ids[i])
                    if not w:
                        continue
                    for cc in (w.get("countries") or ([w["source_country"]] if w.get("source_country") else [])):
                        if cc in NORDIC_COUNTRIES:
                            c_countries[cc] += 1
                    if w.get("pdf") or w["id"] in repo_manifest:
                        c_pdfs += 1
                    sim_c = float(vecs[i] @ c_vec)
                    exemplar_cands.append((sim_c + 0.03 * math.log1p(int(w.get("citations") or 0)), w))
                exemplar_cands.sort(key=lambda t: -t[0])
                exemplars = [{
                    "id": w["id"], "title": w.get("title", ""), "year": w.get("year"),
                    "authors": (w.get("authors") or [])[:3], "pdf": w.get("pdf", ""),
                } for _, w in exemplar_cands[:4]]

                clusters_out.append({
                    "cluster_id": c_id,
                    "theme_key": theme_key,
                    "label": theme_label,
                    "core_works": len(member_indices),
                    "total_assigned": int(np.sum(all_labels == c_id)),
                    "pdfs": c_pdfs,
                    "keywords": keywords,
                    "countries": {cc: c_countries.get(cc, 0) for cc in NORDIC_COUNTRIES},
                    "exemplars": exemplars,
                })

            # 2D projection for interactive canvas map (`semantic_map.json`)
            map_cands = []
            for i in core_indices:
                w = works_by_id.get(ids[i])
                if not w:
                    continue
                has_pdf = 1 if (w.get("pdf") or w["id"] in repo_manifest) else 0
                is_oa_primary = 1 if w.get("scope") == "automatic-title-inclusion" else 0
                cits = int(w.get("citations") or 0)
                map_cands.append((-(has_pdf * 2 + is_oa_primary), -cits, i))
            map_cands.sort()
            chosen_indices = [i for _, _, i in map_cands[:map_limit]]
            coords_2d = _svd_2d(vecs[chosen_indices])
            for pos_i, vec_i in enumerate(chosen_indices):
                wid = ids[vec_i]
                w = works_by_id[wid]
                cs = w.get("countries") or ([w["source_country"]] if w.get("source_country") else [])
                primary_country = next((c for c in cs if c in NORDIC_COUNTRIES), "")
                map_points.append({
                    "id": wid,
                    "x": round(float(coords_2d[pos_i, 0]), 4),
                    "y": round(float(coords_2d[pos_i, 1]), 4),
                    "c": int(all_labels[vec_i]),
                    "y_pub": w.get("year") or 0,
                    "cc": primary_country,
                    "pdf": 1 if (w.get("pdf") or wid in repo_manifest) else 0,
                })

    write_json(out_dir / "semantic_map.json", {
        "model": sem_meta.get("model", "google/embeddinggemma-300m"),
        "count": len(map_points),
        "clusters": [{"id": c["cluster_id"], "label": c["label"], "keywords": c["keywords"]} for c in clusters_out],
        "points": map_points,
    }, compact=True)

    pdf_stats = pdf_kat.get("stats") or {}
    analysis_payload = {
        "generated_at": now_iso(),
        "overview": {
            "total_searchable_works": len(all_works),
            "openalex_works": len(works),
            "openalex_auto_included": sum(w.get("scope") == "automatic-title-inclusion" for w in works),
            "openalex_review_queue": sum(w.get("scope") == "awaiting-eligibility-review" for w in works),
            "nordic_archive_candidates": len(nordic),
            "pre_2000_openalex_works": pre_2000_count,
            "repo_pdf_files": len(repo_manifest),
            "verified_oa_pdfs": pdf_stats.get("verified_oa_pdf_count", len(repo_manifest)),
            "internal_citation_edges": total_internal_edges,
            "cited_canon_works": len(canon_data),
            "google_embedded_works": embedded_total,
            "google_embedding_model": sem_meta.get("model", "google/embeddinggemma-300m"),
            "fulltext_extracted_pdfs": fulltext_extracted_docs,
            "fulltext_indexed_chunks": fulltext_chunks_count,
            "fulltext_google_embedded_chunks": fulltext_embedded_chunks,
        },
        "decades": [decades[k] for k in sorted(decades.keys())],
        "yearly": [yearly[k] for k in sorted(yearly.keys())],
        "countries": [country_stats[c] for c in NORDIC_COUNTRIES],
        "cross_nordic_collaboration": {
            "multi_nordic_works": cross_nordic_works,
            "matrix": co_matrix,
        },
        "top_institutions": inst_data[:30],
        "top_authors": authors_data[:40],
        "top_venues": top_venues,
        "citations": {
            "top_internally_cited": internal_ranked[:40],
            "top_globally_cited": top_global_cited,
            "top_bridge_works": bridge_ranked[:25],
            "top_cited_canon": canon_data[:40],
        },
        "semantic_clusters": clusters_out,
        "methodological_notes": [
            "OpenAlex-korpuset (1900–2026) kombinerer komplette årgangar av 17 sentrale designtidsskrift, 6 nordiske design- og arkitekturhøgskular, fleirspråklege søk på engelsk og fem nordiske språk samt siteringsfrontieren.",
            "Nasjonale og institusjonelle arkivkandidatar (Cristin/NVA, DiVA, Aaltodoc, tidsskrift.dk, IRIS/Skemman, Nordes/DRS) og historiske BibTeX-referansar vert haldne i separate kjeldelag utan automatisk samansmelting.",
            "Semantiske vektorar og klynger er rekna med Google DeepMind EmbeddingGemma-300M (Matryoshka L2-normaliserte einingsvektorar).",
        ],
    }
    write_json(out_dir / "analysis.json", analysis_payload, compact=True)
    return analysis_payload

