---
page_id: daemons/lib.md
okf_level: L3-daemon
claims: yes
verified: full
service: svc:lib
---
## Functionality

- svc:lib is a service in the fused graph; its functional domain is D1737981e. [a22dfd3a]
- svc:lib publishes 34 message types toward the ZAPI bus (ZEBRA_GET_LABEL_CHUNK, ZEBRA_GET_TABLE_CHUNK, ZEBRA_GRE_GET, ...). [a29ba45b]
- It handles 11 notification/event types from the bus (ZEBRA_BFD_DEST_REPLAY, ZEBRA_CAPABILITIES, ZEBRA_ERROR, ...). [a9098ef6]
- Northbound contracts: frr-affinity-map(2), frr-backend(11), frr-filter(41), frr-host(1), frr-interface(11), frr-logging(21), frr-route-map(30), frr-routing(1), frr-vrf(3), ietf-key-chain(26) — 147 YANG paths across 147 NB handler tables. [ad0e28f6]
- Measured roles: shared-infra, zapi-client, zapi-publisher. [aeaf9f03]
- lib:nb — 663 functions; anchors: vty_out (lib/vty.c), nb_cli_enqueue_change (lib/northbound_cli.c), nb_cli_apply_changes (lib/northbound_cli.c), yang_dnode_get_string (lib/yang_wrappers.c). [a5928bb6]
- lib:zlog — 610 functions; anchors: zlog_ref (lib/zlog.h), _zlog_assert_failed (lib/zlog.c), zlog_backtrace (lib/log.c), _darr__resize (lib/darr.c). [a653f25a]
- lib:list — 580 functions; anchors: qfree (lib/memory.c), qcalloc (lib/memory.c), qstrdup (lib/memory.c), listgetdata (lib/linklist.h). [ae5df36d]
- lib:rb — 259 functions; anchors: vrf_lookup_by_id (lib/vrf.c), _rb_insert (lib/openbsd-tree.c), _rb_find (lib/openbsd-tree.c), _rb_max (lib/openbsd-tree.c). [a68224dd]
- lib:typed — 243 functions; anchors: typed_rb_remove (lib/typerb.c), cspf_clean (lib/cspf.c), ls_ted_del_all (lib/link_state.c), typed_rb_insert (lib/typerb.c). [a0483dd1]
- lib:zlog — 207 functions; anchors: rcu_enqueue (lib/frrcu.c), zlog_target_replace (lib/zlog.c), zlog_tls_buffer_flush (lib/zlog.c), atomlist_del_hint (lib/atomlist.c). [a59b7bc0]
- lib:yang — 184 functions; anchors: yang_get_default_value (lib/yang_wrappers.c), vbprintfrr (lib/printf/vfprintf.c), _darr__in_vsprintf (lib/darr.c), yang_dnode_get (lib/yang.c). [abe60e1d]
- 33 cross-service flows originate here; targets: svc:bgpd, svc:ospfd, svc:zebra. [a97a3010]
- 0 handled messages have no in-slice sender (orphan handlers). [a3cb7be2]

## ZAPI contract — published (first 12)

- zapi:ZEBRA_GET_LABEL_CHUNK [a72bcc1b]
- zapi:ZEBRA_GET_TABLE_CHUNK [a2a829d2]
- zapi:ZEBRA_GRE_GET [a31419e8]
- zapi:ZEBRA_HELLO [a46da7c3]
- zapi:ZEBRA_INTERFACE_ADD [a643ff5f]
- zapi:ZEBRA_INTERFACE_DELETE [ae3ec1f7]
- zapi:ZEBRA_INTERFACE_DISABLE_RADV [a2d92063]
- zapi:ZEBRA_INTERFACE_ENABLE_RADV [a0193a84]
- zapi:ZEBRA_INTERFACE_SET_ARP [aeca70b5]
- zapi:ZEBRA_INTERFACE_SET_MASTER [a210b975]
- zapi:ZEBRA_INTERFACE_SET_PROTODOWN [a8d04121]
- zapi:ZEBRA_MLAG_CLIENT_REGISTER [a4c6deb8]

