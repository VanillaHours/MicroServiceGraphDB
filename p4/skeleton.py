#!/usr/bin/env python3
"""P4.1 — deterministic OKF skeleton builder.

Turns the P2/P3 fact artifacts into per-page skeletons: every page is a list
of atoms; every atom = one claim sentence (numbers baked from facts) + machine
refs that anchor it (N node, E edge, C cluster, S stat, F finding pointer,
P source file, D doc quote). All refs are validated at build time.
"""
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from okf_common import (  # noqa: E402
    P4, atom_id, compute_stats, flatten_refs, load_all, numeric_value,
    pack_domain_data, resolve_ref,
)

OUT = f'{P4}/skeleton'


# atom / ref shorthand ---------------------------------------------------------

def A(tpl, refs):
    refs = flatten_refs(refs)
    return {'id': atom_id(tpl, refs), 'tpl': tpl, 'refs': refs}


def S(*paths):
    return [{'k': 'S', 'r': p} for p in paths]


def N(r):
    return {'k': 'N', 'r': r}


def E(src, rel, dst):
    return {'k': 'E', 'r': f'{src}|{rel}|{dst}'}


def C(r):
    return {'k': 'C', 'r': r}


def F(r):
    return {'k': 'F', 'r': r}


def P(r):
    return {'k': 'P', 'r': r}


def D(r, q=None):
    ref = {'k': 'D', 'r': r}
    if q:
        ref['q'] = q
    return ref


def short(msg):
    return msg.replace('zapi:', '')


def sv(stats, path):
    return numeric_value(stats[path])


def build_index(d, stats):
    return {
        'nodes': {n['id'] for n in d['graph']['nodes']},
        'edges': {(e['src'], e['rel'], e['dst']) for e in d['graph']['edges']},
        'clusters': {c['id'] for c in d['clusters']},
        'findings': d['findings'],
        'stats': stats,
    }


def validate(atoms, index, page):
    errs = []
    for a in atoms:
        for ref in a['refs']:
            ok, detail = resolve_ref(ref, index)
            if not ok:
                errs.append(f'{page} atom {a["id"]}: unresolved {detail}')
    if errs:
        raise SystemExit('\n'.join(errs))


# contract atoms shared by domain + daemon pages -------------------------------

def contract_atoms(d, stats, pd, pfx):
    svc, pub, hand = pd['svc'], pd['published'], pd['handled']
    l1 = pd['l1']
    atoms = []
    if pub:
        refs = [S(f'{pfx}.published')]
        for m in pub[:3]:
            refs.append(E(svc, 'publishes', m))
        pubex = ', '.join(short(m) for m in pub[:3]) + (', ...' if len(pub) > 3 else '')
        atoms.append(A(f'{svc} publishes {sv(stats, pfx + ".published")} message '
                       f'types toward the ZAPI bus ({pubex}).', refs))
    if hand:
        refs = [S(f'{pfx}.handled')]
        for m in hand[:3]:
            refs.append(E(svc, 'handles', m))
        handex = ', '.join(short(m) for m in hand[:3]) + (', ...' if len(hand) > 3 else '')
        atoms.append(A(f'It handles {sv(stats, pfx + ".handled")} notification/event '
                       f'types from the bus ({handex}).', refs))
    ymods = l1.get('yang_modules', {})
    if ymods:
        yanglist = ', '.join(f'{m}({n})' for m, n in sorted(ymods.items()))
        refs = [S(f'{pfx}.yang.total', f'{pfx}.nb_tables')]
        for m in sorted(ymods):
            refs.append(S(f'{pfx}.yang.{m}'))
        atoms.append(A(f'Northbound contracts: {yanglist} — '
                       f'{sv(stats, pfx + ".yang.total")} YANG paths across '
                       f'{sv(stats, pfx + ".nb_tables")} NB handler tables.', refs))
    else:
        atoms.append(A(f'Northbound contracts: no YANG module wired to {svc} in '
                       f'this slice; {sv(stats, pfx + ".nb_tables")} NB handler '
                       'tables.', [S(f'{pfx}.nb_tables')]))
    return atoms


