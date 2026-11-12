---
page_id: clusters/D4b2a9ab8.md
okf_level: L2-cluster
claims: yes
verified: full
domain: D4b2a9ab8
---
## Functionality

- svc:zebra forms functional domain D4b2a9ab8: 217 backbone members (1 service, 46 ZAPI message, 170 YANG path nodes). [a3c040e8]
- svc:zebra publishes 44 message types toward the ZAPI bus (ZEBRA_BFD_DEST_REPLAY, ZEBRA_CAPABILITIES, ZEBRA_CLIENT_CLOSE_NOTIFY, ...). [a33adfed]
- It handles 94 notification/event types from the bus (ZEBRA_ADVERTISE_ALL_VNI, ZEBRA_ADVERTISE_DEFAULT_GW, ZEBRA_ADVERTISE_SUBNET, ...). [acec72f5]
- Northbound contracts: frr-zebra(164), frr-zebra-route-map(6) — 170 YANG paths across 183 NB handler tables. [a5771c3e]
- Measured roles: zapi-publisher, zapi-server. [a0c06897]
- The domain contains P3 L2 service area Cb6653b94 (zebra:frr-zebra). [a9b77ca6]
- 90 cross-domain edge bindings point outside the domain. [a9ca2346]
- 44 verified cross-service ZAPI flows originate from svc:zebra. [ad204437]
- 34 handled messages currently have no in-slice sender (orphan handlers). [a3333dd9]
- 4 published sends currently drop on the wire in the extractor view (dropped-on-wire findings). [a923ff51]
- 48 code modules; largest is zebra:dplane with 407 functions. [a97c3f64]
- Bucket zebra:unlinked holds 2941 functions without intra-service call edges (pointer-dispatched callbacks and CLI handlers). [a3c615eb]
- 5203 intra-service `calls` edges leave for other service partitions; densest target lib:zlog (1426 calls). [ae2566bf]

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

## Boundary bindings

- handles ×24 → D1737981e [a23955cc]
- publishes ×14 → D1737981e [af38adaf]
- handles ×23 → D3063a0b0 [ad4eb096]
- publishes ×12 → D3063a0b0 [a2355067]
- handles ×7 → Ded29f1c0 [a48bb287]
- publishes ×7 → Ded29f1c0 [a748ca30]
- publishes ×3 → Dc32724de [aa84df29]

## Orphan handlers (examples)

- zapi:ZEBRA_BFD_CLIENT_REGISTER [a6540301]
- zapi:ZEBRA_BFD_DEST_DEREGISTER [a30d5db9]
- zapi:ZEBRA_BFD_DEST_REGISTER [abcf241d]
- zapi:ZEBRA_BFD_DEST_UPDATE [a8912fa4]
- zapi:ZEBRA_CONFIGURE_ARP [adc184e0]
- zapi:ZEBRA_FEC_REGISTER [ad5bb0f6]
- zapi:ZEBRA_FEC_UNREGISTER [abd48f15]
- zapi:ZEBRA_GRE_SOURCE_SET [a12ee0a0]
- zapi:ZEBRA_LABEL_MANAGER_CONNECT_ASYNC [a00ed39c]
- zapi:ZEBRA_MPLS_LABELS_ADD [a06a077a]
- zapi:ZEBRA_MPLS_LABELS_DELETE [a1813409]
- zapi:ZEBRA_MPLS_LABELS_REPLACE [a213d5ec]

## L3 code modules (largest semantic modules)

- zebra:dplane — 407 functions [a6893823]
- zebra:zebra — 345 functions [a378f11b]
- zebra:rib — 257 functions [a216e427]
- zebra:netlink — 224 functions [af3dc415]
- zebra:dplane — 220 functions [af17bed9]
- zebra:zserv — 173 functions [aa81a2c7]
- zebra:nhlfe — 171 functions [a2ae6376]
- zebra:dplane — 170 functions [aa23e003]
- zebra:zebra — 168 functions [aee2609e]
- zebra:netlink — 135 functions [aad4ff50]


## Anchor ledger