## ZAPI contract — handled (first 12)

- zapi:ZEBRA_BFD_DEST_REPLAY [af658e79]
- zapi:ZEBRA_CAPABILITIES [a21528d1]
- zapi:ZEBRA_ERROR [a1a7ff62]
- zapi:ZEBRA_INTERFACE_ADD [a925a996]
- zapi:ZEBRA_INTERFACE_BFD_DEST_UPDATE [ae5fb4c3]
- zapi:ZEBRA_INTERFACE_DELETE [a2f81d47]
- zapi:ZEBRA_INTERFACE_DOWN [a951ff05]
- zapi:ZEBRA_INTERFACE_UP [a247c86b]
- zapi:ZEBRA_NEXTHOP_UPDATE [a6884ddf]
- zapi:ZEBRA_VRF_ADD [a6abd230]
- zapi:ZEBRA_VRF_DELETE [ae83d490]


## Anchor ledger

| chip | refs |
|---|---|
| [a22dfd3a] | N:svc:lib · C:D1737981e |
| [a29ba45b] | S:pack.D1737981e.published · E:svc:lib|publishes|zapi:ZEBRA_GET_LABEL_CHUNK · E:svc:lib|publishes|zapi:ZEBRA_GET_TABLE_CHUNK · E:svc:lib|publishes|zapi:ZEBRA_GRE_GET |
| [a9098ef6] | S:pack.D1737981e.handled · E:svc:lib|handles|zapi:ZEBRA_BFD_DEST_REPLAY · E:svc:lib|handles|zapi:ZEBRA_CAPABILITIES · E:svc:lib|handles|zapi:ZEBRA_ERROR |
| [ad0e28f6] | S:pack.D1737981e.yang.total · S:pack.D1737981e.nb_tables · S:pack.D1737981e.yang.frr-affinity-map · S:pack.D1737981e.yang.frr-backend · S:pack.D1737981e.yang.frr-filter · S:pack.D1737981e.yang.frr-host · S:pack.D1737981e.yang.frr-interface · S:pack.D1737981e.yang.frr-logging · S:pack.D1737981e.yang.frr-route-map · S:pack.D1737981e.yang.frr-routing · S:pack.D1737981e.yang.frr-vrf · S:pack.D1737981e.yang.ietf-key-chain |
| [aeaf9f03] | S:pack.D1737981e.roles |
| [a5928bb6] | C:M0b7896b1 · S:pack.D1737981e.mod.M0b7896b1.size · P:lib/vty.c · P:lib/northbound_cli.c · P:lib/yang_wrappers.c |
| [a653f25a] | C:Me4dc81e5 · S:pack.D1737981e.mod.Me4dc81e5.size · P:lib/zlog.h · P:lib/zlog.c · P:lib/log.c |
| [ae5df36d] | C:Md41c76a1 · S:pack.D1737981e.mod.Md41c76a1.size · P:lib/memory.c · P:lib/linklist.h · P:lib/linklist.c |
| [a68224dd] | C:M68604753 · S:pack.D1737981e.mod.M68604753.size · P:lib/vrf.c · P:lib/openbsd-tree.c · P:lib/if.h |
| [a0483dd1] | C:M72ca1469 · S:pack.D1737981e.mod.M72ca1469.size · P:lib/typerb.c · P:lib/cspf.c · P:lib/link_state.c |
| [a59b7bc0] | C:Mb6b71573 · S:pack.D1737981e.mod.Mb6b71573.size · P:lib/frrcu.c · P:lib/zlog.c · P:lib/atomlist.c |
| [abe60e1d] | C:M57da9241 · S:pack.D1737981e.mod.M57da9241.size · P:lib/yang_wrappers.c · P:lib/printf/vfprintf.c · P:lib/darr.c |
| [a97a3010] | S:pack.D1737981e.flows.out · F:zapi.cross_svc_flows |
| [a3cb7be2] | S:pack.D1737981e.orphan.n · F:zapi.orphan_handlers_no_sender_in_slice |
| [a72bcc1b] | N:zapi:ZEBRA_GET_LABEL_CHUNK · E:svc:lib|publishes|zapi:ZEBRA_GET_LABEL_CHUNK |
| [a2a829d2] | N:zapi:ZEBRA_GET_TABLE_CHUNK · E:svc:lib|publishes|zapi:ZEBRA_GET_TABLE_CHUNK |
| [a31419e8] | N:zapi:ZEBRA_GRE_GET · E:svc:lib|publishes|zapi:ZEBRA_GRE_GET |
| [a46da7c3] | N:zapi:ZEBRA_HELLO · E:svc:lib|publishes|zapi:ZEBRA_HELLO |
| [a643ff5f] | N:zapi:ZEBRA_INTERFACE_ADD · E:svc:lib|publishes|zapi:ZEBRA_INTERFACE_ADD |
| [ae3ec1f7] | N:zapi:ZEBRA_INTERFACE_DELETE · E:svc:lib|publishes|zapi:ZEBRA_INTERFACE_DELETE |
| [a2d92063] | N:zapi:ZEBRA_INTERFACE_DISABLE_RADV · E:svc:lib|publishes|zapi:ZEBRA_INTERFACE_DISABLE_RADV |
| [a0193a84] | N:zapi:ZEBRA_INTERFACE_ENABLE_RADV · E:svc:lib|publishes|zapi:ZEBRA_INTERFACE_ENABLE_RADV |
| [aeca70b5] | N:zapi:ZEBRA_INTERFACE_SET_ARP · E:svc:lib|publishes|zapi:ZEBRA_INTERFACE_SET_ARP |
| [a210b975] | N:zapi:ZEBRA_INTERFACE_SET_MASTER · E:svc:lib|publishes|zapi:ZEBRA_INTERFACE_SET_MASTER |
| [a8d04121] | N:zapi:ZEBRA_INTERFACE_SET_PROTODOWN · E:svc:lib|publishes|zapi:ZEBRA_INTERFACE_SET_PROTODOWN |
| [a4c6deb8] | N:zapi:ZEBRA_MLAG_CLIENT_REGISTER · E:svc:lib|publishes|zapi:ZEBRA_MLAG_CLIENT_REGISTER |
| [af658e79] | N:zapi:ZEBRA_BFD_DEST_REPLAY · E:svc:lib|handles|zapi:ZEBRA_BFD_DEST_REPLAY |
| [a21528d1] | N:zapi:ZEBRA_CAPABILITIES · E:svc:lib|handles|zapi:ZEBRA_CAPABILITIES |
| [a1a7ff62] | N:zapi:ZEBRA_ERROR · E:svc:lib|handles|zapi:ZEBRA_ERROR |
| [a925a996] | N:zapi:ZEBRA_INTERFACE_ADD · E:svc:lib|handles|zapi:ZEBRA_INTERFACE_ADD |
| [ae5fb4c3] | N:zapi:ZEBRA_INTERFACE_BFD_DEST_UPDATE · E:svc:lib|handles|zapi:ZEBRA_INTERFACE_BFD_DEST_UPDATE |
| [a2f81d47] | N:zapi:ZEBRA_INTERFACE_DELETE · E:svc:lib|handles|zapi:ZEBRA_INTERFACE_DELETE |
| [a951ff05] | N:zapi:ZEBRA_INTERFACE_DOWN · E:svc:lib|handles|zapi:ZEBRA_INTERFACE_DOWN |
| [a247c86b] | N:zapi:ZEBRA_INTERFACE_UP · E:svc:lib|handles|zapi:ZEBRA_INTERFACE_UP |
| [a6884ddf] | N:zapi:ZEBRA_NEXTHOP_UPDATE · E:svc:lib|handles|zapi:ZEBRA_NEXTHOP_UPDATE |
| [a6abd230] | N:zapi:ZEBRA_VRF_ADD · E:svc:lib|handles|zapi:ZEBRA_VRF_ADD |
| [ae83d490] | N:zapi:ZEBRA_VRF_DELETE · E:svc:lib|handles|zapi:ZEBRA_VRF_DELETE |
