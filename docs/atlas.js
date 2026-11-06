/* DESIGNTEORI researcher, institution and citation atlas.
 * Pure client-side browsing of the public OpenAlex metadata snapshot.
 * Reference edges do not mean endorsement, replication or theoretical descent.
 */
(() => {
"use strict";
const $ = (id) => document.getElementById(id);
const fmt = (n) => Number(n || 0).toLocaleString("nb-NO");
const el = (tag, text, cls) => {
 const node = document.createElement(tag);
 if (text !== undefined && text !== null) node.textContent = String(text);
 if (cls) node.className = cls;
 return node;
};
const link = (href, label) => {
 if (!/^https:\/\//i.test(href || "")) return null;
 const a = el("a",label);a.href=href;a.target="_blank";a.rel="noopener noreferrer";return a;
};
const getJSON = async (path) => {
 const result=await fetch(path);
 if(!result.ok)throw new Error("HTTP "+result.status+" for "+path);
 return await result.json();
};
let worksPromise,contextPromise,authorsPromise,institutionsPromise;
const works = () => worksPromise ||= getJSON("./data/publications.json").then(r => new Map(r.map(w=>[w.id,w])));
const contexts = () => contextPromise ||= getJSON("./data/work_context.json");
const authors = () => authorsPromise ||= getJSON("./data/authors.json");
const institutions = () => institutionsPromise ||= getJSON("./data/institutions.json");
function itemList(container,label,ids,byID){
 const section=el("section",undefined,"detail-section");
 section.append(el("h3",label+" ("+fmt(ids.length)+")","detail-subtitle"));
 if(!ids.length){section.append(el("p","Ingen interne lenkjer funne i dette innsamla utvalet.","detail-note"));container.append(section);return}
 for(const id of ids.slice(0,16)){
  const row=el("div",undefined,"detail-item");
  const w=byID.get(id);
  if(w){
   const b=el("button",(w.year||"") + " · " + w.title);b.type="button";b.addEventListener("click",()=>window.openDesignWork(id));
   row.append(b);
  }else row.append(el("span",id));
  section.append(row);
 }
 if(ids.length>16)section.append(el("p","Viser dei 16 første interne koplingane.","detail-note"));
 container.append(section);
}
function tagline(text){
 const p=el("p",text,"detail-note");return p;
}
function closeWork(){
 const dlg=$("work-modal");
 if(dlg.open)dlg.close();
 const u = new URL(location.href);
 u.searchParams.delete("work");
 history.replaceState({},"",u.toString());
}
window.openDesignWork = async function(id){
 const dlg=$("work-modal");
 const box=$("work-detail");
 box.replaceChildren(el("p","Lastar publikasjonen og dei registrerte siteringane…","detail-note"));
 if(!dlg.open)dlg.showModal();
 try{
  const [byID,details]=await Promise.all([works(),contexts()]);
  const w=byID.get(id);
  if(!w){box.replaceChildren(tagline("Ingen publikasjon med denne ID-en i det arkiverte utvalet."));return}
  const ctx=details[id]||{authors:[],cites:[],cited_by:[]};
  box.replaceChildren();
  box.append(el("div",String(w.year)+" · "+w.kind,"eyebrow"));
  const title=el("h2",w.title);title.id="detail-title";box.append(title);
  const meta=el("div",undefined,"metadata");
  meta.append(el("p",[w.source,w.topic].filter(Boolean).join(" · ")));
  meta.append(el("p","OpenAlex: "+w.id+" · "+fmt(w.citations)+" globale OpenAlex-siteringar, slik snapshotet registrerte"));
  if(w.review_priority)meta.append(tagline("Maskinell leseprioritet: "+w.review_priority+" ("+w.review_score+"/100). Dette er ikkje fagleg vurdering."));
  box.append(meta);
  const links=el("p",undefined,"links");
  links.style.flexFlow="row wrap";
  for(const [url,label] of [[w.doi,"Opne DOI"],[w.pdf,"PDF (arkiv)"],[w.text,"Fulltekst (TXT)"],[w.oa_url,"OA-original"]]){
   const a=link(url,label);if(a)links.append(a);
  }
  if(links.childElementCount)box.append(links);
  const heading=el("h3","Registrerte forfattarar og tilknytingar","detail-subtitle");
  heading.style.marginTop="27px";box.append(heading);
  const names=el("div");
  for(const a of (ctx.authors||[])){
   const row=el("div",undefined,"detail-item");
   const b=el("button",a.name);b.type="button";
   b.addEventListener("click",()=>window.openScholar(a.id,"author"));row.append(b);
   for(const ins of (a.institutions||[])){
    const chip=el("span",(ins.name||"Ikkje registrert")+(ins.country?" · "+ins.country:""),"chip");
    row.append(chip);
   }
   names.append(row);
  }
  if(!names.childElementCount)names.append(tagline("Ingen forfattartilknytingar registrerte."));
  box.append(names);
  const cols=el("div",undefined,"detail-columns");
  cols.style.marginTop="25px";
  itemList(cols,"Viser til i korpuset",ctx.cites||[],byID);
  itemList(cols,"Vist til av i korpuset",ctx.cited_by||[],byID);
  box.append(cols);
  box.append(tagline("Dette er automatisk identifiserte referansar mellom verk i utvalet, ikkje påstandar om teoriar som er bygde på, testa eller replikerte."));
  const url=new URL(location.href);url.searchParams.set("work",id);history.replaceState({},"",url.toString());
 }catch(e){box.replaceChildren(tagline("Klarte ikkje laste detaljar: "+e.message));console.error(e)}
};
$("work-close").addEventListener("click",closeWork);
$("work-modal").addEventListener("close",()=>{
 const url = new URL(location.href);if(url.searchParams.has("work")){url.searchParams.delete("work");history.replaceState({},"",url.toString())}
});
let mode = "author";
window.openScholar = async function(id,kind="author"){
 const dlg=$("scholar-modal"),box=$("scholar-detail");
 box.replaceChildren(el("p","Lastar publikasjonar…","detail-note"));
 if(!dlg.open)dlg.showModal();
 try{
  const [people,orgs,byID]=await Promise.all([authors(),institutions(),works()]);
  const x=kind==="author" ? people.items.find(a=>a.id===id) : orgs.items.find(a=>a.id===id);
  if(!x){box.replaceChildren(tagline("Ingen treff i den lokale katalogen."));return}
  box.replaceChildren();
  box.append(el("div",(kind==="author"?"Forskar":"Institusjon")+" · OpenAlex-kandidatkopling","eyebrow"));
  const name=el("h2",x.name);name.id="scholar-title";box.append(name);
  box.append(tagline(fmt(x.works)+" unike verk i dette uttrekket; "+fmt(x.automatically_title_included)+" automatisk tittelinkluderte. Dette er ikkje total produksjon."));
  const subt=el("p",undefined,"metadata");
  subt.textContent=(x.countries||[x.country]).filter(Boolean).join(", ") +
   (x.institutions && x.institutions.length ? " · "+x.institutions.slice(0,6).join("; ") : "");
  box.append(subt);
  const wids=Array.from(x.work_ids||[]);
  wids.sort((a,b)=>(byID.get(b)?.review_score||0)-(byID.get(a)?.review_score||0));
  const list=el("div");
  itemList(list,"Registrerte verk",wids,byID);
  box.append(list);
 }catch(e){box.replaceChildren(tagline("Klarte ikkje laste oppføringa: "+e.message));console.error(e)}
};
$("scholar-close").addEventListener("click",()=>$("scholar-modal").close());

let authorRows=[],instRows=[], authorLimit=16,instLimit=16;
function renderScholars(kind){
 const isAuthor=kind==="author";
 const rows=isAuthor?authorRows:instRows;
 const root=$(isAuthor?"author-results":"institution-results");
 const q=$(isAuthor?"author-search":"institution-search").value.trim().toLocaleLowerCase();
 const selected=rows.filter(r=>!q||(r.name+" "+r.id+" "+(r.country||"")).toLocaleLowerCase().includes(q));
 const limit=isAuthor?authorLimit:instLimit;
 const frag=document.createDocumentFragment();
 for(const r of selected.slice(0,limit)){
  const card=el("div",undefined,"cluster-card");
  const info=el("div");
  const b=el("button",r.name);
  b.type="button";b.addEventListener("click",()=>window.openScholar(r.id,kind));
  info.append(b);
  const p=el("p",isAuthor?(r.countries||[]).join(", "):r.country||"");
  info.append(p);card.append(info);
  card.append(el("span",fmt(r.automatically_title_included)+" / "+fmt(r.works),"cluster-count"));
  frag.append(card);
 }
 root.replaceChildren(frag);
 $(isAuthor?"author-count":"institution-count").textContent=fmt(selected.length)+" oppføringar · inkl. / totalt i utvalet";
 $(isAuthor?"author-more":"institution-more").hidden=selected.length<=limit;
}
function loadScholars(){
 Promise.all([authors(),institutions()]).then(([a,i])=>{
  authorRows=a.items;instRows=i.items;
  renderScholars("author");renderScholars("institution");
 }).catch(err=>{$("author-count").textContent="Feil ved lasting";$("institution-count").textContent="Feil ved lasting";console.error(err)});
}
$("author-search").addEventListener("input",()=>{authorLimit=16;renderScholars("author")});
$("institution-search").addEventListener("input",()=>{instLimit=16;renderScholars("institution")});
$("author-more").addEventListener("click",()=>{authorLimit+=20;renderScholars("author")});
$("institution-more").addEventListener("click",()=>{instLimit+=20;renderScholars("institution")});
// Defer the ~5 MiB author index until users approach the section.
if("IntersectionObserver" in window){
 const observer=new IntersectionObserver((entries)=>{
  if(entries.some(e=>e.isIntersecting)){observer.disconnect();loadScholars()}
 },{rootMargin:"200px"});
 observer.observe($("forskarar"));
}else loadScholars();

const deep=new URL(location.href).searchParams.get("work");
if(deep && /^W[0-9]+$/.test(deep))window.openDesignWork(deep);
})();
