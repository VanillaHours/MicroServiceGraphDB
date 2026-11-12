#!/usr/bin/env python3
"""P3.3 + P3.4 — Cluster profiles and graph-RAG context packs (no LLM).

Every statement is derived from graph facts (P2 fused graph + P3 cluster
assignments). Role/functionality tags are rule-based (structure + naming).
Outputs ($MSG_ROOT/facts/p3/):
  profiles.jsonl   one rich record per cluster (L1/L2/L3)
  packs/<id>.md    human-readable context pack per L1 domain
  packs/<id>.json  machine-readable pack (same facts) per L1 domain
  packs/index.md   global index for the router (P5)
"""
import json, collections, pathlib

import os  # portability: workspace root via MSG_ROOT (default <repo>/data)
FACTS = pathlib.Path(os.environ.get('MSG_ROOT', str(pathlib.Path(__file__).resolve().parents[1] / 'data'))) / 'facts'
P2G = FACTS / 'p2/graph.json'
P2F = FACTS / 'p2/findings.json'

p2 = json.loads(P2G.read_text())
findings = json.loads(P2F.read_text())
rows = [json.loads(l) for l in (FACTS / 'clusters.jsonl').read_text().splitlines()]
bb_assign = json.loads((FACTS / 'backbone_assignments.json').read_text())
code_assign = json.loads((FACTS / 'code_assignments.json').read_text())
bb_nodes = {n['id']: n for n in json.loads((FACTS / 'backbone.json').read_text())['nodes']}
bb_edges = json.loads((FACTS / 'backbone.json').read_text())['edges']
svc_of_func = {n['id']: n['service'] for n in p2['nodes'] if n.get('service')}

cl = {r['id']: r for r in rows}
children = collections.defaultdict(list)
for r in rows:
    if r['parent']:
        children[r['parent']].append(r['id'])

# ---- code-plane facts from P2 graph ----
code_handles, code_publishes = collections.defaultdict(set), collections.defaultdict(set)
cross_calls = collections.Counter()          # (src_mod, dst_mod) -> calls
cross_calls_svc = collections.Counter()
callsites_by_src_mod = collections.defaultdict(collections.Counter)
for e in p2['edges']:
    if e['rel'] == 'handles' and e['src'].startswith('code:'):
        code_handles[e['src']].add(e['dst'])
    if e['rel'] == 'publishes' and e['src'].startswith('code:'):
        code_publishes[e['src']].add(e['dst'])
    if e['rel'] == 'calls':
        s, dsv = svc_of_func.get(e['src']), svc_of_func.get(e['dst'])
        if s and dsv and s != dsv:
            ms, md = code_assign.get(e['src']), code_assign.get(e['dst'])
            if ms and md:
                cross_calls[(ms, md)] += 1
                callsites_by_src_mod[ms][md] += 1
            cross_calls_svc[(s, dsv)] += 1

# svc-level contract edges (backbone)
svc_handle_msgs, svc_publish_msgs = collections.defaultdict(set), collections.defaultdict(set)
for e in bb_edges:
    if e['rel'] == 'handles' and e['src'].startswith('svc:'):
        svc_handle_msgs[e['src']].add(e['dst'])
    if e['rel'] == 'publishes' and e['src'].startswith('svc:'):
        svc_publish_msgs[e['src']].add(e['dst'])

# findings -> entities
f_dropped = findings['zapi']['dropped_on_wire']
f_orphan = findings['zapi']['orphan_handlers_no_sender_in_slice']
f_dead = findings['dead_wiring']['registrations_without_callbacks']
f_flows = findings['zapi']['cross_svc_flows']

