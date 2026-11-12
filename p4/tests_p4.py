#!/usr/bin/env python3
"""P4 stability / integrity tests."""
import filecmp
import json
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from okf_common import P4, norm_ws  # noqa: E402
import render  # noqa: E402
import skeleton  # noqa: E402
import verify  # noqa: E402

REPO = os.environ.get('MSG_ROOT', os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')) + '/src/frr-10.7.1'  # portability: workspace via MSG_ROOT
BUNDLE = f'{P4}/okf-bundle'
SNAP = '/tmp/p4_snapshot'

RESULTS = []


def check(tid, name, ok, detail=''):
    RESULTS.append((tid, name, ok, detail))
    print(f'  {"PASS" if ok else "FAIL"}  {tid} {name}' + (f' — {detail}' if detail else ''))
    if not ok:
        raise SystemExit(f'{tid} {name} FAILED: {detail}')


def run_pipeline():
    skeleton.main()
    render.main()
    verify.main()


def tree_files(root):
    out = {}
    for r, _d, files in os.walk(root):
        for f in files:
            p = os.path.join(r, f)
            out[os.path.relpath(p, root)] = open(p, 'rb').read()
    return out


print('P4 tests — pipeline warm-up')
run_pipeline()

# T1 determinism ----------------------------------------------------------------
print('T1 determinism (rebuild reproduces the bundle byte-for-byte)')
shutil.rmtree(SNAP, ignore_errors=True)
shutil.copytree(BUNDLE, SNAP)
run_pipeline()
a, b = tree_files(SNAP), tree_files(BUNDLE)
same = set(a) == set(b) and all(a[k] == b[k] for k in a)
diff = [k for k in a if k not in b or a[k] != b[k]]
check('T1', 'byte-identical bundle across rebuilds', same, f'diffs: {diff[:4]}')

# T2 anchor integrity -------------------------------------------------------------
print('T2 anchor integrity (every claim anchored, nothing stripped)')
v = json.load(open(f'{P4}/verification.json'))
s = v['summary']
check('T2a', 'all claim pages verified: full', s['full'] == 14 and s['partial'] == 0,
      f"full={s['full']} partial={s['partial']}")
check('T2b', 'zero stripped claims', s['stripped'] == 0, f"claims={s['claims']}")

# T3 mutation strip ---------------------------------------------------------------
print('T3 mutation (unanchored claim is stripped, page stamped partial)')
mut = ('- svc:bgpd also terminates BGP sessions over TCP port 179 with peers '
       'directly [a0000000].')
out = verify.verify_bundle(mutate_page='daemons/bgpd.md', mutate_line=mut)
pg = next(r for r in out['pages'] if r['page'] == 'daemons/bgpd.md')
check('T3a', 'mutated claim stripped', pg['stripped'] == 1 and 'mutation' in ' '.join(pg['reasons']),
      f"stripped={pg['stripped']}")
check('T3b', 'page re-stamped partial', pg['status'] == 'partial')
txt = open(f'{BUNDLE}/daemons/bgpd.md').read()
check('T3c', 'stripped sentence absent from page', 'terminates BGP sessions' not in txt)
run_pipeline()  # restore clean state

# T4 ADR authored quotes ----------------------------------------------------------
print('T4 ADR authored quotes (Context/Decision verbatim doc anchors; '
      'Consequences machine-anchored)')
bad = []
n_q = 0
for root, _d, files in os.walk(f'{BUNDLE}/adrs'):
    for f in files:
        if not (f.startswith('ADR-') and f.endswith('.md')):
            continue
        slug = f.removesuffix('.md')
        sk = json.load(open(f'{P4}/skeleton/adrs/{slug}.json'))
        for a in sk['atoms']:
            drefs = [r for r in a['refs'] if r['k'] == 'D']
            mach = [r for r in a['refs'] if r['k'] != 'D']
            if a['tpl'].startswith(('Context:', 'Decision:')):
                if not any(r.get('q') for r in drefs):
                    bad.append(f'{slug}: {a["tpl"][:40]} lacks verbatim D quote')
                else:
                    n_q += sum(1 for r in drefs if r.get('q'))
            elif not (drefs or mach):
                bad.append(f'{slug}: unanchored atom {a["tpl"][:40]}')
            for r in drefs:
                if r.get('q'):
                    hay = norm_ws(open(os.path.join(REPO, r['r']),
                                       encoding='utf-8', errors='replace').read())
                    if norm_ws(r['q']) not in hay:
                        bad.append(f'{slug}: quote not in {r["r"]}')
check('T4', 'Context/Decision quote-anchored, Consequences machine-anchored, '
      'quotes verbatim in docs',
      not bad and n_q >= 5, f'quotes={n_q} problems={bad[:2]}')

# T5 TOC coverage -------------------------------------------------------------------
print('T5 TOC coverage (index links ↔ pages on disk)')
idx = open(f'{BUNDLE}/index.md').read()
missing = []
for sub in ('clusters', 'daemons', 'adrs'):
    for f in sorted(os.listdir(f'{BUNDLE}/{sub}')):
        if f.endswith('.md') and f != 'README.md' and f != 'TEMPLATE.md':
            if f'{sub}/{f}' not in idx:
                missing.append(f'{sub}/{f}')
n_pages = sum(1 for sub in ('clusters', 'daemons')
              for f in os.listdir(f'{BUNDLE}/{sub}') if f.endswith('.md'))
check('T5', 'every domain/daemon/ADR page listed in L0 index', not missing and n_pages == 10,
      f'pages={n_pages} missing={missing[:3]}')

# T6 stamp hygiene ------------------------------------------------------------------
print('T6 stamp hygiene (no pending stamps, meta pages marked)')
pending = 0
for r, _d, files in os.walk(BUNDLE):
    for f in files:
        if f.endswith('.md') and 'verified: pending' in open(os.path.join(r, f)).read():
            pending += 1
check('T6', 'no "verified: pending" left after verification', pending == 0)

n_full = v['summary']['full']
print(f'\nAll P4 tests passed ({n_full} verified-full pages, '
      f'{v["summary"]["claims"]} anchored claims).')
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       'tests_output.txt'), 'w') as f:
    for tid, name, ok, detail in RESULTS:
        f.write(f'{"PASS" if ok else "FAIL"}  {tid} {name}  {detail}\n')
    f.write(f'ALL {len(RESULTS)} TESTS PASS\n')
