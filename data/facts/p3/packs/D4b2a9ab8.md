# Domain pack `D4b2a9ab8` — zebra [46z/170y]

Level L1 (functional domain) · gamma 1.2 · seed 42 · Leiden RBConfiguration

## Functionality (rule-derived from graph facts)

- zebra is the ZAPI message bus: handles 94 message types published by the route daemons (bgpd, ospfd) and publishes 44 notification/event types back to clients
- northbound contracts: 170 YANG paths across 2 modules (frr-zebra(164), frr-zebra-route-map(6))

Role tags: zapi-publisher, zapi-server
Members: 217 backbone nodes — 1 svc, 46 zapi, 170 yang

## ZAPI contract

- `svc:zebra` handles 42: `ZEBRA_BFD_CLIENT_REGISTER`, `ZEBRA_BFD_DEST_DEREGISTER`, `ZEBRA_BFD_DEST_REGISTER`, `ZEBRA_BFD_DEST_REPLAY`, `ZEBRA_BFD_DEST_UPDATE`, `ZEBRA_CONFIGURE_ARP`, `ZEBRA_FEC_REGISTER`, `ZEBRA_FEC_UNREGISTER`, `ZEBRA_GET_LABEL_CHUNK`, `ZEBRA_GET_TABLE_CHUNK`, `ZEBRA_GRE_SOURCE_SET`, `ZEBRA_IPMR_ROUTE_STATS` ...
- `svc:zebra` publishes 12: `ZEBRA_BFD_DEST_REPLAY`, `ZEBRA_GET_LABEL_CHUNK`, `ZEBRA_GET_TABLE_CHUNK`, `ZEBRA_GRE_UPDATE`, `ZEBRA_IPMR_ROUTE_STATS`, `ZEBRA_LABEL_MANAGER_CONNECT`, `ZEBRA_NEXTHOP_LOOKUP`, `ZEBRA_NHG_NOTIFY_OWNER`, `ZEBRA_PW_STATUS_UPDATE`, `ZEBRA_SRV6_MANAGER_GET_LOCATOR_CHUNK`, `ZEBRA_SR_POLICY_NOTIFY_STATUS`, `ZEBRA_TABLE_MANAGER_CONNECT`

## Northbound (YANG) contracts

- frr-zebra: 164 paths
- frr-zebra-route-map: 6 paths

## Boundary (edges to other domains)

- -> `D1737981e` (lib [34z/147y]): handles×24, publishes×14
- -> `D3063a0b0` (bgpd [41z/65y]): handles×23, publishes×12
- -> `Ded29f1c0` (ospfd [15z/1y]): handles×7, publishes×7
- -> `Dc32724de` (staticd [6z/27y]): publishes×3

## Cross-service ZAPI flows in this domain

- 6 flows: `lib→zebra`, `zebra→bgpd`, `zebra→lib`

## Code modules (L3)

