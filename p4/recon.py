#!/usr/bin/env python3
"""P4 recon: dump the shapes of every input the OKF publisher consumes."""
import json, os, glob, collections

import os  # portability: workspace root via MSG_ROOT
ROOT = os.environ.get('MSG_ROOT', os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data'))
F = f'{ROOT}/facts'

print('== packs ==')
for p in sorted(glob.glob(f'{F}/p3/packs/D*.json')):
    d = json.load(open(p))
    print(os.path.basename(p), 'keys:', list(d.keys()))
    if 'modules' in d:
        print('  module[0]:', json.dumps(d['modules'][0])[:400] if d['modules'] else 'EMPTY')

print('\n== profiles.jsonl ==')
profs = [json.loads(l) for l in open(f'{F}/p3/profiles.jsonl')]
lv = collections.Counter(p.get('level') for p in profs)
print('levels:', dict(lv))
l1 = [p for p in profs if p.get('level') == 'L1'][0]
print('L1 keys:', list(l1.keys()))
for k in ('modules', 'anchors', 'contract', 'boundary', 'findings'):
    if k in l1:
        print(f'  {k}:', json.dumps(l1[k])[:500])
l3 = [p for p in profs if p.get('level') == 'L3']
print('L3 sample keys:', list(l3[0].keys()))
print('L3 sample:', json.dumps(l3[0])[:700])

print('\n== clusters.jsonl ==')
clus = [json.loads(l) for l in open(f'{F}/p3/clusters.jsonl')]
print('levels:', dict(collections.Counter(c.get('level') for c in clus)))
print('L1 row:', json.dumps([c for c in clus if c.get('level')=='L1'][0])[:400])

print('\n== findings.json ==')
fin = json.load(open(f'{F}/p2/findings.json'))
print(type(fin).__name__, list(fin.keys()) if isinstance(fin, dict) else f'list[{len(fin)}]')
for k, v in (fin.items() if isinstance(fin, dict) else []):
    print(' ', k, '->', type(v).__name__, len(v) if hasattr(v, '__len__') else '')
    if isinstance(v, list) and v:
        print('    [0]:', json.dumps(v[0])[:300])

print('\n== svc nodes in graph ==')
g = json.load(open(f'{F}/p2/graph.json'))
svcs = sorted(n['id'] for n in g['nodes'] if n['id'].startswith('svc:'))
print(len(svcs), svcs)

print('\n== backbone.json ==')
bb = json.load(open(f'{F}/p3/backbone.json'))
print('keys:', list(bb.keys()))
for k in bb:
    if isinstance(bb[k], list):
        print(' ', k, f'[{len(bb[k])}]', json.dumps(bb[k][0])[:200] if bb[k] else '')

print('\n== FRR doc files (ADR candidates) ==')
for pat in ('doc/developer/zapi*', 'doc/developer/*.rst', 'doc/user/zebra.rst', 'doc/user/mgmtd.rst'):
    hits = sorted(glob.glob(f'{ROOT}/src/frr-10.7.1/{pat}'))
    print(pat, '->', [os.path.basename(h) for h in hits][:12])
