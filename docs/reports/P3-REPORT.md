# P3 Report — Analytics: Hierarchical Leiden Clustering + Graph-RAG Cluster Packs

**Status:** P3 COMPLETE (2026-11-12). Exit gate **PASS**: recall **12/12 = 1.00** vs FRR documented functional associations (bar 0.8). Stability tests **9/9** (IDs identical across rebuilds, cross-seed ARI 1.0). Hierarchy: **5 domains (L1) → 5 areas (L2) → 193 code modules (L3)** over the fused graph (30,229 nodes / 54,246 edges). God-node ranking **skipped by user instruction**; clustering used **Leiden only, zero LLM**; per-cluster functionality/responsibilities derived from graph facts; context packs in graph-RAG style.

**Scope per user directive (2026-11-12):** *"skip god nodes, focus on each cluster based on functionality, responsibilities, and other, use hierarchical clustering graph RAG styled no LLM for clustering, use leiden."* Accordingly: the P3 deliverable "god-nodes report" (degree ranking + hub exclusion) is dropped; cluster profiling and context packs are added; the clustering algorithm remains Leiden (multi-resolution = the hierarchical clustering mechanism).

---

## 1. Method

### 1.1 Clustering backbone (P3.1, `build_backbone.py`)

The fused graph is hub-and-spoke: services never call each other directly — they exchange `zapi:*` messages and register `nb:*` handler tables. Clustering therefore runs on the **semantic backbone**:

| Layer | Nodes | Kept as | Dropped |
|---|---|---|---|
| `svc:*` | 5 daemons (bgpd, lib, ospfd, staticd, zebra) | nodes | — |
| `zapi:*` | 142 of 157 messages wired to ≥1 svc | nodes | 15 unwired |
| `yang:*` | 410 paths reachable via `nb:implements` | nodes | 1,670 floating (models of daemons outside the slice: isisd, ripd, bfdd, pim...) |
| `nb:*` / `code:*` / `build:*` | 426 / 27,205 / 356 | collapsed into `svc -nb_implements-> yang` edges / routed to L3 | — |

Backbone: **557 nodes / 782 edges** (`backbone.json`). Weights: handles/publishes 2.0, nb_implements 1.5, yang member_of 0.5; design rules AMBIGUOUS-only ×0.5 and n_planes>1 ×1.5 are implemented but **do not fire** on this slice (all 2,114 contract edges are DECLARED, n_planes=1 — recorded as a fact, not an assumption).

**`lib` universal hub handling.** The hub phenomenon is real but lives at the **code plane**: 19,155 cross-service call sites, **100% of them pointing into lib** (bgpd→lib 8,696, zebra→lib 6,061, ospfd→lib 3,909, staticd→lib 484, zebra→fpm 5). At the backbone level lib is *peripheral* (10 shared YANG modules, no ZAPI client edges), so no hub exclusion was needed — Leiden naturally gives lib its own "shared infrastructure" domain, which is exactly the "northbound/zclient infrastructure community" the design doc predicted. The code-plane hub is instead *quantified and packed* (module→module call bridges), not used to distort the partition.

### 1.2 Hierarchical Leiden (P3.2, `cluster.py`)

`leidenalg.RBConfigurationVertexPartition`, seed **42** pinned at every call; gamma sweeps recorded in `sweep.json`. Stable IDs = `<level-prefix><blake2b-8hex(sorted members)>` — content-derived, reproducible.

| Level | Graph | Resolution | Result | Rationale |
|---|---|---|---|---|
| **L1 functional domains** | full backbone | sweep 0.05→1.2, prefer k∈[2,6], blob-guard 0.6 | gamma 1.2 → **5 domains** | the level that must match FRR's documented functional decomposition |
| **L2 service areas** | full backbone (global re-run) | sweep 1.5→8.0, prefer k∈[4,20] | gamma 1.5 → **5 areas** (containment 1.0) | induced per-domain refinement is vacuous here — each domain is a *star* around its service (measured: modularity 0.03); global multi-resolution keeps areas coherent and flags cross-domain areas via `containment` |
| **L3 code modules** | per-service intra-`calls` graphs (25,184 functions) | size-classed gamma (≥500-func comps: 0.8→3.0, k∈[6,24]) | **193 modules** | the responsibilities layer |

**Component-aware split** (the decisive implementation lesson): static call graphs fragment heavily — 32–39% of functions per service have *zero* intra-service call edges (CLI `DEFUN` handlers, pointer-dispatched callbacks, unused symbols), and naive Leiden floors at the connected-component count (first run produced 3,339 modules for bgpd). Fix: components ≥10 functions → Leiden; 4–9 → own module; <4 → per-service `misc` bucket; unlinked functions → per-service `unlinked` bucket (largest: bgpd 3,161). Result: bgpd 36 modules, lib 58, zebra 47, ospfd 28, staticd 18, fpm 1 — top modules are semantically clean (e.g. bgpd:bgp 697 = route/dest core, zebra:dplane 407 = data-plane, zebra:netlink 224 = kernel plumbing, lib:nb 663 = CLI/northbound glue).

