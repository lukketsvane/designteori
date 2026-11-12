"""Samsvar mellom kodarar i valideringa av teorielementbasen.

Del A (kodarane finn hovudpåstandane sjølve): treff, presisjon, gjenfinning og F1 for kvart par av kodarar.
Del B (felt for felt på same utdrag): prosent samsvar og Cohen's kappa for kvart par, Krippendorff's alfa
for alle kodarane, Jaccard-likskap for omgrep og støtteformer, og overlapp mellom utdrag.
Konfidensintervall: bootstrap over tekstar (persentil, 95 %).

  python semje.py --maskin ../data/teorielement/rader.json --utval utval.json \
      --a A=kodeark-del-a-A.xlsx --a B=kodeark-del-a-B.xlsx \
      --b A=kodeark-del-b-A.xlsx --b B=kodeark-del-b-B.xlsx --ut semje.json

  python semje.py --sjolvtest --maskin ../data/teorielement/rader.json --utval utval.json \
      --mal-a kodeark-del-a.xlsx --mal-b kodeark-del-b.xlsx

Sjølvtesten lagar syntetiske kodarar frå maskinkodinga. Utan støy skal alle mål bli 1.
Krev openpyxl.
"""
import argparse, collections, difflib, itertools, json, pathlib, random, re, sys, tempfile
import openpyxl

FIELDS = ['is_claim', 'is_headline', 'claim_location', 'attribution', 'relation_kind', 'support_status', 'scope', 'explanation', 'prediction']
EXC = {'relation_expression': None, 'scope_utdrag': 'scope', 'explanation_utdrag': 'explanation', 'prediction_utdrag': 'prediction'}
TRI = ['stated', 'not_stated', 'stated_none_exists']
LISTS = dict(claim_location=['abstract', 'introduction', 'conclusion'], attribution=['own', 'adopted'],
             relation_kind=['kind_of', 'part_of', 'causes_or_enables', 'requires', 'precedes', 'associated_with', 'defined_as', 'differs_from', 'has_property', 'prescribes', 'other'],
             support_status=['reported', 'not_stated', 'stated_untested'], scope=TRI, explanation=TRI, prediction=TRI,
             role=['from', 'to', 'condition', 'other'], definition_status=['defined', 'defined_by_citation', 'not_stated', 'stated_none_exists'])
MACHINE = 'modell'


# ---------- normalisering ----------
def norm(v):
    if v is None: return None
    if isinstance(v, float) and v.is_integer(): v = int(v)
    s = str(v).strip()
    return s or None

def toks(s): return set(re.findall(r'\w{3,}', (s or '').lower()))

def overlap(a, b):
    """Del av orda i det kortaste utdraget som òg står i det andre (ord på minst tre teikn)."""
    ta, tb = toks(a), toks(b)
    if not ta or not tb: return 1.0 if a and (a or '').strip().lower() == (b or '').strip().lower() else 0.0
    return len(ta & tb) / min(len(ta), len(tb))

def tkey(s): return re.sub(r'[\s\-–]+', ' ', re.sub(r"[\"'«»“”‘’().,;:]", '', (s or '').casefold())).strip()
def same_term(a, b): return a == b or difflib.SequenceMatcher(None, a, b).ratio() >= 0.85
def text_of(item): return item.rsplit('-', 1)[0]
def pick(d, prefix): return next((v for k, v in d.items() if k.startswith(prefix)), None)


# ---------- innlesing ----------
def rows_of(ws):
    it = ws.iter_rows(values_only=True); head = [norm(h) for h in next(it)]
    for r in it:
        d = {h: norm(v) for h, v in zip(head, r) if h}
        if any(v is not None for v in d.values()): yield d

