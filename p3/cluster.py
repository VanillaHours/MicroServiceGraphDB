#!/usr/bin/env python3
"""P3.2 — Hierarchical Leiden clustering (no LLM in the loop).

Level tree:
  L1 "functional domains"      backbone graph (svc + zapi + yang), gamma sweep
  L2 "service/contract areas"  induced per-domain subgraph, component-aware:
                               components >=6 nodes -> Leiden, smaller -> own area
  L3 "code modules"            per-service intra-call graph, component-aware:
                               components >=10 funcs -> Leiden, 4..9 -> own module,
                               <4 -> per-service misc bucket; funcs with no
                               intra-service call edges -> per-service unlinked bucket

Determinism: seed=42 pinned at every find_partition call.
Stable IDs:  <prefix><blake2b-8hex of sorted member ids> — identical across
             rebuilds (asserted by tests_p3.py).
Selection:   gamma sweep -> prefer k in range with blob guard (max_frac<=0.6)
             -> k in range -> fewest k>=2; ties break to lower gamma.

Outputs ($MSG_ROOT/facts/p3/):
  backbone_assignments.json  {node: {L1: id, L2: id}}
  code_assignments.json      {func_id: module_id}
  clusters.jsonl             one row per cluster (all levels)
  sweep.json                 gamma sweep records per level
"""
import json, hashlib, collections, pathlib
import igraph as ig
import leidenalg

import os  # portability: workspace root via MSG_ROOT (default <repo>/data)
_ROOT = pathlib.Path(os.environ.get('MSG_ROOT', str(pathlib.Path(__file__).resolve().parents[1] / 'data')))
FACTS = _ROOT / 'facts/p3'
P2G = _ROOT / 'facts/p2/graph.json'
SEED = 42

def cid(prefix, members):
    h = hashlib.blake2b("\n".join(sorted(members)).encode(), digest_size=4).hexdigest()[:8]
    return f"{prefix}{h}"

def label_l1(members_info):
    svcs = [m['label'] for m in members_info if m['kind'] == 'svc']
    nz = sum(1 for m in members_info if m['kind'] == 'zapi-msg')
    ny = sum(1 for m in members_info if m['kind'] == 'yang-path')
    ymods = collections.Counter(m['service'] for m in members_info if m['kind'] == 'yang-path')
    top_mod = ymods.most_common(1)[0][0] if ymods else '-'
    base = '+'.join(svcs) if svcs else f'yang:{top_mod}'
    return f"{base} [{nz}z/{ny}y]"

def label_l2(members_info):
    svcs = [m['label'] for m in members_info if m['kind'] == 'svc']
    ymods = collections.Counter(m['service'] for m in members_info if m['kind'] == 'yang-path')
    zpre = collections.Counter(m['label'].split('_')[0] for m in members_info if m['kind'] == 'zapi-msg')
    bits = []
    if svcs: bits.append('+'.join(svcs))
    if ymods: bits.append(ymods.most_common(1)[0][0])
    if zpre and not ymods: bits.append(f"zapi:{zpre.most_common(1)[0][0]}*")
    return ':'.join(bits) if bits else 'area'