### 1.3 No-LLM profiling (P3.3, `profile.py`)

Every cluster gets a profile built exclusively from graph facts (`profiles.jsonl`):

- **functionality statements** — templated from measured facts: *"zebra is the ZAPI message bus: handles 94 message types published by the route daemons (bgpd, ospfd) and publishes 44 notification/event types back to clients"*; *"staticd is a config/route client: handles 8 notification types from the ZAPI bus; its route sends go through lib zclient wrappers"* (the graph honestly shows staticd has 0 publish edges — wrapper-mediated sends are attributed to lib in this slice).
- **role tags** — rule-based: `zapi-server` = handles messages published by ≥2 *route* daemons (lib excluded: its publishes are the zclient wrapper layer); `zapi-client`, `zapi-publisher`, `nb-owner`, `shared-infra`. Module tags from anchors (`northbound`, `cli`, `zapi-client`, `memory`, `rbtree`, `yang`...).
- **contract inventory** — per-domain ZAPI handled/published lists, YANG modules with path counts, NB table counts (68/147/1/27/183).
- **boundary edges** — cross-domain edges with relations and counts (zebra↔lib handles×24 publishes×14, zebra↔bgpd handles×23 publishes×12, ...).
- **findings attached** — P2 findings mapped into clusters (orphan handlers, dropped-on-wire, dead wiring, cross-service flows).
- **anchors with files** — top-8 within-module functions, file attribution recovered from the pre-fusion fact store (`facts.duckdb` src_ref; the fused graph drops src_ref) — e.g. `nb_cli_enqueue_change (lib/northbound_cli.c)`, `netlink_route_multipath_msg_encode (zebra/rt_netlink.c)`.

### 1.4 Graph-RAG packs (P3.4)

`packs/` = self-contained per-domain context for P4 (OKF publisher) and P5 (router):

- `packs/D<id>.md` — human-readable pack: functionality → ZAPI contract → YANG contracts → boundary → flows → code-module table → findings → query hints.
- `packs/D<id>.json` — the same facts machine-readable (pack = {services, functionality, roles, yang_modules, zapi_msgs, boundary_edges, findings, modules[anchors+tags+zapi touched]}).
- `packs/index.md` — global index for routing.
- `kb.py cluster` — list / show / of / find over the hierarchy (P2 commands untouched; P2 `kb.py` copy stays frozen).

## 2. Results

### 2.1 L1 domains vs expected shape

| Domain | Service | Members | Roles | Contracts |
|---|---|---|---|---|
| `D4b2a9ab8` **zebra** | zebra | 217 (46z/170y) | **zapi-server**, zapi-publisher, nb-owner | handles 94 (42 in-domain), publishes 44, frr-zebra(164) + frr-zebra-route-map(6), 183 NB tables |
| `D3063a0b0` **bgpd** | bgpd | 107 (41z/65y) | zapi-client, zapi-publisher, nb-owner | publishes 27 (EVPN/ADVERTISE/IPSET...), handles 30, frr-bgp-route-map(65), 68 NB tables |
| `Dc32724de` **staticd** | staticd | 34 (6z/27y) | zapi-client | handles 8 notifications, frr-staticd(27), 27 NB tables |
| `Ded29f1c0` **ospfd** | ospfd | 17 (15z/1y) | zapi-client, zapi-publisher | publishes 7 (REDISTRIBUTE...), handles 8, 1 NB table |
| `D1737981e` **lib** | lib | 182 (34z/147y) | **shared-infra**, nb-owner | 10 shared models (filter 41, route-map 30, key-chain 26, logging 21...), 147 NB tables, zclient wrapper publishes |

This is precisely the POC-DESIGN expected shape: *one community per daemon + a northbound/zclient infrastructure community* (vty/CLI machinery exists inside the `lib:nb` module — vty.c/northbound_cli.c anchors — but no vty extractor plane was built, so no separate vty domain; noted as scope).

### 2.2 Recall evaluation (`eval.json`)

Ground truth = associations grep-verified against `poc/src/frr-10.7.1/doc/user/*.rst`. **12/12 = 1.00 ≥ 0.8 PASS.** Verdicts computed from cluster artifacts only (domains, boundary edges, L2 containment, cross-service call facts):

