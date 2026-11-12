---
page_id: adrs/ADR-0003-zebra-kernel.md
okf_level: ADR
claims: yes
verified: full
adr: ADR-0003
status: accepted
provenance: authored
---
## Authored claims

- Context: zebra is an IP routing manager providing kernel routing table updates, interface lookups, and redistribution of routes between different routing protocols. [a3a3e7c3]
- Decision: zebra is the process that communicates with the kernel routing tables — protocol daemons interact only through ZAPI requests and notifications. [af3fd906]
- Consequence: zebra implements the frr-zebra northbound model with 164 YANG paths and 6 YANG paths on frr-zebra-route-map, served by 183 NB handler tables. [ae5fb10f]
- Consequence: zebra is the ZAPI server — it handles 94 message types published by the route daemons and emits 44 notification/event types back to clients. [a240c9de]
- Provenance: decision statements are authored from FRR documentation; quotes are validated verbatim by the verifier, consequences are measured graph facts. [aa3b2c47]


## Anchor ledger

| chip | refs |
|---|---|
| [a3a3e7c3] | D:doc/user/zebra.rst |
| [af3fd906] | D:doc/user/zebra.rst · C:D4b2a9ab8 · N:svc:zebra |
| [ae5fb10f] | S:pack.D4b2a9ab8.yang.frr-zebra · S:pack.D4b2a9ab8.yang.frr-zebra-route-map · S:pack.D4b2a9ab8.nb_tables |
| [a240c9de] | S:pack.D4b2a9ab8.handled · S:pack.D4b2a9ab8.published · C:D4b2a9ab8 |
| [aa3b2c47] | D:doc/user/zebra.rst · D:doc/user/mgmtd.rst · D:doc/user/ospfd.rst · D:doc/user/bgp.rst |
