# P5 Report — Router v0 (6 Intents, No LLM) + In-RAM KB Map + /slice Instrument

**Status:** P5 COMPLETE (2026-11-12). Exit gate demonstrated end-to-end in `p5/demo_transcript.txt`: **structural questions answered in milliseconds with per-hop evidence** (path 0.28ms, callers 0.11ms, impact 548ms cold → 0.11ms memoized); **lifetime/dataflow question answered via the scoped /slice instrument** (`zread_route_add`: CFG 51 blocks / 72 edges, DFG 20 defs / 94 def-use chains, params recovered from the `ZAPI_HANDLER_ARGS` macro expansion, 495.8ms cold compute); **repeat question = cache hit** (0.05–0.06ms, `cache_hit=True`). All six router intents covered rule-based with zero LLM. Tests **69/69** (`p5/tests_output.txt`, includes real-socket HTTP e2e).

**Scope per POC-DESIGN:** *"`/query` API + rule-based router v0 (6 intents); `/slice` CFG/DFG instrument, memoized by (scope-hash, tool ver)"*. Router note: *"`impact`, `path`, `explain`, `callers`, `slice` (dataflow), `docs`. S1-model router is a drop-in later behind the same interface; golden set from P6 tunes it."*

---

## 1. Method

### 1.1 Architecture (`scripts/p5/`)

```
P2 facts.duckdb ─┐
P3 clusters/profiles/packs ├─► kbmap.KB ──► router.classify ──► intents backends ──► server
P4 okf-bundle/ ──┘   (in-RAM,     (64 weighted      (impact/path/explain/     (/query /slice /health)
                      fingerprint) rules, no LLM)    callers/docs; evidence)
                                      └────────────► slice.SliceEngine ──► /slice
                                                       (CFG+DFG+liveness, disk-memoized)
```

- **kbmap.py — the in-RAM map.** Loads once at startup (553–621ms): the P2 fused graph via `scripts/p2/kb.py` reused verbatim (`Graph`/`connect`), the P3 cluster layer (`clusters.jsonl`, `profiles.jsonl`, assignments, `packs/`), and the P4 OKF bundle (`manifest.json` + pages) — **30,229 nodes / 54,246 fused edges / 203 clusters (5 domains + 5 areas + 193 modules) / 14 OKF claim pages**. Builds entity-linking indexes (service aliases `bgpd/bgp/zebra/ospfd/staticd/lib`, qualified `svc:`/`code:`/`yang:`/`zapi:` IDs, bare function names, YANG leaf paths, ZAPI enums; stopword guard so intent words never become entities). Computes a **content fingerprint** = sha256 over the P4 manifest `inputs_sha256` + the fact-DB stat, truncated to 16 hex chars (`7574aee1e25c0fa5` at this input set; moved from `4c1575b460638dda` when the P6 determinism check rewrote the fact DB — mtime enters by design, content proved byte-identical) — every cache key embeds it, so any upstream input change invalidates all caches automatically.
- **router.py — rule-based v0, no LLM.** 65 weighted regex rules over the 6 intents (tie-break order slice > callers > impact > path > docs > explain; the 65th rule and the docs ADR fallback were added by the P6 golden-set loop — see `p6/P6-REPORT.md` §3); `confidence = best / (best + second)`; every decision ships its fired rules and score vector, so the S1-model router can drop in behind the same interface and be A/B-compared (design note). Explicit `/intent` prefix overrides.
- **intents.py — five backends.** Every answer carries evidence (`tag:plane` + `src_ref`) drawn from the fused graph; **no answer without an anchor**.
  - `impact` — YANG-leaf mode: NB entries → `implements` anchor → code callbacks → owning daemons → ZAPI side effects with handlers; memoized per `(id, call_depth)` at the KB layer. Code/svc/zapi targets: reverse-closure over `calls` edges + `publishes` side effects.
  - `path` — prefers the evidence-dense **2-hop ZAPI hub-and-spoke flow** (`s -publishes-> msg <-handles- d`, or the reverse for notifications; deterministic ROUTE-first message choice), falls back to BFS over all endpoint-ID pairs (`max_hops`).
  - `explain` — adjacency grouped by relation with per-peer evidence, plus the node's P3 clusters/domain.
  - `callers` — `zapi:` mode returns senders + handlers + dispatch site (`src_ref` into `zapi_msg.c`); `code:` mode returns callers + the messages the function serves.
  - `docs` — P3 cluster profiles (no-LLM functionality/roles) + the sha256-anchored domain pack (hash from the P4 manifest) + P4 OKF pages + ADR keyword scan, with the bundle's `verify` stamp carried through.