def load_machine(path):
    items, theories = {}, {}
    for r in json.load(open(path, encoding='utf-8'))['rows']:
        st = lambda k: (r.get(k) or {}).get('status'); ex = lambda k: (r.get(k) or {}).get('excerpt')
        items[r['id']] = dict(
            is_claim='1', is_headline='1', claim_location=r.get('claim_location'), attribution=r.get('attribution'), relation_kind=r.get('relation_kind'),
            support_status=r.get('support_status'), scope=st('scope'), explanation=st('explanation'), prediction=st('prediction'),
            relation_expression=r.get('relation_expression'), scope_utdrag=ex('scope'), explanation_utdrag=ex('explanation'), prediction_utdrag=ex('prediction'),
            concepts=[dict(term=c['term'], role=c.get('role'), definition_status=c.get('definition_status'), definition_excerpt=c.get('definition_excerpt'), definition_page=c.get('definition_page')) for c in r.get('concepts') or []],
            support=[dict(source=s.get('source'), form=s.get('form'), excerpt=s.get('excerpt')) for s in r.get('support') or []],
            excerpt=r.get('excerpt'), pdf_page=r.get('pdf_page'))
        theories.setdefault(text_of(r['id']), [dict(name=t['name'], role=t.get('role'), excerpt=t.get('excerpt')) for t in r.get('theories') or []])
    return dict(items=items, theories=theories)

def load_b(path):
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True); items = {}
    for d in rows_of(wb['Påstandar']):
        if d.get('item'): items[d['item']] = dict(d, concepts=[], support=[])
    for d in rows_of(wb['Omgrep']):
        if d.get('item') in items and d.get('term_as_written'):
            items[d['item']]['concepts'].append(dict(term=d['term_as_written'], role=d.get('role'), definition_status=d.get('definition_status'), definition_excerpt=d.get('definisjon_utdrag')))
    for d in rows_of(wb['Støtte']):
        if d.get('item') in items and d.get('form'):
            items[d['item']]['support'].append(dict(source=d.get('source'), form=d['form'], excerpt=d.get('støtte_utdrag')))
    theories = collections.defaultdict(list)
    if 'Teoriar' in wb.sheetnames:
        for d in rows_of(wb['Teoriar']):
            if d.get('tekst') and d.get('name_as_written'): theories[d['tekst'].split()[0]].append(dict(name=d['name_as_written'], role=d.get('role')))
    return dict(items=items, theories=dict(theories))

def load_a(path, labels):
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True); claims = {t: [] for t in labels.values()}
    for d in rows_of(wb['Påstandar']):
        ex = pick(d, 'utdrag')
        if d.get('tekst') in labels and ex: claims[labels[d['tekst']]].append(ex)
    return claims


# ---------- mål ----------
def kappa(pairs):
    n = len(pairs)
    if not n: return None
    po = sum(a == b for a, b in pairs) / n
    ca = collections.Counter(a for a, _ in pairs); cb = collections.Counter(b for _, b in pairs)
    pe = sum(ca[k] * cb[k] for k in ca) / n ** 2
    return None if pe >= 1 else (po - pe) / (1 - pe)

def alpha(units):
    """Krippendorff's alfa for nominale data. units: liste av lister med verdiar (manglande verdiar utelatne)."""
    o = collections.Counter()
    for u in units:
        m = len(u)
        if m < 2: continue
        for i, j in itertools.permutations(range(m), 2): o[(u[i], u[j])] += 1 / (m - 1)
    nc = collections.Counter()
    for (a, _), w in o.items(): nc[a] += w
    n = sum(nc.values())
    if n <= 1: return None
    do = sum(w for (a, b), w in o.items() if a != b)
    de = sum(nc[a] * nc[b] for a in nc for b in nc if a != b) / (n - 1)
    return None if de == 0 else 1 - do / de

def boot(texts, stat, draws, rng):
    vals = [v for v in (stat([rng.choice(texts) for _ in texts]) for _ in range(draws)) if v is not None]
    if not texts or len(vals) < draws / 2: return None
    vals.sort()
    return [round(vals[int(0.025 * (len(vals) - 1))], 3), round(vals[int(0.975 * (len(vals) - 1))], 3)]

def r3(x): return None if x is None else round(x, 3)
def flat(by, ts): return [p for t in ts for p in by.get(t, [])]

