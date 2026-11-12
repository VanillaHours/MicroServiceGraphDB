---
page_id: daemons/staticd.md
okf_level: L3-daemon
claims: yes
verified: full
service: svc:staticd
---
## Functionality

- svc:staticd is a service in the fused graph; its functional domain is Dc32724de. [a3dd9765]
- It handles 8 notification/event types from the bus (ZEBRA_INTERFACE_ADDRESS_ADD, ZEBRA_INTERFACE_ADDRESS_DELETE, ZEBRA_NEIGH_ADDED, ...). [ab23686d]
- Northbound contracts: frr-staticd(27) — 27 YANG paths across 27 NB handler tables. [a33ba0cd]
- Measured roles: zapi-client. [a405a038]
- staticd:static — 77 functions; anchors: debug_staticd_magic (staticd/static_vty.c), static_add_route (staticd/static_routes.c), static_next_hop_bfd_profile (staticd/static_bfd.c), static_nexthop_list_prev (staticd/static_routes.h). [aca36653]
- staticd:static — 34 functions; anchors: static_nexthop_list_first (staticd/static_routes.h), static_nexthop_list_next (staticd/static_routes.h), static_path_list_first (staticd/static_routes.h), static_path_list_next (staticd/static_routes.h). [a59c6cd4]
- staticd:static — 31 functions; anchors: static_nexthop_move_path (staticd/static_nb_config.c), static_del_path (staticd/static_routes.c), static_delete_nexthop (staticd/static_routes.c), ecmp_path_list_validate (staticd/static_nb_config.c). [af0c0af4]
- staticd:static — 28 functions; anchors: static_zebra_srv6_sid_uninstall (staticd/static_zebra.c), static_zebra_release_srv6_sid (staticd/static_zebra.c), static_zebra_request_srv6_sid (staticd/static_zebra.c), static_zebra_process_srv6_locator_internal (staticd/static_zebra.c). [af757fbb]
- staticd:static — 25 functions; anchors: static_srv6_neigh_add (staticd/static_srv6.c), static_ifp_srv6_sids_update (staticd/static_srv6.c), static_srv6_neigh_lookup (staticd/static_srv6.c), static_srv6_neigh_table_find (staticd/static_srv6.c). [a9505b72]
- staticd:static — 23 functions; anchors: main (staticd/static_main.c), static_srv6_neigh_cache_cleanup (staticd/static_srv6.c), static_srv6_neigh_cache_init (staticd/static_srv6.c), static_zebra_init (staticd/static_zebra.c). [a94871d6]
- staticd:static — 22 functions; anchors: svrf_name_head_RB_MIN (staticd/static_vrf.h), svrf_name_head_RB_NEXT (staticd/static_vrf.h), static_bfd_show (staticd/static_bfd.c), show_static_routes_magic (staticd/static_vty.c). [a6907c1f]
- 450 intra-service `calls` edges reach other service partitions; densest target lib:nb (125 calls). [ac771529]
- 3 handled messages have no in-slice sender (orphan handlers). [aa78803b]

## ZAPI contract — handled (first 12)

- zapi:ZEBRA_INTERFACE_ADDRESS_ADD [a7cde9e4]
- zapi:ZEBRA_INTERFACE_ADDRESS_DELETE [a3c80449]
- zapi:ZEBRA_NEIGH_ADDED [ad5cb70d]
- zapi:ZEBRA_NEIGH_REMOVED [a5d777b7]
- zapi:ZEBRA_ROUTE_NOTIFY_OWNER [a0d48a96]
- zapi:ZEBRA_SRV6_LOCATOR_ADD [a9d064b3]
- zapi:ZEBRA_SRV6_LOCATOR_DELETE [a27f544b]
- zapi:ZEBRA_SRV6_SID_NOTIFY [afc69c81]


## Anchor ledger