- **slice.py — the /slice instrument.** Scoped to ONE function (design §2 mode 2: computed on demand, **memoized by (content-hash(scope), tool version)**, never persisted as a global graph). Reuses the P1 parse setup — `clang.cindex` + `compile_commands.json` via `clang_facts.sanitize_args` (the "same tool" family). CFG: statement-level basic blocks with `then/else/loop-true/loop-false/exit-false/switch/case/latch/return/goto` edges. DFG: reaching-definitions worklist over the CFG → per-use def chains. Liveness: backward live-variable sets, params live-in at entry. Var identity: referenced-decl USR for plain variables, `base->field` access paths for member lvalues (v0 granularity, §4). Function parameters — including those hidden behind the `ZAPI_HANDLER_ARGS` macro — come from the expanded declaration. Tool version: `p5-slice/1.0.0+clang18`.
- **server.py — `/query` + `/slice` + `/health` + `/admin/cache/clear`.** ThreadingHTTPServer; query cache keyed by `(normalized question, intent, max_hops, call_depth, kb fingerprint)`; thread-safe with hit/miss stats. CLI: `--serve [--port 8915]`, `--ask "…"`, `--slice FILE FN`, `--json`.

### 1.2 Cache design (why two caches)

| Cache | Key | Store | Invalidated when |
|---|---|---|---|
| Query cache | sha256(norm question, intent, max_hops, call_depth, **kb fingerprint**) | RAM | KB map reloads with changed inputs (fingerprint moves) or `/admin/cache/clear` |
| Slice cache | sha256(scope file+function content) + **tool_ver** | disk `poc/facts/p5/cache/slices/<sha>.json` | source content changes or the tool version bumps (extractor bump ⇒ versioned recompute, per design risk table) |

The demo additionally exercises a third, KB-level memo for `impact` on YANG leaves (`(id, depth)`-keyed), which is why gate-3's impact repeat is 0.1ms even in a fresh process.

## 2. Results

### 2.1 Exit gates (transcript: `p5/demo_transcript.txt`)

| Gate | Question | Measured |
|---|---|---|
| 1 — structural Q in ms, evidence carried | `path from svc:bgpd to svc:zebra` | 0.28ms, 2 hops via `zapi:ZEBRA_ROUTE_ADD`, per-hop evidence (2 items, tag:plane + src_ref) |
| 1 | `who handles ZEBRA_ROUTE_ADD` | 0.11ms — senders bgpd/lib/ospfd, handler `zread_route_add @ zebra/zapi_msg.c:4139`, 5 evidence items |
| 1 | `who calls zclient_route_send` | 0.1ms — 10 callers across bgpd/ospfd/staticd/lib |
| 1 | `impact of yang:frr-bgp-route-map:ipv4-address` | 547.9ms cold — daemons bgpd; 4 NB callbacks; 6 ZAPI side effects w/ handlers → **0.11ms memoized** |
| 2 — lifetime/dataflow via scoped /slice | `slice zread_route_add in zebra/zapi_msg.c` | CFG 51 blocks / 72 edges (entry 0 → exit 1); DFG 20 defs / 94 chains / 61 possibly-undef uses; params `client, hdr, msg, zvrf` (from `ZAPI_HANDLER_ARGS` expansion); compute 495.8ms, **memoized by (content-hash, tool ver)** |
| 2 | `where does the value of api come from in zread_route_add?` | routed to the same scope, 0.87ms, def-use chains excerpted from the memoized slice (`api` produced by `zapi_route_decode`) |
| 3 — repeat Q = cache hit | repeats of gate-1 Qs | 0.06ms / 0.05ms / 0.11ms, all `cache_hit=True`; query cache 3 hits / 6 misses; slice cache 2 hits |

Router coverage of all six intents (rule-based v0, no LLM): callers 0.06ms conf 1.0 · path 0.14ms conf 1.0 · explain 0.12ms conf 1.0 · impact 0.12ms conf 0.6 · docs 0.77ms conf 0.6 · slice 0.75ms conf 1.0. Demo wall time **1.2s including KB load**.

### 2.2 Tests (`tests_p5.py`, 69/69 PASS, 2.8s)