def match_terms(ca, cb):
    pairs, used = [], set()
    for x in ca:
        kx = tkey(x.get('term') or x.get('name'))
        for j, y in enumerate(cb):
            if j not in used and same_term(kx, tkey(y.get('term') or y.get('name'))):
                used.add(j); pairs.append((x, y)); break
    return pairs

def uniq(cs):
    seen, out = set(), []
    for c in cs:
        k = tkey(c.get('term') or c.get('name'))
        if k and k not in seen: seen.add(k); out.append(c)
    return out

def match_claims(xs, ys):
    c = sorted(((overlap(x, y), i, j) for i, x in enumerate(xs) for j, y in enumerate(ys)), key=lambda t: (-t[0], t[1], t[2]))
    ui, uj = set(), set()
    for s, i, j in c:
        if s < 0.5: break
        if i not in ui and j not in uj: ui.add(i); uj.add(j)
    return len(ui)

def is_claim(c, item): return (c['items'].get(item) or {}).get('is_claim') == '1'


# ---------- analyse ----------
def analyse(B, A, draws=1000, seed=20261112):
    """B: kodar -> {'items', 'theories'}. A: kodar -> {tekst: [utdrag]}."""
    rng = random.Random(seed); res = dict(coders_b=list(B), coders_a=list(A), draws=draws, part_b={}, part_a={})
    pairs = list(itertools.combinations(B, 2)); items = sorted(set().union(*[set(c['items']) for c in B.values()])) if B else []
    texts = sorted({text_of(i) for i in items}); res['n_items'] = len(items); res['n_texts'] = len(texts)

    fields = {}
    for f in FIELDS:
        ok = lambda c, i: B[c]['items'].get(i, {}).get(f) is not None and (f == 'is_claim' or is_claim(B[c], i))
        units = collections.defaultdict(list)
        for i in items:
            u = [B[c]['items'][i][f] for c in B if ok(c, i)]
            if len(u) >= 2: units[text_of(i)].append(u)
        e = dict(n_units=sum(len(v) for v in units.values()), alpha=r3(alpha(flat(units, texts))), alpha_ci=boot(texts, lambda ts: alpha(flat(units, ts)), draws, rng), pairs={},
                 dist={c: dict(collections.Counter(B[c]['items'][i][f] for i in items if ok(c, i)).most_common()) for c in B})
        for x, y in pairs:
            by = collections.defaultdict(list)
            for i in items:
                if ok(x, i) and ok(y, i): by[text_of(i)].append((B[x]['items'][i][f], B[y]['items'][i][f]))
            p = flat(by, texts)
            e['pairs'][f'{x}–{y}'] = dict(n=len(p), pct=r3(sum(a == b for a, b in p) / len(p)) if p else None, kappa=r3(kappa(p)), kappa_ci=boot(texts, lambda ts: kappa(flat(by, ts)), draws, rng))
        fields[f] = e
    res['part_b']['fields'] = fields

    cons, sups, excs, ths = {}, {}, {}, {}
    for x, y in pairs:
        both = [i for i in items if is_claim(B[x], i) and is_claim(B[y], i)]
        jac, roles, defs, dex = [], [], [], []
        for i in both:
            ca, cb = uniq(B[x]['items'][i]['concepts']), uniq(B[y]['items'][i]['concepts'])
            if not ca or not cb: continue
            m = match_terms(ca, cb); jac.append(len(m) / (len(ca) + len(cb) - len(m)))
            for a, b in m:
                if a.get('role') and b.get('role'): roles.append((a['role'], b['role']))
                if a.get('definition_status') and b.get('definition_status'): defs.append((a['definition_status'], b['definition_status']))
                if a.get('definition_excerpt') and b.get('definition_excerpt'): dex.append(overlap(a['definition_excerpt'], b['definition_excerpt']) >= 0.5)
        ag = lambda p: dict(n=len(p), pct=r3(sum(a == b for a, b in p) / len(p)) if p else None, kappa=r3(kappa(p)), dist=[dict(collections.Counter(a for a, _ in p)), dict(collections.Counter(b for _, b in p))])
        cons[f'{x}–{y}'] = dict(n_items=len(jac), jaccard=r3(sum(jac) / len(jac)) if jac else None, role=ag(roles), definition_status=ag(defs),
                                definition_excerpt=dict(n=len(dex), share_overlap=r3(sum(dex) / len(dex)) if dex else None))
        fa = {i: {s['form'] for s in B[x]['items'][i]['support']} for i in both}; fb = {i: {s['form'] for s in B[y]['items'][i]['support']} for i in both}
        sj = [len(fa[i] & fb[i]) / len(fa[i] | fb[i]) for i in both if fa[i] | fb[i]]
        forms = sorted(set().union(*fa.values(), *fb.values())) if both else []
        sups[f'{x}–{y}'] = dict(n_items=len(both), n_with_form=len(sj), jaccard=r3(sum(sj) / len(sj)) if sj else None,
                                kappa_per_form={f: r3(kappa([(f in fa[i], f in fb[i]) for i in both])) for f in forms})
        ex = {}
        for f, need in EXC.items():
            v = [overlap(B[x]['items'][i].get(f), B[y]['items'][i].get(f)) >= 0.5 for i in both if B[x]['items'][i].get(f) and B[y]['items'][i].get(f)]
            ex[f] = dict(n=len(v), share_overlap=r3(sum(v) / len(v)) if v else None)
        excs[f'{x}–{y}'] = ex
        if B[x]['theories'] and B[y]['theories']:
            tj = []
            for t in texts:
                ta, tb = uniq(B[x]['theories'].get(t, [])), uniq(B[y]['theories'].get(t, []))
                if ta or tb: m = match_terms(ta, tb); tj.append(len(m) / (len(ta) + len(tb) - len(m)))
            ths[f'{x}–{y}'] = dict(n_texts=len(tj), jaccard=r3(sum(tj) / len(tj)) if tj else None)
    res['part_b'].update(concepts=cons, support_forms=sups, excerpts=excs, theories=ths)

    a_texts = sorted(set().union(*[set(c) for c in A.values()])) if A else []
    for x, y in itertools.combinations(A, 2):
        per = {t: (match_claims(A[x].get(t, []), A[y].get(t, [])), len(A[x].get(t, [])), len(A[y].get(t, []))) for t in a_texts}
        def f1(ts):
            m = sum(per[t][0] for t in ts); n = sum(per[t][1] + per[t][2] for t in ts)
            return 2 * m / n if n else None
        m, nx, ny = (sum(per[t][k] for t in a_texts) for k in range(3))
        res['part_a'][f'{x}–{y}'] = dict(matched=m, n_first=nx, n_second=ny, share_of_first=r3(m / nx) if nx else None, share_of_second=r3(m / ny) if ny else None,
                                         f1=r3(f1(a_texts)), f1_ci=boot(a_texts, f1, draws, rng), per_text={t: list(per[t]) for t in a_texts})
    return res


