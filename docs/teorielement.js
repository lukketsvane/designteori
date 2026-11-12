/* Teorielement: søk i hovudpåstandar. Sjølvstendig modul som ikkje rører resten av arbeidsbenken. */
(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  const REL = { kind_of: "er ein type", part_of: "er del av", causes_or_enables: "fører til eller gjer mogleg", requires: "krev", precedes: "kjem før", associated_with: "heng saman med", defined_as: "er definert som", differs_from: "skil seg frå", has_property: "har eigenskapen", prescribes: "bør", other: "anna" };
  const DEF = { defined: "definert", defined_by_citation: "definert ved tilvising", not_stated: "ikkje oppgjeve", stated_none_exists: "teksten seier at det ikkje finst" };
  const FORM = { argument: "argument", literature: "litteratur", example: "døme", case: "case", data_collection: "datainnsamling", experiment: "eksperiment", design_work: "designarbeid", practice_reflection: "praksisrefleksjon", modelling: "modellering", use_in_practice: "bruk i praksis", other: "anna" };
  const LOC = { abstract: "samandrag", introduction: "innleiing", conclusion: "konklusjon" };
  const SUP = { reported: "oppgjeve", not_stated: "ikkje oppgjeve i teksten", stated_untested: "teksten seier at det ikkje er prøvd" };
  const ROLE = { from: "frå", to: "til", condition: "vilkår", other: "anna" };
  let rows = [];

  function fill(id, map, first) {
    const el = $(id);
    if (!el) return;
    el.innerHTML = `<option value="">${first}</option>` + Object.keys(map).map((k) => `<option value="${k}">${esc(map[k])}</option>`).join("");
  }

  function stated(label, o) {
    if (o && o.status === "stated") return `<div class="te-line"><span class="te-k">${label}</span>«${esc(o.excerpt)}»</div>`;
    if (o && o.status === "stated_none_exists") return `<div class="te-line"><span class="te-k">${label}</span>teksten seier at det ikkje finst: «${esc(o.excerpt)}»</div>`;
    return `<div class="te-line te-dim"><span class="te-k">${label}</span>ikkje oppgjeve i teksten</div>`;
  }

  function rowHtml(r) {
    const w = r.work || {};
    const doi = w.doi ? ` · <a href="${esc(w.doi)}" target="_blank" rel="noopener">DOI</a>` : "";
    const cons = (r.concepts || []).map((c) => `${esc(c.term)} <span class="te-dim">(${ROLE[c.role] || esc(c.role)}; ${DEF[c.definition_status] || esc(c.definition_status)})</span>`).join(" · ");
    const sup = (r.support || []).map((s) => FORM[s.form] || esc(s.form)).join(", ");
    const th = (r.theories || []).map((t) => esc(t.name)).join(", ");
    const meta = esc(w.title || "") + (w.year ? ` (${esc(w.year)})` : "") + (r.pdf_page ? ` · s. ${esc(r.pdf_page)}` : "") + (r.claim_location ? ` · ${LOC[r.claim_location] || esc(r.claim_location)}` : "") + doi;
    return `<div class="te-row">
      <div class="te-ex">«${esc(r.excerpt)}»</div>
      <div class="te-meta">${meta}</div>
      <div class="te-line"><span class="te-k">samanheng</span>${REL[r.relation_kind] || esc(r.relation_kind)}${r.relation_expression ? ` («${esc(r.relation_expression)}»)` : ""}</div>
      <div class="te-line"><span class="te-k">omgrep</span>${cons}</div>
      ${stated("bruksområde", r.scope)}${stated("forklaring", r.explanation)}${stated("føreseiing", r.prediction)}
      <div class="te-line"><span class="te-k">prøvd</span>${SUP[r.support_status] || esc(r.support_status)}${sup ? `: ${sup}` : ""}</div>
      ${th ? `<div class="te-line"><span class="te-k">teori</span>${th}</div>` : ""}
    </div>`;
  }

  function render() {
    const q = ($("teQ").value || "").trim().toLowerCase();
    const rel = $("teRel").value, def = $("teDef").value, form = $("teForm").value;
    const hits = rows.filter((r) => {
      if (rel && r.relation_kind !== rel) return false;
      if (def && !(r.concepts || []).some((c) => c.definition_status === def)) return false;
      if (form && !(r.support || []).some((s) => s.form === form)) return false;
      return !q || r._q.indexOf(q) !== -1;
    });
    $("teCount").textContent = `${hits.length} av ${rows.length} rader`;
    $("teList").innerHTML = hits.map(rowHtml).join("");
  }

  async function init() {
    if (!$("teList")) return;
    const st = document.createElement("style");
    st.textContent = ".te-row{padding:14px 0;border-top:1px solid var(--line,rgba(127,127,127,.3))}.te-ex{line-height:1.45}.te-meta,.te-line{font-size:12.5px;margin-top:6px;line-height:1.45}.te-meta,.te-dim,.te-note{color:var(--dim,#767676)}.te-k{font-family:'IBM Plex Mono',monospace;font-size:11px;text-transform:uppercase;letter-spacing:.04em;margin-right:8px}.te-note{font-size:12.5px;margin:10px 0}.te-p{font-size:14px;line-height:1.5;margin:0 0 10px}";
    document.head.appendChild(st);
    fill("teRel", REL, "Alle samanhengar");
    fill("teDef", DEF, "Alle definisjonsstatusar");
    fill("teForm", FORM, "Alle støtteformer");
    let d = null;
    try { const r = await fetch("data/teorielement/rader.json"); if (r.ok) d = await r.json(); } catch (e) { d = null; }
    if (!d || !Array.isArray(d.rows)) { $("teCount").textContent = "Radene kunne ikkje lastast."; return; }
    rows = d.rows;
    for (const r of rows) {
      const parts = [r.excerpt, r.relation_expression, (r.work || {}).title];
      for (const c of r.concepts || []) parts.push(c.term, c.definition_excerpt);
      for (const t of r.theories || []) parts.push(t.name);
      for (const k of ["scope", "explanation", "prediction"]) if (r[k] && r[k].excerpt) parts.push(r[k].excerpt);
      for (const s of r.support || []) parts.push(s.excerpt);
      r._q = parts.filter(Boolean).join(" ").toLowerCase();
    }
    if (d.synthetic) $("teNote").textContent = "Radene under er syntetiske døme som viser formatet. Dei er ikkje henta frå korpuset.";
    ["teRel", "teDef", "teForm"].forEach((id) => $(id).addEventListener("change", render));
    let tmr = null;
    $("teQ").addEventListener("input", () => { clearTimeout(tmr); tmr = setTimeout(render, 90); });
    render();
  }

  init();
})();
