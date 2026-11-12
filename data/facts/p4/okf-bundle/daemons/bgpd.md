---
page_id: daemons/bgpd.md
okf_level: L3-daemon
claims: yes
verified: full
service: svc:bgpd
---
## Functionality

- svc:bgpd is a service in the fused graph; its functional domain is D3063a0b0. [a7978249]
- svc:bgpd publishes 27 message types toward the ZAPI bus (ZEBRA_ADVERTISE_ALL_VNI, ZEBRA_ADVERTISE_DEFAULT_GW, ZEBRA_ADVERTISE_SUBNET, ...). [a2ccd54d]
- It handles 30 notification/event types from the bus (ZEBRA_FEC_UPDATE, ZEBRA_INTERFACE_ADDRESS_ADD, ZEBRA_INTERFACE_ADDRESS_DELETE, ...). [a8b1b604]
- Northbound contracts: frr-bgp-route-map(65) — 65 YANG paths across 68 NB handler tables. [a6338b18]
- Measured roles: zapi-client, zapi-publisher. [a270cdb1]
- bgpd:bgp — 697 functions; anchors: bgp_route_next (bgpd/bgp_table.h), bgp_dest_unlock_node (bgpd/bgp_table.c), bgp_table_top (bgpd/bgp_table.h), bgp_update (bgpd/bgp_route.c). [ae847f47]
- bgpd:peer — 607 functions; anchors: bgp_debug_neighbor_events (bgpd/bgp_debug.c), peer_set_last_reset (bgpd/bgpd.h), peer_delete (bgpd/bgpd.c), peer_notify_config_change (bgpd/bgpd.c). [a4f40fd9]
- bgpd:bgp — 556 functions; anchors: bgp_attr_intern (bgpd/bgp_attr.c), bgp_attr_flush (bgpd/bgp_attr.c), bgp_attr_parse (bgpd/bgp_attr.c), bgp_attr_unintern_sub (bgpd/bgp_attr.c). [a625f059]
- bgpd:bgp — 530 functions; anchors: bgp_lookup_by_vrf_id (bgpd/bgpd.c), bgp_evpn_local_vni_add (bgpd/bgp_evpn.c), bgp_show_ethernet_vpn (bgpd/bgp_evpn_vty.c), bgp_evpn_es_find (bgpd/bgp_evpn_mh.c). [a414da58]
- bgpd:peer — 331 functions; anchors: peer_and_group_lookup_vty (bgpd/bgp_vty.c), bgp_vty_return (bgpd/bgp_vty.c), peer_af_flag_unset_vty (bgpd/bgp_vty.c), peer_flag_set_vty (bgpd/bgp_vty.c). [ad885bf3]
- bgpd:bgp — 308 functions; anchors: as_list_list_prev (bgpd/bgp_aspath.h), bgp_ac_neighbor (bgpd/bgp_vty.c), bgp_adv_fifo_next (bgpd/bgp_advertise.h), bgp_adv_fifo_prev (bgpd/bgp_advertise.h). [ac1fc9e0]
- bgpd:bgp — 306 functions; anchors: bgp_get_default (bgpd/bgpd.c), vpn_leak_postchange (bgpd/bgp_mplsvpn.h), bgp_delete (bgpd/bgpd.c), vpn_leak_prechange (bgpd/bgp_mplsvpn.h). [a751331c]
- 7813 intra-service `calls` edges reach other service partitions; densest target lib:list (2171 calls). [a5c7f6a0]
- 27 cross-service flows originate here; targets: svc:zebra. [a17e6c3c]
- 7 handled messages have no in-slice sender (orphan handlers). [a177e5a9]

## ZAPI contract — published (first 12)

- zapi:ZEBRA_ADVERTISE_ALL_VNI [abe021ef]
- zapi:ZEBRA_ADVERTISE_DEFAULT_GW [a82da21d]
- zapi:ZEBRA_ADVERTISE_SUBNET [a3b56db9]
- zapi:ZEBRA_ADVERTISE_SVI_MACIP [ad948363]
- zapi:ZEBRA_CLIENT_CAPABILITIES [a2ea0162]
- zapi:ZEBRA_DUPLICATE_ADDR_DETECTION [ad928eb5]
- zapi:ZEBRA_EVPN_REMOTE_NH_ADD [a99ff74b]
- zapi:ZEBRA_EVPN_REMOTE_NH_DEL [acc566dc]
- zapi:ZEBRA_IPSET_CREATE [aa45ed9a]
- zapi:ZEBRA_IPSET_DESTROY [a919ed71]
- zapi:ZEBRA_IPSET_ENTRY_ADD [a36d1ce3]
- zapi:ZEBRA_IPSET_ENTRY_DELETE [a9b55f7c]