def report(res, title):
    f = lambda x: '–' if x is None else f'{x:.2f}'; ci = lambda c: '' if not c else f' [{c[0]:.2f}, {c[1]:.2f}]'; pc = lambda x: '–' if x is None else f'{100 * x:.0f} %'
    print(f'\n===== {title} =====')
    if res['part_a']:
        print(f"\nDEL A: kodarane finn hovudpåstandane sjølve ({', '.join(res['coders_a'])})")
        for k, v in res['part_a'].items():
            print(f"  {k:14s} treff {v['matched']:3d} | første har {v['n_first']:3d} ({pc(v['share_of_first'])} funne att) | andre har {v['n_second']:3d} ({pc(v['share_of_second'])} funne att) | F1 {f(v['f1'])}{ci(v['f1_ci'])}")
    if res['part_b'].get('fields'):
        print(f"\nDEL B: felt for felt ({res['n_items']} utdrag frå {res['n_texts']} tekstar; kodarar: {', '.join(res['coders_b'])})")
        print('  (Kappa og alfa seier lite når éin kodar har same verdi på alle utdrag, slik modellen har for is_claim og is_headline. Les prosent samsvar der.)')
        for fld, e in res['part_b']['fields'].items():
            print(f"  {fld}: alfa {f(e['alpha'])}{ci(e['alpha_ci'])} ({e['n_units']} utdrag)")
            for k, v in e['pairs'].items(): print(f"      {k:14s} n={v['n']:3d}  samsvar {pc(v['pct'])}  kappa {f(v['kappa'])}{ci(v['kappa_ci'])}")
            for c, d in e['dist'].items(): print(f"      fordeling {c}: " + ', '.join(f'{a} {b}' for a, b in d.items()))
        print('  omgrep (Jaccard per utdrag; rolle og definisjonsstatus for omgrep begge har registrert):')
        for k, v in res['part_b']['concepts'].items():
            print(f"      {k:14s} Jaccard {f(v['jaccard'])} ({v['n_items']} utdrag) | rolle: n={v['role']['n']} samsvar {pc(v['role']['pct'])} kappa {f(v['role']['kappa'])} | definisjonsstatus: n={v['definition_status']['n']} samsvar {pc(v['definition_status']['pct'])} kappa {f(v['definition_status']['kappa'])}")
        print('  støtteformer (Jaccard for utdrag der minst éin har registrert ei form):')
        for k, v in res['part_b']['support_forms'].items():
            print(f"      {k:14s} Jaccard {f(v['jaccard'])} ({v['n_with_form']} av {v['n_items']} utdrag) | kappa per form: " + ', '.join(f'{a} {f(b)}' for a, b in v['kappa_per_form'].items()))
        print('  utdrag (del med minst 50 % overlapp, der begge har gjeve utdrag):')
        for k, v in res['part_b']['excerpts'].items(): print(f"      {k:14s} " + ' | '.join(f"{a}: {pc(b['share_overlap'])} (n={b['n']})" for a, b in v.items()))
        for k, v in res['part_b']['theories'].items(): print(f"  teoriar {k}: Jaccard {f(v['jaccard'])} ({v['n_texts']} tekstar)")


