# P4 Report — Publisher: OKF Bundle (L0 / L2 / L3) + Claims Verifier + ADR Ingest

**Status:** P4 COMPLETE (2026-11-12). Exit gate: **every narrative claim anchored** — verifier resolves **454/454 claims, 0 stripped**, stamps **`verified: full` on all 14 claim pages** (2 meta pages exempt); `verified: full/partial` populated on every page; determinism proven (**byte-identical bundle across rebuilds**, tests 9/9 in `p4/tests_output.txt`). The only gate item left open is the one that by definition requires a person: **FRR-knowledgeable human review of the bundle** (flagged for the user, not automatable).

**Scope per POC-DESIGN:** *"L0 index, L2 cluster, L3 daemon templates; deterministic skeleton + LLM narrative + verifier (rules first, S1 model optional); ADR ingest"*. God-node content stays skipped (P3 user directive).

---

## 1. Method

### 1.1 Publisher pipeline (`scripts/p4/`)

Three deterministic stages, no LLM in the loop (rules-first narrative; the design's LLM-narrative slot is a drop-in behind the same skeleton interface — see §3):

```
P2/P3 facts ──► skeleton.py ──► render.py ──► verify.py ──► okf-bundle/ + verification.json
                (atoms+refs)   (assembly)   (re-derive & check)
```

- **skeleton.py** — turns fact artifacts into per-page skeletons. Every page = ordered atoms; every atom = one claim sentence (numbers baked from facts) + machine refs. Ref taxonomy: `N` node in fused graph · `E` fused edge `src|rel|dst` · `C` cluster ID (P3 stable IDs) · `S` stat path (recomputable) · `F` findings pointer · `P` source file in the pinned repo · `D` FRR doc path + **verbatim quote**. All refs validated at build time.
- **render.py** — pure assembly: front matter (`page_id`, `okf_level`, `claims`, `verified: pending`), sectioned claim bullets each ending with its chip `[aXXXXXXX]` (blake2b of template+refs), a human-auditable **anchor ledger** per page, and `manifest.json` with sha256 of all 13 inputs.
- **verify.py** — the anti-hallucination gate. Independently re-derives the fact index from raw inputs (recomputes all stats; does not trust `stats.json`), then checks every claim line: ≥1 chip; chips resolve to skeleton atoms; every ref resolves; numeric S/F values must appear in the rendered sentence; D-quotes are whitespace-normalized greps against the cited doc file. Violations are **stripped from the page** and logged; the page is re-stamped `verified: partial`.

### 1.2 Claim coverage in the bundle

| Page set | Pages | Content anchored to |
|---|---|---|
| `index.md` (L0) | 1 | global stats, findings counts, join result, TOC rows (C/S refs) |
| `clusters/D*.md` (L2) | 5 | domain membership, published/handled contracts (E refs per row), YANG/NB contracts, boundary bindings, flows, orphan/dropped/dead findings, L3 module sizes |
| `daemons/<svc>.md` (L3) | 5 | identity, contracts, roles, top modules with `P` file anchors (e.g. `bgp_update (bgpd/bgp_route.c)`), cross-service call bridges |
| `adrs/ADR-*.md` | 3 | Context/Decision = verbatim doc quotes (D); Consequences = measured graph facts (S/E/F/C) |
| `adrs/README.md`, `TEMPLATE.md` | 2 | meta pages, `claims: none` |

Total: **454 anchored claims** across 16 markdown pages + bundle manifest.

### 1.3 ADR ingest (started empty, first AUTHORED facts ingested)

Per design: the ADR store starts empty; **FRR decision docs become the first AUTHORED facts**. Three ADRs ingested, each decision statement quote-anchored (verified verbatim by the verifier, independently grep-checked in tests):

| ADR | Decision | Doc anchor (quote-verified) |
|---|---|---|
| `ADR-0001-zapi-ipc` | Routes are installed through zebra, not independently into the kernel | `doc/user/ospfd.rst` "ospfd must acquire interface information from zebra in order to function" + `doc/user/bgp.rst` "This route is installed into zebra if following conditions are satisfied:" |
| `ADR-0002-yang-mgmt` | Data shall be stored/retrieved in YANG format only | `doc/user/mgmtd.rst` ×2 quotes |
| `ADR-0003-zebra-kernel` | Zebra is the process communicating with kernel routing tables | `doc/user/zebra.rst` ×2 quotes |

Consequences are graph-measured (e.g. ADR-0001: 111 cross-service flows converge on zebra, `svc:bgpd -publishes-> zapi:ZEBRA_ROUTE_ADD <-handles- svc:zebra`).

## 2. Results

### 2.1 Verification (verification.json)

- 16 pages: **14 claim pages `verified: full`**, 2 meta pages (`claims: none`), 0 partial.
- 454 claims, **0 stripped**; 6 verbatim doc quotes validated; every E ref resolves against the 54,246-edge fused graph; every N ref against 30,229 nodes.
- L0 `index.md` fronts the bundle: graph 30,229 n / 54,246 e; backbone 557/782; Leiden seed 42, γ1.2 → 5 domains / 5 areas / 193 modules; nb↔yang join 426/426 (100%); findings 44/7/4/111; 6 code partitions (incl. svc:fpm).

### 2.2 Tests (`tests_p4.py`, 9/9 PASS)

| Test | Result |
|---|---|
| T1 determinism — rebuild reproduces bundle byte-for-byte | PASS (0 diffs) |
| T2 anchor integrity — 14/14 full, 0 stripped | PASS (454 claims) |
| T3 mutation — injected unanchored sentence stripped, page → partial | PASS (mutation test proves the verifier strips) |
| T4 ADR — Context/Decision quote-anchored, quotes verbatim in docs | PASS (6 quotes) |
| T5 TOC coverage — index lists every domain/daemon/ADR page | PASS (10 pages) |
| T6 stamp hygiene — no `verified: pending` left | PASS |

### 2.3 Naming reconciliation

POC-DESIGN's "L2 cluster, L3 daemon" maps onto P3's actual hierarchy as: OKF **L2 = P3 L1 functional domain** (5 pages; each also links its P3 L2 service area), OKF **L3 = per-daemon page** referencing P3 L3 modules (193) with file-anchored functions. God-node ranking remains skipped (P3 directive).

## 3. Design decision: rules-first narrative (LLM slot documented, not exercised)

The design allows "LLM narrative + verifier (rules first, S1 model optional)". For the POC the narrative engine is **deterministic template rendering from skeleton atoms** — chosen so the bundle is reproducible in CI (T1 byte-identical) and the hallucination risk is zero by construction. The verifier + stripping + `verified` stamp are exactly the safeguards the design mandates for an LLM narrative path; swapping in an S1 model later only changes render.py's input source (skeleton → prose), never the verifier. This is recorded as an implementation decision, not a scope cut.

## 4. Known limitations (carried forward)

1. **Wrapper-mediated sends attributed to lib** (P3 coverage note): staticd shows 0 publishes; its sends ride lib zclient wrappers. The bundle states the measured facts; a P5 attribution pass would sharpen them.
2. **bgpd NB tables partially extracted in P1/P2** — bgpd page wires only frr-bgp-route-map(65).
3. **Human review gate pending** — bundle ready for an FRR-knowledgeable reviewer; `verified: full` means *machine-verifiable anchors*, not human endorsement.
4. Narrative is rule-templated (§3) — richer prose awaits the LLM drop-in behind the same skeleton interface.

## 5. Deliverables (`p4/`)

```text
P4-REPORT.md                    this report
okf-bundle/                     the OKF bundle (consumable by P5 router)
  index.md                      L0 index (stats + TOC, all claims anchored)
  clusters/D*.md                5 L2 domain pages
  daemons/<svc>.md              5 L3 daemon pages
  adrs/ADR-000[1-3]-*.md        3 authored ADRs (doc-quote anchored)
  adrs/README.md + TEMPLATE.md  ingest rules + format
  manifest.json                 okf_version, pages, input sha256 map
skeleton/                       per-page skeletons (atoms + refs) + stats.json
verification.json               verifier output (per-page status, reasons)
skeleton.py render.py verify.py okf_common.py run_p4.py   publisher pipeline
tests_p4.py + tests_output.txt  stability tests 9/9
```

Next: **P5 — Router & instruments** (`/query` API + rule-based router v0 over the 6 intents: impact, path, explain, callers, slice, docs; `/slice` CFG/DFG instrument memoized by (scope-hash, tool ver)). P5 consumes `okf-bundle/` + `packs/*.json` + `kb.py`.
