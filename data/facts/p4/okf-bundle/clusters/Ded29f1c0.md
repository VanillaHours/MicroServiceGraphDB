---
page_id: clusters/Ded29f1c0.md
okf_level: L2-cluster
claims: yes
verified: full
domain: Ded29f1c0
---
## Functionality

- svc:ospfd forms functional domain Ded29f1c0: 17 backbone members (1 service, 15 ZAPI message, 1 YANG path nodes). [a063b4da]
- svc:ospfd publishes 7 message types toward the ZAPI bus (ZEBRA_CLIENT_CAPABILITIES, ZEBRA_REDISTRIBUTE_ADD, ZEBRA_REDISTRIBUTE_DEFAULT_ADD, ...). [a63a4adf]
- It handles 8 notification/event types from the bus (ZEBRA_CLIENT_CLOSE_NOTIFY, ZEBRA_INTERFACE_ADDRESS_ADD, ZEBRA_INTERFACE_ADDRESS_DELETE, ...). [aa395e93]
- Northbound contracts: frr-ospf-route-map(1) — 1 YANG paths across 1 NB handler tables. [ae33cf5e]
- Measured roles: zapi-client, zapi-publisher. [aceed916]
- The domain contains P3 L2 service area Ced29f1c0 (ospfd:frr-ospf-route-map). [aec28f17]
- 31 cross-domain edge bindings point outside the domain. [a5a928fd]
- 7 verified cross-service ZAPI flows originate from svc:ospfd. [a83126e1]
- 0 handled messages currently have no in-slice sender (orphan handlers). [aaf36476]
- 29 code modules; largest is ospfd:ospf with 212 functions. [a952ffd9]
- Bucket ospfd:unlinked holds 1012 functions without intra-service call edges (pointer-dispatched callbacks and CLI handlers). [a3d96ce8]
- 3625 intra-service `calls` edges leave for other service partitions; densest target lib:zlog (968 calls). [a853b444]

## ZAPI contract — published (first 12)

- zapi:ZEBRA_CLIENT_CAPABILITIES [a5d0d1c2]
- zapi:ZEBRA_REDISTRIBUTE_ADD [a9571ff6]
- zapi:ZEBRA_REDISTRIBUTE_DEFAULT_ADD [a7dce706]
- zapi:ZEBRA_REDISTRIBUTE_DEFAULT_DELETE [a6f81ce6]
- zapi:ZEBRA_REDISTRIBUTE_DELETE [a20df46f]
- zapi:ZEBRA_ROUTE_ADD [a472edc6]
- zapi:ZEBRA_ROUTE_DELETE [a0a6e4e9]

## ZAPI contract — handled (first 12)

- zapi:ZEBRA_CLIENT_CLOSE_NOTIFY [a9a7fdac]
- zapi:ZEBRA_INTERFACE_ADDRESS_ADD [a972961d]
- zapi:ZEBRA_INTERFACE_ADDRESS_DELETE [a5c218a6]
- zapi:ZEBRA_INTERFACE_LINK_PARAMS [a1ad582d]
- zapi:ZEBRA_OPAQUE_MESSAGE [a8696d4a]
- zapi:ZEBRA_REDISTRIBUTE_ROUTE_ADD [ae5b8485]
- zapi:ZEBRA_REDISTRIBUTE_ROUTE_DEL [ac26575a]
- zapi:ZEBRA_ROUTER_ID_UPDATE [a7b59ae6]

## Boundary bindings

- handles ×7 → D4b2a9ab8 [ab1372ae]
- publishes ×7 → D4b2a9ab8 [a2a7f395]
- handles ×6 → D3063a0b0 [a3fa625f]
- publishes ×5 → D3063a0b0 [adc960b5]
- publishes ×4 → D1737981e [a90a3645]
- handles ×2 → Dc32724de [ac2943d1]

## L3 code modules (largest semantic modules)