# ---------- sjølvtest med syntetiske kodarar ----------
def synthetic(mal_a, mal_b, machine, labels, rate, seed, out_a, out_b):
    rng = random.Random(seed)
    noisy = lambda field, v: v if v is None or rng.random() >= rate else rng.choice([x for x in LISTS[field] if x != v])
    wb = openpyxl.load_workbook(mal_b); ws = wb['Påstandar']; col = {c.value: c.column for c in ws[1]}; alive = {}
    for r in range(2, ws.max_row + 1):
        item = ws.cell(row=r, column=col['item']).value; m = machine['items'].get(item)
        if not m: continue
        alive[item] = rng.random() >= rate / 2
        ws.cell(row=r, column=col['is_claim'], value='1' if alive[item] else '0')
        if not alive[item]: continue
        ws.cell(row=r, column=col['is_headline'], value='1' if rng.random() >= rate else '0')
        for f in FIELDS[2:]: ws.cell(row=r, column=col[f], value=noisy(f, m.get(f)))
        for f in EXC: ws.cell(row=r, column=col[f], value=m.get(f))
    def fill(sheet, key, write):
        ws = wb[sheet]; queue = {i: [x for x in machine['items'][i][key] if rng.random() >= rate / 2] for i in alive if alive[i]}
        for r in range(2, ws.max_row + 1):
            q = queue.get(ws.cell(row=r, column=1).value)
            if q: write(ws, r, q.pop(0))
    def w_con(ws, r, c):
        for j, v in enumerate([c['term'], noisy('role', c['role']), noisy('definition_status', c['definition_status']), c.get('definition_excerpt')], 3): ws.cell(row=r, column=j, value=v)
    def w_sup(ws, r, s):
        for j, v in enumerate([s['source'], s['form'], None, s.get('excerpt')], 3): ws.cell(row=r, column=j, value=v)
    fill('Omgrep', 'concepts', w_con); fill('Støtte', 'support', w_sup)
    ws = wb['Teoriar']; tq = {t: list(v) for t, v in machine['theories'].items()}
    for r in range(2, ws.max_row + 1):
        q = tq.get((ws.cell(row=r, column=1).value or '').split(' ')[0])
        if q:
            t = q.pop(0); ws.cell(row=r, column=2, value=t['name']); ws.cell(row=r, column=3, value=t['role'])
    wb.save(out_b)
    wa = openpyxl.load_workbook(mal_a); ws = wa['Påstandar']; r = 2; back = {v: k for k, v in labels.items()}
    for item, m in machine['items'].items():
        if text_of(item) in back and rng.random() >= rate:
            for j, v in enumerate([back[text_of(item)], m['pdf_page'], m['excerpt'], m['claim_location']], 1): ws.cell(row=r, column=j, value=v)
            r += 1
    wa.save(out_a)

