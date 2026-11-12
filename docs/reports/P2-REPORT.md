# P2 Report — Fusion & Graph (CLOSED)

**Date:** 2026-11-12 · **Source pin:** FRR `frr-10.7.1` (unchanged) ·
**Run id:** `e082ab760d0b7e50` · **Verdict: both P2 exit gates PASS.**

## 1. Exit gates (POC-DESIGN.md §4)

| Gate | Status | Evidence |
|---|---|---|
| `path svc:bgpd svc:zebra` resolves via real ZAPI edge | **PASS** | 2-hop fused paths in **both directions**: `svc:bgpd -publishes-> zapi:ZEBRA_ROUTE_ADD <-handles- svc:zebra` (send site `bgpd/bgp_zebra.c:1741`, handler `zebra/zapi_msg.c:4139` `zserv_handlers[ZEBRA_ROUTE_ADD] = zread_route_add`) and the reverse `svc:zebra -publishes-> zapi:ZEBRA_* <-handles- svc:bgpd` (client handler tables). `kb.py path` + test T6 |
| YANG-leaf impact lists daemons + callbacks | **PASS** | `kb.py impact yang:frr-staticd:staticd/route-list/prefix` → daemon `svc:staticd`, NB entry `nb:staticd:frr-routing:…/frr-staticd:staticd/route-list` (ancestor container), callbacks `…_route_list_create/_destroy` @ `staticd/static_nb.c:18`, 82 ZAPI side-effect messages within call depth 10. 24/25 sampled joined leaves yield daemon+callback impact (test T7) |

Deliverables (design §6): `graph.json` (30,229 nodes / 54,246 fused edges,
12.1 MB) · query CLI (`kb.py`: explain / path / impact / stats) · fusion tests
(`tests_fusion.py`, **22/22 green**).

## 2. What was built

| Tool | Role | Output |
|---|---|---|
| `lysc_paths.c` (+`run_lysc.sh`) | libyang 2.1.148 compiled-schema walk: loads 50 modules (58 attempted; 2 deviation targets unshipped) with **explicit feature enabling**, emits LOG (schema, choice/case kept) + DATA paths, module, bare path per node | `lysc_paths.jsonl` (4,806 nodes) |
| `zapi_srv.py` | grep extractor for zebra's **server-side** dispatch table `zserv_handlers[]` (`zebra/zapi_msg.c:4133-4230`) — the handle side P1 structurally lacked | 94 messages → 188 edges, 72 unique fns |
| `zapi_send_grep.py` | grep extractor for **wrapper-mediated sends**: enum-as-first-arg calls to lib/zebra ZAPI wrappers (`zclient_route_send(ZEBRA_ROUTE_ADD, …)`); message namespace validated against the 157-message type facts (route-type enums rejected) | 39 sites → 25 svc-level edges (bgpd 12 · zebra 16 · ospfd 9 · lib 3) |
| `fuse.py` | merge + both joins + findings + ledger + `graph.json` export | `facts.duckdb` (P2), `findings.json`, `fusion_summary.json` |
| `kb.py` | Tier-1 RAM graph (~54k edges), evidence-carrying queries | CLI |
| `tests_fusion.py` | schema integrity, both joins, both gates, ledger consistency | 22 assertions |

## 3. The fused fact base

| plane | tag | edges | Δ vs P1 |
|---|---|---|---|
| code | DECLARED | 78,482 | — |
| contract | DECLARED | 1,822 | +426 implements, member_of re-based |
| wiring | DECLARED | 1,792 | +188 zapi_srv, +25 send-grep, +88 svc-pub, +63 zebra svc-handles |
| build | BUILD | 356 | — |
| **total** | | **82,477 raw → 54,246 fused** | nodes 30,092 → 30,229 |

- Contract plane grew +137 nodes from libyang expansion (grouping/uses-derived
  nodes pyang's statement walk never emitted, plus `ietf-key-chain` — 26 NB
  entries target a module that lives in `yang/ietf/`, which P1's 45-root-model
  glob never loaded).
- Multi-plane fused pairs: **0** — planes don't overlap in endpoints until a
  runtime plane arrives (P5/P6); the `fused_edges` evidence machinery is in
  place and tested (T2).

## 4. Join #1 — nb↔yang: 28% → 100%

The P1 carry-forward said "do the join with libyang itself; target ≥90%". Done:
**426/426 (100.0%)**, strategies `schema-exact` 271 + `flex-raw` 155, zero
misses. Reaching it surfaced three normalization facts about FRR's NB xpaths,
each now encoded (and commented) in `fuse.py`:

1. **libyang qualification form** — first segment is `module:name`
   (`/frr-affinity-map:lib/…`); naive `/{module}/{path}` keys hit nothing.
2. **FRR hand-writes xpaths that drop an ARBITRARY SUBSET of choice/case
   segments** — outer choice/case kept, inner dropped (e.g. staticd's
   `…/frr-staticd:staticd/route-list` augment path, route-map's
   `…/rmap-match-condition/list-name` with the inner `match-condition` choice
   elided). Fix: enumerate every keep/drop variant per schema path (bounded 2^k,
   ≤4 nested) — 9,425 variants index 7,437 flex keys.