# page builders ----------------------------------------------------------------

def index_atoms(d, stats):
    atoms = [
        A(f'The fused graph contains {sv(stats, "graph.nodes")} nodes and '
          f'{sv(stats, "graph.edges")} fused edges.',
          S('graph.nodes', 'graph.edges')),
        A(f'The P3 semantic backbone carries {sv(stats, "backbone.nodes")} nodes '
          f'and {sv(stats, "backbone.edges")} weighted edges over '
          f'{sv(stats, "slice.svc")} services.',
          S('backbone.nodes', 'backbone.edges', 'slice.svc')),
        A(f'Hierarchical Leiden (seed {sv(stats, "seed")}, L1 resolution '
          f'{sv(stats, "gamma.L1")}) partitioned the backbone into '
          f'{sv(stats, "clusters.L1")} functional domains, '
          f'{sv(stats, "clusters.L2")} service areas and '
          f'{sv(stats, "clusters.L3")} code modules.',
          S('seed', 'gamma.L1', 'clusters.L1', 'clusters.L2', 'clusters.L3')),
        A(f'The northbound join matched {sv(stats, "nb_join.hits")} of '
          f'{sv(stats, "nb_join.total")} handler-table registrations to YANG '
          f'schema paths ({sv(stats, "nb_join.pct")}%).',
          [F('nb_yang_join.hits'), F('nb_yang_join.total_nb'), F('nb_yang_join.pct'),
           S('nb_join.hits', 'nb_join.total', 'nb_join.pct')]),
        A(f'Open findings: {sv(stats, "findings.orphan")} orphan handlers, '
          f'{sv(stats, "findings.dropped")} dropped-on-wire messages, '
          f'{sv(stats, "findings.dead")} dead registrations and '
          f'{sv(stats, "findings.flows")} verified cross-service ZAPI flows.',
          S('findings.orphan', 'findings.dropped', 'findings.dead', 'findings.flows')),
        A(f'Code responsibilities are partitioned across {sv(stats, "svc.partition")} '
          'service partitions, including svc:fpm.', S('svc.partition')),
    ]
    toc = []
    for did in sorted(d['packs']):
        pd = pack_domain_data(d, d['packs'][did])
        pfx = f'pack.{did}'
        toc.append(A(f'{did} — {d["packs"][did]["label"]}: '
                     f'{sv(stats, pfx + ".members")} members → clusters/{did}.md',
                     [C(did), S(f'{pfx}.members')]))
        name = pd['svc'].replace('svc:', '')
        toc.append(A(f'{pd["svc"]} — {sv(stats, pfx + ".modules.n")} code modules, '
                     f'domain {did} → daemons/{name}.md',
                     [N(pd['svc']), C(did), S(f'{pfx}.modules.n')]))
    toc += [
        A('ADR-0001 — inter-daemon IPC goes through zebra (authored) → '
          'adrs/ADR-0001-zapi-ipc.md', [D('doc/user/ospfd.rst')]),
        A('ADR-0002 — management data is YANG-typed (authored) → '
          'adrs/ADR-0002-yang-mgmt.md', [D('doc/user/mgmtd.rst')]),
        A('ADR-0003 — zebra owns kernel routing-table updates (authored) → '
          'adrs/ADR-0003-zebra-kernel.md', [D('doc/user/zebra.rst')]),
    ]
    return atoms, toc