ROLE_RULES = [
    ('nb-owner',      lambda s: sum(1 for e in bb_edges if e['rel'] == 'registers' and e['src'] == s) >= 20),
    ('shared-infra',  lambda s: s == 'svc:lib'),
    ('forwarding-mgr', lambda s: s == 'svc:fpm'),
]
# zapi-server: its handled messages are published by >=2 OTHER route daemons
# (message bus); lib is excluded — its publishes are wrapper-mediated (zclient
# send helpers live in lib/zclient.c).
pub_by = collections.defaultdict(set)      # zapi msg -> {publisher svc}
for e in bb_edges:
    if e['rel'] == 'publishes' and e['src'].startswith('svc:'):
        pub_by[e['dst']].add(e['src'])

def is_zapi_server(s):
    pubs = set()
    for m in svc_handle_msgs.get(s, set()):
        pubs |= {p for p in pub_by.get(m, set()) if p not in (s, 'svc:lib')}
    return len(pubs) >= 2

def svc_roles(s):
    tags = [t for t, f in ROLE_RULES if f(s)]
    if is_zapi_server(s):
        tags.append('zapi-server')
    elif svc_handle_msgs.get(s):
        tags.append('zapi-client')
    if svc_publish_msgs.get(s):
        tags.append('zapi-publisher')
    return tags
MOD_TAG_RULES = [
    ('northbound', ('nb_', 'nb_cb', '_nb')), ('zapi-client', ('zclient_', 'zsend', 'zrecv', 'zserv_')),
    ('cli', ('vty_', 'cli_', 'defun')), ('logging', ('zlog',)),
    ('event-loop', ('thread_', 'event_', 'frr_pthread')),
    ('memory', ('qmalloc', 'qfree', 'qcalloc', 'qstr', 'xmembar')),
    ('rbtree', ('rb_', 'typed_rb')), ('yang', ('yang_', 'lyd_')),
]

# file attribution from the pre-fusion fact store (fused graph drops src_ref)
import duckdb
_con = duckdb.connect(str(FACTS / 'p2/facts.duckdb'), read_only=True)
ffile_db = collections.defaultdict(collections.Counter)
for _src, _ref in _con.sql("select src, src_ref from edges where src_ref is not null").fetchall():
    if _ref and '/' in _ref:
        ffile_db[_src][_ref.split(':')[0]] += 1
_con.close()

def enrich_anchor(a):
    if a.get('file'):
        return a
    f = ffile_db.get(a['id'])
    return {'id': a['id'], 'file': f.most_common(1)[0][0] if f else None}

def mod_tags(members):
    tags = set()
    for m in members:
        low = m.lower()
        for t, pats in MOD_TAG_RULES:
            if any(low.startswith(p) or '::' + p in low for p in pats):
                tags.add(t)
    return sorted(tags)

def module_zapi(module_id):
    msgs = set()
    for f, mod in code_assign.items():
        if mod != module_id:
            continue
        msgs |= code_handles.get(f, set()) | code_publishes.get(f, set())
    return sorted(msgs)

def anchor_files(r):
    return [a for a in r.get('anchors', []) if a.get('file')]

# NB table counts from the pre-fusion fact store (registers edges are collapsed
# into nb_implements in the backbone, so count them on the P2 graph)
nb_of_svc = collections.Counter()
for e in p2['edges']:
    if e['rel'] == 'registers' and e['src'].startswith('svc:'):
        nb_of_svc[e['src']] += 1

