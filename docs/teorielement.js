/* Teorielement: søk i hovudpåstandar. Sjølvstendig modul som ikkje rører resten av arbeidsbenken. */
(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  const REL = { kind_of: "er ein type", part_of: "er del av", causes_or_enables: "fører til eller gjer mogleg", requires: "krev", precedes: "kjem før", associated_with: "heng saman med", defined_as: "er definert som", differs_from: "skil seg frå", has_property: "har eigenskapen", prescribes: "bør", other: "anna" };
  const DEF = { defined: "definert", defined_by_citation: "definert ved tilvising", not_stated: "ikkje funnen i søk", stated_none_exists: "teksten seier at det ikkje finst" };
  const FORM = { argument: "argument", literature: "litteratur", example: "døme", case: "case", data_collection: "datainnsamling", experiment: "eksperiment", design_work: "designarbeid", practice_reflection: "praksisrefleksjon", modelling: "modellering", use_in_practice: "bruk i praksis", other: "anna" };
  const LOC = { abstract: "samandrag", introduction: "innleiing", conclusion: "konklusjon" };
  const SUP = { reported: "oppgjeve", not_stated: "ikkje oppgjeve i delane som er lesne", stated_untested: "teksten seier at det ikkje er prøvd" };
  const ROLE = { from: "frå", to: "til", condition: "vilkår", other: "anna" };
  const TROLE = { foundation: "byggjer på", counterpoint: "set seg opp mot", tested: "prøver", extended: "byggjer ut", other: "nemner" };
  let rows = [];

  function fill(id, map, first) {
    const el = $(id);
    if (!el) return;
    el.innerHTML = `<option value="">${first}</option>` + Object.keys(map).map((k) => `<option value="${k}">${esc(map[k])}</option>`).join("");
  }

  const qlink = (s) => `<a href="#teorielement" class="te-q" data-q="${esc(s)}">${esc(s)}</a>`;

  function stated(label, o) {
    if (o && o.status === "stated") return `<div class="te-line"><span class="te-k">${label}</span>«${esc(o.excerpt)}»</div>`;
    if (o && o.status === "stated_none_exists") return `<div class="te-line"><span class="te-k">${label}</span>teksten seier at det ikkje finst: «${esc(o.excerpt)}»</div>`;
    return `<div class="te-line te-dim"><span class="te-k">${label}</span>ikkje oppgjeve i delane som er lesne</div>`;
  }

  function rowHtml(r) {
    const w = r.work || {};
    const au = Array.isArray(w.authors) && w.authors.length ? w.authors.slice(0, 3).join(", ") + (w.authors.length > 3 ? " mfl." : "") : "";
    const doi = w.doi ? ` · <a href="${esc(w.doi)}" target="_blank" rel="noopener">DOI</a>` : "";
    const lic = w.license ? ` · ${esc(w.license)}` : "";
    const cons = (r.concepts || []).map((c) => `${qlink(c.term)} <span class="te-dim">(${ROLE[c.role] || esc(c.role)}; ${DEF[c.definition_status] || esc(c.definition_status)})</span>`).join(" · ");
    const defs = (r.concepts || []).filter((c) => c.definition_excerpt).map((c) => `<div class="te-line"><span class="te-k">definisjon</span>${esc(c.term)} <span class="te-dim">(${DEF[c.definition_status] || esc(c.definition_status)}${c.definition_page ? `, s. ${esc(c.definition_page)}` : ""})</span>: «${esc(c.definition_excerpt)}»</div>`).join("");
    const sup = (r.support || []).map((s) => FORM[s.form] || esc(s.form)).join(", ");
    const th = (r.theories || []).map((t) => `${TROLE[t.role] || esc(t.role)} ${qlink(t.name)}`).join(" · ");
    const att = r.attribution === "adopted" ? "overteken" + (r.adopted_from ? ` frå ${esc(r.adopted_from)}` : "") : r.attribution === "own" ? "eigen" : "";
    const rel = r.relation_kind === "other" && r.relation_kind_other ? esc(r.relation_kind_other) : (REL[r.relation_kind] || esc(r.relation_kind));
    const rt = r.retest === true ? "påstanden gjekk att då teksten vart lesen ein gong til" : r.retest === false ? "påstanden gjekk ikkje att då teksten vart lesen ein gong til" : "";
    const meta = (au ? `${esc(au)}: ` : "") + esc(w.title || "") + (w.year ? ` (${esc(w.year)})` : "") + (r.pdf_page ? ` · s. ${esc(r.pdf_page)}` : "") + (r.claim_location ? ` · ${LOC[r.claim_location] || esc(r.claim_location)}` : "") + doi + lic;
    return `<div class="te-row">
      <div class="te-ex">«${esc(r.excerpt)}»</div>
      <div class="te-meta">${meta}</div>
      <div class="te-line"><span class="te-k">samanheng</span>${rel}${r.relation_expression ? ` («${esc(r.relation_expression)}»)` : ""}${att ? ` · ${att}` : ""}</div>
      <div class="te-line"><span class="te-k">omgrep</span>${cons}</div>${defs}
      ${stated("bruksområde", r.scope)}${stated("forklaring", r.explanation)}${stated("føreseiing", r.prediction)}
      <div class="te-line"><span class="te-k">prøvd</span>${SUP[r.support_status] || esc(r.support_status)}${sup ? `: ${sup}` : ""}</div>
      ${th ? `<div class="te-line"><span class="te-k">teori</span>${th}</div>` : ""}
      ${rt ? `<div class="te-line te-dim"><span class="te-k">maskinkoding</span>${rt}</div>` : ""}
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
    st.textContent = ".te-row{padding:14px 0;border-top:1px solid var(--line,rgba(127,127,127,.3))}.te-ex{line-height:1.45}.te-meta,.te-line{font-size:12.5px;margin-top:6px;line-height:1.45}.te-meta,.te-dim,.te-note{color:var(--dim,#767676)}.te-k{font-family:'IBM Plex Mono',monospace;font-size:11px;text-transform:uppercase;letter-spacing:.04em;margin-right:8px}.te-note{font-size:12.5px;margin:10px 0}.te-p{font-size:14px;line-height:1.5;margin:0 0 10px}.te-q{color:inherit;text-decoration:underline dotted;text-underline-offset:2px}";
    document.head.appendChild(st);
    fill("teRel", REL, "Alle samanhengar");
    fill("teDef", DEF, "Alle definisjonsstatusar");
    fill("teForm", FORM, "Alle støtteformer");
    let d = null;
    try { const r = await fetch("data/teorielement/rader.json"); if (r.ok) d = await r.json(); } catch (e) { d = null; }
    if (!d || !Array.isArray(d.rows)) { $("teCount").textContent = "Radene kunne ikkje lastast."; return; }
    rows = d.rows;
    for (const r of rows) {
      const w = r.work || {};
      const parts = [r.excerpt, r.relation_expression, r.relation_kind_other, r.adopted_from, w.title];
      if (Array.isArray(w.authors)) parts.push(w.authors.join(" "));
      for (const c of r.concepts || []) parts.push(c.term, c.definition_excerpt);
      for (const t of r.theories || []) parts.push(t.name);
      for (const k of ["scope", "explanation", "prediction"]) if (r[k] && r[k].excerpt) parts.push(r[k].excerpt);
      for (const s of r.support || []) parts.push(s.excerpt);
      r._q = parts.filter(Boolean).join(" ").toLowerCase();
    }
    let note = "";
    if (d.synthetic) {
      note = "Radene under er syntetiske døme som viser formatet. Dei er ikkje henta frå korpuset.";
    } else {
      const s = d.stats || {};
      note = `${rows.length} maskinkoda rader frå ${s.texts_with_rows && s.texts ? `${s.texts_with_rows} av ${s.texts}` : (s.texts || "nokre")} ope lisensierte verk. Radene er ikkje validerte mot handkoding.`;
      if (typeof s.retest_share === "number") note += ` ${Math.round(s.retest_share * 100)} % av radene gjekk att då tekstane vart lesne ein gong til.`;
      if (s.dropped_in_review) note += ` ${s.dropped_in_review} rader er tekne ut i ein maskinell kontroll.`;
      if (d.excerpt_rule) note += ` ${d.excerpt_rule}.`;
      if (d.definition_rule) note += ` ${d.definition_rule}.`;
    }
    $("teNote").textContent = note;
    ["teRel", "teDef", "teForm"].forEach((id) => $(id).addEventListener("change", render));
    let tmr = null;
    $("teQ").addEventListener("input", () => { clearTimeout(tmr); tmr = setTimeout(render, 90); });
    $("teList").addEventListener("click", (e) => {
      const a = e.target && e.target.closest ? e.target.closest("a.te-q") : null;
      if (!a) return;
      e.preventDefault();
      $("teQ").value = a.getAttribute("data-q") || "";
      render();
      $("teQ").scrollIntoView({ block: "center" });
    });
    render();
  }

  init();
})();
