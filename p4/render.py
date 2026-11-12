#!/usr/bin/env python3
"""P4.2 — deterministic OKF bundle renderer.

Assembles okf-bundle/ from skeleton pages: front matter, sectioned claim
bullets (each ending with its atom chip), an anchor ledger per page, plus a
bundle manifest with input hashes. No prose is invented here — every line
comes from a skeleton atom.
"""
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from okf_common import P4, front_matter, input_hashes  # noqa: E402

SKEL = f'{P4}/skeleton'
BUNDLE = f'{P4}/okf-bundle'

LEDGER = '## Anchor ledger'
OKF_VERSION = '0.1.0'

ADR_TITLES = {
    'ADR-0001-zapi-ipc': 'Inter-daemon IPC goes through zebra',
    'ADR-0002-yang-mgmt': 'Management data is YANG-typed',
    'ADR-0003-zebra-kernel': 'Zebra owns kernel routing-table updates',
}

ADR_README = """---
page_id: adrs/README.md
okf_level: meta
claims: none
verified: none
---

# ADR ingest

Architecture Decision Records are **authored** knowledge: human-readable
decision statements anchored to citations the verifier can check. The store
started empty per POC-DESIGN; the first AUTHORED facts (ADR-0001..0003) are
ingested from FRR's own documentation (doc/user/*.rst), quote-validated by
the P4 verifier.

## Ingest rules

1. Every claim sentence ends with an atom chip [aXXXXXXX] defined in
   skeleton/adrs/<slug>.json.
2. Decision statements carry D-anchors: doc path + verbatim quote; the
   verifier whitespace-normalizes and greps the quote in the cited file.
3. Consequence statements carry machine refs: E (fused edge), S (stat),
   F (finding pointer), C (cluster), N (node).
4. Front matter: status (accepted/proposed), provenance: authored,
   verified: full once every claim resolves.
5. Unanchored claims are stripped and the page is stamped verified: partial.

## Format

See TEMPLATE.md.
"""

ADR_TEMPLATE = """---
page_id: adrs/TEMPLATE.md
okf_level: meta
claims: none
verified: none
---

# ADR-NNNN — <title>

## Authored claims

- Context: <situation, quoting the source doc> [aXXXXXXX]
- Decision: <the decision> [aXXXXXXX]
- Consequence: <measured corroboration from the fact graph> [aXXXXXXX]

## Anchor ledger

| chip | refs |
|---|---|
| [aXXXXXXX] | D:doc/user/<file>.rst; N:svc:<name> |
"""


def bullets(atoms):
    return [f"- {a['tpl']} [{a['id']}]" for a in atoms]


def ledger_section(atoms):
    lines = ['', LEDGER, '', '| chip | refs |', '|---|---|']
    for a in atoms:
        refs = ' · '.join(f"{r['k']}:{r['r']}" for r in a['refs'])
        lines.append(f"| [{a['id']}] | {refs} |")
    return lines


def page_text(pg, sections, atoms_all, fm_extra=None):
    fm = {
        'page_id': pg['page_id'],
        'okf_level': pg['okf_level'],
        'claims': pg.get('claims', 'yes'),
        'verified': 'pending',
    }
    if fm_extra:
        fm.update(fm_extra)
    lines = [front_matter(fm), '']
    for title, content in sections:
        if content:
            lines += [title, ''] + content + ['']
    lines += ledger_section(atoms_all)
    return '\n'.join(lines) + '\n'


def classify_rows(rows):
    """Split row atoms into contract/boundary/orphan/module buckets by refs."""
    pub, hand, bnd, orph, mod = [], [], [], [], []
    for a in rows:
        kinds = [r['k'] for r in a['refs']]
        if any(r['k'] == 'E' for r in a['refs']):
            rel = next(r['r'].split('|')[1] for r in a['refs'] if r['k'] == 'E')
            (pub if rel == 'publishes' else hand).append(a)
        elif any(r['k'] == 'S' and '.boundary.' in r['r'] for r in a['refs']):
            bnd.append(a)
        elif any(r['k'] == 'F' and 'orphan' in r['r'] for r in a['refs']):
            orph.append(a)
        elif any(r['k'] == 'S' and '.mod.' in r['r'] for r in a['refs']):
            mod.append(a)
        else:
            mod.append(a)
    return pub, hand, bnd, orph, mod