| chip | refs |
|---|---|
| [a3dd9765] | N:svc:staticd · C:Dc32724de |
| [ab23686d] | S:pack.Dc32724de.handled · E:svc:staticd|handles|zapi:ZEBRA_INTERFACE_ADDRESS_ADD · E:svc:staticd|handles|zapi:ZEBRA_INTERFACE_ADDRESS_DELETE · E:svc:staticd|handles|zapi:ZEBRA_NEIGH_ADDED |
| [a33ba0cd] | S:pack.Dc32724de.yang.total · S:pack.Dc32724de.nb_tables · S:pack.Dc32724de.yang.frr-staticd |
| [a405a038] | S:pack.Dc32724de.roles |
| [aca36653] | C:M4fc85874 · S:pack.Dc32724de.mod.M4fc85874.size · P:staticd/static_vty.c · P:staticd/static_routes.c · P:staticd/static_bfd.c |
| [a59c6cd4] | C:M9cc473a4 · S:pack.Dc32724de.mod.M9cc473a4.size · P:staticd/static_routes.h · P:staticd/static_routes.c · P:staticd/static_bfd.c |
| [af0c0af4] | C:M9b01cc7b · S:pack.Dc32724de.mod.M9b01cc7b.size · P:staticd/static_nb_config.c · P:staticd/static_routes.c |
| [af757fbb] | C:M71861180 · S:pack.Dc32724de.mod.M71861180.size · P:staticd/static_zebra.c · P:staticd/static_nb_config.c · P:staticd/static_srv6.c |
| [a9505b72] | C:M6b0e6125 · S:pack.Dc32724de.mod.M6b0e6125.size · P:staticd/static_srv6.c · P:staticd/static_routes.c |
| [a94871d6] | C:Mb7dec354 · S:pack.Dc32724de.mod.Mb7dec354.size · P:staticd/static_main.c · P:staticd/static_srv6.c · P:staticd/static_zebra.c |
| [a6907c1f] | C:M87eb3a08 · S:pack.Dc32724de.mod.M87eb3a08.size · P:staticd/static_vrf.h · P:staticd/static_bfd.c · P:staticd/static_vty.c |
| [ac771529] | S:pack.Dc32724de.bridge.total · S:pack.Dc32724de.bridge.lib:nb |
| [aa78803b] | S:pack.Dc32724de.orphan.n · F:zapi.orphan_handlers_no_sender_in_slice |
| [a7cde9e4] | N:zapi:ZEBRA_INTERFACE_ADDRESS_ADD · E:svc:staticd|handles|zapi:ZEBRA_INTERFACE_ADDRESS_ADD |
| [a3c80449] | N:zapi:ZEBRA_INTERFACE_ADDRESS_DELETE · E:svc:staticd|handles|zapi:ZEBRA_INTERFACE_ADDRESS_DELETE |
| [ad5cb70d] | N:zapi:ZEBRA_NEIGH_ADDED · E:svc:staticd|handles|zapi:ZEBRA_NEIGH_ADDED |
| [a5d777b7] | N:zapi:ZEBRA_NEIGH_REMOVED · E:svc:staticd|handles|zapi:ZEBRA_NEIGH_REMOVED |
| [a0d48a96] | N:zapi:ZEBRA_ROUTE_NOTIFY_OWNER · E:svc:staticd|handles|zapi:ZEBRA_ROUTE_NOTIFY_OWNER |
| [a9d064b3] | N:zapi:ZEBRA_SRV6_LOCATOR_ADD · E:svc:staticd|handles|zapi:ZEBRA_SRV6_LOCATOR_ADD |
| [a27f544b] | N:zapi:ZEBRA_SRV6_LOCATOR_DELETE · E:svc:staticd|handles|zapi:ZEBRA_SRV6_LOCATOR_DELETE |
| [afc69c81] | N:zapi:ZEBRA_SRV6_SID_NOTIFY · E:svc:staticd|handles|zapi:ZEBRA_SRV6_SID_NOTIFY |