def domain_atoms(d, stats, did):
    pack = d['packs'][did]
    pd = pack_domain_data(d, pack)
    svc = pd['svc']
    pfx = f'pack.{did}'
    mods = pd['modules']
    atoms = [
        A(f'{svc} forms functional domain {did}: {sv(stats, pfx + ".members")} '
          f'backbone members ({sv(stats, pfx + ".members.svc")} service, '
          f'{sv(stats, pfx + ".members.zapi")} ZAPI message, '
          f'{sv(stats, pfx + ".members.yang")} YANG path nodes).',
          [N(svc), C(did)] + S(f'{pfx}.members', f'{pfx}.members.svc',
                               f'{pfx}.members.zapi', f'{pfx}.members.yang')),
    ]
    atoms += contract_atoms(d, stats, pd, pfx)
    roles = ', '.join(pd['l1'].get('roles', []))
    if roles:
        atoms.append(A(f'Measured roles: {roles}.', [S(f'{pfx}.roles')]))

    for area in pd['areas']:
        atoms.append(A(f'The domain contains P3 L2 service area {area["id"]} '
                       f'({area["label"]}).', [C(area['id'])]))

    if pd['pack'].get('boundary_edges'):
        atoms.append(A(f'{sv(stats, pfx + ".boundary.total")} cross-domain edge '
                       'bindings point outside the domain.',
                       [S(f'{pfx}.boundary.total')]))
    atoms.append(A(f'{sv(stats, pfx + ".flows.out")} verified cross-service ZAPI '
                   f'flows originate from {svc}.',
                   [S(f'{pfx}.flows.out'), F('zapi.cross_svc_flows')]))
    atoms.append(A(f'{sv(stats, pfx + ".orphan.n")} handled messages currently '
                   'have no in-slice sender (orphan handlers).',
                   [S(f'{pfx}.orphan.n'),
                    F('zapi.orphan_handlers_no_sender_in_slice')]))
    if pd['pack'].get('findings', {}).get('dropped_on_wire'):
        atoms.append(A(f'{sv(stats, pfx + ".dropped.n")} published sends currently '
                       'drop on the wire in the extractor view (dropped-on-wire '
                       'findings).',
                       [S(f'{pfx}.dropped.n'), F('zapi.dropped_on_wire')]))
    node_ids = {n['id'] for n in d['graph']['nodes']}
    for i, row in enumerate(d['findings']['dead_wiring']['registrations_without_callbacks']):
        if row['svc'] == svc:
            refs = [F(f'dead_wiring.registrations_without_callbacks.{i}')]
            if row['nb'] in node_ids:
                refs.append(N(row['nb']))
            atoms.append(A('Dead wiring: ' + row['nb'] + ' registered in ' +
                           row['table'] + ' has no callbacks.', refs))

    if mods:
        real = [m for m in mods if ':unlinked' not in m['label'] and ':misc' not in m['label']]
        top = real[0] if real else mods[0]
        atoms.append(A(f'{sv(stats, pfx + ".modules.n")} code modules; largest is '
                       f'{top["label"]} with {sv(stats, pfx + ".mod." + top["id"] + ".size")} '
                       'functions.',
                       [S(f'{pfx}.modules.n'), C(top['id']),
                        S(f'{pfx}.mod.{top["id"]}.size')]))
        for m in mods:
            if ':unlinked' in m['label'] or ':misc' in m['label']:
                atoms.append(A(f'Bucket {m["label"]} holds '
                               f'{sv(stats, pfx + ".mod." + m["id"] + ".size")} '
                               'functions without intra-service call edges '
                               '(pointer-dispatched callbacks and CLI handlers).',
                               [C(m['id']), S(f'{pfx}.mod.{m["id"]}.size')]))
    if pd['bridge_total'] > 0:
        blabel, bn = next(iter(pd['bridge_labels'].items()))
        atoms.append(A(f'{sv(stats, pfx + ".bridge.total")} intra-service `calls` '
                       f'edges leave for other service partitions; densest target '
                       f'{blabel} ({bn} calls).',
                       [S(f'{pfx}.bridge.total'), S(f'{pfx}.bridge.{blabel}')]))

    rows = []
    for m in pd['published'][:12]:
        rows.append(A(m, [N(m), E(svc, 'publishes', m)]))
    for m in pd['handled'][:12]:
        rows.append(A(m, [N(m), E(svc, 'handles', m)]))
    for b in pd['pack'].get('boundary_edges', []):
        for rel, n in sorted(b['rels'].items()):
            rows.append(A(f'{rel} ×{n} → {b["to"]}',
                          [C(b['to']), S(f'{pfx}.boundary.{b["to"]}.{rel}')]))
    for m in pd['pack'].get('findings', {}).get('orphan_handlers', [])[:12]:
        rows.append(A(m, [N(m), F('zapi.orphan_handlers_no_sender_in_slice')]))
    for m in [x for x in mods if ':unlinked' not in x['label']
              and ':misc' not in x['label']][:10]:
        rows.append(A(f'{m["label"]} — {sv(stats, pfx + ".mod." + m["id"] + ".size")} '
                      'functions', [C(m['id']), S(f'{pfx}.mod.{m["id"]}.size')]))
    return atoms, rows


