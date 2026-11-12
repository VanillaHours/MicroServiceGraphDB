#!/usr/bin/env python3
"""P4 OKF publisher — shared fact index, deterministic stats, anchor utilities.

Everything the skeleton builder, renderer and verifier need. The verifier
re-derives all facts through these same functions from raw inputs only.
"""
import collections
import hashlib
import json
import os
import re

from hashlib import blake2b

ROOT = os.environ.get('MSG_ROOT', os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data'))  # portability: workspace root via MSG_ROOT
FACTS = f'{ROOT}/facts'
REPO = f'{ROOT}/src/frr-10.7.1'
P4 = f'{FACTS}/p4'

CHIP_RE = re.compile(r'\[a[0-9a-f]{7}\]')


def blake2b_hex(s: str, n: int = 7) -> str:
    return blake2b(s.encode(), digest_size=16).hexdigest()[:n]


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------- load facts

def load_all():
    d = {}
    d['graph'] = json.load(open(f'{FACTS}/p2/graph.json'))
    d['findings'] = json.load(open(f'{FACTS}/p2/findings.json'))
    d['backbone'] = json.load(open(f'{FACTS}/p3/backbone.json'))
    d['clusters'] = [json.loads(l) for l in open(f'{FACTS}/p3/clusters.jsonl')]
    d['profiles'] = [json.loads(l) for l in open(f'{FACTS}/p3/profiles.jsonl')]
    d['code_assign'] = json.load(open(f'{FACTS}/p3/code_assignments.json'))
    d['backbone_assign'] = json.load(open(f'{FACTS}/p3/backbone_assignments.json'))
    d['packs'] = {}
    for p in sorted(os.listdir(f'{FACTS}/p3/packs')):
        if p.startswith('D') and p.endswith('.json'):
            pk = json.load(open(f'{FACTS}/p3/packs/{p}'))
            d['packs'][pk['id']] = pk
    d['sweep'] = json.load(open(f'{FACTS}/p3/sweep.json'))
    return d


def edge_set(graph) -> set:
    return {(e['src'], e['rel'], e['dst']) for e in graph['edges']}


def node_set(graph) -> set:
    return {n['id'] for n in graph['nodes']}


def cluster_index(clusters) -> dict:
    return {c['id']: c for c in clusters}


def profile_index(profiles) -> dict:
    return {p['id']: p for p in profiles}


# ------------------------------------------------------------- derived views

def svc_contract(backbone, svc):
    """Messages a service publishes / handles, from backbone edges (ground truth)."""
    pub, hand = set(), set()
    for e in backbone['edges']:
        if e['src'] == svc and e['rel'] == 'publishes':
            pub.add(e['dst'])
        elif e['src'] == svc and e['rel'] == 'handles':
            hand.add(e['dst'])
    return sorted(pub), sorted(hand)


def svc_modules(profiles, svc):
    """L3 modules whose parent is this service partition, largest first."""
    mods = [p for p in profiles if p['level'] == 'L3' and p['parent'] == svc]
    mods.sort(key=lambda m: (-m['size'], m['id']))
    return mods


def svc_bridges(profiles, svc):
    """Aggregate intra-`calls` bridges from svc's modules into other service
    partitions. Returns (total, {target_module_label: calls}) both sorted."""
    prof = profile_index(profiles)
    per_label = collections.Counter()
    total = 0
    for m in profiles:
        if m['level'] == 'L3' and m['parent'] == svc:
            for tgt_id, n in m.get('calls_into_other_svcs', []):
                tgt = prof.get(tgt_id)
                if tgt is None or tgt.get('parent') == svc:
                    continue
                per_label[tgt['label']] += n
                total += n
    return total, dict(sorted(per_label.items(), key=lambda kv: (-kv[1], kv[0])))


def pack_domain_data(d, pack):
    """All fact data one domain/daemon page needs, recomputable from raw inputs."""
    svc = pack['services'][0]
    profs = profile_index(d['profiles'])
    pr = profs[pack['id']]                      # L1 profile shares the domain id
    pub, hand = svc_contract(d['backbone'], svc)
    mods = svc_modules(d['profiles'], svc)
    total_bridges, bridge_labels = svc_bridges(d['profiles'], svc)
    areas = [c for c in d['clusters'] if c['level'] == 'L2' and c['parent'] == pack['id']]
    return {
        'svc': svc,
        'pack': pack,
        'l1': pr,
        'published': pub,
        'handled': hand,
        'modules': mods,
        'bridge_total': total_bridges,
        'bridge_labels': bridge_labels,
        'areas': areas,
    }


# ------------------------------------------------------------------- stats

def compute_stats(d) -> dict:
    """Deterministic, sorted stats tree. Paths used as S: anchors."""
    s = {}
    s['graph.nodes'] = len(d['graph']['nodes'])
    s['graph.edges'] = len(d['graph']['edges'])
    s['backbone.nodes'] = len(d['backbone']['nodes'])
    s['backbone.edges'] = len(d['backbone']['edges'])
    lv = collections.Counter(c['level'] for c in d['clusters'])
    s['clusters.L1'] = lv['L1']
    s['clusters.L2'] = lv['L2']
    s['clusters.L3'] = lv['L3']
    s['seed'] = 42
    l1rows = [c for c in d['clusters'] if c['level'] == 'L1']
    s['gamma.L1'] = l1rows[0]['gamma'] if l1rows and l1rows[0].get('gamma') is not None else None
    s['slice.svc'] = len({n['id'] for n in d['graph']['nodes'] if n['id'].startswith('svc:')})
    s['svc.partition'] = len({p['parent'] for p in d['profiles'] if p['level'] == 'L3'})
    j = d['findings']['nb_yang_join']
    s['nb_join.total'] = j['total_nb']
    s['nb_join.hits'] = j['hits']
    s['nb_join.pct'] = j['pct']
    z = d['findings']['zapi']
    s['findings.orphan'] = len(z['orphan_handlers_no_sender_in_slice'])
    s['findings.dropped'] = len(z['dropped_on_wire'])
    s['findings.dead'] = len(d['findings']['dead_wiring']['registrations_without_callbacks'])
    s['findings.flows'] = len(z['cross_svc_flows'])
    for did in sorted(d['packs']):
        pd = pack_domain_data(d, d['packs'][did])
        pfx = f'pack.{did}'
        s[f'{pfx}.members'] = pd['l1']['size']
        s[f'{pfx}.published'] = len(pd['published'])
        s[f'{pfx}.handled'] = len(pd['handled'])
        s[f'{pfx}.contract.total'] = len(set(pd['published']) | set(pd['handled']))
        s[f'{pfx}.nb_tables'] = pd['l1'].get('nb_tables', 0)
        s[f'{pfx}.yang.total'] = sum(pd['l1'].get('yang_modules', {}).values())
        for ymod, yn in sorted(pd['l1'].get('yang_modules', {}).items()):
            s[f'{pfx}.yang.{ymod}'] = yn
        l1row = next((c for c in d['clusters'] if c['id'] == did), None)
        if l1row:
            kh = l1row.get('kind_hist', {})
            s[f'{pfx}.members.svc'] = kh.get('svc', 0)
            s[f'{pfx}.members.zapi'] = kh.get('zapi-msg', 0)
            s[f'{pfx}.members.yang'] = kh.get('yang-path', 0)
        s[f'{pfx}.modules.n'] = len(pd['modules'])
        s[f'{pfx}.orphan.n'] = len(pd['pack'].get('findings', {}).get('orphan_handlers', []))
        s[f'{pfx}.dropped.n'] = len(pd['pack'].get('findings', {}).get('dropped_on_wire', []))
        s[f'{pfx}.flows.out'] = sum(1 for f in d['findings']['zapi']['cross_svc_flows']
                                    if f['from'] == pd['svc'])
        bnd = pd['pack'].get('boundary_edges', [])
        s[f'{pfx}.boundary.total'] = sum(sum(r['rels'].values()) for r in bnd)
        for row in bnd:
            for rel, n in sorted(row['rels'].items()):
                s[f'{pfx}.boundary.{row["to"]}.{rel}'] = n
        s[f'{pfx}.bridge.total'] = pd['bridge_total']
        for lbl, n in list(pd['bridge_labels'].items())[:6]:
            s[f'{pfx}.bridge.{lbl}'] = n
        for m in pd['modules']:
            s[f'{pfx}.mod.{m["id"]}.size'] = m['size']
        s[f'{pfx}.roles'] = ', '.join(pd['l1'].get('roles', []))
    return {k: v for k, v in sorted(s.items()) if v is not None}


# ------------------------------------------------------------ ref resolution

def norm_ws(s: str) -> str:
    return re.sub(r'\s+', ' ', s).strip()


def resolve_ref(ref, index) -> tuple:
    """Return (ok, detail). index = dict with nodes/edges/clusters/findings/stats/docs."""
    k, r = ref['k'], ref['r']
    if k == 'N':
        return (r in index['nodes'], f'node {r}')
    if k == 'E':
        src, rel, dst = r.split('|', 2)
        return ((src, rel, dst) in index['edges'], f'edge {r}')
    if k == 'C':
        return (r in index['clusters'], f'cluster {r}')
    if k == 'S':
        return (r in index['stats'], f'stat {r}')
    if k == 'F':
        cur = index['findings']
        for part in r.split('.'):
            if isinstance(cur, list):
                try:
                    cur = cur[int(part)]
                except (ValueError, IndexError):
                    return (False, f'finding {r}')
            elif isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
                return (False, f'finding {r}')
        return (True, f'finding {r}')
    if k == 'P':
        ok = os.path.isfile(os.path.join(REPO, r))
        return (ok, f'src file {r}')
    if k == 'D':
        path = os.path.join(REPO, r)
        if not os.path.isfile(path):
            return (False, f'doc {r}')
        if ref.get('q'):
            hay = norm_ws(open(path, encoding='utf-8', errors='replace').read())
            ok = norm_ws(ref['q']) in hay
            return (ok, f'doc quote in {r}')
        return (True, f'doc {r}')
    return (False, f'unknown ref kind {k}')


def numeric_value(v) -> str:
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, float):
        return ('%g' % v) if v == int(v) else str(v)
    return str(v)


