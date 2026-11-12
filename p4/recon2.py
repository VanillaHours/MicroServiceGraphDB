#!/usr/bin/env python3
"""P4 recon round 2: anchors, findings detail, L2, doc quotes for ADR."""
import json, glob, collections, re

import os  # portability: workspace root via MSG_ROOT
ROOT = os.environ.get('MSG_ROOT', os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data'))
F = f'{ROOT}/facts'

profs = [json.loads(l) for l in open(f'{F}/p3/profiles.jsonl')]
l3 = [p for p in profs if p['level'] == 'L3' and p.get('anchors')]
print('== L3 with anchors:', len(l3), 'of', len([p for p in profs if p['level']=='L3']))
big = sorted(l3, key=lambda p: -p['size'])[0]
print('biggest:', json.dumps(big)[:900])

lab = {p['id']: p['label'] for p in profs}
print('\ncalls_into_other_svcs resolved:', [(lab.get(m, m), n) for m, n in big.get('calls_into_other_svcs', [])][:4])

print('\n== findings.json detail ==')
fin = json.load(open(f'{F}/p2/findings.json'))
def walk(d, pre=''):
    if isinstance(d, dict):
        for k, v in d.items():
            walk(v, f'{pre}.{k}' if pre else k)
    elif isinstance(d, list):
        print(f'{pre}: list[{len(d)}]')
        if d: print('   [0]:', json.dumps(d[0])[:280])
    else:
        print(f'{pre}:', json.dumps(d)[:200])
walk(fin)

print('\n== L2 row ==')
l2 = [p for p in profs if p['level'] == 'L2'][0]
print(json.dumps({k: v for k, v in l2.items() if k not in ('functionality',)})[:500])

l1 = [p for p in profs if p['level'] == 'L1'][0]
print('\n== L1 extras ==')
for k in ('children', 'nb_tables', 'gamma', 'parent'):
    print(k, '=', json.dumps(l1.get(k))[:200])

print('\n== doc quotes for ADR (grep-verified) ==')
D = f'{ROOT}/src/frr-10.7.1/doc'
pats = [(f'{D}/user/zebra.rst', ['kernel', 'route']), (f'{D}/user/mgmtd.rst', ['YANG', 'northbound']),
        (f'{D}/user/bgp.rst', ['zebra']), (f'{D}/user/ospfd.rst', ['zebra'])]
for path, words in pats:
    try:
        txt = open(path, encoding='utf-8', errors='replace').read()
    except OSError as e:
        print(path, 'ERR', e); continue
    print(f'--- {path.split("frr-10.7.1/")[1]} ({len(txt)} chars)')
    shown = 0
    for ln in txt.splitlines():
        if any(w.lower() in ln.lower() for w in words) and 30 < len(ln) < 160 and not ln.startswith('   '):
            print('   |', ln.strip())
            shown += 1
            if shown >= 6: break

print('\n== developer docs list (non-building) ==')
print([p.split('/')[-1] for p in glob.glob(f'{D}/developer/*.rst')
       if not p.split('/')[-1].startswith('building')][:30])