| chip | refs |
|---|---|
| [a3c040e8] | N:svc:zebra · C:D4b2a9ab8 · S:pack.D4b2a9ab8.members · S:pack.D4b2a9ab8.members.svc · S:pack.D4b2a9ab8.members.zapi · S:pack.D4b2a9ab8.members.yang |
| [a33adfed] | S:pack.D4b2a9ab8.published · E:svc:zebra|publishes|zapi:ZEBRA_BFD_DEST_REPLAY · E:svc:zebra|publishes|zapi:ZEBRA_CAPABILITIES · E:svc:zebra|publishes|zapi:ZEBRA_CLIENT_CLOSE_NOTIFY |
| [acec72f5] | S:pack.D4b2a9ab8.handled · E:svc:zebra|handles|zapi:ZEBRA_ADVERTISE_ALL_VNI · E:svc:zebra|handles|zapi:ZEBRA_ADVERTISE_DEFAULT_GW · E:svc:zebra|handles|zapi:ZEBRA_ADVERTISE_SUBNET |
| [a5771c3e] | S:pack.D4b2a9ab8.yang.total · S:pack.D4b2a9ab8.nb_tables · S:pack.D4b2a9ab8.yang.frr-zebra · S:pack.D4b2a9ab8.yang.frr-zebra-route-map |
| [a0c06897] | S:pack.D4b2a9ab8.roles |
| [a9b77ca6] | C:Cb6653b94 |
| [a9ca2346] | S:pack.D4b2a9ab8.boundary.total |
| [ad204437] | S:pack.D4b2a9ab8.flows.out · F:zapi.cross_svc_flows |
| [a3333dd9] | S:pack.D4b2a9ab8.orphan.n · F:zapi.orphan_handlers_no_sender_in_slice |
| [a923ff51] | S:pack.D4b2a9ab8.dropped.n · F:zapi.dropped_on_wire |
| [a97c3f64] | S:pack.D4b2a9ab8.modules.n · C:M6816d16c · S:pack.D4b2a9ab8.mod.M6816d16c.size |
| [a3c615eb] | C:Mb5ff12d4 · S:pack.D4b2a9ab8.mod.Mb5ff12d4.size |
| [ae2566bf] | S:pack.D4b2a9ab8.bridge.total · S:pack.D4b2a9ab8.bridge.lib:zlog |
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
| [a23955cc] | C:D1737981e · S:pack.D4b2a9ab8.boundary.D1737981e.handles |
| [af38adaf] | C:D1737981e · S:pack.D4b2a9ab8.boundary.D1737981e.publishes |
| [ad4eb096] | C:D3063a0b0 · S:pack.D4b2a9ab8.boundary.D3063a0b0.handles |
| [a2355067] | C:D3063a0b0 · S:pack.D4b2a9ab8.boundary.D3063a0b0.publishes |
| [a48bb287] | C:Ded29f1c0 · S:pack.D4b2a9ab8.boundary.Ded29f1c0.handles |
| [a748ca30] | C:Ded29f1c0 · S:pack.D4b2a9ab8.boundary.Ded29f1c0.publishes |
| [aa84df29] | C:Dc32724de · S:pack.D4b2a9ab8.boundary.Dc32724de.publishes |
| [a6540301] | N:zapi:ZEBRA_BFD_CLIENT_REGISTER · F:zapi.orphan_handlers_no_sender_in_slice |
| [a30d5db9] | N:zapi:ZEBRA_BFD_DEST_DEREGISTER · F:zapi.orphan_handlers_no_sender_in_slice |
| [abcf241d] | N:zapi:ZEBRA_BFD_DEST_REGISTER · F:zapi.orphan_handlers_no_sender_in_slice |
| [a8912fa4] | N:zapi:ZEBRA_BFD_DEST_UPDATE · F:zapi.orphan_handlers_no_sender_in_slice |
| [adc184e0] | N:zapi:ZEBRA_CONFIGURE_ARP · F:zapi.orphan_handlers_no_sender_in_slice |
| [ad5bb0f6] | N:zapi:ZEBRA_FEC_REGISTER · F:zapi.orphan_handlers_no_sender_in_slice |
| [abd48f15] | N:zapi:ZEBRA_FEC_UNREGISTER · F:zapi.orphan_handlers_no_sender_in_slice |
| [a12ee0a0] | N:zapi:ZEBRA_GRE_SOURCE_SET · F:zapi.orphan_handlers_no_sender_in_slice |
| [a00ed39c] | N:zapi:ZEBRA_LABEL_MANAGER_CONNECT_ASYNC · F:zapi.orphan_handlers_no_sender_in_slice |
| [a06a077a] | N:zapi:ZEBRA_MPLS_LABELS_ADD · F:zapi.orphan_handlers_no_sender_in_slice |
| [a1813409] | N:zapi:ZEBRA_MPLS_LABELS_DELETE · F:zapi.orphan_handlers_no_sender_in_slice |
| [a213d5ec] | N:zapi:ZEBRA_MPLS_LABELS_REPLACE · F:zapi.orphan_handlers_no_sender_in_slice |
| [a6893823] | C:M6816d16c · S:pack.D4b2a9ab8.mod.M6816d16c.size |
| [a378f11b] | C:M11ed049a · S:pack.D4b2a9ab8.mod.M11ed049a.size |
| [a216e427] | C:M749027f4 · S:pack.D4b2a9ab8.mod.M749027f4.size |
| [af3dc415] | C:M36d601bd · S:pack.D4b2a9ab8.mod.M36d601bd.size |
| [af17bed9] | C:M761377d9 · S:pack.D4b2a9ab8.mod.M761377d9.size |
| [aa81a2c7] | C:Med7a3cb2 · S:pack.D4b2a9ab8.mod.Med7a3cb2.size |
| [a2ae6376] | C:Mf3415498 · S:pack.D4b2a9ab8.mod.Mf3415498.size |
| [aa23e003] | C:Md257f514 · S:pack.D4b2a9ab8.mod.Md257f514.size |
| [aee2609e] | C:M9a38c8b6 · S:pack.D4b2a9ab8.mod.M9a38c8b6.size |
| [aad4ff50] | C:M884ca7f8 · S:pack.D4b2a9ab8.mod.M884ca7f8.size |