def value_in_sentence(ref, index, sentence: str) -> bool:
    """S/F refs carrying numeric values must be visible in the rendered claim.
    S paths are flat dotted keys in stats; F paths walk the nested findings tree."""
    k, r = ref['k'], ref['r']
    if k not in ('S', 'F'):
        return True
    if k == 'S':
        cur = index['stats'].get(r, '_missing_')
    else:
        cur = index['findings']
        for part in r.split('.'):
            if isinstance(cur, list):
                try:
                    cur = cur[int(part)]
                except (ValueError, IndexError):
                    return False
            elif isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
                return False
    if isinstance(cur, (int, float)) and not isinstance(cur, bool):
        return numeric_value(cur) in sentence
    if isinstance(cur, str):
        return cur in sentence
    return True


# -------------------------------------------------------------- atom helper

def atom_id(tpl: str, refs) -> str:
    canon = tpl + '|' + ';'.join(f'{r["k"]}:{r["r"]}' for r in refs)
    return 'a' + blake2b_hex(canon, 7)


def flatten_refs(refs):
    flat = []
    for r in refs:
        if isinstance(r, list):
            flat.extend(r)
        else:
            flat.append(r)
    return flat


def chip(aid: str) -> str:
    return f'[{aid}]'


# ------------------------------------------------------------ front matter

