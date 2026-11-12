#!/usr/bin/env python3
"""P3.1 — Build the clustering backbone from P2 graph.json.

Backbone = semantic layer of the fused graph:
  svc:*  (5 daemon nodes)                    — functional units
  zapi:* messages wired to >=1 svc           — inter-service contract plane
  yang:* paths reachable via nb:implements   — northbound contract plane

Excluded (recorded in census): code:* (27,205 -> L3 per-service call graphs),
build:* tu (356 -> L3 TU attribution), floating yang nodes (models of daemons
outside the slice), 15 zapi msgs with no svc-level wiring.

Weights (design rule, POC-DESIGN "AMBIGUOUS 0.5x"):
  svc -handles->   zapi       2.0
  svc -publishes-> zapi       2.0
  svc -nb_implements-> yang   1.5   (registers+implements chain collapsed)
  yang -member_of-> yang      0.5   (tree cohesion, both endpoints reachable)
  evidence AMBIGUOUS-only     x0.5  (rule present; 0 fires on this slice)
  n_planes > 1                x1.5  (rule present; 0 fires on this slice)

Output: $MSG_ROOT/facts/p3/backbone.json  {meta, nodes, edges} + census on stdout.
"""
import json, collections, pathlib

import os  # portability: workspace root via MSG_ROOT (default <repo>/data)
_ROOT = pathlib.Path(os.environ.get('MSG_ROOT', str(pathlib.Path(__file__).resolve().parents[1] / 'data')))
P2 = _ROOT / 'facts/p2/graph.json'
OUT = _ROOT / 'facts/p3/backbone.json'

g = json.loads(P2.read_text())
nodes = {n['id']: n for n in g['nodes']}
edges = g['edges']
P = lambda x: x.split(':', 1)[0]

svc_nodes = [n['id'] for n in g['nodes'] if n['kind'] == 'daemon']
svc_of_func = {n['id']: n['service'] for n in g['nodes'] if n.get('service')}

# --- yang reachability via nb:implements (426 edges) ---
nb_owner = {}                       # nb id -> owning svc (from svc -registers-> nb)
for e in edges:
    if e['rel'] == 'registers':
        nb_owner[e['dst']] = e['src']
yang_reach, svc_impl = set(), collections.defaultdict(set)
for e in edges:
    if e['rel'] == 'implements' and e['dst'].startswith('yang:') and e['src'] in nb_owner:
        yang_reach.add(e['dst'])
        svc_impl[nb_owner[e['src']]].add(e['dst'])
ymods_reach = {y.split(':')[1] for y in yang_reach}

# --- zapi wiring ---
svc_zapi = collections.defaultdict(list)
for e in edges:
    if e['rel'] in ('handles', 'publishes') and e['src'].startswith('svc:') and e['dst'].startswith('zapi:'):
        svc_zapi[e['dst']].append(e)
zapi_reach = set(svc_zapi)

# --- assemble backbone nodes ---
bn, be = [], []
def add(nid, kind, label, service=None):
    bn.append({'id': nid, 'kind': kind, 'label': label, 'service': service})

for s in sorted(svc_nodes):
    add(s, 'svc', s.split(':', 1)[1], s)
for z in sorted(zapi_reach):
    add(z, 'zapi-msg', z.split(':', 1)[1])
for y in sorted(yang_reach):
    parts = y.split(':', 2)
    mod = parts[1] if len(parts) > 1 else ''
    path = parts[2] if len(parts) > 2 else ''
    add(y, 'yang-path', f'{mod}:{path}', mod)

def w(ev_evidence, n_planes, base):
    m = 1.0
    if ev_evidence and all(x.split(':', 1)[0] == 'AMBIGUOUS' for x in ev_evidence):
        m *= 0.5
    if n_planes and n_planes > 1:
        m *= 1.5
    return round(base * m, 3)

