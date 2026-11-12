#!/usr/bin/env python3
"""P4.3 — rules-first OKF verifier.

Independently re-derives the fact index from raw inputs (graph, findings,
clusters, profiles, stats) and checks every claim unit in the bundle:

1. each claim line ends with >=1 atom chip [aXXXXXXX];
2. each chip maps to a skeleton atom;
3. every ref of that atom resolves (N node, E edge, C cluster, S stat,
   F finding pointer, P source file, D doc + verbatim quote);
4. numeric S/F values appear in the rendered sentence.

Violations are stripped from the page and logged; pages are stamped
`verified: full` or `verified: partial` in front matter. Results are written
to verification.json.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from okf_common import (  # noqa: E402
    P4, CHIP_RE, compute_stats, front_matter, load_all, parse_front_matter,
    resolve_ref, value_in_sentence,
)
from skeleton import build_index  # noqa: E402

BUNDLE = f'{P4}/okf-bundle'
LEDGER = '## Anchor ledger'


def claim_units(body):
    """Yield (line_index_in_body, line). Skips headings, the ledger section,
    table separator rows and blanks."""
    units = []
    in_ledger = False
    for i, ln in enumerate(body.splitlines()):
        s = ln.strip()
        if s.startswith('## '):
            in_ledger = s.startswith(LEDGER)
            continue
        if in_ledger or not s or s.startswith('#'):
            continue
        if s.startswith('|') and set(s.replace('|', '').strip()) <= set('- '):
            continue
        units.append((i, ln))
    return units


def check_line(line, atoms_by_id, index):
    """Return None if the claim holds, else the strip reason."""
    chips = CHIP_RE.findall(line)
    if not chips:
        return 'no anchor chip'
    for c in chips:
        atom = atoms_by_id.get(c[1:-1])
        if atom is None:
            return f'unknown chip {c}'
        for ref in atom['refs']:
            ok, detail = resolve_ref(ref, index)
            if not ok:
                return f'unresolved {detail}'
            if not value_in_sentence(ref, index, line):
                return f'value missing for {ref["k"]}:{ref["r"]}'
    return None


def verify_page(path, atoms_by_id, index, mutate_line=None):
    text = open(path, encoding='utf-8').read()
    fm, body = parse_front_matter(text)
    if fm.get('claims') == 'none':
        return {'page': os.path.relpath(path, BUNDLE), 'status': 'meta',
                'claims': 0, 'stripped': 0, 'reasons': []}, text

    units = claim_units(body)
    stripped, reasons, stripped_idx = [], [], set()
    for i, ln in units:
        why = check_line(ln, atoms_by_id, index)
        if why:
            stripped_idx.add(i)
            stripped.append(ln.strip())
            reasons.append(why)
    if mutate_line is not None:
        # inject an unanchored claim as the last body line
        lines = body.splitlines() + [mutate_line]
        stripped_idx.add(len(lines) - 1)
        stripped.append(mutate_line.strip())
        reasons.append('no anchor chip (mutation)')
        body = '\n'.join(lines)

    status = 'partial' if stripped else 'full'
    fm['verified'] = status
    kept = [ln for i, ln in enumerate(body.splitlines()) if i not in stripped_idx]
    new_text = front_matter(fm) + '\n' + '\n'.join(kept).rstrip('\n') + '\n'
    return ({'page': os.path.relpath(path, BUNDLE), 'status': status,
             'claims': len(units) + (1 if mutate_line is not None else 0),
             'stripped': len(stripped), 'reasons': reasons,
             'stripped_lines': stripped}, new_text)


def page_atoms(skel_dir):
    atoms_by_id = {}
    for root, _dirs, files in os.walk(skel_dir):
        for f in sorted(files):
            if f.endswith('.json') and f not in ('manifest.json', 'stats.json'):
                pg = json.load(open(os.path.join(root, f)))
                for a in (pg.get('atoms', []) + pg.get('row_atoms', [])
                          + pg.get('toc_atoms', [])):
                    atoms_by_id[a['id']] = a
    return atoms_by_id


def verify_bundle(bundle=BUNDLE, mutate_page=None, mutate_line=None):
    d = load_all()
    index = build_index(d, compute_stats(d))
    atoms_by_id = page_atoms(f'{P4}/skeleton')

    results = []
    for root, _dirs, files in os.walk(bundle):
        for f in sorted(files):
            if not f.endswith('.md'):
                continue
            path = os.path.join(root, f)
            mut = None
            if mutate_page and path.endswith(mutate_page):
                mut = mutate_line
            res, new_text = verify_page(path, atoms_by_id, index, mut)
            if new_text is not None:
                with open(path, 'w', encoding='utf-8') as fh:
                    fh.write(new_text)
            results.append(res)

    full = sum(1 for r in results if r['status'] == 'full')
    partial = sum(1 for r in results if r['status'] == 'partial')
    meta = sum(1 for r in results if r['status'] == 'meta')
    summary = {'pages': len(results), 'full': full, 'partial': partial,
               'meta': meta,
               'claims': sum(r['claims'] for r in results),
               'stripped': sum(r['stripped'] for r in results)}
    out = {'summary': summary, 'pages': sorted(results, key=lambda r: r['page'])}
    return out


def main():
    out = verify_bundle()
    json.dump(out, open(f'{P4}/verification.json', 'w'), indent=1, sort_keys=True)
    s = out['summary']
    print(f"verify: {s['pages']} pages — full {s['full']}, partial {s['partial']}, "
          f"meta {s['meta']}; claims {s['claims']}, stripped {s['stripped']}")
    for r in out['pages']:
        if r['status'] != 'full':
            print(f"  {r['page']}: {r['status']} ({r['reasons'][:3]})")
    return out


if __name__ == '__main__':
    main()
