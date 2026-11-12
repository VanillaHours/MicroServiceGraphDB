---
page_id: adrs/ADR-0002-yang-mgmt.md
okf_level: ADR
claims: yes
verified: full
adr: ADR-0002
status: accepted
provenance: authored
---
## Authored claims

- Context: mgmtd requires that management data is stored in YANG in compliance with a pre-defined set of YANG based schema. [a36ed344]
- Decision: data shall also be stored/retrieved in YANG format only — no private config stores. [a42a7ce4]
- Consequence: the northbound join validated this contract plane — 426 of 426 handler-table registrations matched YANG schema paths (100%). [a546bfb3]
- Consequence: shared models frr-filter(41), ietf-key-chain(26), frr-logging(21), frr-route-map(30) sit in domain D1737981e — 147 YANG paths total — and are wired from multiple daemons' domains. [a5651bdd]
- Provenance: decision statements are authored from FRR documentation; quotes are validated verbatim by the verifier, consequences are measured graph facts. [aa3b2c47]


## Anchor ledger

| chip | refs |
|---|---|
| [a36ed344] | D:doc/user/mgmtd.rst |
| [a42a7ce4] | D:doc/user/mgmtd.rst |
| [a546bfb3] | F:nb_yang_join.hits · F:nb_yang_join.total_nb · F:nb_yang_join.pct · S:nb_join.hits · S:nb_join.total · S:nb_join.pct |
| [a5651bdd] | C:D1737981e · S:pack.D1737981e.yang.frr-filter · S:pack.D1737981e.yang.ietf-key-chain · S:pack.D1737981e.yang.frr-logging · S:pack.D1737981e.yang.frr-route-map · S:pack.D1737981e.yang.total |
| [aa3b2c47] | D:doc/user/zebra.rst · D:doc/user/mgmtd.rst · D:doc/user/ospfd.rst · D:doc/user/bgp.rst |