| Module | Size | Tags | Top anchors (file) |
|---|---|---|---|
| `Mb5ff12d4` zebra:unlinked | 2941 | - | no intra-service call edges observed |
| `M6816d16c` zebra:dplane | 407 | - | `backup_nexthop_recursive_use_enable_magic` (zebra/zebra_vty.c); `dplane_ctx_list_prev` (zebra/zebra_dplane.c); `dplane_intf_extra_list_const_first` (None) |
| `M11ed049a` zebra:zebra | 345 | - | `is_evpn_enabled` (zebra/zebra_vxlan.h); `zebra_vrf_get_evpn` (zebra/zebra_router.h); `zebra_evpn_lookup` (zebra/zebra_evpn.c) |
| `M749027f4` zebra:rib | 257 | - | `rib_dest_from_rnode` (None); `re_list_first` (zebra/rib.h); `re_list_next` (zebra/rib.h) |
| `M36d601bd` zebra:netlink | 224 | - | `dplane_ctx_get_op` (None); `netlink_route_multipath_msg_encode` (zebra/rt_netlink.c); `netlink_route_change_read_unicast_internal` (zebra/rt_netlink.c) |
| `M761377d9` zebra:dplane | 220 | - | `netlink_parse_info` (zebra/kernel_netlink.c); `kernel_dplane_process_func` (zebra/zebra_dplane.c); `nl_msg_type_to_str` (zebra/kernel_netlink.c) |
| `Med7a3cb2` zebra:zserv | 173 | zapi-client | `zserv_client_list_first` (zebra/zserv.h); `zserv_client_list_next` (zebra/zserv.h); `zserv_send_message` (zebra/zserv.c) |
| `Mf3415498` zebra:nhlfe | 171 | - | `zebra_vrf_lookup_by_id` (zebra/zebra_vrf.c); `nhlfe_list_first` (zebra/zebra_mpls.h); `nhlfe_list_next_safe` (zebra/zebra_mpls.h) |
| `Md257f514` zebra:dplane | 170 | - | `zebra_ns_lookup` (zebra/zebra_ns.c); `dplane_ctx_alloc` (zebra/zebra_dplane.c); `dplane_ctx_free` (zebra/zebra_dplane.c) |
| `M9a38c8b6` zebra:zebra | 168 | - | `zebra_srv6_get_default` (zebra/zebra_srv6.c); `zebra_srv6_sid_format_changed_cb` (zebra/zebra_srv6.c); `no_srv6_locator` (zebra/zebra_srv6_vty.c) |
| `M884ca7f8` zebra:netlink | 135 | - | `netlink_link_change` (zebra/if_netlink.c); `netlink_route_read_unicast_ctx` (zebra/rt_netlink.c); `netlink_macfdb_change` (zebra/rt_netlink.c) |
| `Mf7a3167a` zebra:zebra | 134 | - | `zebra_evpn_es_local_info_set` (zebra/zebra_evpn_mh.c); `zebra_evpn_local_es_update` (zebra/zebra_evpn_mh.c); `zebra_evpn_es_br_port_dplane_update` (zebra/zebra_evpn_mh.c) |
| `Ma1f4c59c` zebra:zebra | 130 | - | `zebra_evpn_mac_lookup` (zebra/zebra_evpn_mac.c); `zebra_evpn_sync_mac_dp_install` (zebra/zebra_evpn_mac.c); `zebra_evpn_local_neigh_update` (zebra/zebra_evpn_neigh.c) |
| `Mb095eb5a` zebra:if | 125 | - | `zebra_if_dplane_ifp_handling` (zebra/interface.c); `if_down` (zebra/interface.c); `interface_update_l2info` (zebra/interface.c) |
| `M84e7242a` zebra:nhg | 123 | - | `nhg_connected_tree_first` (zebra/zebra_nhg_private.h); `nhg_ctx_process_new` (zebra/zebra_nhg.c); `nhg_connected_tree_next` (zebra/zebra_nhg_private.h) |
| `M08c681c1` zebra:rtadv | 113 | - | `zvrf_id` (None); `rtadv_send_packet` (zebra/rtadv.c); `adv_if_list_count` (None) |
| `M6e57a9ac` zebra:zebra | 109 | cli | `zebra_evaluate_rnh` (zebra/zebra_rnh.c); `zebra_pw_change` (zebra/zebra_pw.c); `zebra_pw_del` (zebra/zebra_pw.c) |
| `M78454a78` zebra:zebra | 92 | - | `main` (zebra/main.c); `_hook_typecheck_zserv_client_close` (None); `zebra_finalize` (zebra/main.c) |
| `Mc1a75b29` zebra:if | 72 | - | `zebra_if_addr_update_ctx` (zebra/interface.c); `if_refresh` (None); `if_set_flags` (zebra/ioctl.c) |
| `M0c304f00` zebra:opq | 51 | - | `sigint` (zebra/main.c); `handle_opq_notif_req` (zebra/zebra_opaque.c); `handle_opq_registration` (zebra/zebra_opaque.c) |
| `M9254c380` zebra:parse | 45 | - | `parse_netlink_msg` (zebra/fpm_listener.c); `sigusr1_handler` (zebra/fpm_listener.c); `get_timestamp` (None) |
| `M63859ec5` zebra:dump | 39 | - | `nl_dump` (zebra/debug_nl.c); `flag_write` (None); `nllink_dump` (zebra/debug_nl.c) |
| `M58343762` zebra:zebra | 38 | - | `zebra_neigh_free` (zebra/zebra_neigh.c); `zebra_neigh_show` (zebra/zebra_neigh.c); `zebra_pbr_add_rule` (zebra/zebra_pbr.c) |
| `Mdf340e26` zebra:mpls | 33 | - | `mq_add_handler` (zebra/zebra_rib.c); `mpls_zapi_labels_process` (zebra/zebra_rib.c); `rib_add_gr_run` (zebra/zebra_rib.c) |
| `Mff698da4` zebra:ipforward | 26 | - | `ipforward` (zebra/ipforward_proc.c); `config_write_protocol` (zebra/zebra_vty.c); `ipforward_ipv6` (None) |
| `Mdb4d7fb2` zebra:show | 24 | - | `if_dump_vty` (zebra/interface.c); `if_dump_vty_json` (zebra/interface.c); `show_interface_magic` (zebra/interface.c) |
| `Mf14c2f93` zebra:dplane | 23 | - | `netlink_tfilter_flower_put_options` (zebra/tc_netlink.c); `netlink_tfilter_msg_encode` (zebra/tc_netlink.c); `dplane_ctx_tc_filter_get_eth_proto` (None) |
| `Ma8b65012` zebra:label | 22 | - | `assign_label_chunk` (zebra/label_manager.c); `assign_specific_label_chunk` (zebra/label_manager.c); `release_daemon_label_chunks` (zebra/label_manager.c) |
| `M8d105308` zebra:zserv | 13 | zapi-client | `zserv_handle_commands` (zebra/zapi_msg.c); `zsend_error_msg` (zebra/zapi_msg.c); `zserv_client_fail` (zebra/zserv.c) |
| `Maeefa3dc` zebra:lib | 11 | - | `link_param_cmd_set_float` (None); `lib_interface_zebra_link_params_available_bandwidth_modify` (zebra/zebra_nb_config.c); `lib_interface_zebra_link_params_max_bandwidth_destroy` (zebra/zebra_nb_config.c) |
| `M390e7d14` zebra:zebra | 10 | - | `zebra_vrf_alloc` (zebra/zebra_vrf.c); `zebra_vrf_new` (zebra/zebra_vrf.c); `zebra_pw_init_vrf` (zebra/zebra_pw.c) |
| `Ma53a1dab` zebra:lib | 10 | - | `zebra_vrf_indent_cli_write` (zebra/zebra_cli.c); `lib_vrf_mpls_fec_nexthop_resolution_cli_write` (zebra/zebra_cli.c); `lib_vrf_zebra_filter_nht_cli_write` (zebra/zebra_cli.c) |
| `M310102fb` zebra:zebra | 9 | - | `show_evpn_access_vlan_magic` (zebra/zebra_vty.c); `zebra_evpn_acc_vl_show_entry_detail` (zebra/zebra_evpn_mh.c); `zebra_evpn_acc_vl_json_fill` (zebra/zebra_evpn_mh.c) |
| `Mbb221a0f` zebra:lib | 8 | - | `link_param_cmd_unset` (None); `lib_interface_zebra_link_params_available_bandwidth_destroy` (zebra/zebra_nb_config.c); `lib_interface_zebra_link_params_delay_destroy` (zebra/zebra_nb_config.c) |
| `M671c4009` zebra:zebra | 7 | - | `zebra_import_kernel_table_xpath` (zebra/zebra_cli.c); `ip_zebra_import_table_distance_magic` (zebra/zebra_cli.c); `ipv6_zebra_import_table_distance_magic` (zebra/zebra_cli.c) |
| `M0f151d26` zebra:lib | 7 | - | `table_manager_range` (zebra/table_manager.c); `table_range_validate` (zebra/zebra_nb_config.c); `lib_vrf_zebra_netns_table_range_create` (zebra/zebra_nb_config.c) |
| `M91b44ac9` zebra:hook | 6 | - | `zebra_mlag_module_init` (zebra/zebra_mlag_private.c); `_hook_typecheck_zebra_mlag_private_cleanup_data` (None); `_hook_typecheck_zebra_mlag_private_close_channel` (None) |
| `Md7f46b4f` zebra:pref64 | 6 | - | `pref64_cmp` (zebra/rtadv.c); `pref64_advs_const_find_gteq` (zebra/rtadv.c); `pref64_advs_const_find_lt` (zebra/rtadv.c) |
| `M234c1383` zebra:evpn | 5 | - | `evpn_accept_bgp_seq_magic` (zebra/zebra_vty.c); `no_evpn_accept_bgp_seq_magic` (zebra/zebra_vty.c); `zebra_vxlan_set_accept_bgp_seq` (None) |
| `Mc45fffa8` zebra:zebra | 5 | - | `zebra_pbr_show_ipset_entry_walkcb` (zebra/zebra_pbr.c); `hook_call_zebra_pbr_ipset_entry_get_stat` (None); `zebra_pbr_display_icmp` (zebra/zebra_pbr.c) |
| `Me89a1c94` zebra:lib | 5 | - | `link_param_cmd_set_uint32` (None); `lib_interface_zebra_link_params_delay_modify` (zebra/zebra_nb_config.c); `lib_interface_zebra_link_params_delay_variation_modify` (zebra/zebra_nb_config.c) |
| `M07cb66e3` zebra:pref64 | 5 | - | `pref64_advs_const_find` (zebra/rtadv.c); `pref64_advs_find` (zebra/rtadv.c); `rtadv_pref64_set` (zebra/rtadv.c) |
| `M5d1331e1` zebra:dplane | 4 | - | `dplane_intf_extra_list_const_next` (None); `dplane_intf_extra_list_next` (zebra/zebra_dplane.c); `dplane_ctx_intf_extra_next` (zebra/zebra_dplane.c) |
| `Mb4e151b7` zebra:zebra | 4 | - | `zebra_pbr_show_iptable_unit` (zebra/zebra_pbr.c); `hook_call_zebra_pbr_iptable_get_stat` (None); `zebra_pbr_show_iptable_walkcb` (zebra/zebra_pbr.c) |
| `M981276f3` zebra:zserv | 4 | zapi-client | `zserv_client_create` (zebra/zserv.c); `hook_call_zserv_client_connect` (None); `zserv_accept` (zebra/zserv.c) |
| `M0bcc5dc1` zebra:rtadv | 4 | - | `lib_interface_zebra_ipv6_router_advertisements_dnssl_dnssl_domain_create` (zebra/zebra_nb_config.c); `rtadv_dnssl_set` (zebra/rtadv.c); `rtadv_dnssl_encode` (None) |
| `M221b9839` zebra:zebra | 4 | - | `zebra_route_map_mark_update` (zebra/zebra_routemap.c); `zebra_route_map_add` (zebra/zebra_routemap.c); `zebra_route_map_delete` (zebra/zebra_routemap.c) |
| `Mcd6940af` zebra:host | 4 | rbtree | `rb_host_count` (zebra/zebra_vxlan.c); `zl3vni_print_nh` (zebra/zebra_vxlan.c); `host_rb_tree_entry_RB_MIN` (zebra/zebra_evpn_base.h) |

## Findings attached

- dropped-on-wire msgs: `ZEBRA_GRE_UPDATE`, `ZEBRA_NHG_NOTIFY_OWNER`, `ZEBRA_PW_STATUS_UPDATE`, `ZEBRA_SR_POLICY_NOTIFY_STATUS`
- orphan handlers (sender not in slice): 34 msgs

## Query hints

```
python3 kb.py cluster show D4b2a9ab8
python3 kb.py path svc:zebra svc:zebra   # cross-domain ZAPI path
python3 kb.py impact yang:<module>:<path>
```