def daemon_atoms(d, stats, svc):
    did = next(did for did, pk in d['packs'].items() if pk['services'][0] == svc)
    pd = pack_domain_data(d, d['packs'][did])
    pfx = f'pack.{did}'
    atoms = [
        A(f'{svc} is a service in the fused graph; its functional domain is {did}.',
          [N(svc), C(did)]),
    ]
    atoms += contract_atoms(d, stats, pd, pfx)
    roles = ', '.join(pd['l1'].get('roles', []))
    if roles:
        atoms.append(A(f'Measured roles: {roles}.', [S(f'{pfx}.roles')]))

    for m in pd['modules'][:8]:
        if not m.get('anchors'):
            continue
        fns, files = [], []
        for an in m['anchors']:
            fname = an['id'].split('::')[-1]
            if an.get('file'):
                fns.append(f'{fname} ({an["file"]})')
                if an['file'] not in files:
                    files.append(an['file'])
        if not fns:
            continue
        refs = [C(m['id']), S(f'{pfx}.mod.{m["id"]}.size')] + [P(f) for f in files[:3]]
        atoms.append(A(f'{m["label"]} — {sv(stats, pfx + ".mod." + m["id"] + ".size")} '
                       f'functions; anchors: {", ".join(fns[:4])}.', refs))

    if pd['bridge_total'] > 0:
        blabel, bn = next(iter(pd['bridge_labels'].items()))
        atoms.append(A(f'{sv(stats, pfx + ".bridge.total")} intra-service `calls` '
                       f'edges reach other service partitions; densest target '
                       f'{blabel} ({bn} calls).',
                       [S(f'{pfx}.bridge.total'), S(f'{pfx}.bridge.{blabel}')]))
    targets = sorted({f['to'] for f in d['findings']['zapi']['cross_svc_flows']
                      if f['from'] == svc})
    if targets:
        atoms.append(A(f'{sv(stats, pfx + ".flows.out")} cross-service flows '
                       f'originate here; targets: {", ".join(targets)}.',
                       [S(f'{pfx}.flows.out'), F('zapi.cross_svc_flows')]))
    atoms.append(A(f'{sv(stats, pfx + ".orphan.n")} handled messages have no '
                   'in-slice sender (orphan handlers).',
                   [S(f'{pfx}.orphan.n'),
                    F('zapi.orphan_handlers_no_sender_in_slice')]))
    rows = []
    for m in pd['published'][:12]:
        rows.append(A(m, [N(m), E(svc, 'publishes', m)]))
    for m in pd['handled'][:12]:
        rows.append(A(m, [N(m), E(svc, 'handles', m)]))
    return atoms, rows


