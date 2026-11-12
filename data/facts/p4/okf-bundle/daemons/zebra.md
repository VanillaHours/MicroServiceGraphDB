---
page_id: daemons/zebra.md
okf_level: L3-daemon
claims: yes
verified: full
service: svc:zebra
---
## Functionality

- svc:zebra is a service in the fused graph; its functional domain is D4b2a9ab8. [a0e6e595]
- svc:zebra publishes 44 message types toward the ZAPI bus (ZEBRA_BFD_DEST_REPLAY, ZEBRA_CAPABILITIES, ZEBRA_CLIENT_CLOSE_NOTIFY, ...). [a33adfed]
- It handles 94 notification/event types from the bus (ZEBRA_ADVERTISE_ALL_VNI, ZEBRA_ADVERTISE_DEFAULT_GW, ZEBRA_ADVERTISE_SUBNET, ...). [acec72f5]
- Northbound contracts: frr-zebra(164), frr-zebra-route-map(6) — 170 YANG paths across 183 NB handler tables. [a5771c3e]
- Measured roles: zapi-publisher, zapi-server. [a0c06897]
- zebra:dplane — 407 functions; anchors: backup_nexthop_recursive_use_enable_magic (zebra/zebra_vty.c), dplane_ctx_list_prev (zebra/zebra_dplane.c), dplane_intf_extra_list_prev (zebra/zebra_dplane.c), dplane_prov_list_prev (zebra/zebra_dplane.c). [a425c705]
- zebra:zebra — 345 functions; anchors: is_evpn_enabled (zebra/zebra_vxlan.h), zebra_vrf_get_evpn (zebra/zebra_router.h), zebra_evpn_lookup (zebra/zebra_evpn.c), zebra_vxlan_if_update_vni (zebra/zebra_vxlan_if.c). [a5ee8cef]
- zebra:rib — 257 functions; anchors: re_list_first (zebra/rib.h), re_list_next (zebra/rib.h), zebra_vrf_table (zebra/zebra_vrf.c), process_subq_early_route_add (zebra/zebra_rib.c). [aeeea52d]
- zebra:netlink — 224 functions; anchors: netlink_route_multipath_msg_encode (zebra/rt_netlink.c), netlink_route_change_read_unicast_internal (zebra/rt_netlink.c), kernel_dplane_log_detail (zebra/zebra_dplane.c), netlink_nexthop_msg_encode (zebra/rt_netlink.c). [a39b480c]
- zebra:dplane — 220 functions; anchors: netlink_parse_info (zebra/kernel_netlink.c), kernel_dplane_process_func (zebra/zebra_dplane.c), nl_msg_type_to_str (zebra/kernel_netlink.c), dplane_provider_enqueue_out_ctx (zebra/zebra_dplane.c). [a84ef0c7]
- zebra:zserv — 173 functions; anchors: zserv_client_list_first (zebra/zserv.h), zserv_client_list_next (zebra/zserv.h), zserv_send_message (zebra/zserv.c), zsend_rule_notify_owner (zebra/zapi_msg.c). [a65b2f01]
- zebra:nhlfe — 171 functions; anchors: zebra_vrf_lookup_by_id (zebra/zebra_vrf.c), nhlfe_list_first (zebra/zebra_mpls.h), nhlfe_list_next_safe (zebra/zebra_mpls.h), lsp_uninstall (zebra/zebra_mpls.c). [a7128326]
- 5203 intra-service `calls` edges reach other service partitions; densest target lib:zlog (1426 calls). [a9e82b74]
- 44 cross-service flows originate here; targets: svc:bgpd, svc:lib, svc:ospfd, svc:staticd. [a8ad7dfa]
- 34 handled messages have no in-slice sender (orphan handlers). [a229a26b]

## ZAPI contract — published (first 12)

- zapi:ZEBRA_BFD_DEST_REPLAY [a5724978]
- zapi:ZEBRA_CAPABILITIES [af6ac915]
- zapi:ZEBRA_CLIENT_CLOSE_NOTIFY [ad14d95b]
- zapi:ZEBRA_ERROR [af0a9126]
- zapi:ZEBRA_FEC_UPDATE [a9df89ac]
- zapi:ZEBRA_GET_LABEL_CHUNK [a8b6d2a9]
- zapi:ZEBRA_GET_TABLE_CHUNK [a86cf124]
- zapi:ZEBRA_GRE_UPDATE [a00a6a15]
- zapi:ZEBRA_INTERFACE_ADD [ad189903]
- zapi:ZEBRA_INTERFACE_ADDRESS_ADD [a9b330da]
- zapi:ZEBRA_INTERFACE_ADDRESS_DELETE [ae59cf87]
- zapi:ZEBRA_INTERFACE_BFD_DEST_UPDATE [a7a3314c]