def render_index(pg):
    cluster_rows = [a for a in pg['toc_atoms'] if a['tpl'].startswith('D')
                    and '—' in a['tpl']]
    daemon_rows = [a for a in pg['toc_atoms'] if a['tpl'].startswith('svc:')]
    adr_rows = [a for a in pg['toc_atoms'] if a['tpl'].startswith('ADR-')]
    sections = [
        ('## Knowledge base', bullets(pg['atoms'])),
        ('## Domain pages (OKF L2 clusters, from P3 L1 domains)',
         bullets(cluster_rows)),
        ('## Daemon pages (OKF L3, per-service responsibilities)',
         bullets(daemon_rows)),
        ('## Authored decisions (ADRs)', bullets(adr_rows)),
    ]
    fm_extra = {'okf_version': OKF_VERSION}
    return page_text(pg, sections, pg['atoms'] + pg['toc_atoms'], fm_extra)


def render_cluster(pg):
    did = pg['page_id'].split('/')[1].removesuffix('.md')
    pub, hand, bnd, orph, mod = classify_rows(pg['row_atoms'])
    sections = [
        ('## Functionality', bullets(pg['atoms'])),
        ('## ZAPI contract — published (first 12)', bullets(pub)),
        ('## ZAPI contract — handled (first 12)', bullets(hand)),
        ('## Boundary bindings', bullets(bnd)),
        ('## Orphan handlers (examples)', bullets(orph)),
        ('## L3 code modules (largest semantic modules)', bullets(mod)),
    ]
    fm_extra = {'domain': did}
    return page_text(pg, sections, pg['atoms'] + pg['row_atoms'], fm_extra)


def render_daemon(pg):
    svc = pg['page_id'].split('/')[1].removesuffix('.md')
    pub, hand, bnd, orph, mod = classify_rows(pg['row_atoms'])
    sections = [
        ('## Functionality', bullets(pg['atoms'])),
        ('## ZAPI contract — published (first 12)', bullets(pub)),
        ('## ZAPI contract — handled (first 12)', bullets(hand)),
    ]
    fm_extra = {'service': f'svc:{svc}'}
    return page_text(pg, sections, pg['atoms'] + pg['row_atoms'], fm_extra)


def render_adr(pg):
    slug = pg['page_id'].split('/')[1].removesuffix('.md')
    sections = [('## Authored claims', bullets(pg['atoms']))]
    fm_extra = {'adr': slug.split('-')[0] + '-' + slug.split('-')[1],
                'status': 'accepted', 'provenance': 'authored'}
    return page_text(pg, sections, pg['atoms'], fm_extra)


def main():
    shutil.rmtree(BUNDLE, ignore_errors=True)
    os.makedirs(f'{BUNDLE}/clusters', exist_ok=True)
    os.makedirs(f'{BUNDLE}/daemons', exist_ok=True)
    os.makedirs(f'{BUNDLE}/adrs', exist_ok=True)

    manifest = json.load(open(f'{SKEL}/manifest.json'))
    renderers = {'index': render_index, 'clusters': render_cluster,
                 'daemons': render_daemon, 'adrs': render_adr}
    for key, meta in manifest['pages'].items():
        pg = json.load(open(f'{SKEL}/{key}.json'))
        kind = key.split('/')[0]
        text = renderers[kind](pg)
        with open(f'{BUNDLE}/{pg["page_id"]}', 'w') as f:
            f.write(text)

    with open(f'{BUNDLE}/adrs/README.md', 'w') as f:
        f.write(ADR_README)
    with open(f'{BUNDLE}/adrs/TEMPLATE.md', 'w') as f:
        f.write(ADR_TEMPLATE)

    bundle_manifest = {
        'okf_version': OKF_VERSION,
        'phase': 'P4',
        'pages': manifest['pages'],
        'total_atoms': manifest['total_atoms'],
        'inputs_sha256': input_hashes(),
        'verify': 'scripts/p4/verify.py',
    }
    json.dump(bundle_manifest, open(f'{BUNDLE}/manifest.json', 'w'),
              indent=1, sort_keys=True)
    n = sum(1 for _, _, files in os.walk(BUNDLE) for f in files if f.endswith('.md'))
    print(f'bundle: {n} markdown pages + manifest.json -> {BUNDLE}')


if __name__ == '__main__':
    main()
