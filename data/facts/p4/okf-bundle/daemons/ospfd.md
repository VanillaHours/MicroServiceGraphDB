---
page_id: daemons/ospfd.md
okf_level: L3-daemon
claims: yes
verified: full
service: svc:ospfd
---
## Functionality

- svc:ospfd is a service in the fused graph; its functional domain is Ded29f1c0. [aa9e3cd3]
- svc:ospfd publishes 7 message types toward the ZAPI bus (ZEBRA_CLIENT_CAPABILITIES, ZEBRA_REDISTRIBUTE_ADD, ZEBRA_REDISTRIBUTE_DEFAULT_ADD, ...). [a63a4adf]
- It handles 8 notification/event types from the bus (ZEBRA_CLIENT_CLOSE_NOTIFY, ZEBRA_INTERFACE_ADDRESS_ADD, ZEBRA_INTERFACE_ADDRESS_DELETE, ...). [aa395e93]
- Northbound contracts: frr-ospf-route-map(1) — 1 YANG paths across 1 NB handler tables. [ae33cf5e]
- Measured roles: zapi-client, zapi-publisher. [aceed916]
- ospfd:ospf — 212 functions; anchors: ospf_lsa_install (ospfd/ospf_lsa.c), ospf_lsa_unlock (ospfd/ospf_lsa.c), ospf_flood_through_area (ospfd/ospf_flood.c), ospf_lsa_header_dump (ospfd/ospf_dump_api.c). [a3d22836]
- ospfd:ospf — 154 functions; anchors: ospf_get_name (ospfd/ospfd.c), ospf_show_vrf_name (ospfd/ospf_vty.c), show_ip_ospf_neighbor_detail_sub (ospfd/ospf_vty.c), ospf_lookup_instance (ospfd/ospfd.c). [a82b0b41]
- ospfd:ospf — 136 functions; anchors: ospf_route_free (ospfd/ospf_route.c), ospf_ase_calculate_route (ospfd/ospf_ase.c), ospf_spf_calculate_schedule_worker (ospfd/ospf_spf.c), ospf_abr_task (ospfd/ospf_abr.c). [ac392813]
- ospfd:ospf — 121 functions; anchors: ospf_if_update_params (ospfd/ospf_interface.c), ospf_get_if_params (ospfd/ospf_interface.c), ospf_free_if_params (ospfd/ospf_interface.c), ospf_lookup_if_params (ospfd/ospf_interface.c). [ae7e93bc]
- ospfd:ospf — 116 functions; anchors: ospf_finish_final (ospfd/ospfd.c), ospf_if_down (ospfd/ospf_interface.c), ospf_if_free (ospfd/ospf_interface.c), ospf_router_id_update (ospfd/ospfd.c). [ac082ca9]
- ospfd:ospf — 112 functions; anchors: ospf_router_info_update_sr (ospfd/ospf_ri.c), ospf_sr_start (ospfd/ospf_sr.c), update_sr_blocks (ospfd/ospf_sr.c), ospf_ext_link_update_adj_sid (ospfd/ospf_ext.c). [ad276fd9]
- ospfd:ospf — 107 functions; anchors: ospf_area_get (ospfd/ospfd.c), ospf_schedule_abr_task (ospfd/ospf_abr.c), ospf_area_lookup_by_area_id (ospfd/ospfd.c), ospf_area_check_free (ospfd/ospfd.c). [a6911ec6]
- 3625 intra-service `calls` edges reach other service partitions; densest target lib:zlog (968 calls). [a612b864]
- 7 cross-service flows originate here; targets: svc:zebra. [af3b7f80]
- 0 handled messages have no in-slice sender (orphan handlers). [af9f095e]

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


## Anchor ledger

| chip | refs |
|---|---|
| [aa9e3cd3] | N:svc:ospfd · C:Ded29f1c0 |
| [a63a4adf] | S:pack.Ded29f1c0.published · E:svc:ospfd|publishes|zapi:ZEBRA_CLIENT_CAPABILITIES · E:svc:ospfd|publishes|zapi:ZEBRA_REDISTRIBUTE_ADD · E:svc:ospfd|publishes|zapi:ZEBRA_REDISTRIBUTE_DEFAULT_ADD |
| [aa395e93] | S:pack.Ded29f1c0.handled · E:svc:ospfd|handles|zapi:ZEBRA_CLIENT_CLOSE_NOTIFY · E:svc:ospfd|handles|zapi:ZEBRA_INTERFACE_ADDRESS_ADD · E:svc:ospfd|handles|zapi:ZEBRA_INTERFACE_ADDRESS_DELETE |
| [ae33cf5e] | S:pack.Ded29f1c0.yang.total · S:pack.Ded29f1c0.nb_tables · S:pack.Ded29f1c0.yang.frr-ospf-route-map |
| [aceed916] | S:pack.Ded29f1c0.roles |
| [a3d22836] | C:M90387781 · S:pack.Ded29f1c0.mod.M90387781.size · P:ospfd/ospf_lsa.c · P:ospfd/ospf_flood.c · P:ospfd/ospf_dump_api.c |
| [a82b0b41] | C:M38cd72c7 · S:pack.Ded29f1c0.mod.M38cd72c7.size · P:ospfd/ospfd.c · P:ospfd/ospf_vty.c · P:ospfd/ospf_flood.h |
| [ac392813] | C:Mbed952fb · S:pack.Ded29f1c0.mod.Mbed952fb.size · P:ospfd/ospf_route.c · P:ospfd/ospf_ase.c · P:ospfd/ospf_spf.c |
| [ae7e93bc] | C:M62a211d6 · S:pack.Ded29f1c0.mod.M62a211d6.size · P:ospfd/ospf_interface.c · P:ospfd/ospfd.c · P:ospfd/ospf_vty.c |
| [ac082ca9] | C:M89381b56 · S:pack.Ded29f1c0.mod.M89381b56.size · P:ospfd/ospfd.c · P:ospfd/ospf_interface.c · P:ospfd/ospf_lsdb.c |
| [ad276fd9] | C:M2af12f08 · S:pack.Ded29f1c0.mod.M2af12f08.size · P:ospfd/ospf_ri.c · P:ospfd/ospf_sr.c · P:ospfd/ospf_ext.c |
| [a6911ec6] | C:M9e2457c9 · S:pack.Ded29f1c0.mod.M9e2457c9.size · P:ospfd/ospfd.c · P:ospfd/ospf_abr.c · P:ospfd/ospf_vty.c |
| [a612b864] | S:pack.Ded29f1c0.bridge.total · S:pack.Ded29f1c0.bridge.lib:zlog |
| [af3b7f80] | S:pack.Ded29f1c0.flows.out · F:zapi.cross_svc_flows |
| [af9f095e] | S:pack.Ded29f1c0.orphan.n · F:zapi.orphan_handlers_no_sender_in_slice |
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