## ZAPI contract — handled (first 12)

- zapi:ZEBRA_ADVERTISE_ALL_VNI [addf6671]
- zapi:ZEBRA_ADVERTISE_DEFAULT_GW [ad727056]
- zapi:ZEBRA_ADVERTISE_SUBNET [ad42c26d]
- zapi:ZEBRA_ADVERTISE_SVI_MACIP [a7e2ba25]
- zapi:ZEBRA_BFD_CLIENT_REGISTER [a0d89d09]
- zapi:ZEBRA_BFD_DEST_DEREGISTER [a885d035]
- zapi:ZEBRA_BFD_DEST_REGISTER [a21f6f86]
- zapi:ZEBRA_BFD_DEST_REPLAY [a1cccebe]
- zapi:ZEBRA_BFD_DEST_UPDATE [a5e88b33]
- zapi:ZEBRA_CLIENT_CAPABILITIES [a4cf96f4]
- zapi:ZEBRA_CONFIGURE_ARP [a1527306]
- zapi:ZEBRA_DUPLICATE_ADDR_DETECTION [a13448fe]


## Anchor ledger

| chip | refs |
|---|---|
| [a0e6e595] | N:svc:zebra · C:D4b2a9ab8 |
| [a33adfed] | S:pack.D4b2a9ab8.published · E:svc:zebra|publishes|zapi:ZEBRA_BFD_DEST_REPLAY · E:svc:zebra|publishes|zapi:ZEBRA_CAPABILITIES · E:svc:zebra|publishes|zapi:ZEBRA_CLIENT_CLOSE_NOTIFY |
| [acec72f5] | S:pack.D4b2a9ab8.handled · E:svc:zebra|handles|zapi:ZEBRA_ADVERTISE_ALL_VNI · E:svc:zebra|handles|zapi:ZEBRA_ADVERTISE_DEFAULT_GW · E:svc:zebra|handles|zapi:ZEBRA_ADVERTISE_SUBNET |
| [a5771c3e] | S:pack.D4b2a9ab8.yang.total · S:pack.D4b2a9ab8.nb_tables · S:pack.D4b2a9ab8.yang.frr-zebra · S:pack.D4b2a9ab8.yang.frr-zebra-route-map |
| [a0c06897] | S:pack.D4b2a9ab8.roles |
| [a425c705] | C:M6816d16c · S:pack.D4b2a9ab8.mod.M6816d16c.size · P:zebra/zebra_vty.c · P:zebra/zebra_dplane.c |
| [a5ee8cef] | C:M11ed049a · S:pack.D4b2a9ab8.mod.M11ed049a.size · P:zebra/zebra_vxlan.h · P:zebra/zebra_router.h · P:zebra/zebra_evpn.c |
| [aeeea52d] | C:M749027f4 · S:pack.D4b2a9ab8.mod.M749027f4.size · P:zebra/rib.h · P:zebra/zebra_vrf.c · P:zebra/zebra_rib.c |
| [a39b480c] | C:M36d601bd · S:pack.D4b2a9ab8.mod.M36d601bd.size · P:zebra/rt_netlink.c · P:zebra/zebra_dplane.c · P:zebra/zebra_rib.c |
| [a84ef0c7] | C:M761377d9 · S:pack.D4b2a9ab8.mod.M761377d9.size · P:zebra/kernel_netlink.c · P:zebra/zebra_dplane.c · P:zebra/rt_netlink.c |
| [a65b2f01] | C:Med7a3cb2 · S:pack.D4b2a9ab8.mod.Med7a3cb2.size · P:zebra/zserv.h · P:zebra/zserv.c · P:zebra/zapi_msg.c |
| [a7128326] | C:Mf3415498 · S:pack.D4b2a9ab8.mod.Mf3415498.size · P:zebra/zebra_vrf.c · P:zebra/zebra_mpls.h · P:zebra/zebra_mpls.c |
| [a9e82b74] | S:pack.D4b2a9ab8.bridge.total · S:pack.D4b2a9ab8.bridge.lib:zlog |
| [a8ad7dfa] | S:pack.D4b2a9ab8.flows.out · F:zapi.cross_svc_flows |
| [a229a26b] | S:pack.D4b2a9ab8.orphan.n · F:zapi.orphan_handlers_no_sender_in_slice |
| [a5724978] | N:zapi:ZEBRA_BFD_DEST_REPLAY · E:svc:zebra|publishes|zapi:ZEBRA_BFD_DEST_REPLAY |
| [af6ac915] | N:zapi:ZEBRA_CAPABILITIES · E:svc:zebra|publishes|zapi:ZEBRA_CAPABILITIES |
| [ad14d95b] | N:zapi:ZEBRA_CLIENT_CLOSE_NOTIFY · E:svc:zebra|publishes|zapi:ZEBRA_CLIENT_CLOSE_NOTIFY |
| [af0a9126] | N:zapi:ZEBRA_ERROR · E:svc:zebra|publishes|zapi:ZEBRA_ERROR |
| [a9df89ac] | N:zapi:ZEBRA_FEC_UPDATE · E:svc:zebra|publishes|zapi:ZEBRA_FEC_UPDATE |
| [a8b6d2a9] | N:zapi:ZEBRA_GET_LABEL_CHUNK · E:svc:zebra|publishes|zapi:ZEBRA_GET_LABEL_CHUNK |
| [a86cf124] | N:zapi:ZEBRA_GET_TABLE_CHUNK · E:svc:zebra|publishes|zapi:ZEBRA_GET_TABLE_CHUNK |
| [a00a6a15] | N:zapi:ZEBRA_GRE_UPDATE · E:svc:zebra|publishes|zapi:ZEBRA_GRE_UPDATE |
| [ad189903] | N:zapi:ZEBRA_INTERFACE_ADD · E:svc:zebra|publishes|zapi:ZEBRA_INTERFACE_ADD |
| [a9b330da] | N:zapi:ZEBRA_INTERFACE_ADDRESS_ADD · E:svc:zebra|publishes|zapi:ZEBRA_INTERFACE_ADDRESS_ADD |
| [ae59cf87] | N:zapi:ZEBRA_INTERFACE_ADDRESS_DELETE · E:svc:zebra|publishes|zapi:ZEBRA_INTERFACE_ADDRESS_DELETE |
| [a7a3314c] | N:zapi:ZEBRA_INTERFACE_BFD_DEST_UPDATE · E:svc:zebra|publishes|zapi:ZEBRA_INTERFACE_BFD_DEST_UPDATE |
| [addf6671] | N:zapi:ZEBRA_ADVERTISE_ALL_VNI · E:svc:zebra|handles|zapi:ZEBRA_ADVERTISE_ALL_VNI |
| [ad727056] | N:zapi:ZEBRA_ADVERTISE_DEFAULT_GW · E:svc:zebra|handles|zapi:ZEBRA_ADVERTISE_DEFAULT_GW |
| [ad42c26d] | N:zapi:ZEBRA_ADVERTISE_SUBNET · E:svc:zebra|handles|zapi:ZEBRA_ADVERTISE_SUBNET |
| [a7e2ba25] | N:zapi:ZEBRA_ADVERTISE_SVI_MACIP · E:svc:zebra|handles|zapi:ZEBRA_ADVERTISE_SVI_MACIP |
| [a0d89d09] | N:zapi:ZEBRA_BFD_CLIENT_REGISTER · E:svc:zebra|handles|zapi:ZEBRA_BFD_CLIENT_REGISTER |
| [a885d035] | N:zapi:ZEBRA_BFD_DEST_DEREGISTER · E:svc:zebra|handles|zapi:ZEBRA_BFD_DEST_DEREGISTER |
| [a21f6f86] | N:zapi:ZEBRA_BFD_DEST_REGISTER · E:svc:zebra|handles|zapi:ZEBRA_BFD_DEST_REGISTER |
| [a1cccebe] | N:zapi:ZEBRA_BFD_DEST_REPLAY · E:svc:zebra|handles|zapi:ZEBRA_BFD_DEST_REPLAY |
| [a5e88b33] | N:zapi:ZEBRA_BFD_DEST_UPDATE · E:svc:zebra|handles|zapi:ZEBRA_BFD_DEST_UPDATE |
| [a4cf96f4] | N:zapi:ZEBRA_CLIENT_CAPABILITIES · E:svc:zebra|handles|zapi:ZEBRA_CLIENT_CAPABILITIES |
| [a1527306] | N:zapi:ZEBRA_CONFIGURE_ARP · E:svc:zebra|handles|zapi:ZEBRA_CONFIGURE_ARP |
| [a13448fe] | N:zapi:ZEBRA_DUPLICATE_ADDR_DETECTION · E:svc:zebra|handles|zapi:ZEBRA_DUPLICATE_ADDR_DETECTION |