def front_matter(fields: dict) -> str:
    lines = ['---']
    for k, v in fields.items():
        lines.append(f'{k}: {v}')
    lines.append('---')
    return '\n'.join(lines)


def parse_front_matter(text: str) -> tuple:
    """Return (fields dict, body). Expects leading --- block."""
    if not text.startswith('---'):
        return {}, text
    end = text.find('\n---', 3)
    if end < 0:
        return {}, text
    block = text[3:end].strip('\n')
    body = text[end + 4:].lstrip('\n')
    fields = {}
    for ln in block.splitlines():
        if ':' in ln:
            k, v = ln.split(':', 1)
            fields[k.strip()] = v.strip()
    return fields, body


def input_hashes() -> dict:
    files = [
        'p2/graph.json', 'p2/findings.json', 'p3/backbone.json',
        'p3/clusters.jsonl', 'p3/profiles.jsonl', 'p3/code_assignments.json',
        'p3/backbone_assignments.json', 'p3/sweep.json',
        'p3/packs/D1737981e.json', 'p3/packs/D3063a0b0.json',
        'p3/packs/D4b2a9ab8.json', 'p3/packs/Dc32724de.json',
        'p3/packs/Ded29f1c0.json',
    ]
    return {f: sha256_file(os.path.join(FACTS, f)) for f in files}