| Suite | Checks | Result |
|---|---|---|
| T1 router goldens | 17 golden Q→intent pairs + explicit-override + unknown-rejected | PASS (19) |
| T2 entity linking | zapi enum, svc with punctuation, qualified IDs, bare function, YANG leaf, defining file, code→svc domain bridge | PASS (7) |
| T3 callers backend | P2 exit-gate flow re-checked (senders, handler fn, src_ref evidence) | PASS (6) |
| T4 path backend | 2-hop ZAPI flow, `publishes→handles` pattern, per-hop evidence, degenerate path clarified | PASS (5) |
| T5 impact backend | daemons/callbacks/side-effects/evidence + KB-memoized re-ask <50ms | PASS (5) |
| T6 slice instrument | CFG invariants (entry/exit, block count, edge kinds, no exit successors), macro-expanded params, def-use chains, liveness subset, memoization on repeat, code_id resolution, loop back-edges, unknown-fn clarify | PASS (14) |
| T7 query cache | repeat hit, latency drop, case/whitespace normalization, different Q = miss | PASS (4) |
| T8 docs backend | P3 pack found, sha256 anchored, no-LLM functionality, OKF pages referenced | PASS (4) |
| T9 HTTP e2e | real sockets: /health, /query, /slice, repeat-query cache hit, 404 | PASS (5) |

## 3. Design decisions

1. **No LLM anywhere in P5** (router v0 keyword rules; backends pure graph/parsing) — per the P3/P5 no-LLM directives; the S1-model router is a documented drop-in behind `classify()`'s interface, tuned by the P6 golden set.
2. **Answers from an in-RAM map**, not per-query DuckDB: ms-level structural answers are the gate; the map fingerprint makes staleness detectable rather than assumed.
3. **Path prefers the 2-hop ZAPI flow over BFS**: the P2 graph is hub-and-spoke (`publishes`/`handles` through `zapi:` nodes), so the evidence-dense pattern is both faster and more faithful; BFS remains for non-ZAPI endpoints.
4. **Slice memoized exactly per design** — `(content-hash(scope), tool ver)` on disk — so CI re-runs and cache audits are possible; `force=True` bypasses for debugging.
5. **Impact on YANG leaves memoized at the KB layer** (separate from the query cache) because the same leaf recurs across questions; result ships with `memoized` flag for honesty.

## 4. Known limitations (carried forward)

1. **Router v0 confidence on overlap-heavy phrasings is 0.6** (impact/docs vs explain keyword overlap) — acceptable for the POC; the P6 golden set tunes rules, and the S1 router replaces them behind the same interface.
2. **Slice granularity v0**: statement-level CFG; member lvalues identified as `base->field` access paths (no field-sensitive analysis); single-function scope (no interprocedural slicing); "possibly-undef" uses are conservative and include macro-expansion artifacts (e.g. `_xrefdata`).
3. **Wrapper-mediated sends still attributed to `svc:lib`** (P2/P3 coverage note): staticd shows 0 publishes; impact/callers answers that traverse those edges inherit the coarser attribution.
4. **bgpd NB tables partially extracted** (P1/P2 note) — bgpd YANG-leaf impact is narrower than reality.
5. **POC server**: single-process, localhost-only, no auth/TLS/persistence — appropriate for the demo gate, not for deployment.

## 5. Deliverables (`p5/`)

```text
P5-REPORT.md              this report
demo_transcript.txt       exit-gate demo (3 gates + 6-intent router coverage)
tests_output.txt          tests_p5.py run log (69/69)
server.py                 /query /slice /health endpoints + Service + CLI
router.py                 rule-based router v0 (64 rules, 6 intents, no LLM)
intents.py                impact/path/explain/callers/docs backends (evidence-carried)
kbmap.py                  in-RAM KB map (P2 graph + P3 clusters + P4 OKF) + fingerprint
slice.py                  /slice instrument (CFG/DFG/liveness, memoized by scope-hash+tool ver)
tests_p5.py               69-check test suite incl. HTTP e2e
demo_e2e.py               exit-gate demo driver (writes demo_transcript.txt)
cache/slices/*.json       the 2 memoized slice artifacts (content-hash keyed)
```

Next: **P6 — Eval & port** (golden set ≈100 questions vs FRR docs; precision/recall report; port pipeline to SONiC swss slice). P5 hands P6 a working `/query` surface, a transparent router to tune against the golden set, and the cache/fingerprint machinery for CI.
