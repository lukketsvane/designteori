/* FUNN - figurane slik sida viser dei: kvar figur set saman ein eller fleire delar (d01 til d36) som svarer på same spørsmål.
   Ei figur kan ha delar som alltid står synlege (vis), delar som ein byter mellom (tabs) og delar bak eit trykk (tap). */
(function () {
  "use strict";
  const F = window.FUNN;

  /* byggjer ei figurfunksjon frå ei liste: {k, cap?} synleg, {tabs:[{k,t}]} faner, {k, tap:"tekst"} bak trykk */
  F.sam = function (items) {
    return async function (m, d, ctx) {
      const st = ctx.st; st.open = st.open || {}; st.tab = st.tab || {};
      const man = {}; (ctx.m.delar || []).forEach((x) => { man[x.id] = x; });
      /* ein del: eiga flate med eiga breidd, og nemnarlinja rett under */
      async function part(host, did, o) {
        o = o || {};
        const box = F.d("div", { cls: "del", "data-del": did }, host);
        if (o.cap) F.d("h4", { cls: "dtit", text: o.cap }, box);
        const slot = F.d("div", { cls: "del-in" }, box);
        const w = Math.floor(slot.getBoundingClientRect().width);
        const pc = Object.assign({}, ctx, { id: did, w, mob: w < 520, st: F.st[did] || (F.st[did] = {}), el: slot, part: did });
        await F.del[did](slot, d[did], pc);
        if (man[did]) F.d("p", { cls: "nem nem-del", text: man[did].nemnar }, box);
        return box;
      }
      for (let i = 0; i < items.length; i++) {
        const it = items[i];
        if (it.tabs) {
          const wrap = F.d("div", { cls: "tabs" }, m);
          const ctl = F.d("div", { cls: "ctl" }, wrap);
          const body = F.d("div", { cls: "tabbody" }, wrap);
          const key = "t" + i, cur = st.tab[key] && it.tabs.some((x) => x.k === st.tab[key]) ? st.tab[key] : it.tabs[0].k;
          st.tab[key] = cur;
          const show = async (k) => {
            const h = body.offsetHeight;
            body.style.minHeight = h + "px";
            body.textContent = "";
            await part(body, k);
            body.style.minHeight = "";
          };
          F.seg(ctl, it.tabs.map((x) => ({ k: x.k, t: x.t })), cur, (k) => { st.tab[key] = k; show(k); }, "Visning");
          await show(cur);
        } else if (it.tap) {
          F.tap(m, it.tap, async (body) => { await part(body, it.k); }, st.open, it.k);
        } else {
          await part(m, it.k, it);
        }
      }
    };
  };

  /* figurane, i sidas rekkjefølgje (same id-ar som i manifestet) */
  F.fig.f01 = F.sam([{ k: "d01" }, { k: "d27", cap: "Dublettar og dekning" }, { k: "d29", tap: "Arkivlaget, arkiv for arkiv" }]);
  F.fig.f02 = F.sam([{ k: "d28" }, { k: "d36", tap: "Same tal etter vekting av fulltekstutvalet" }]);
  F.fig.f03 = F.sam([{ tabs: [{ k: "d32", t: "Open PDF" }, { k: "d33", t: "Avhandlingar" }] }, { k: "d04", tap: "Fulltekst etter slag og siteringar" }]);
  F.fig.f04 = F.sam([{ tabs: [{ k: "d02", t: "Verk per år" }, { k: "d05", t: "Land" }, { k: "d30", t: "Fast panel" }] }]);
  F.fig.f05 = F.sam([{ k: "d06" }, { k: "d31", cap: "Same mål i nordiske verk utanfor scope" }, { k: "d07", tap: "Nordisk samarbeid mot ein nullmodell" }, { k: "d08", tap: "Institusjonar og forfattarar" }]);
  F.fig.f06 = F.sam([{ k: "d09" }]);
  F.fig.f07 = F.sam([{ tabs: [{ k: "d10", t: "Konsentrasjon" }, { k: "d11", t: "Nordiske kanalar og porten" }] }]);
  F.fig.f08 = F.sam([{ k: "d13" }]);
  F.fig.f09 = F.sam([{ tabs: [{ k: "d14", t: "Mottekne siteringar" }, { k: "d12", t: "Etter kanal og over tid" }] }]);
  F.fig.f10 = F.sam([{ tabs: [{ k: "d15", t: "Referansetal og alder" }, { k: "d16", t: "Kvar referansane går" }] }]);
  F.fig.f11 = F.sam([{ k: "d18" }]);
  F.fig.f12 = F.sam([{ tabs: [{ k: "d17", t: "Siteringssamfunn" }, { k: "d19", t: "Tekstklynger" }] }]);
  F.fig.f13 = F.sam([{ k: "d20" }]);
  F.fig.f14 = F.sam([{ tabs: [{ k: "d21", t: "Breidde og anker" }, { k: "d22", t: "Stig og fell" }] }]);
  F.fig.f15 = F.sam([{ tabs: [{ k: "d03", t: "Språkmerke" }, { k: "d34", t: "Nordiske tekstar" }, { k: "d35", t: "Praksis og handverk" }] }]);
  F.fig.f16 = F.sam([{ k: "d23" }, { k: "d24", tap: "Datainnsamlingsmarkørar over tid, etter kjelde og land" }]);
  F.fig.f17 = F.sam([{ k: "d25" }]);
  F.fig.f18 = F.sam([{ k: "d26" }]);
})();