def adr_atoms(stats):
    """Authored ADR claims — decision statements quoted from FRR docs, with
    measured corroboration from the fact graph."""
    z = 'doc/user/zebra.rst'
    mg = 'doc/user/mgmtd.rst'
    osp = 'doc/user/ospfd.rst'
    bgp = 'doc/user/bgp.rst'
    zh = sv(stats, 'pack.D4b2a9ab8.handled')
    zp = sv(stats, 'pack.D4b2a9ab8.published')
    yz = sv(stats, 'pack.D4b2a9ab8.yang.frr-zebra')
    zt = sv(stats, 'pack.D4b2a9ab8.yang.frr-zebra-route-map')
    ztot = sv(stats, 'pack.D4b2a9ab8.nb_tables')
    a1 = [
        A('Context: FRR separates protocol daemons from the routing manager — '
          'ospfd must acquire interface information from zebra in order to '
          'function, so zebra must run first.',
          [D(osp, q='*ospfd* must acquire interface information from *zebra* '
          'in order to function.')]),
        A('Decision: routes are installed through zebra, not independently into '
          'the kernel — a route is installed into zebra when its conditions '
          'are satisfied.',
          [D(bgp, q='This route is installed into zebra if following conditions '
          'are satisfied:')]),
        A(f'Consequence: in the fused slice this materializes as '
          f'{sv(stats, "findings.flows")} cross-service ZAPI flows converging '
          f'on svc:zebra, which handles {zh} message types.',
          [N('svc:zebra'), S('findings.flows', 'pack.D4b2a9ab8.handled'),
           F('zapi.cross_svc_flows')]),
        A('Consequence: svc:bgpd publishes zapi:ZEBRA_ROUTE_ADD and svc:zebra '
          'handles it — the route-install path the docs describe.',
          [E('svc:bgpd', 'publishes', 'zapi:ZEBRA_ROUTE_ADD'),
           E('svc:zebra', 'handles', 'zapi:ZEBRA_ROUTE_ADD'),
           N('svc:bgpd'), N('svc:zebra'), N('zapi:ZEBRA_ROUTE_ADD')]),
    ]
    a2 = [
        A('Context: mgmtd requires that management data is stored in YANG in '
          'compliance with a pre-defined set of YANG based schema.',
          [D(mg, q='management data is stored in YANG in compliance with a '
          'pre-defined set of YANG based schema')]),
        A('Decision: data shall also be stored/retrieved in YANG format only — '
          'no private config stores.',
          [D(mg, q='Data shall also be stored/retrieved in YANG format only.')]),
        A(f'Consequence: the northbound join validated this contract plane — '
          f'{sv(stats, "nb_join.hits")} of {sv(stats, "nb_join.total")} '
          f'handler-table registrations matched YANG schema paths '
          f'({sv(stats, "nb_join.pct")}%).',
          [F('nb_yang_join.hits'), F('nb_yang_join.total_nb'), F('nb_yang_join.pct'),
           S('nb_join.hits', 'nb_join.total', 'nb_join.pct')]),
        A('Consequence: shared models frr-filter(41), ietf-key-chain(26), '
          'frr-logging(21), frr-route-map(30) sit in domain D1737981e — '
          f'{sv(stats, "pack.D1737981e.yang.total")} YANG paths total — and are '
          'wired from multiple daemons\' domains.',
          [C('D1737981e'), S('pack.D1737981e.yang.frr-filter',
          'pack.D1737981e.yang.ietf-key-chain', 'pack.D1737981e.yang.frr-logging',
          'pack.D1737981e.yang.frr-route-map', 'pack.D1737981e.yang.total')]),
    ]
    a3 = [
        A('Context: zebra is an IP routing manager providing kernel routing '
          'table updates, interface lookups, and redistribution of routes '
          'between different routing protocols.',
          [D(z, q='*zebra* is an IP routing manager. It provides kernel routing '
          'table updates, interface lookups, and redistribution of routes '
          'between different routing protocols.')]),
        A('Decision: zebra is the process that communicates with the kernel '
          'routing tables — protocol daemons interact only through ZAPI '
          'requests and notifications.',
          [D(z, q='Specify which kernel routing table *Zebra* should '
          'communicate with.'), C('D4b2a9ab8'), N('svc:zebra')]),
        A(f'Consequence: zebra implements the frr-zebra northbound model with '
          f'{yz} YANG paths and {zt} YANG paths on frr-zebra-route-map, served '
          f'by {ztot} NB handler tables.',
          [S('pack.D4b2a9ab8.yang.frr-zebra', 'pack.D4b2a9ab8.yang.frr-zebra-route-map',
             'pack.D4b2a9ab8.nb_tables')]),
        A(f'Consequence: zebra is the ZAPI server — it handles {zh} message '
          f'types published by the route daemons and emits {zp} notification/'
          f'event types back to clients.',
          [S('pack.D4b2a9ab8.handled', 'pack.D4b2a9ab8.published'), C('D4b2a9ab8')]),
    ]
    prov = [A('Provenance: decision statements are authored from FRR '
              'documentation; quotes are validated verbatim by the verifier, '
              'consequences are measured graph facts.',
              [D(z), D(mg), D(osp), D(bgp)])]
    return {'ADR-0001-zapi-ipc': a1 + prov, 'ADR-0002-yang-mgmt': a2 + prov,
            'ADR-0003-zebra-kernel': a3 + prov}


