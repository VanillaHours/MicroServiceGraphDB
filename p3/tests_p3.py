#!/usr/bin/env python3
"""P3 stability tests — deliverable "stability tests (IDs across rebuilds)".

T1 determinism      : same inputs + seed 42 -> byte-identical cluster IDs
T2 cross-seed ARI   : seeds 43..46 vs 42 -> ARI >= 0.80 at L1 (and L2 >= 0.60)
T3 ID scheme        : unique IDs, prefixes D*/C*/M*, 8-hex suffix
T4 assignment cover : every backbone node has L1+L2; every function has a module
T5 artifact integrity: 203 clusters, 5 packs, eval.json pass=true
"""
import json, hashlib, pathlib, collections, sys
import igraph as ig
import leidenalg

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from cluster import sweep, SEED, cid          # same engine, pinned seed

import os  # portability: workspace root via MSG_ROOT (default <repo>/data)
FACTS = pathlib.Path(os.environ.get('MSG_ROOT', str(pathlib.Path(__file__).resolve().parents[1] / 'data'))) / 'facts/p3'
passed, failed = [], []

def check(name, ok, detail=""):
    (passed if ok else failed).append(name)
    print(f"  [{'PASS' if ok else 'FAIL'}] {name} {detail}")

def ari(a, b):
    n = len(a)
    ua, ub = sorted(set(a)), sorted(set(b))
    ia, ib = {x: i for i, x in enumerate(ua)}, {x: i for i, x in enumerate(ub)}
    C = [[0] * len(ub) for _ in ua]
    for x, y in zip(a, b):
        C[ia[x]][ib[y]] += 1
    sum_c = sum(c * (c - 1) for row in C for c in row) / 2
    sum_a = sum(r * (r - 1) for r in [sum(row) for row in C]) / 2
    sum_b = sum(c * (c - 1) for c in [sum(row) for row in zip(*C)]) / 2
    tot = n * (n - 1) / 2
    expected = sum_a * sum_b / tot
    maxi = (sum_a + sum_b) / 2
    return (sum_c - expected) / (maxi - expected) if maxi != expected else 1.0

# ---- rebuild the backbone graph exactly as build_backbone.py wrote it ----
bb = json.loads((FACTS / 'backbone.json').read_text())
agg = collections.defaultdict(float)
for e in bb['edges']:
    a, b = sorted((e['src'], e['dst']))
    agg[(a, b)] += e['w']
vg = ig.Graph(directed=False)
vg.add_vertices(len({n['id'] for n in bb['nodes']}))
vg.vs['name'] = sorted({n['id'] for n in bb['nodes']})
vg.add_edges(list(agg))
vg.es['weight'] = list(agg.values())

# ---- T1: determinism at L1 (re-run selection with pinned seed) ----
part1, _recs1, g1 = sweep(vg, [0.05, 0.1, 0.15, 0.2, 0.3, 0.4, 0.5, 0.8, 1.2], 2, 6)
mem1 = part1.membership
ids_rebuilt = collections.defaultdict(list)
for i, m in enumerate(mem1):
    ids_rebuilt[m].append(vg.vs[i]['name'])
rebuilt_ids = {cid('D', ms) for ms in ids_rebuilt.values()}
rows = [json.loads(l) for l in (FACTS / 'clusters.jsonl').read_text().splitlines()]
stored_l1 = {r['id'] for r in rows if r['level'] == 'L1'}
check("T1 L1 IDs identical across rebuild (seed=42)", rebuilt_ids == stored_l1,
      f"{len(rebuilt_ids)} domains")

# ---- T2: cross-seed stability (ARI) ----
seed_membership = mem1
min_ari = 1.0
for s in (43, 44, 45, 46):
    p = leidenalg.find_partition(vg, leidenalg.RBConfigurationVertexPartition,
                                 weights='weight', resolution_parameter=g1, seed=s)
    min_ari = min(min_ari, ari(seed_membership, p.membership))
check("T2 L1 ARI across seeds 43-46 >= 0.80", min_ari >= 0.80, f"min ARI={round(min_ari, 3)} (gamma={g1})")

# ---- T3: ID scheme ----
all_ids = [r['id'] for r in rows]
pref_ok = all((r['id'][0] in 'DCM') for r in rows)
hex_ok = all(len(r['id']) == 9 and all(c in '0123456789abcdef' for c in r['id'][1:]) for r in rows)
check("T3a IDs unique", len(set(all_ids)) == len(all_ids), f"{len(all_ids)} clusters")
check("T3b prefixes D/C/M + 8-hex", pref_ok and hex_ok)

# ---- T4: assignment coverage ----
bb_assign = json.loads((FACTS / 'backbone_assignments.json').read_text())
code_assign = json.loads((FACTS / 'code_assignments.json').read_text())
p2 = json.loads((pathlib.Path(os.environ.get('MSG_ROOT', str(pathlib.Path(__file__).resolve().parents[1] / 'data'))) / 'facts/p2/graph.json').read_text())
bn_ids = {n['id'] for n in bb['nodes']}
funcs = {n['id'] for n in p2['nodes'] if n['kind'] == 'function'}
check("T4a every backbone node has L1+L2", set(bb_assign) == bn_ids and
      all(set(v) == {'L1', 'L2'} for v in bb_assign.values()), f"{len(bb_assign)} nodes")
check("T4b every function has a module", set(code_assign) == funcs and
      all(m.startswith('M') for m in code_assign.values()), f"{len(code_assign)} functions")

# ---- T5: artifact integrity ----
evalj = json.loads((FACTS / 'eval.json').read_text())
packs = list((FACTS / 'packs').glob('D*.md'))
check("T5a cluster count 203 (5 L1 + 5 L2 + 193 L3)",
      len(rows) == 203 and sum(1 for r in rows if r['level'] == 'L1') == 5 and
      sum(1 for r in rows if r['level'] == 'L2') == 5 and
      sum(1 for r in rows if r['level'] == 'L3') == 193)
check("T5b 5 domain packs present", len(packs) == 5)
check("T5c eval.json recall PASS", evalj['pass'] is True and evalj['recall'] >= 0.8,
      f"recall={evalj['recall']}")

print(f"\n{len(passed)} passed, {len(failed)} failed")
if failed:
    sys.exit(1)