def machine_a(machine, labels):
    claims = {t: [] for t in labels.values()}
    for item, m in machine['items'].items():
        if text_of(item) in claims: claims[text_of(item)].append(m['excerpt'])
    return claims

def selftest(args, machine, labels):
    tmp = pathlib.Path(tempfile.mkdtemp()); ok = True
    for rate, names in ((0.0, ('S1', 'S2')), (0.25, ('S3', 'S4'))):
        B, A = {MACHINE: machine}, {MACHINE: machine_a(machine, labels)}
        for k, n in enumerate(names):
            pa, pb = tmp / f'a-{n}.xlsx', tmp / f'b-{n}.xlsx'
            synthetic(args.mal_a, args.mal_b, machine, labels, rate, 100 + k + int(rate * 100), pa, pb)
            B[n] = load_b(pb); A[n] = load_a(pa, labels)
        res = analyse(B, A, draws=200)
        report(res, f'SJØLVTEST MED SYNTETISKE KODARAR, støy {rate:.2f} (ikkje verkelege kodarar)')
        if rate == 0:
            bad = [f for f, e in res['part_b']['fields'].items() for v in e['pairs'].values() if v['pct'] != 1.0]
            bad += [k for k, v in res['part_b']['concepts'].items() if v['jaccard'] != 1.0 or v['definition_status']['pct'] != 1.0]
            bad += [k for k, v in res['part_b']['support_forms'].items() if v['jaccard'] != 1.0]
            bad += [k for k, v in res['part_a'].items() if v['f1'] != 1.0]
            ok = not bad; print('\nUtan støy:', 'alle mål er 1, som dei skal vere.' if ok else f'FEIL i {bad}')
    return ok


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--maskin', required=True); ap.add_argument('--utval', required=True)
    ap.add_argument('--a', action='append', default=[], metavar='NAMN=FIL'); ap.add_argument('--b', action='append', default=[], metavar='NAMN=FIL')
    ap.add_argument('--ut'); ap.add_argument('--trekk', type=int, default=1000)
    ap.add_argument('--sjolvtest', action='store_true'); ap.add_argument('--mal-a'); ap.add_argument('--mal-b')
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    machine = load_machine(args.maskin); utval = json.load(open(args.utval, encoding='utf-8'))
    labels = {t['label']: t['text_id'] for t in utval['part_a']['texts']}
    keep = {i['item'] for i in utval['part_b']['items']}; machine['items'] = {k: v for k, v in machine['items'].items() if k in keep}
    if args.sjolvtest: sys.exit(0 if selftest(args, machine, labels) else 1)
    B = {MACHINE: machine}; A = {MACHINE: machine_a(machine, labels)}
    for s in args.b: n, p = s.split('=', 1); B[n] = load_b(p)
    for s in args.a: n, p = s.split('=', 1); A[n] = load_a(p, labels)
    res = analyse(B if len(B) > 1 else {}, A if len(A) > 1 else {}, draws=args.trekk)
    report(res, 'SAMSVAR')
    if args.ut: json.dump(res, open(args.ut, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

if __name__ == '__main__':
    main()