# ---------- build profiles ----------
profiles = []
for r in rows:
    lvl = r['level']
    prof = {'id': r['id'], 'level': lvl, 'parent': r['parent'], 'label': r['label'],
            'size': r['size'], 'gamma': r.get('gamma')}
    if lvl == 'L3':
        members_ids = None
        prof['service'] = r['service']
        prof['anchors'] = [enrich_anchor(a) for a in r.get('anchors', [])]
        prof['tags'] = mod_tags([a['id'].split('::', 1)[1] for a in r.get('anchors', [])])
        prof['zapi_msgs_touched'] = module_zapi(r['id'])
        out_calls = [(d, c) for (s, d), c in cross_calls.items() if s == r['id']]
        prof['calls_into_other_svcs'] = sorted(
            ((d, c) for (s, d), c in cross_calls.items() if s == r['id']), key=lambda x: -x[1])[:6]
        prof['called_from_other_svcs'] = sorted(
            ((s, c) for (s, d), c in cross_calls.items() if d == r['id']), key=lambda x: -x[1])[:6]
        if r.get('note'):
            prof['note'] = r['note']
        profiles.append(prof)
        continue
    members = r['members']
    svcs = [m for m in members if m.startswith('svc:')]
    zapi_m = [m for m in members if m.startswith('zapi:')]
    yang_m = [m for m in members if m.startswith('yang:')]
    ymods = collections.Counter(m.split(':')[1] for m in yang_m)
    prof['services'] = svcs
    prof['roles'] = sorted({t for s in svcs for t in svc_roles(s)})
    prof['yang_modules'] = dict(ymods)
    prof['zapi_msgs'] = sorted(zapi_m)
    prof['nb_tables'] = sum(nb_of_svc[s] for s in svcs)
    # boundary: backbone edges leaving this cluster (same level)
    key = 'L1' if lvl == 'L1' else 'L2'
    boundary = collections.Counter()
    for e in bb_edges:
        a, b = e['src'], e['dst']
        ka, kb = bb_assign.get(a), bb_assign.get(b)
        if not ka or not kb:
            continue
        if ka[key] == r['id'] and kb[key] != r['id']:
            boundary[(kb[key], e['rel'])] += 1
        if kb[key] == r['id'] and ka[key] != r['id']:
            boundary[(ka[key], e['rel'])] += 1
    prof['boundary_edges'] = []
    by_to = collections.defaultdict(collections.Counter)
    for (to, rel), c in boundary.items():
        by_to[to][rel] += c
    prof['boundary_edges'] = [{'to': t, 'rels': dict(rc)} for t, rc in
                              sorted(by_to.items(), key=lambda x: -sum(x[1].values()))[:8]]
    prof['children'] = children.get(r['id'], [])
    # findings attached
    mset = set(members)
    prof['findings'] = {
        'dropped_on_wire': [m for m in f_dropped if m in mset],
        'orphan_handlers': [m for m in f_orphan if m in mset],
        'dead_wiring': [d for d in f_dead if d['nb'] in mset or d['svc'] in svcs],
        'cross_svc_flows': [f for f in f_flows
                            if f['msg'] in mset and (f['from'] in svcs or f['to'] in svcs)],
    }
    # derived functionality statements (templated facts)
    stmts = []
    for s in svcs:
        h, p = sorted(svc_handle_msgs.get(s, set())), sorted(svc_publish_msgs.get(s, set()))
        name = s.split(':')[1]
        client_pubs = set()
        for m in h:
            client_pubs |= {x for x in pub_by.get(m, set()) if x not in (s, 'svc:lib')}
        if s == 'svc:lib':
            stmts.append(f"lib is shared infrastructure: owns the northbound/YANG config models "
                         f"({', '.join(list(ymods)[:5])}{'...' if len(ymods) > 5 else ''}), "
                         f"registers {nb_of_svc[s]} NB callback tables, and hosts the zclient "
                         f"send wrappers ({len(p)} publish sites attributed to the wrapper layer)")
        elif 'zapi-server' in prof['roles']:
            stmts.append(f"{name} is the ZAPI message bus: handles {len(h)} message types published "
                         f"by the route daemons ({', '.join(sorted(x.split(':')[1] for x in client_pubs))}) "
                         f"and publishes {len(p)} notification/event types back to clients")
        elif p:
            stmts.append(f"{name} is a route client: publishes {len(p)} message types toward the ZAPI "
                         f"bus ({', '.join(z.split(':')[1].split('_', 2)[-1].lower() for z in p[:4])}"
                         f"{'...' if len(p) > 4 else ''}) and handles {len(h)} notifications from it")
        else:
            stmts.append(f"{name} is a config/route client: handles {len(h)} notification types from the "
                         f"ZAPI bus ({', '.join(z.split(':')[1].split('_', 2)[-1].lower() for z in h[:4])}"
                         f"{'...' if len(h) > 4 else ''}); its route sends go through lib zclient wrappers")
    if yang_m:
        n = len(ymods)
        stmts.append(f"northbound contracts: {len(yang_m)} YANG paths across {n} "
                     f"{'module' if n == 1 else 'modules'} "
                     f"({', '.join(f'{k}({v})' for k, v in ymods.most_common(4))})")
    prof['functionality'] = stmts
    profiles.append(prof)