3. **Same-name collisions resolve by libyang's own semantics** —
   `…/rmap-match-condition/list-name` matches frr-route-map's own leaf, the
   frr-bgp-route-map augment leaf, and the frr-pim-route-map augment leaf.
   FRR resolves this at runtime via libyang's tolerant data-path parser:
   data nodes only, **first match in compiled order**, module-qualified
   segments disambiguating (`frr-bgp-route-map:list-name` → the augment leaf).
   `put()` mirrors exactly those rules — verified on the 4 hardest cases:
   lib's unqualified `list-name` → own leaf; bgpd's qualified `…:list-name` →
   `yang:frr-bgp-route-map:list-name`; `ipv4-address` → own leaf;
   key-chain `lifetime/send-lifetime` → feature-enabled subtree.

Two emitter-side discoveries en route: the 6 `frr-bgp-*.yang` are **submodules**
of build-generated `frr-bgp.yang` (they must not be loaded directly), and
libyang's `"*"` feature wildcard did NOT enable features — explicit per-module
feature lists are passed (`ietf-key-chain`'s `independent-send-accept-lifetime`
case was invisible without it; that alone was 3 NB entries).

## 5. Join #2 — ZAPI: zebra's handle side + wrapper-mediated sends

P1 had client handler tables (59 svc-level handles, no zebra) and
`zclient_create_header`-site publishes (92 fn-level). Two gaps closed:

- **Server dispatch** (`zapi_srv`): `zserv_handlers[]` is a designated
  initializer over the same ZEBRA_* enums → 94 messages, svc + fn level. This
  is what makes `svc:bgpd → svc:zebra` a *closed loop* rather than a one-sided
  claim.
- **Wrapper sends** (`zapi_send_grep`): bgpd never calls `zclient_create_header`
  for routes — it calls `zclient_route_send(ZEBRA_ROUTE_ADD, …)` with the enum
  as an argument, invisible to the create_header-site matcher. Grep class
  (per-site file:line in `zapi_send_grep_sites.json`), message namespace
  validated against the type facts; one false positive class rejected on the
  way (`ZEBRA_ROUTE_BGP` is a route-type argument of `zclient_get_nhg_start`).

Net: **111 cross-service message flows** (sender svc → message → handler svc),
e.g. bgpd→zebra 33 send-kinds, zebra→bgpd/lib/ospfd/staticd notification kinds.

## 6. Findings (ledgered in `findings.json`, not silent)

- **Dead wiring (4 registrations):** `svc:lib` tables with empty `cbs` —
  `frr-host:host/allow-reserved-ranges` (`host_cli.c:45`, `host_nb.c:30`) and
  the mgmtd backend tables (`mgmt_be_client.c:1313/1371`) whose callbacks live
  in the unsliced mgmtd daemon. Per-registration semantics: a shared NB node
  counts as dead only when *no* callback of that svc serves it.
- **Dropped-on-the-wire (7 messages):** published in-slice, handled by nobody —
  `ZEBRA_OPAQUE_*` (opaque API registers handlers *dynamically* via
  `zclient_register_opaque` — the exact "observed-undeclared = dynamic
  registration" class the design predicts; no runtime plane yet to observe it),
  `ZEBRA_GRE_UPDATE`, `ZEBRA_NHG_NOTIFY_OWNER`, `ZEBRA_SR_POLICY_NOTIFY_STATUS`,
  `ZEBRA_PW_STATUS_UPDATE` (zebra→client notifications whose client handlers
  live in unsliced daemons' tables).
- **Orphan handlers (44 messages):** handled in-slice, no in-slice sender —
  senders live in ripd/isisd/pimd/bfdd (outside the POC slice). Expected;
  becomes measurable when the slice grows.
- **Known gaps carried:** grep-class facts have no enclosing-function
  attribution (svc-level only); fn-level send attribution for wrapper calls
  would need the clang extractor extended to call-argument positions (P3
  optional); runtime plane (OBSERVED) still absent by design until P5/P6.

## 7. Reproduce

```bash
cd /home/z/my-project/poc
bash /home/z/my-project/scripts/p2/run_lysc.sh          # libyang paths (~2 s)
python3 /home/z/my-project/scripts/p2/zapi_srv.py       # zebra dispatch
python3 /home/z/my-project/scripts/p2/zapi_send_grep.py # wrapper sends
python3 /home/z/my-project/scripts/p2/fuse.py           # fusion + graph.json
python3 /home/z/my-project/scripts/p2/kb.py stats       # Tier-1 graph sanity
python3 /home/z/my-project/scripts/p2/tests_fusion.py   # 22/22
```

Needs: `gcc`, `pip install duckdb`; source tree per P0 restore recipe;
libyang 2.1.148 from `poc/deps/usr` (P0 vendored, no rebuild needed).

## 8. Handoff to P3 (analytics)

- `graph.json` is the Leiden input; wiring edges carry svc ownership so
  daemon-shaped communities are checkable against the FRR-docs ground truth.
- `lib` is the universal hub (19,596 bgpd→lib call edges): hub exclusion will
  matter immediately; design's split-oversized rule applies.
- Impact closure (`kb.py impact`) is the recall eval harness for P3/P6 — it
  already answers "which daemons + callbacks does this YANG leaf touch".
- Optional P3 prep: extend clang extractor to record call-argument enums
  (fn-level send attribution), add `sends_to` derived svc-edges if clustering
  benefits from a service-level projection.