for z, es in sorted(svc_zapi.items()):
    for e in es:
        be.append({'src': e['src'], 'rel': e['rel'], 'dst': z,
                   'w': w(e['evidence'], e['n_planes'], 2.0),
                   'evidence': e['evidence'], 'n_planes': e['n_planes']})
# collapsed svc -nb_implements-> yang (registers x implements chain)
seen = set()
for s, ys in svc_impl.items():
    for y in ys:
        if (s, y) not in seen:
            seen.add((s, y))
            be.append({'src': s, 'rel': 'nb_implements', 'dst': y, 'w': 1.5,
                       'evidence': ['DECLARED:contract'], 'n_planes': 1})
# yang tree cohesion within reachable set
for e in edges:
    if e['rel'] == 'member_of' and e['src'] in yang_reach and e['dst'] in yang_reach:
        be.append({'src': e['src'], 'rel': 'member_of', 'dst': e['dst'], 'w': 0.5,
                   'evidence': e['evidence'], 'n_planes': e['n_planes']})

# --- census of exclusions ---
code_n = sum(1 for n in g['nodes'] if P(n['id']) == 'code')
build_n = sum(1 for n in g['nodes'] if P(n['id']) == 'build')
zapi_all = [n['id'] for n in g['nodes'] if n['kind'] == 'message']
zapi_unwired = sorted(set(zapi_all) - zapi_reach)
yang_all = [n['id'] for n in g['nodes'] if n['kind'] == 'yang-node']
yang_float = sorted(set(yang_all) - yang_reach)
ymods_float = sorted({y.split(':')[1] for y in yang_float} - ymods_reach)
# cross-service calls (L3 boundary facts)
cross_calls = collections.Counter()
for e in edges:
    if e['rel'] == 'calls':
        ss, sd = svc_of_func.get(e['src']), svc_of_func.get(e['dst'])
        if ss and sd and ss != sd:
            cross_calls[(ss, sd)] += 1
func_by_svc = collections.Counter(svc_of_func.values())

meta = {
    'phase': 'P3', 'step': 'backbone', 'source': str(P2),
    'p2_nodes': len(nodes), 'p2_edges': len(edges),
    'backbone_nodes': len(bn), 'backbone_edges': len(be),
    'svc': svc_nodes, 'zapi_wired': len(zapi_reach), 'yang_reachable': len(yang_reach),
    'yang_modules_reachable': sorted(ymods_reach),
    'excluded': {'code_nodes': code_n, 'build_nodes': build_n,
                 'zapi_unwired': zapi_unwired, 'yang_floating_modules': ymods_float,
                 'yang_floating_count': len(yang_float)},
    'cross_service_calls': {f'{a}->{b}': c for (a, b), c in sorted(cross_calls.items())},
    'functions_by_service': dict(func_by_svc),
    'weights': {'handles': 2.0, 'publishes': 2.0, 'nb_implements': 1.5,
                'member_of': 0.5, 'ambiguous_only_x0.5': True, 'n_planes_gt1_x1.5': True},
}
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps({'meta': meta, 'nodes': bn, 'edges': be}, indent=1))

print(f"backbone: {len(bn)} nodes / {len(be)} edges  -> {OUT}")
print(f"  svc {len(svc_nodes)} | zapi wired {len(zapi_reach)} (unwired {len(zapi_unwired)}) | "
      f"yang reachable {len(yang_reach)} in {len(ymods_reach)} modules (floating {len(yang_float)})")
print(f"  edges: handles/publishes {sum(1 for e in be if e['rel'] in ('handles','publishes'))}, "
      f"nb_implements {sum(1 for e in be if e['rel']=='nb_implements')}, "
      f"member_of {sum(1 for e in be if e['rel']=='member_of')}")
print(f"  excluded: code {code_n}, build {build_n}; floating yang modules: {ymods_float}")
print(f"  cross-service calls (L3 boundary facts): {dict(cross_calls)}")
print(f"  functions per service: {dict(func_by_svc)}")