# code-module rollup per L1 domain for packs
l1_domains = [r for r in rows if r['level'] == 'L1']
for d in l1_domains:
    d['_modules'] = sorted([r for r in rows if r['level'] == 'L3' and r.get('service') in d['members']],
                           key=lambda r: -r['size'])

(FACTS / 'profiles.jsonl').write_text("\n".join(json.dumps(x) for x in profiles) + "\n")
prof_by_id = {p['id']: p for p in profiles}

# ---------- packs ----------
PACKS = FACTS / 'packs'
PACKS.mkdir(exist_ok=True)
index_lines = ["# Cluster pack index (P3, seed=42)", "",
               "| Domain | Label | Services | Modules | ZAPI msgs | YANG paths |", "|---|---|---|---|---|---|"]

for d in l1_domains:
    did = d['id']
    pd = prof_by_id[did]
    mods = d['_modules']
    pack_json = {'id': did, 'label': d['label'], 'level': 'L1',
                 'services': [m for m in d['members'] if m.startswith('svc:')] if isinstance(d['members'], list) else [],
                 'functionality': pd['functionality'], 'roles': pd['roles'],
                 'yang_modules': pd['yang_modules'], 'zapi_msgs': pd['zapi_msgs'],
                 'boundary_edges': pd['boundary_edges'], 'children': children.get(did, []),
                 'findings': pd['findings'],
                 'modules': [{'id': m['id'], 'label': m['label'], 'size': m['size'],
                              'anchors': [enrich_anchor(a) for a in m['anchors']], 'tags': m.get('tags', []),
                              'note': m.get('note'),
                              'zapi_msgs_touched': m.get('zapi_msgs_touched', [])[:12]}
                             for m in mods]}
    (PACKS / f'{did}.json').write_text(json.dumps(pack_json, indent=1))

    md = [f"# Domain pack `{did}` — {d['label']}", "",
          f"Level L1 (functional domain) · gamma {d.get('gamma')} · seed 42 · Leiden RBConfiguration",
          ""]
    md += ["## Functionality (rule-derived from graph facts)", ""]
    md += [f"- {s}" for s in pd['functionality']] or ["- (no service members)"]
    md += ["", f"Role tags: {', '.join(pd['roles']) or '-'}",
           f"Members: {d['size']} backbone nodes — "
           f"{sum(1 for m in d['members'] if m.startswith('svc:'))} svc, "
           f"{sum(1 for m in d['members'] if m.startswith('zapi:'))} zapi, "
           f"{sum(1 for m in d['members'] if m.startswith('yang:'))} yang", ""]
    if pd['zapi_msgs']:
        md += ["## ZAPI contract", ""]
        for s in [m for m in d['members'] if m.startswith('svc:')]:
            h = [z for z in pd['zapi_msgs'] if z in svc_handle_msgs.get(s, set())]
            p = [z for z in pd['zapi_msgs'] if z in svc_publish_msgs.get(s, set())]
            if h: md.append(f"- `{s}` handles {len(h)}: {', '.join('`' + z.split(':')[1] + '`' for z in h[:12])}{' ...' if len(h) > 12 else ''}")
            if p: md.append(f"- `{s}` publishes {len(p)}: {', '.join('`' + z.split(':')[1] + '`' for z in p[:12])}{' ...' if len(p) > 12 else ''}")
        md.append("")
    if pd['yang_modules']:
        md += ["## Northbound (YANG) contracts", ""]
        md += [f"- {k}: {v} paths" for k, v in sorted(pd['yang_modules'].items(), key=lambda x: -x[1])]
        md.append("")
    if pd['boundary_edges']:
        md += ["## Boundary (edges to other domains)", ""]
        md += [f"- -> `{b['to']}` ({cl.get(b['to'], {}).get('label', '?')}): " +
               ", ".join(f"{k}×{v}" for k, v in b['rels'].items())
               for b in pd['boundary_edges']]
        md.append("")
    flows = pd['findings']['cross_svc_flows']
    if flows:
        md += ["## Cross-service ZAPI flows in this domain", ""]
        seen = set()
        for f in flows:
            k = (f['from'], f['to'])
            seen.add(k)
        md.append(f"- {len(flows)} flows: " +
                  ", ".join(f"`{a.split(':')[1]}→{b.split(':')[1]}`" for a, b in sorted(seen)))
        md.append("")
    md += ["## Code modules (L3)", "",
           "| Module | Size | Tags | Top anchors (file) |", "|---|---|---|---|"]
    for m in mods:
        pm = prof_by_id.get(m['id'], {})
        anc = "; ".join(f"`{a['id'].split('::')[1]}` ({a['file']})" for a in pm.get('anchors', [])[:3]) \
              or (m.get('note') or '-')
        md.append(f"| `{m['id']}` {m['label']} | {m['size']} | {','.join(pm.get('tags', [])) or '-'} | {anc} |")
    md.append("")
    fn = pd['findings']
    if any(fn.values()):
        md += ["## Findings attached", ""]
        if fn['dropped_on_wire']:
            md.append(f"- dropped-on-wire msgs: {', '.join('`' + z.split(':')[1] + '`' for z in fn['dropped_on_wire'])}")
        if fn['orphan_handlers']:
            md.append(f"- orphan handlers (sender not in slice): {len(fn['orphan_handlers'])} msgs")
        if fn['dead_wiring']:
            md.append(f"- dead NB registrations: {len(fn['dead_wiring'])}")
        md.append("")
    dsvcs = [m.split(':')[1] for m in d['members'] if m.startswith('svc:')]
    hint_svc = dsvcs[0] if dsvcs else 'bgpd'
    md += ["## Query hints", "",
           "```",
           f"python3 kb.py cluster show {did}",
           f"python3 kb.py path svc:{hint_svc} svc:zebra   # cross-domain ZAPI path",
           "python3 kb.py impact yang:<module>:<path>",
           "```", ""]
    (PACKS / f'{did}.md').write_text("\n".join(md))
    index_lines.append(f"| `{did}` | {d['label']} | {', '.join(s.split(':')[1] for s in pack_json['services'])} | "
                       f"{len(mods)} | {len(pd['zapi_msgs'])} | {sum(pd['yang_modules'].values())} |")

index_lines += ["", "Machine-readable packs: `packs/<domain-id>.json`; profiles for all levels: `profiles.jsonl`."]
(PACKS / 'index.md').write_text("\n".join(index_lines) + "\n")

print(f"profiles: {len(profiles)} ({sum(1 for p in profiles if p['level']=='L1')} L1, "
      f"{sum(1 for p in profiles if p['level']=='L2')} L2, "
      f"{sum(1 for p in profiles if p['level']=='L3')} L3)")
print(f"packs: {len(l1_domains)} domain packs -> {PACKS}")
sample = next(p for p in profiles if p['level'] == 'L1' and 'bgpd' in p['label'])
print("bgpd domain functionality:", *sample['functionality'], sep="\n  ")
