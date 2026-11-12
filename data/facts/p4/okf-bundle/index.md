---
page_id: index.md
okf_level: L0-index
claims: yes
verified: full
okf_version: 0.1.0
---
## Knowledge base

- The fused graph contains 30229 nodes and 54246 fused edges. [aeba72d8]
- The P3 semantic backbone carries 557 nodes and 782 weighted edges over 5 services. [a345e6fa]
- Hierarchical Leiden (seed 42, L1 resolution 1.2) partitioned the backbone into 5 functional domains, 5 service areas and 193 code modules. [a9755b27]
- The northbound join matched 426 of 426 handler-table registrations to YANG schema paths (100%). [ac7cf2e7]
- Open findings: 44 orphan handlers, 7 dropped-on-wire messages, 4 dead registrations and 111 verified cross-service ZAPI flows. [a9df207f]
- Code responsibilities are partitioned across 6 service partitions, including svc:fpm. [abeb63f3]

## Domain pages (OKF L2 clusters, from P3 L1 domains)

- D1737981e — lib [34z/147y]: 182 members → clusters/D1737981e.md [a3980ff5]
- D3063a0b0 — bgpd [41z/65y]: 107 members → clusters/D3063a0b0.md [aa5b31f9]
- D4b2a9ab8 — zebra [46z/170y]: 217 members → clusters/D4b2a9ab8.md [aafe0748]
- Dc32724de — staticd [6z/27y]: 34 members → clusters/Dc32724de.md [a6e38ec3]
- Ded29f1c0 — ospfd [15z/1y]: 17 members → clusters/Ded29f1c0.md [a882cf2a]

## Daemon pages (OKF L3, per-service responsibilities)

- svc:lib — 59 code modules, domain D1737981e → daemons/lib.md [a02ac317]
- svc:bgpd — 37 code modules, domain D3063a0b0 → daemons/bgpd.md [a0cc0754]
- svc:zebra — 48 code modules, domain D4b2a9ab8 → daemons/zebra.md [a4448e2d]
- svc:staticd — 19 code modules, domain Dc32724de → daemons/staticd.md [a5a363b5]
- svc:ospfd — 29 code modules, domain Ded29f1c0 → daemons/ospfd.md [a79d79ed]

## Authored decisions (ADRs)

- ADR-0001 — inter-daemon IPC goes through zebra (authored) → adrs/ADR-0001-zapi-ipc.md [a7785e89]
- ADR-0002 — management data is YANG-typed (authored) → adrs/ADR-0002-yang-mgmt.md [a4f5dd5b]
- ADR-0003 — zebra owns kernel routing-table updates (authored) → adrs/ADR-0003-zebra-kernel.md [a0f593c8]


## Anchor ledger

| chip | refs |
|---|---|
| [aeba72d8] | S:graph.nodes · S:graph.edges |
| [a345e6fa] | S:backbone.nodes · S:backbone.edges · S:slice.svc |
| [a9755b27] | S:seed · S:gamma.L1 · S:clusters.L1 · S:clusters.L2 · S:clusters.L3 |
| [ac7cf2e7] | F:nb_yang_join.hits · F:nb_yang_join.total_nb · F:nb_yang_join.pct · S:nb_join.hits · S:nb_join.total · S:nb_join.pct |
| [a9df207f] | S:findings.orphan · S:findings.dropped · S:findings.dead · S:findings.flows |
| [abeb63f3] | S:svc.partition |
| [a3980ff5] | C:D1737981e · S:pack.D1737981e.members |
| [a02ac317] | N:svc:lib · C:D1737981e · S:pack.D1737981e.modules.n |
| [aa5b31f9] | C:D3063a0b0 · S:pack.D3063a0b0.members |
| [a0cc0754] | N:svc:bgpd · C:D3063a0b0 · S:pack.D3063a0b0.modules.n |
| [aafe0748] | C:D4b2a9ab8 · S:pack.D4b2a9ab8.members |
| [a4448e2d] | N:svc:zebra · C:D4b2a9ab8 · S:pack.D4b2a9ab8.modules.n |
| [a6e38ec3] | C:Dc32724de · S:pack.Dc32724de.members |
| [a5a363b5] | N:svc:staticd · C:Dc32724de · S:pack.Dc32724de.modules.n |
| [a882cf2a] | C:Ded29f1c0 · S:pack.Ded29f1c0.members |
| [a79d79ed] | N:svc:ospfd · C:Ded29f1c0 · S:pack.Ded29f1c0.modules.n |
| [a7785e89] | D:doc/user/ospfd.rst |
| [a4f5dd5b] | D:doc/user/mgmtd.rst |
| [a0f593c8] | D:doc/user/zebra.rst |
