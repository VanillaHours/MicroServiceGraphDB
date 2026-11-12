# P1 Report — Extractors (CLOSED)

**Date:** 2026-11-12 · **Source pin:** FRR `frr-10.7.1` (unchanged from P0) ·
**Extraction universe:** 356 slice TUs (`lib`, `zebra`, `bgpd`, `staticd`, `ospfd`)
from P0's `compile_commands.json` · **Verdict: both P1 exit gates PASS.**

## 1. Exit gates (POC-DESIGN.md §4)

| Gate | Status | Evidence |
|---|---|---|
| Fact DB covers `lib/ + zebra + bgpd + staticd` | **PASS** | code-plane nodes per dir: bgpd 8,407 · lib 8,259 · zebra 6,945 · staticd 579 (+ ospfd 3,009 bonus) — `load_summary.json:code_nodes_by_dir` |
| 20-fact spot check vs source passes | **PASS** | 20/20 verified against pinned source at `src_ref` (`spot_check.txt`): 6 call (3 direct / 2 window / 3 macro-mediated classes among them), 5 nb_handles, 3 zapi_handles, 3 publishes, 2 yang, 1 build |

Deliverables (design §6): clang-facts tool (`clang_facts.py`) · `facts.duckdb` ·
coverage report (`coverage.json`, `load_summary.json`, per-extractor JSONs).

## 2. What was built

| Tool | Role | Output |
|---|---|---|
| `clang_facts.py` | libclang (v18 wheel) extraction: one fresh subprocess per TU, two passes (decl table → fact edges), per-TU crash isolation with retry + ledger | `nodes.jsonl`, `edges.jsonl` |
| `yang_facts.py` | pyang Python API over 58 FRR models + libyang's standard-module store | `yang_*.jsonl` |
| `build_facts.py` | compile_commands → svc/TU build-plane facts | `build_*.jsonl` |
| `load_facts.py` | bulk JSONL → DuckDB (frozen schema v0.1.0), PK-dedup, referential filter, `extractor_coverage` ledger | `facts.duckdb` |
| `spot_check.py` | the P1 gate: samples facts, re-verifies each at its `src_ref` in source | `spot_check.txt` |

Parser setup learned on the way: absolute `-I` paths + gcc-14 builtin headers via
`-isystem`, input-file token stripped from argv, `CXTranslationUnit_KeepGoing`
(raw `0x1000`) for best-effort ASTs, and **fork+Queue deadlocks** in this sandbox —
hence the subprocess-per-TU isolation (a worker crash or hang loses one TU and is
recorded as a ledger skip; final run: zero skips, zero parse exceptions).

## 3. The fact base

| plane | edges | notes |
|---|---|---|
| code (DECLARED) | 78,482 | 78,482 call edges resolved **semantically** via `cursor.referenced` — zero name-ambiguity; 58,142 external (system headers) and 1,149 fn-pointer calls correctly left unresolved |
| contract (DECLARED) | 1,396 | 45 modules, 1,943 yang nodes |
| wiring (DECLARED) | 1,516 | nb + zapi facts below |
| build (BUILD) | 356 | svc → TU |

Nodes: 30,092 total · 157 ZAPI messages · 426 NB handler-table entries · 5 daemons.
Raw observations 190,000 → unique facts 82,047: the fusion rule working — header
inline-function call sites seen from many TUs collapse to one fact per `src_ref`.

Wiring detail:
- **NB tables** (`nb_reg`): 426 entries — zebra 183 · lib 147 · bgpd 68 · staticd 27 · ospfd 1;
  each emits `(svc registers nb)` + `(nb handles code:cb)` with the expanded-AST
  designated-initializer walk (1,058 tables pre-dedup; 184 empty-cbs entries kept).
- **ZAPI handler tables** (`zapi_reg`): 10 `zclient_handler` tables → 59 svc-level +
  59 fn-level `handles` edges (bgpd 32, lib 11, ospfd 8, staticd 8).
- **Send side** (`type`): 92 `publishes` edges (zebra 37, lib 33, bgpd 22) from
  `zclient_create_header`/`zebra_message_send` call sites, enum extracted under
  implicit casts.

Cross-service shape (P3 preview): 37,900 of 78,482 call edges cross dirs;
bgpd→lib alone is 19,596 — `lib` is the universal callee, exactly the hub
profile the design predicts for god nodes.

## 4. The P2 join — measured, gap understood

Direct join `nb:<dir>:<xpath>` → `yang:<module>:<path>` (string transform):
**121/426 (28%)**. The 75% miss rate decomposes into exactly two causes, both now
understood:

1. **NB xpaths are libyang *schema* paths** — they can contain choice/case
   segments (`…/entry/match-condition/rmap-match-condition/…`) while pyang AST
   paths are data-style. Deciding per-segment is ambiguous without libyang context.
2. **Cross-module augments** — `frr-staticd:staticd/route-list` augments
   `frr-routing:routing/control-plane-protocols/control-plane-protocol`; our
   pyang walk keeps augmented nodes under the defining module, NB xpaths use the
   full target path.

**P2 decision (carried forward):** do the validation join with **libyang itself**
(`poc/deps/usr` already has libyang 2.1.148) — load the 58 modules into a context
and emit lysc schema paths, the same strings FRR's `nb_info_new` consumes. That
replaces pyang for the contract plane's path naming (pyang remains useful for
structure). Target: ≥90% nb↔yang join before fusion runs.

## 5. Known gaps (ledgered, not silent)

- Scalar `zclient->…_cb = fn` lifecycle registrations (~5 per daemon) are not yet
  extracted — they are connection-level wiring, not message handlers; P2 optional.
- 1,387 edges dropped by the referential filter (targets outside extracted decl
  set); count visible in `load_summary.json`.
- `fpm` dir contributes 6 stray call-target nodes (zebra→fpm header decls).
- Binary/library-only callees (libc, openssl) classified `external` — by design.
- `extractor_coverage` counts are unique-fact counts computed from final tables;
  raw per-TU observation counts remain in `coverage.json` (e.g. 769,948 decl
  observations → 27,205 unique code nodes).

## 6. Reproduce

```bash
cd /home/z/my-project/poc
python3 /home/z/my-project/scripts/p1/build_facts.py                  # build plane
python3 /home/z/my-project/scripts/p1/clang_facts.py                  # ~8.5 min, 356 TUs
python3 /home/z/my-project/scripts/p1/yang_facts.py                   # contract plane
python3 /home/z/my-project/scripts/p1/load_facts.py                   # facts.duckdb
python3 /home/z/my-project/scripts/p1/spot_check.py                   # gate: 20/20
```

Extraction runs the pinned FRR tree at `poc/src/frr-10.7.1` (restore recipe in
`p0/P0-REPORT.md §4`) and needs `pip install libclang pyang duckdb`.