| GT row | Type | Verdict | Evidence |
|---|---|---|---|
| bgpd↔zebra | flow | OK | domains linked via handles+publishes (bgp.rst `--no_zebra`) |
| ospfd↔zebra | flow | OK | handles+publishes (ospfd.rst) |
| staticd↔zebra | flow | OK | publishes×3 boundary (static.rst nexthop tracking) |
| zebra = ZAPI server | server | OK | handles-edges from 4 client domains (zebra.rst ZAPI counters) |
| staticd↔frr-staticd | nb-owns | OK | 27/27 paths in-domain, same L2 area |
| zebra↔frr-zebra | nb-owns | OK | 164/164 |
| bgpd↔frr-bgp-route-map | nb-owns | OK | 65/65 |
| ospfd↔frr-ospf-route-map | nb-owns | OK | 1/1 |
| zebra↔frr-zebra-route-map | nb-owns | OK | 6/6 |
| lib shared models | infra | OK | contract-plane bridges to zebra+ospfd domains |
| lib machinery used by all daemons | infra-code | OK | bgpd 8,696 / zebra 6,061 / ospfd 3,909 / staticd 484 calls into lib |
| community shape | shape | OK | 5 domains = 4 daemon + 1 infra |

**Coverage notes (extraction, not clustering — carried forward):** staticd→zebra route sends sit in the lib wrapper layer in this slice; bgpd's frr-bgp\* NB tables were never extracted (bgpd wired only to frr-bgp-route-map); 28 of 43 repo YANG modules belong to out-of-slice daemons; bgpd's route-map augment paths lack member_of linkage to the shared frr-route-map tree (P1 yang-tree characteristic), which is why the shared-machinery claim is verified on the code plane. The eval is scoped to associations the fact graph actually encodes — the scoping is stated, not hidden.

### 2.3 Stability tests (`tests_p3.py`, 9/9 PASS)

| Test | Result |
|---|---|
| T1 L1 IDs identical across rebuild (seed 42) | PASS — 5/5 IDs reproduced |
| T2 cross-seed ARI 43–46 vs 42 (L1) | PASS — min ARI **1.0** (partition is seed-stable at this density) |
| T3 ID scheme (unique, D/C/M + 8-hex) | PASS — 203 clusters |
| T4 assignment coverage | PASS — 557/557 backbone nodes, 25,184/25,184 functions |
| T5 artifact integrity (counts, 5 packs, eval pass) | PASS — recall 1.0 |

### 2.4 L3 responsibilities layer (sample)

Top modules demonstrate the "responsibilities" granularity: bgpd `bgp`(697, route/dest core), `peer`(607, FSM/neighbor events), `bgp`(556, attributes), `bgp`(530, EVPN), `peer`(331, neighbor CLI); lib `nb`(663, vty+northbound CLI glue), `nb`(610, zlog), `route`(580, qmalloc/list), `if`(259, VRF/rbtree), `yang`(184); zebra `dplane`(407), `zebra`(345, EVPN), `netlink`(224), `dplane`(220, kernel netlink). Anchors carry file attribution for every module (25,184 functions → modules; unlinked buckets flagged, never silently dropped).

## 3. Known limitations

1. **Unlinked code buckets are large** (bgpd 3,161 / lib 3,023 / zebra 2,941 functions ≈ 38–40%): pointer-dispatched callbacks (DEFUN CLI handlers, event callbacks) have no static call edges. They are kept, flagged, and counted — a pointer-analysis or runtime-plane pass (P5 trace ingester) would re-attach them.
2. **L2 ≈ L1 at slice density** (5 areas, containment 1.0): the backbone's star topology gives no finer global structure (gamma 2.0 already fragments to 44 noisy pieces). The L2 machinery (containment metric, cross-domain areas) earns its keep on denser graphs — e.g. the 200-service product where one svc serves multiple models.
3. **Wrapper-mediated sends attributed to lib** (staticd route sends, 30 lib→zebra flows): per-plane authority is preserved, but a daemon-attribution pass on wrapper call sites would sharpen flow facts.
4. God-node ranking skipped by instruction; hub quantification exists only as the cross-service call census (§1.1).

## 4. Deliverables (`p3/`)

```text
P3-REPORT.md                    this report
backbone.json                   557n/782e weighted backbone + census of exclusions
clusters.jsonl                  203 clusters (5 L1, 5 L2, 193 L3) with stable IDs
backbone_assignments.json       node -> {L1, L2}
code_assignments.json           function -> module (25,184)
profiles.jsonl                  203 rich profiles (no-LLM functionality/responsibilities)
packs/                          5 domain packs (.md + .json) + index.md  [graph-RAG]
sweep.json                      all gamma sweeps + chosen resolutions (seed 42)
eval.json                       GT verdicts, recall 1.0, coverage notes
kb.py                           P2 CLI + cluster list/show/of/find
tests_p3.py + tests_output.txt  stability tests 9/9
build_backbone.py cluster.py profile.py eval_recall.py   pipeline scripts
```

Next: **P4 — OKF publisher** (L0 index / L2 cluster / L3 daemon pages from these packs, deterministic skeleton + verifier, every narrative claim anchored). P5 router consumes `packs/*.json` + `kb.py`.
