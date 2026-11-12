# Domain pack `Ded29f1c0` — ospfd [15z/1y]

Level L1 (functional domain) · gamma 1.2 · seed 42 · Leiden RBConfiguration

## Functionality (rule-derived from graph facts)

- ospfd is a route client: publishes 7 message types toward the ZAPI bus (capabilities, add, default_add, default_delete...) and handles 8 notifications from it
- northbound contracts: 1 YANG paths across 1 module (frr-ospf-route-map(1))

Role tags: zapi-client, zapi-publisher
Members: 17 backbone nodes — 1 svc, 15 zapi, 1 yang

## ZAPI contract

- `svc:ospfd` handles 8: `ZEBRA_CLIENT_CLOSE_NOTIFY`, `ZEBRA_INTERFACE_ADDRESS_ADD`, `ZEBRA_INTERFACE_ADDRESS_DELETE`, `ZEBRA_INTERFACE_LINK_PARAMS`, `ZEBRA_OPAQUE_MESSAGE`, `ZEBRA_REDISTRIBUTE_ROUTE_ADD`, `ZEBRA_REDISTRIBUTE_ROUTE_DEL`, `ZEBRA_ROUTER_ID_UPDATE`
- `svc:ospfd` publishes 7: `ZEBRA_CLIENT_CAPABILITIES`, `ZEBRA_REDISTRIBUTE_ADD`, `ZEBRA_REDISTRIBUTE_DEFAULT_ADD`, `ZEBRA_REDISTRIBUTE_DEFAULT_DELETE`, `ZEBRA_REDISTRIBUTE_DELETE`, `ZEBRA_ROUTE_ADD`, `ZEBRA_ROUTE_DELETE`

## Northbound (YANG) contracts

- frr-ospf-route-map: 1 paths

## Boundary (edges to other domains)

- -> `D4b2a9ab8` (zebra [46z/170y]): handles×7, publishes×7
- -> `D3063a0b0` (bgpd [41z/65y]): publishes×5, handles×6
- -> `D1737981e` (lib [34z/147y]): publishes×4
- -> `Dc32724de` (staticd [6z/27y]): handles×2

## Cross-service ZAPI flows in this domain

- 15 flows: `lib→ospfd`, `ospfd→zebra`, `zebra→ospfd`

## Code modules (L3)