def label_l3(svc, names, anchor_names=None):
    """Label from top-anchor name prefixes (fallback: member token histogram)."""
    src = anchor_names or names
    toks = collections.Counter()
    for n in src:
        parts = n.split('_')
        if parts and parts[0]: toks[parts[0].lower()] += 2
        if len(parts) > 1 and parts[1]: toks[parts[1].lower()] += 1
    lbl = toks.most_common(1)[0][0] if toks else 'core'
    if not anchor_names:  # member-histogram mode: require frequency
        big = [t for t, c in toks.most_common() if c >= max(3, len(src) // 10) * 2]
        lbl = big[0] if big else lbl
    return f"{svc.split(':', 1)[1]}:{lbl}"

def sweep(g, gammas, lo, hi, blob=0.6):
    """Gamma sweep; deterministic selection. Returns (partition, records, chosen)."""
    recs = []
    for gamma in gammas:
        part = leidenalg.find_partition(
            g, leidenalg.RBConfigurationVertexPartition,
            weights='weight', resolution_parameter=gamma, seed=SEED)
        mem = part.membership
        k = max(mem) + 1
        sizes = collections.Counter(mem)
        recs.append({'gamma': gamma, 'n_clusters': k,
                     'modularity': round(g.modularity(mem, weights='weight'), 4),
                     'max_frac': round(max(sizes.values()) / len(mem), 3),
                     'sizes': sorted(sizes.values(), reverse=True)})
    key = lambda r: (r['modularity'], -r['gamma'])
    ok_blob = [r for r in recs if lo <= r['n_clusters'] <= hi and r['max_frac'] <= blob]
    ok = [r for r in recs if lo <= r['n_clusters'] <= hi]
    pool = ok_blob or ok or sorted([r for r in recs if r['n_clusters'] >= 2],
                                   key=lambda r: (r['n_clusters'], -r['modularity']))[:1]
    chosen = max(pool, key=key)['gamma']
    part = leidenalg.find_partition(
        g, leidenalg.RBConfigurationVertexPartition,
        weights='weight', resolution_parameter=chosen, seed=SEED)
    return part, recs, chosen

def sweep_class(g, comp_size):
    """Size-classed resolution: bigger components get finer gamma windows.
    Returns (partition, records, chosen)."""
    if comp_size >= 500:
        gammas, lo, hi, blob = [0.8, 1.0, 1.5, 2.0, 3.0], 6, 24, 0.5
    elif comp_size >= 100:
        gammas, lo, hi, blob = [0.4, 0.8, 1.5], 2, 12, 0.6
    else:
        gammas, lo, hi, blob = [0.05, 0.2, 0.5], 1, 8, 0.7
    return sweep(g, gammas, lo, hi, blob)

def main():
    bb = json.loads((FACTS / 'backbone.json').read_text())
    agg = collections.defaultdict(float)
    for e in bb['edges']:
        a, b = sorted((e['src'], e['dst']))
        agg[(a, b)] += e['w']
    nmap = {n['id']: n for n in bb['nodes']}
    vg = ig.Graph(directed=False)
    vg.add_vertices(len(nmap))
    vg.vs['name'] = list(nmap)
    vg.vs['kind'] = [nmap[i]['kind'] for i in vg.vs['name']]
    vg.vs['label'] = [nmap[i]['label'] for i in vg.vs['name']]
    vg.vs['service'] = [nmap[i].get('service') for i in vg.vs['name']]
    vg.add_edges(list(agg))
    vg.es['weight'] = list(agg.values())

    rows, sweeps = [], {}

    # ---------------- L1 ----------------
    p1, rec1, gamma1 = sweep(vg, [0.05, 0.1, 0.15, 0.2, 0.3, 0.4, 0.5, 0.8, 1.2], 2, 6)
    sweeps['L1'] = {'chosen_gamma': gamma1, 'records': rec1}
    g1 = collections.defaultdict(list)
    for i, m in enumerate(p1.membership):
        g1[m].append(i)
    print(f"L1: {len(g1)} domains (gamma={gamma1}); candidates {[(r['gamma'], r['n_clusters']) for r in rec1]}")

    for m, idxs in sorted(g1.items(), key=lambda kv: min(kv[1])):
        members = [vg.vs[i]['name'] for i in idxs]
        did = cid('D', members)
        mi = [{'kind': vg.vs[i]['kind'], 'label': vg.vs[i]['label'],
               'service': vg.vs[i]['service']} for i in idxs]
        rows.append({'id': did, 'level': 'L1', 'parent': None, 'gamma': gamma1,
                     'label': label_l1(mi), 'size': len(idxs),
                     'kind_hist': dict(collections.Counter(x['kind'] for x in mi)),
                     'members': members})

    # ---------------- L2 ----------------
    # Global multi-resolution refinement on the full backbone (induced-domain
    # refinement is vacuous here: each domain is a star around its service).
    # Areas may span domains (e.g. shared route-map models); parent = majority
    # L1 domain, containment ratio reported.
    p2r, rec2, gamma2 = sweep(vg, [1.5, 2.0, 2.5, 3.0, 4.0, 6.0, 8.0], 4, 20, blob=0.45)
    sweeps['L2'] = {'mode': 'global', 'chosen_gamma': gamma2, 'records': rec2}
    g2 = collections.defaultdict(list)
    for i, m in enumerate(p2r.membership):
        g2[m].append(i)
    print(f"L2: {len(g2)} areas (global gamma={gamma2}); candidates {[(r['gamma'], r['n_clusters'], round(r['modularity'],3)) for r in rec2]}")
    l1_of = {}
    for did, r in ((r['id'], r) for r in rows if r['level'] == 'L1'):
        for nid in r['members']:
            l1_of[nid] = did
    bb_assign = {}
    for m, idxs in sorted(g2.items(), key=lambda kv: min(kv[1])):
        members = [vg.vs[i]['name'] for i in idxs]
        aid = cid('C', members)
        mi = [{'kind': vg.vs[i]['kind'], 'label': vg.vs[i]['label'],
               'service': vg.vs[i]['service']} for i in idxs]
        parent_hist = collections.Counter(l1_of[nid] for nid in members)
        parent, containment = parent_hist.most_common(1)[0]
        rows.append({'id': aid, 'level': 'L2', 'parent': parent,
                     'containment': round(containment / len(members), 3),
                     'label': label_l2(mi), 'size': len(members),
                     'kind_hist': dict(collections.Counter(x['kind'] for x in mi)),
                     'members': members})
        for nid in members:
            bb_assign[nid] = {'L1': l1_of[nid], 'L2': aid}
    # merge singleton/tiny L2 areas into the largest sibling of the same parent
    by_parent = collections.defaultdict(list)
    for r in [x for x in rows if x['level'] == 'L2']:
        by_parent[r['parent']].append(r)
    for parent, areas in by_parent.items():
        if len(areas) > 1:
            areas.sort(key=lambda r: -r['size'])
            big = areas[0]
            for r in areas[1:]:
                if r['size'] <= 2:
                    big['members'].extend(r['members'])
                    big['size'] = len(big['members'])
                    big.setdefault('merged', []).append(r['id'])
                    rows.remove(r)
                    for nid in r['members']:
                        bb_assign[nid]['L2'] = big['id']

    # ---------------- L3 ----------------
    p2 = json.loads(P2G.read_text())
    svc_of = {n['id']: n.get('service') for n in p2['nodes'] if n['kind'] == 'function'}
    fids_by_svc = collections.defaultdict(list)
    for fid, s in svc_of.items():
        fids_by_svc[s].append(fid)
    ffile = collections.defaultdict(collections.Counter)
    for e in p2['edges']:
        if e['rel'] == 'calls' and e.get('src_ref') and '/' in e['src_ref']:
            ffile[e['src']][e['src_ref'].split(':')[0]] += 1

    code_assign = {}
    for s in sorted(fids_by_svc):
        fids = sorted(set(fids_by_svc[s]))
        intra = collections.defaultdict(set)
        for e in p2['edges']:
            if e['rel'] == 'calls' and svc_of.get(e['src']) == s and svc_of.get(e['dst']) == s:
                intra[e['src']].add(e['dst']); intra[e['dst']].add(e['src'])
        linked = sorted({f for f in fids if intra[f]})
        unlinked = sorted(set(fids) - set(linked))
        if unlinked:
            uid = cid('M', unlinked)
            code_assign.update({f: uid for f in unlinked})
            rows.append({'id': uid, 'level': 'L3', 'parent': s,
                         'label': f"{s.split(':', 1)[1]}:unlinked", 'size': len(unlinked),
                         'service': s, 'anchors': [], 'members': None,
                         'note': 'no intra-service call edges observed'})
        # call graph over linked nodes
        idx = {f: i for i, f in enumerate(linked)}
        ug = ig.Graph(directed=False)
        ug.add_vertices(len(linked))
        ug.vs['name'] = linked
        ed = [(idx[e['src']], idx[e['dst']]) for e in p2['edges']
              if e['rel'] == 'calls' and e['src'] in idx and e['dst'] in idx]
        ug.add_edges(ed)
        ug.es['weight'] = [1.0] * ug.ecount()
        ug.simplify(combine_edges={'weight': 'sum'})
        # component-aware modules: >=10 leiden, 4..9 own module, <4 misc bucket
        big, mid, misc = [], [], []
        for comp in ug.connected_components():
            members_c = [ug.vs[i]['name'] for i in comp]
            n = len(comp)
            if n >= 10: big.append(members_c)
            elif n >= 4: mid.append(members_c)
            else: misc.append(members_c)
        misc_members = sorted(f for c in misc for f in c)
        final_mods = list(mid)
        for comp in big:
            idxc = {f: i for i, f in enumerate(comp)}
            cg = ig.Graph(directed=False)
            cg.add_vertices(len(comp))
            cg.vs['name'] = comp
            ced = [(idxc[e['src']], idxc[e['dst']]) for e in p2['edges']
                   if e['rel'] == 'calls' and e['src'] in idxc and e['dst'] in idxc]
            cg.add_edges(ced)
            cg.es['weight'] = [1.0] * cg.ecount()
            cg.simplify(combine_edges={'weight': 'sum'})
            part, recs, gamma = sweep_class(cg, len(comp))
            sweeps.setdefault('L3', []).append(
                {'service': s, 'component': len(comp), 'chosen_gamma': gamma, 'records': recs})
            mem = part.membership
            grp = collections.defaultdict(list)
            for i, m in enumerate(mem):
                grp[m].append(cg.vs[i]['name'])
            final_mods.extend(sorted(grp.values(), key=lambda v: min(v)))
        if misc_members:
            final_mods.append(misc_members)
        # within-module degree for anchors
        inmod = {}
        for ms in final_mods:
            for f in ms:
                inmod[f] = id(ms)
        mdeg = collections.Counter()
        for e in p2['edges']:
            if (e['rel'] == 'calls' and svc_of.get(e['src']) == s and svc_of.get(e['dst']) == s
                    and e['src'] in inmod and inmod[e['src']] == inmod.get(e['dst'])):
                mdeg[e['src']] += 1; mdeg[e['dst']] += 1
        print(f"  L3 {s}: {len(final_mods)} modules "
              f"(funcs {len(fids)}, linked {len(linked)}, unlinked {len(unlinked)})")
        for ms in final_mods:
            ms = sorted(set(ms))
            mid = cid('M', ms)
            code_assign.update({f: mid for f in ms})
            names = [n.split('::', 1)[1] for n in ms]
            anchors = sorted(ms, key=lambda f: (-mdeg[f], f))[:8]
            note = ('misc (<4-func call fragments)' if ms == misc_members else
                    ('no intra-service call edges observed' if ms == unlinked else None))
            an = [n.split('::', 1)[1] for n in anchors]
            rows.append({'id': mid, 'level': 'L3', 'parent': s,
                         'label': label_l3(s, names, an), 'size': len(ms), 'service': s,
                         'anchors': [{'id': a, 'file': ffile[a].most_common(1)[0][0] if ffile[a] else None}
                                     for a in anchors],
                         'members': None, **({'note': note} if note else {})})
    # ---------------- write ----------------
    (FACTS / 'backbone_assignments.json').write_text(json.dumps(bb_assign, indent=0))
    (FACTS / 'code_assignments.json').write_text(json.dumps(code_assign, indent=0))
    with (FACTS / 'clusters.jsonl').open('w') as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    (FACTS / 'sweep.json').write_text(json.dumps({'seed': SEED, 'levels': sweeps}, indent=1))
    n_rows = collections.Counter(r['level'] for r in rows)
    print(f"\nwrote: backbone_assignments {len(bb_assign)}, code_assignments {len(code_assign)}, "
          f"clusters {len(rows)} (L1 {n_rows['L1']}, L2 {n_rows['L2']}, L3 {n_rows['L3']})")

if __name__ == '__main__':
    main()