## ZAPI contract — handled (first 12)

- zapi:ZEBRA_FEC_UPDATE [ab7449cb]
- zapi:ZEBRA_INTERFACE_ADDRESS_ADD [a6e32beb]
- zapi:ZEBRA_INTERFACE_ADDRESS_DELETE [a116ae9f]
- zapi:ZEBRA_INTERFACE_NBR_ADDRESS_ADD [a0213eb3]
- zapi:ZEBRA_INTERFACE_NBR_ADDRESS_DELETE [aac7f786]
- zapi:ZEBRA_IPSET_ENTRY_NOTIFY_OWNER [a9d694b4]
- zapi:ZEBRA_IPSET_NOTIFY_OWNER [a07a745d]
- zapi:ZEBRA_IPTABLE_NOTIFY_OWNER [a92f4f52]
- zapi:ZEBRA_IP_PREFIX_ROUTE_ADD [a324cc47]
- zapi:ZEBRA_IP_PREFIX_ROUTE_DEL [a2d63596]
- zapi:ZEBRA_L3VNI_ADD [aa1a5127]
- zapi:ZEBRA_L3VNI_DEL [ae5c17cb]


## Anchor ledger

| chip | refs |
|---|---|
| [a7978249] | N:svc:bgpd · C:D3063a0b0 |
| [a2ccd54d] | S:pack.D3063a0b0.published · E:svc:bgpd|publishes|zapi:ZEBRA_ADVERTISE_ALL_VNI · E:svc:bgpd|publishes|zapi:ZEBRA_ADVERTISE_DEFAULT_GW · E:svc:bgpd|publishes|zapi:ZEBRA_ADVERTISE_SUBNET |
| [a8b1b604] | S:pack.D3063a0b0.handled · E:svc:bgpd|handles|zapi:ZEBRA_FEC_UPDATE · E:svc:bgpd|handles|zapi:ZEBRA_INTERFACE_ADDRESS_ADD · E:svc:bgpd|handles|zapi:ZEBRA_INTERFACE_ADDRESS_DELETE |
| [a6338b18] | S:pack.D3063a0b0.yang.total · S:pack.D3063a0b0.nb_tables · S:pack.D3063a0b0.yang.frr-bgp-route-map |
| [a270cdb1] | S:pack.D3063a0b0.roles |
| [ae847f47] | C:M05216fef · S:pack.D3063a0b0.mod.M05216fef.size · P:bgpd/bgp_table.h · P:bgpd/bgp_table.c · P:bgpd/bgp_route.c |
| [a4f40fd9] | C:M5fbc08dc · S:pack.D3063a0b0.mod.M5fbc08dc.size · P:bgpd/bgp_debug.c · P:bgpd/bgpd.h · P:bgpd/bgpd.c |
| [a625f059] | C:M8a2078aa · S:pack.D3063a0b0.mod.M8a2078aa.size · P:bgpd/bgp_attr.c · P:bgpd/bgp_route.c · P:bgpd/bgp_ecommunity.c |
| [a414da58] | C:M0db7f269 · S:pack.D3063a0b0.mod.M0db7f269.size · P:bgpd/bgpd.c · P:bgpd/bgp_evpn.c · P:bgpd/bgp_evpn_vty.c |
| [ad885bf3] | C:M177e2382 · S:pack.D3063a0b0.mod.M177e2382.size · P:bgpd/bgp_vty.c |
| [ac1fc9e0] | C:M96bf08bc · S:pack.D3063a0b0.mod.M96bf08bc.size · P:bgpd/bgp_aspath.h · P:bgpd/bgp_vty.c · P:bgpd/bgp_advertise.h |
| [a751331c] | C:M68866613 · S:pack.D3063a0b0.mod.M68866613.size · P:bgpd/bgpd.c · P:bgpd/bgp_mplsvpn.h · P:bgpd/bgp_zebra.c |
| [a5c7f6a0] | S:pack.D3063a0b0.bridge.total · S:pack.D3063a0b0.bridge.lib:list |
| [a17e6c3c] | S:pack.D3063a0b0.flows.out · F:zapi.cross_svc_flows |
| [a177e5a9] | S:pack.D3063a0b0.orphan.n · F:zapi.orphan_handlers_no_sender_in_slice |
| [abe021ef] | N:zapi:ZEBRA_ADVERTISE_ALL_VNI · E:svc:bgpd|publishes|zapi:ZEBRA_ADVERTISE_ALL_VNI |
| [a82da21d] | N:zapi:ZEBRA_ADVERTISE_DEFAULT_GW · E:svc:bgpd|publishes|zapi:ZEBRA_ADVERTISE_DEFAULT_GW |
| [a3b56db9] | N:zapi:ZEBRA_ADVERTISE_SUBNET · E:svc:bgpd|publishes|zapi:ZEBRA_ADVERTISE_SUBNET |
| [ad948363] | N:zapi:ZEBRA_ADVERTISE_SVI_MACIP · E:svc:bgpd|publishes|zapi:ZEBRA_ADVERTISE_SVI_MACIP |
| [a2ea0162] | N:zapi:ZEBRA_CLIENT_CAPABILITIES · E:svc:bgpd|publishes|zapi:ZEBRA_CLIENT_CAPABILITIES |
| [ad928eb5] | N:zapi:ZEBRA_DUPLICATE_ADDR_DETECTION · E:svc:bgpd|publishes|zapi:ZEBRA_DUPLICATE_ADDR_DETECTION |
| [a99ff74b] | N:zapi:ZEBRA_EVPN_REMOTE_NH_ADD · E:svc:bgpd|publishes|zapi:ZEBRA_EVPN_REMOTE_NH_ADD |
| [acc566dc] | N:zapi:ZEBRA_EVPN_REMOTE_NH_DEL · E:svc:bgpd|publishes|zapi:ZEBRA_EVPN_REMOTE_NH_DEL |
| [aa45ed9a] | N:zapi:ZEBRA_IPSET_CREATE · E:svc:bgpd|publishes|zapi:ZEBRA_IPSET_CREATE |
| [a919ed71] | N:zapi:ZEBRA_IPSET_DESTROY · E:svc:bgpd|publishes|zapi:ZEBRA_IPSET_DESTROY |
| [a36d1ce3] | N:zapi:ZEBRA_IPSET_ENTRY_ADD · E:svc:bgpd|publishes|zapi:ZEBRA_IPSET_ENTRY_ADD |
| [a9b55f7c] | N:zapi:ZEBRA_IPSET_ENTRY_DELETE · E:svc:bgpd|publishes|zapi:ZEBRA_IPSET_ENTRY_DELETE |
| [ab7449cb] | N:zapi:ZEBRA_FEC_UPDATE · E:svc:bgpd|handles|zapi:ZEBRA_FEC_UPDATE |
| [a6e32beb] | N:zapi:ZEBRA_INTERFACE_ADDRESS_ADD · E:svc:bgpd|handles|zapi:ZEBRA_INTERFACE_ADDRESS_ADD |
| [a116ae9f] | N:zapi:ZEBRA_INTERFACE_ADDRESS_DELETE · E:svc:bgpd|handles|zapi:ZEBRA_INTERFACE_ADDRESS_DELETE |
| [a0213eb3] | N:zapi:ZEBRA_INTERFACE_NBR_ADDRESS_ADD · E:svc:bgpd|handles|zapi:ZEBRA_INTERFACE_NBR_ADDRESS_ADD |
| [aac7f786] | N:zapi:ZEBRA_INTERFACE_NBR_ADDRESS_DELETE · E:svc:bgpd|handles|zapi:ZEBRA_INTERFACE_NBR_ADDRESS_DELETE |
| [a9d694b4] | N:zapi:ZEBRA_IPSET_ENTRY_NOTIFY_OWNER · E:svc:bgpd|handles|zapi:ZEBRA_IPSET_ENTRY_NOTIFY_OWNER |
| [a07a745d] | N:zapi:ZEBRA_IPSET_NOTIFY_OWNER · E:svc:bgpd|handles|zapi:ZEBRA_IPSET_NOTIFY_OWNER |
| [a92f4f52] | N:zapi:ZEBRA_IPTABLE_NOTIFY_OWNER · E:svc:bgpd|handles|zapi:ZEBRA_IPTABLE_NOTIFY_OWNER |
| [a324cc47] | N:zapi:ZEBRA_IP_PREFIX_ROUTE_ADD · E:svc:bgpd|handles|zapi:ZEBRA_IP_PREFIX_ROUTE_ADD |
| [a2d63596] | N:zapi:ZEBRA_IP_PREFIX_ROUTE_DEL · E:svc:bgpd|handles|zapi:ZEBRA_IP_PREFIX_ROUTE_DEL |
| [aa1a5127] | N:zapi:ZEBRA_L3VNI_ADD · E:svc:bgpd|handles|zapi:ZEBRA_L3VNI_ADD |
| [ae5c17cb] | N:zapi:ZEBRA_L3VNI_DEL · E:svc:bgpd|handles|zapi:ZEBRA_L3VNI_DEL |