- ospfd:ospf — 212 functions [a4f3ed04]
- ospfd:ospf — 154 functions [a44e07c5]
- ospfd:ospf — 136 functions [a684bfe4]
- ospfd:ospf — 121 functions [aa9d67c9]
- ospfd:ospf — 116 functions [aba45c0d]
- ospfd:ospf — 112 functions [ac15ce29]
- ospfd:ospf — 107 functions [a05cc168]
- ospfd:ospf — 101 functions [a517c333]
- ospfd:ospf — 101 functions [a95ff474]
- ospfd:ospf — 100 functions [a6d89379]


## Anchor ledger

| chip | refs |
|---|---|
| [a063b4da] | N:svc:ospfd · C:Ded29f1c0 · S:pack.Ded29f1c0.members · S:pack.Ded29f1c0.members.svc · S:pack.Ded29f1c0.members.zapi · S:pack.Ded29f1c0.members.yang |
| [a63a4adf] | S:pack.Ded29f1c0.published · E:svc:ospfd|publishes|zapi:ZEBRA_CLIENT_CAPABILITIES · E:svc:ospfd|publishes|zapi:ZEBRA_REDISTRIBUTE_ADD · E:svc:ospfd|publishes|zapi:ZEBRA_REDISTRIBUTE_DEFAULT_ADD |
| [aa395e93] | S:pack.Ded29f1c0.handled · E:svc:ospfd|handles|zapi:ZEBRA_CLIENT_CLOSE_NOTIFY · E:svc:ospfd|handles|zapi:ZEBRA_INTERFACE_ADDRESS_ADD · E:svc:ospfd|handles|zapi:ZEBRA_INTERFACE_ADDRESS_DELETE |
| [ae33cf5e] | S:pack.Ded29f1c0.yang.total · S:pack.Ded29f1c0.nb_tables · S:pack.Ded29f1c0.yang.frr-ospf-route-map |
| [aceed916] | S:pack.Ded29f1c0.roles |
| [aec28f17] | C:Ced29f1c0 |
| [a5a928fd] | S:pack.Ded29f1c0.boundary.total |
| [a83126e1] | S:pack.Ded29f1c0.flows.out · F:zapi.cross_svc_flows |
| [aaf36476] | S:pack.Ded29f1c0.orphan.n · F:zapi.orphan_handlers_no_sender_in_slice |
| [a952ffd9] | S:pack.Ded29f1c0.modules.n · C:M90387781 · S:pack.Ded29f1c0.mod.M90387781.size |
| [a3d96ce8] | C:Mb7c3d1fd · S:pack.Ded29f1c0.mod.Mb7c3d1fd.size |
| [a853b444] | S:pack.Ded29f1c0.bridge.total · S:pack.Ded29f1c0.bridge.lib:zlog |
| [a5d0d1c2] | N:zapi:ZEBRA_CLIENT_CAPABILITIES · E:svc:ospfd|publishes|zapi:ZEBRA_CLIENT_CAPABILITIES |
| [a9571ff6] | N:zapi:ZEBRA_REDISTRIBUTE_ADD · E:svc:ospfd|publishes|zapi:ZEBRA_REDISTRIBUTE_ADD |
| [a7dce706] | N:zapi:ZEBRA_REDISTRIBUTE_DEFAULT_ADD · E:svc:ospfd|publishes|zapi:ZEBRA_REDISTRIBUTE_DEFAULT_ADD |
| [a6f81ce6] | N:zapi:ZEBRA_REDISTRIBUTE_DEFAULT_DELETE · E:svc:ospfd|publishes|zapi:ZEBRA_REDISTRIBUTE_DEFAULT_DELETE |
| [a20df46f] | N:zapi:ZEBRA_REDISTRIBUTE_DELETE · E:svc:ospfd|publishes|zapi:ZEBRA_REDISTRIBUTE_DELETE |
| [a472edc6] | N:zapi:ZEBRA_ROUTE_ADD · E:svc:ospfd|publishes|zapi:ZEBRA_ROUTE_ADD |
| [a0a6e4e9] | N:zapi:ZEBRA_ROUTE_DELETE · E:svc:ospfd|publishes|zapi:ZEBRA_ROUTE_DELETE |
| [a9a7fdac] | N:zapi:ZEBRA_CLIENT_CLOSE_NOTIFY · E:svc:ospfd|handles|zapi:ZEBRA_CLIENT_CLOSE_NOTIFY |
| [a972961d] | N:zapi:ZEBRA_INTERFACE_ADDRESS_ADD · E:svc:ospfd|handles|zapi:ZEBRA_INTERFACE_ADDRESS_ADD |
| [a5c218a6] | N:zapi:ZEBRA_INTERFACE_ADDRESS_DELETE · E:svc:ospfd|handles|zapi:ZEBRA_INTERFACE_ADDRESS_DELETE |
| [a1ad582d] | N:zapi:ZEBRA_INTERFACE_LINK_PARAMS · E:svc:ospfd|handles|zapi:ZEBRA_INTERFACE_LINK_PARAMS |
| [a8696d4a] | N:zapi:ZEBRA_OPAQUE_MESSAGE · E:svc:ospfd|handles|zapi:ZEBRA_OPAQUE_MESSAGE |
| [ae5b8485] | N:zapi:ZEBRA_REDISTRIBUTE_ROUTE_ADD · E:svc:ospfd|handles|zapi:ZEBRA_REDISTRIBUTE_ROUTE_ADD |
| [ac26575a] | N:zapi:ZEBRA_REDISTRIBUTE_ROUTE_DEL · E:svc:ospfd|handles|zapi:ZEBRA_REDISTRIBUTE_ROUTE_DEL |
| [a7b59ae6] | N:zapi:ZEBRA_ROUTER_ID_UPDATE · E:svc:ospfd|handles|zapi:ZEBRA_ROUTER_ID_UPDATE |
| [ab1372ae] | C:D4b2a9ab8 · S:pack.Ded29f1c0.boundary.D4b2a9ab8.handles |
| [a2a7f395] | C:D4b2a9ab8 · S:pack.Ded29f1c0.boundary.D4b2a9ab8.publishes |
| [a3fa625f] | C:D3063a0b0 · S:pack.Ded29f1c0.boundary.D3063a0b0.handles |
| [adc960b5] | C:D3063a0b0 · S:pack.Ded29f1c0.boundary.D3063a0b0.publishes |
| [a90a3645] | C:D1737981e · S:pack.Ded29f1c0.boundary.D1737981e.publishes |
| [ac2943d1] | C:Dc32724de · S:pack.Ded29f1c0.boundary.Dc32724de.handles |
| [a4f3ed04] | C:M90387781 · S:pack.Ded29f1c0.mod.M90387781.size |
| [a44e07c5] | C:M38cd72c7 · S:pack.Ded29f1c0.mod.M38cd72c7.size |
| [a684bfe4] | C:Mbed952fb · S:pack.Ded29f1c0.mod.Mbed952fb.size |
| [aa9d67c9] | C:M62a211d6 · S:pack.Ded29f1c0.mod.M62a211d6.size |
| [aba45c0d] | C:M89381b56 · S:pack.Ded29f1c0.mod.M89381b56.size |
| [ac15ce29] | C:M2af12f08 · S:pack.Ded29f1c0.mod.M2af12f08.size |
| [a05cc168] | C:M9e2457c9 · S:pack.Ded29f1c0.mod.M9e2457c9.size |
| [a517c333] | C:M03ee9eb0 · S:pack.Ded29f1c0.mod.M03ee9eb0.size |
| [a95ff474] | C:M28664eb2 · S:pack.Ded29f1c0.mod.M28664eb2.size |
| [a6d89379] | C:M21fd366a · S:pack.Ded29f1c0.mod.M21fd366a.size |