| Module | Size | Tags | Top anchors (file) |
|---|---|---|---|
| `Mb7c3d1fd` ospfd:unlinked | 1012 | - | no intra-service call edges observed |
| `M90387781` ospfd:ospf | 212 | - | `ospf_lsa_install` (ospfd/ospf_lsa.c); `ospf_lsa_unlock` (ospfd/ospf_lsa.c); `ospf_flood_through_area` (ospfd/ospf_flood.c) |
| `M38cd72c7` ospfd:ospf | 154 | - | `ospf_get_name` (ospfd/ospfd.c); `ospf_show_vrf_name` (ospfd/ospf_vty.c); `show_ip_ospf_neighbor_detail_sub` (ospfd/ospf_vty.c) |
| `Mbed952fb` ospfd:ospf | 136 | - | `get_metric` (None); `ospf_route_free` (ospfd/ospf_route.c); `ospf_ase_calculate_route` (ospfd/ospf_ase.c) |
| `M62a211d6` ospfd:ospf | 121 | - | `ospf_if_update_params` (ospfd/ospf_interface.c); `ospf_get_if_params` (ospfd/ospf_interface.c); `ospf_free_if_params` (ospfd/ospf_interface.c) |
| `M89381b56` ospfd:ospf | 116 | - | `ospf_finish_final` (ospfd/ospfd.c); `ospf_if_down` (ospfd/ospf_interface.c); `ospf_if_free` (ospfd/ospf_interface.c) |
| `M2af12f08` ospfd:ospf | 112 | - | `ospf_router_info_update_sr` (ospfd/ospf_ri.c); `ospf_sr_start` (ospfd/ospf_sr.c); `update_sr_blocks` (ospfd/ospf_sr.c) |
| `M9e2457c9` ospfd:ospf | 107 | - | `str2area_id` (None); `ospf_area_get` (ospfd/ospfd.c); `ospf_schedule_abr_task` (ospfd/ospf_abr.c) |
| `M03ee9eb0` ospfd:ospf | 101 | - | `ospf_lookup_by_vrf_id` (ospfd/ospfd.c); `msg_free` (ospfd/ospf_api.c); `msg_new` (ospfd/ospf_api.c) |
| `M28664eb2` ospfd:ospf | 101 | - | `ospf_external_aggregator_timer_set` (None); `ospf_lsa_list_prev` (ospfd/ospf_flood.h); `ospf_spf_print` (ospfd/ospf_spf.c) |
| `M21fd366a` ospfd:ospf | 100 | - | `ospf_if_name_string` (None); `ospf_read_helper` (ospfd/ospf_packet.c); `ospf_dr_election` (ospfd/ospf_ism.c) |
| `M2b687c44` ospfd:ospf | 91 | - | `ospf_external_info_find_lsa` (ospfd/ospf_asbr.c); `ospf_zebra_read_route` (ospfd/ospf_zebra.c); `ospf_redistribute_check` (ospfd/ospf_zebra.c) |
| `M27c27e13` ospfd:ospf | 85 | - | `ospf_spf_calculate` (ospfd/ospf_spf.c); `ospf_ti_lfa_generate_inner_label_stack` (ospfd/ospf_ti_lfa.c); `ospf_ti_lfa_generate_q_spaces` (ospfd/ospf_ti_lfa.c) |
| `M6d735b77` ospfd:ospf | 84 | - | `__builtin_constant_p` (None); `ospf_mpls_te_show_link_subtlv` (ospfd/ospf_te.c); `show_mpls_te_link_sub` (ospfd/ospf_te.c) |
| `M493e9884` ospfd:ospf | 59 | - | `main` (ospfd/ospf_main.c); `ospf_router_info_schedule` (ospfd/ospf_ri.c); `ospf_opaque_init` (ospfd/ospf_opaque.c) |
| `M91e48105` ospfd:ospf | 53 | - | `ospf_interface_bfd_apply` (ospfd/ospf_bfd.c); `ospf_nbr_new` (ospfd/ospf_neighbor.c); `ospf_nbr_nbma_lookup` (ospfd/ospfd.c) |
| `Me289c4ec` ospfd:ospf | 43 | - | `update_linkparams` (ospfd/ospf_te.c); `ospf_mpls_te_lsa_schedule` (ospfd/ospf_te.c); `lookup_linkparams_by_ifp` (ospfd/ospf_te.c) |
| `Mbf53aa82` ospfd:config | 25 | - | `ospf_config_write_one` (ospfd/ospf_vty.c); `config_write_interface_one` (ospfd/ospf_vty.c); `area_id2str` (None) |
| `M3f425e72` ospfd:ospf | 13 | - | `ospf_asbr_external_aggregator_set` (ospfd/ospf_asbr.c); `ospf_asbr_external_rt_no_advertise` (ospfd/ospf_asbr.c); `is_valid_summary_addr` (None) |
| `M473b7235` ospfd:lsa | 13 | - | `router_lsa_link_set` (ospfd/ospf_lsa.c); `link_info_set` (ospfd/ospf_lsa.c); `lsa_link_broadcast_set` (ospfd/ospf_lsa.c) |
| `M92ec5b9d` ospfd:vertex | 8 | - | `vertex_cmp` (None); `vertex_pqueue_member` (ospfd/ospf_spf.c); `vertex_pqueue_const_find_gteq` (ospfd/ospf_spf.c) |
| `Mcf464450` ospfd:show | 6 | - | `show_sr_node` (ospfd/ospf_sr.c); `show_sr_prefix` (ospfd/ospf_sr.c); `sr_op2str` (None) |
| `Mc86b940d` ospfd:ospf | 5 | - | `no_ospf_gr_helper_enable_lsacheck_magic` (ospfd/ospf_vty.c); `ospf_gr_helper_enable_lsacheck_magic` (ospfd/ospf_vty.c); `ospf_gr_helper_lsa_check_set` (None) |
| `M2f947b1f` ospfd:ospf | 5 | - | `no_ospf_gr_helper_planned_only_magic` (ospfd/ospf_vty.c); `ospf_gr_helper_planned_only_magic` (ospfd/ospf_vty.c); `ospf_gr_helper_set_supported_planned_only_restart` (None) |
| `M2686ff36` ospfd:ospf | 5 | - | `no_ospf_gr_helper_supported_grace_time_magic` (ospfd/ospf_vty.c); `ospf_gr_helper_supported_grace_time_magic` (ospfd/ospf_vty.c); `ospf_gr_helper_supported_gracetime_set` (None) |
| `M36f87242` ospfd:ospf | 5 | - | `no_ospf_mpls_ldp_sync_holddown_magic` (ospfd/ospf_ldp_sync.c); `ospf_if_set_ldp_sync_holddown` (ospfd/ospf_ldp_sync.c); `ospf_mpls_ldp_sync_holddown_magic` (ospfd/ospf_ldp_sync.c) |
| `Mf2ef1b91` ospfd:debug | 4 | - | `debug_ospf_lsa_magic` (ospfd/ospf_dump.c); `debug_ospf_lsa` (ospfd/ospf_dump_clippy.c); `debug_ospf_lsa_common` (ospfd/ospf_dump.c) |
| `Md2a8e4fe` ospfd:debug | 4 | - | `debug_ospf_nsm_magic` (ospfd/ospf_dump.c); `debug_ospf_nsm` (ospfd/ospf_dump_clippy.c); `debug_ospf_nsm_common` (ospfd/ospf_dump.c) |
| `M164b9495` ospfd:debug | 4 | - | `debug_ospf_zebra_magic` (ospfd/ospf_dump.c); `debug_ospf_zebra` (ospfd/ospf_dump_clippy.c); `debug_ospf_zebra_common` (ospfd/ospf_dump.c) |

## Findings attached


## Query hints

```
python3 kb.py cluster show Ded29f1c0
python3 kb.py path svc:ospfd svc:zebra   # cross-domain ZAPI path
python3 kb.py impact yang:<module>:<path>
```
