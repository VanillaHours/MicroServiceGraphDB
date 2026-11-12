---
page_id: adrs/ADR-0001-zapi-ipc.md
okf_level: ADR
claims: yes
verified: full
adr: ADR-0001
status: accepted
provenance: authored
---
## Authored claims

- Context: FRR separates protocol daemons from the routing manager — ospfd must acquire interface information from zebra in order to function, so zebra must run first. [a7092afc]
- Decision: routes are installed through zebra, not independently into the kernel — a route is installed into zebra when its conditions are satisfied. [afa4156e]
- Consequence: in the fused slice this materializes as 111 cross-service ZAPI flows converging on svc:zebra, which handles 94 message types. [a0c0d831]
- Consequence: svc:bgpd publishes zapi:ZEBRA_ROUTE_ADD and svc:zebra handles it — the route-install path the docs describe. [aa5ee17b]
- Provenance: decision statements are authored from FRR documentation; quotes are validated verbatim by the verifier, consequences are measured graph facts. [aa3b2c47]


## Anchor ledger

| chip | refs |
|---|---|
| [a7092afc] | D:doc/user/ospfd.rst |
| [afa4156e] | D:doc/user/bgp.rst |
| [a0c0d831] | N:svc:zebra · S:findings.flows · S:pack.D4b2a9ab8.handled · F:zapi.cross_svc_flows |
| [aa5ee17b] | E:svc:bgpd|publishes|zapi:ZEBRA_ROUTE_ADD · E:svc:zebra|handles|zapi:ZEBRA_ROUTE_ADD · N:svc:bgpd · N:svc:zebra · N:zapi:ZEBRA_ROUTE_ADD |
| [aa3b2c47] | D:doc/user/zebra.rst · D:doc/user/mgmtd.rst · D:doc/user/ospfd.rst · D:doc/user/bgp.rst |