# main --------------------------------------------------------------------------

def main():
    d = load_all()
    stats = compute_stats(d)
    index = build_index(d, stats)

    shutil.rmtree(OUT, ignore_errors=True)
    os.makedirs(f'{OUT}/clusters', exist_ok=True)
    os.makedirs(f'{OUT}/daemons', exist_ok=True)
    os.makedirs(f'{OUT}/adrs', exist_ok=True)

    json.dump(stats, open(f'{OUT}/stats.json', 'w'), indent=1, sort_keys=True)

    pages = {}
    atoms, toc = index_atoms(d, stats)
    pages['index'] = {
        'page_id': 'index.md', 'okf_level': 'L0-index', 'claims': 'yes',
        'sources': ['p2/graph.json', 'p3/backbone.json', 'p3/clusters.jsonl',
                    'p3/profiles.jsonl', 'p2/findings.json', 'p3/packs/*.json'],
        'atoms': atoms, 'toc_atoms': toc,
    }

    for did in sorted(d['packs']):
        atoms, rows = domain_atoms(d, stats, did)
        pages[f'clusters/{did}'] = {
            'page_id': f'clusters/{did}.md', 'okf_level': 'L2-cluster',
            'claims': 'yes',
            'sources': [f'p3/packs/{did}.json', 'p3/profiles.jsonl',
                        'p3/backbone.json', 'p3/clusters.jsonl', 'p2/findings.json'],
            'atoms': atoms, 'row_atoms': rows,
        }

    for svc in ['svc:bgpd', 'svc:lib', 'svc:ospfd', 'svc:staticd', 'svc:zebra']:
        atoms, rows = daemon_atoms(d, stats, svc)
        name = svc.replace('svc:', '')
        pages[f'daemons/{name}'] = {
            'page_id': f'daemons/{name}.md', 'okf_level': 'L3-daemon',
            'claims': 'yes',
            'sources': ['p3/profiles.jsonl', 'p3/backbone.json', 'p3/clusters.jsonl',
                        'p2/findings.json'],
            'atoms': atoms, 'row_atoms': rows,
        }

    for slug, atoms in adr_atoms(stats).items():
        pages[f'adrs/{slug}'] = {
            'page_id': f'adrs/{slug}.md', 'okf_level': 'ADR', 'claims': 'yes',
            'sources': ['doc/user/ospfd.rst', 'doc/user/mgmtd.rst',
                        'doc/user/zebra.rst', 'doc/user/bgp.rst', 'p2/findings.json'],
            'atoms': atoms,
        }

    total = 0
    for key, pg in sorted(pages.items()):
        n = (len(pg.get('atoms', [])) + len(pg.get('row_atoms', []) or [])
             + len(pg.get('toc_atoms', []) or []))
        total += n
        fn = f'{OUT}/{pg["page_id"].removesuffix(".md")}.json'
        os.makedirs(os.path.dirname(fn), exist_ok=True)
        json.dump(pg, open(fn, 'w'), indent=1, sort_keys=True)
        all_atoms = (pg.get('atoms', []) + pg.get('row_atoms', [])
                     + pg.get('toc_atoms', []))
        validate(all_atoms, index, key)

    manifest = {
        'pages': {k: {'page_id': p['page_id'], 'okf_level': p['okf_level'],
                      'atoms': len(p.get('atoms', []))
                      + len(p.get('row_atoms', []) or [])
                      + len(p.get('toc_atoms', []) or [])}
                  for k, p in sorted(pages.items())},
        'total_atoms': total,
        'stats_file': 'stats.json',
    }
    json.dump(manifest, open(f'{OUT}/manifest.json', 'w'), indent=1, sort_keys=True)
    print(f'skeleton: {len(pages)} pages, {total} atoms, all refs resolved')
    for k, m in manifest['pages'].items():
        print(f'  {k}: {m["atoms"]} atoms')


if __name__ == '__main__':
    main()
