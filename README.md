# MicroServiceGraphDB

A data-driven, **framework-layer code knowledge base**: index a real codebase once, then answer
architecture questions over HTTP with **evidence-carrying answers** — deterministic, fully
rule-based, **no LLM anywhere in the loop**.

POC target: **FRR 10.7.1** (a real 30k-node C codebase) standing in for a
**200-microservice estate** where services register with a framework and talk through
its message bus — the layer that grep cannot see.

---

## Overview

Micro-service frameworks create two kinds of structure that are invisible to text search:

1. **Registration** — a service hands the framework a table of handlers ("when message X
   arrives, call my function Y"), usually via function pointers, macros or generated code.
2. **Message passing** — services publish opaque messages on a bus; the *framework*, not the
   caller, decides who runs.

This project builds a knowledge base of exactly that layer from plain source code, without
any runtime instrumentation or LLM summarization:

- **P1** extracts facts from C/C++ with libclang and from YANG schema files (the northbound
  IDL) into a DuckDB fact store.
- **P2** fuses them with the *message plane*: ZAPI publish/dispatch edges recovered from the
  server-side dispatch table and client-side send wrappers, cross-checked against libyang
  compiled schema paths. 30,229 nodes; 82,477 raw edges fuse to **54,246**.
- **P3** clusters the graph hierarchically with **Leiden** (graph-RAG style, no LLM) into
  203 clusters across 3 levels, with one pack of grounded facts per domain.
- **P4** renders an "open knowledge frame" bundle — 454 anchored claims with provenance,
  daemon pages, ADRs.
- **P5** is the query layer: a 65-rule weighted router maps free-text questions onto **6
  intents** (callers / path / impact / explain / docs / slice), each answered from a
  dedicated backend against an in-RAM KB. Every answer carries `tag:plane` + `src_ref`
  evidence — **no anchor, no answer**. `/slice` computes a real CFG + DFG + liveness for one
  function on demand with libclang.
- **P6** evaluates it: a 103-question golden set with independently re-verified ground truth.

**POC results (measured, see `docs/reports/P6-REPORT.md`):**

| Metric | Value |
|---|---|
| Golden set | 103 questions, ground truth re-verified against source + docs |
| Exact answers | **103/103 (100%)**, routing accuracy 1.000 |
| Evidence anchor rate | 1.00 on every item-level intent |
| Latency | p50 **0.22 ms**, p95 555 ms (cold impact closure) |
| Cold re-index P1→P4 | 520.7 s for 356 translation units |
| Knowledge base size | 43.3 MB ≈ **73 KB per source KLOC** |
| Eval-driven fixes | 5 real defects found & fixed by the golden set |
| Findings beyond grep | 4 dead registrations, 7 dropped-on-wire messages, 44 orphan handlers |

The repo **ships the real fused KB** (`data/facts/`, ~45 MB), so every query below works
out of the box after `pip install` — no rebuild needed.

## Features

- **Evidence-carrying answers.** Every item in every response carries a `src_ref`
  (`file:line`) and a plane tag (`DECLARED:code`, `fusion:send-grep`, …). Answers without
  anchors are refused, not invented.
- **Six intents, one router, zero LLM.** 65 weighted lexical rules with transparent
  `rules_fired` + confidence in every response; ties broken deterministically.
- **Message-plane fusion.** `svc:bgpd -publishes-> zapi:ZEBRA_ROUTE_ADD <-handles- svc:zebra`
  style edges recovered statically, server dispatch and client sends cross-checked against
  YANG schema paths (426/426 northbound paths matched, 100%).
- **On-demand program slices.** Statement-level CFG (with then/else/loop/switch edges),
  reaching-definitions DFG with def-use chains, and backward liveness — computed per request
  with the same libclang setup as the indexer, memoized by content hash + tool version.
- **Graph-RAG clustering without an LLM.** Hierarchical Leiden over the fused graph; per-domain
  packs of grounded claims; explanations cite the cluster a symbol belongs to.
- **Three-tier caching.** In-RAM query cache, on-disk slice cache, memoized impact closure —
  repeat questions answer in ~0.05–0.1 ms.
- **HTTP server + CLI.** `ThreadingHTTPServer` with `/query`, `/slice`, `/health`,
  `/admin/cache/clear`; the same engine callable one-shot from the command line.
- **Measured, not vibes.** A 103-question golden set with anti-circular ground-truth
  verification, stage-wise indexing timings, storage accounting, and a KPI book
  (`p6/kpis.json`).
- **Portable by construction.** All paths resolve through env vars (`MSG_ROOT`, `MSG_SRC`,
  `MSG_CC`, `MSG_PUB`, `MSG_LIBCLANG`); the packaged code contains no absolute paths.

## Steps for setup

Requirements: Linux (tested), Python **3.12**, pip. The `libclang` wheel ships the shared
library — no system LLVM needed.

```bash
git clone https://github.com/VanillaHours/MicroServiceGraphDB.git
cd MicroServiceGraphDB

python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt          # duckdb, igraph, leidenalg, libclang

# sanity check: 69 checks incl. a real-socket HTTP end-to-end test (~3 s)
python p5/tests_p5.py

# start the server (default port 8915)
python p5/server.py --serve
```

The server boots in ~0.6 s from `data/facts/p2/facts.duckdb` and answers all query intents
immediately. `/slice` additionally needs the target source tree and its compile database:

```bash
# Option A: point the env at any FRR 10.7.1 checkout + its compile_commands.json
export MSG_SRC=/path/to/frr-10.7.1
export MSG_CC=/path/to/compile_commands.json

# Option B: build FRR + libyang2 from upstream the same way the POC did
# (p0/build_frr_p0.sh downloads, configures and builds, recording compile_commands.json)
```

Without a compile database the 5 query intents still work; `/slice` returns a per-request
error telling you to set `MSG_CC`.

**Environment variables**

| Variable | Default | Purpose |
|---|---|---|
| `MSG_ROOT` | `<repo>/data` | workspace root: fact DB, clustering artifacts, slice cache |
| `MSG_SRC` | `$MSG_ROOT/src/frr-10.7.1` | source tree used by `/slice` |
| `MSG_CC` | `$MSG_ROOT/compile_commands.json` | compile database used by `/slice` |
| `MSG_PUB` | `<repo>/out` | published outputs (demo transcript) |
| `MSG_LIBCLANG` | auto-detect | explicit path to `libclang.so` |

## Usage

**Server mode** (all examples below use this):

```bash
python p5/server.py --serve                # listens on http://127.0.0.1:8915
python p5/server.py --serve --port 9000
```

**CLI mode** (one-shot, same engine):

```bash
python p5/server.py --ask "who handles ZEBRA_ROUTE_ADD"
python p5/server.py --ask "what is the impact of yang:frr-bgp-route-map:ipv4-address" --json
python p5/server.py --slice zebra/zapi_msg.c zread_route_add --json
```

**Endpoints**

| Method | Path | Body | Returns |
|---|---|---|---|
| GET | `/health` | – | KB stats, fingerprint, cache counters, tool versions |
| POST | `/query` | `{"question": "..."}` | routed intent + answer + evidence + routing trace |
| POST | `/slice` | `{"file": "...", "function": "..."}` | CFG, DFG, liveness for one function |
| POST | `/admin/cache/clear` | `{}` | clears the query cache |

**What the router understands** (intent → example question):

| Intent | Example |
|---|---|
| `callers` | *who handles ZEBRA_ROUTE_ADD* · *who calls zclient_route_send* |
| `path` | *path from svc:bgpd to svc:zebra* |
| `impact` | *what is the impact of yang:frr-bgp-route-map:ipv4-address* |
| `docs` | *what are the responsibilities of ospfd* |
| `explain` | *explain code:zebra::zread_route_add* |
| `slice` | POST `/slice` with file + function |

**Demo & tests**

```bash
python p5/demo_e2e.py        # end-to-end scripted demo, writes out/demo_transcript.txt
python p5/tests_p5.py        # 69 checks, self-contained against the shipped KB
```

## Tool table

| Tool | Version | Role |
|---|---|---|
| Python | 3.12.16 | runtime; stdlib `http.server` / `threading` for the query service |
| DuckDB | 2.0.0 | fact store (P1/P2), in-RAM KB queries |
| libclang (pip `libclang`) | 18.1.1 | C/C++ AST facts (P1) and on-demand CFG/DFG/liveness slices (P5), via `clang.cindex` |
| python-igraph | 1.0.0 | graph operations: paths, impact closure, cluster lookups |
| leidenalg | 0.12.0 | hierarchical Leiden community detection (P3) |
| compiledb + CMake | – | record `compile_commands.json` while building FRR/libyang (P0) |
| FRR 10.7.1 (+ libyang2) | input | POC target codebase — downloaded at build time, **not redistributed** |
| LLM | **none** | routing, answering, clustering and docs are fully deterministic rules + graph ops |

## Curl examples from real db

All responses below were captured from the **shipped KB** (fingerprint `db5d33a41bf1d576`,
KB load 572.6 ms). Raw JSON for every example is in
[`examples/responses/`](examples/responses/). Latencies were measured on the POC sandbox
(2 cores); your numbers will vary, the *shape* will not.

### 1. Health — what is loaded

```bash
curl -s http://127.0.0.1:8915/health | python3 -m json.tool
```

```json
{
 "status": "ok",
 "kb": {"nodes": 30229, "edges_raw": 82477, "edges_fused": 54246,
        "clusters": 203, "okf_pages": 14, "packs": 5,
        "fingerprint": "db5d33a41bf1d576", "load_ms": 572.6},
 "slice_engine": {"parses": 0, "computes": 0, "hits": 0},
 "query_cache": {"hits": 0, "misses": 0, "entries": 0}
}
```

### 2. Who handles a message (the framework's dispatch, statically)

```bash
curl -s -X POST http://127.0.0.1:8915/query \
     -H 'Content-Type: application/json' \
     -d '{"question": "who handles ZEBRA_ROUTE_ADD"}'
```

Answer in **0.19 ms**, confidence 1.0 — 3 senders, 2 handlers, 5 evidence items:

```json
{
 "intent": "callers", "confidence": 1.0,
 "routed": {"scores": {"callers": 3, "slice": 0, "impact": 0, "path": 0, "docs": 0, "explain": 0},
            "rules_fired": [["callers", "who handles"]]},
 "entities": [{"mention": "ZEBRA_ROUTE_ADD", "kind": "zapi"}],
 "answer": {
   "target": "zapi:ZEBRA_ROUTE_ADD", "mode": "zapi",
   "senders":  [{"node": "svc:bgpd", "src_ref": "fusion:send-grep"},
                {"node": "svc:ospfd", "src_ref": "fusion:send-grep"},
                {"node": "svc:lib",  "src_ref": "fusion:send-grep"}],
   "handlers": [{"node": "svc:zebra",                  "src_ref": "zebra/zapi_msg.c:4133"},
                {"node": "code:zebra::zread_route_add", "src_ref": "zebra/zapi_msg.c:4139"}],
   "evidence": [{"rel": "publishes", "dir": "in", "peer": "svc:lib",
                 "evidence": ["DECLARED:wiring"], "src_ref": "fusion:send-grep"}]
 }
}
```

### 3. Who calls a function (10 call sites, all anchored)

```bash
curl -s -X POST http://127.0.0.1:8915/query \
     -d '{"question": "who calls zclient_route_send"}'
```

**0.17 ms**, confidence 1.0 — `callers` list of 10, each with `file:line`:

```json
{"answer": {"callers": [
   {"node": "code:lib::zclient_send_localsid",  "service": "svc:lib",   "src_ref": "lib/zclient.c:603"},
   {"node": "code:ospfd::ospf_zebra_add",       "service": "svc:ospfd", "src_ref": "ospfd/ospf_zebra.c:352"},
   {"node": "code:ospfd::ospf_zebra_delete_discard", "...": "ospfd/ospf_zebra.c:426"}]}}
```

Re-asking the same question hits the query cache: **0.08 ms**, `"cache_hit": true`.

### 4. Path between two services (message-bus hop included)

```bash
curl -s -X POST http://127.0.0.1:8915/query \
     -d '{"question": "path from svc:bgpd to svc:zebra"}'
```

**0.30 ms** — a 2-hop ZAPI flow with per-hop evidence:

```json
{"answer": {"hops": 2, "via": "zapi:ZEBRA_ROUTE_ADD", "path": [
   {"from": "svc:bgpd", "to": "zapi:ZEBRA_ROUTE_ADD", "rel": "publishes"},
   {"from": "zapi:ZEBRA_ROUTE_ADD", "to": "svc:zebra", "rel": "handles"}]},
 "text": "path svc:bgpd -> svc:zebra  (2 hops)  via zapi:ZEBRA_ROUTE_ADD (ZAPI flow)\n  evidence items: 2 (per-hop tag:plane + src_ref)"}
```

### 5. Impact of a northbound YANG leaf (the deep one)

```bash
curl -s -X POST http://127.0.0.1:8915/query \
     -d '{"question": "what is the impact of yang:frr-bgp-route-map:ipv4-address"}'
```

**552 ms cold** (depth-10 NB → callbacks → ZAPI closure; **0.1 ms memoized**), confidence 0.6:

```json
{"answer": {
   "target": "yang:frr-bgp-route-map:ipv4-address", "mode": "yang-leaf",
   "daemons": ["svc:bgpd"],
   "nb_entries": 2, "callbacks": 4,
   "zapi_side_effects": {"zapi:ZEBRA_INTERFACE_ADD":     ["svc:lib", "svc:zebra"],
                         "zapi:ZEBRA_GET_LABEL_CHUNK":   ["svc:zebra"],
                         "zapi:ZEBRA_ROUTE_NOTIFY_OWNER":["svc:bgpd", "..."]},
   "evidence": ["… 6 items …"]}
```

Grep baseline for the same question: **0 files hit** — the question vocabulary never
appears in the code; only the graph join answers it.

### 6. Docs for a service (cluster pack + OKF bundle pages)

```bash
curl -s -X POST http://127.0.0.1:8915/query \
     -d '{"question": "what are the responsibilities of ospfd"}'
```

**1.01 ms** — grounded excerpts from the P3 pack and P4 bundle:

```json
{"answer": {"clusters": 2, "okf_pages": [{"page": "daemons/ospfd", "okf_level": "L3-daemon", "atoms": 30}],
            "adrs": [{"adr": "ADR-0001-zapi-ipc.md"}, "..."],
            "evidence": ["… 2 items …"]},
 "text": "docs for svc:ospfd\n  domain pack Ded29f1c0 'ospfd [15z/1y]'\n    - ospfd is a route client: publishes 7 message types toward the ZAPI bus ..."}
```

### 7. Explain a symbol (cluster + call context)

```bash
curl -s -X POST http://127.0.0.1:8915/query \
     -d '{"question": "explain code:zebra::zread_route_add"}'
```

**0.19 ms**, confidence 1.0:

```json
{"answer": {"clusters": [{"id": "M749027f4", "level": "L3", "label": "zebra:rib"}],
            "calls": 15},
 "text": "code:zebra::zread_route_add  kind=function service=svc:zebra\n  clusters: M749027f4(L3)\n  domain pack: D4b2a9ab8\n  calls (15)\n    out code:lib::zapi_route_decode [DECLARED:code] zebra/zapi_msg.c:2162 ..."}
```

### 8. Slice one function (real CFG + DFG + liveness)

```bash
curl -s -X POST http://127.0.0.1:8915/slice \
     -H 'Content-Type: application/json' \
     -d '{"file": "zebra/zapi_msg.c", "function": "zread_route_add"}'
```

**1.2 ms** on disk-cache hit (first compute ≈ 0.5 s), tool `p5-slice/1.0.0+clang18`:

```json
{"scope": {"file": "zebra/zapi_msg.c", "function": "zread_route_add", "line_span": [2148, 2299]},
 "cfg":  {"n_blocks": 51, "n_edges": 72, "entry": 0, "exit": 1,
          "blocks": [{"id": 0, "tag": "entry",
                      "stmts": [{"kind": "DECL_STMT", "line": 2150, "spell": "struct stream * s ;"}]}]},
 "dfg":  {"defs": 20, "n_chains": 94, "undef_uses": 61,
          "chains": [{"use": "msg", "line": 2161, "stmt": "s = msg", "defs": ["d18"]}]},
 "liveness": {"params_live_at_entry": ["client", "msg", "zvrf"]}}
```

## Pipeline (P0–P6)

| Phase | What it does | Key artifact |
|---|---|---|
| P0 | Build FRR 10.7.1, freeze the fact schema, census | `compile_commands.json`, `schema.sql` |
| P1 | libclang + YANG extractors → DuckDB fact base | 30,092 nodes / 81,750 edges (~8.5 min) |
| P2 | Message-plane fusion: ZAPI dispatch + sends + lysc paths | `facts.duckdb` (54,246 fused edges), `findings.json` |
| P3 | Hierarchical Leiden clustering + per-domain packs | 203 clusters, packs, backbone |
| P4 | Open knowledge frame: anchored claims, daemon pages, ADRs | 454 anchored claims, 0 stripped |
| P5 | Router (65 rules) + 6 intent backends + slice engine + server | `server.py`, 69-check test suite |
| P6 | 103-question golden set, P/R eval, KPI book, SONiC rehearsal | `eval_results.json`, `kpis.json` |

Stage-wise indexing time and storage accounting are in
`docs/reports/P6-REPORT.md` (§4) and `p6/kpis.json`.

## Repository layout

```
MicroServiceGraphDB/
├── README.md, requirements.txt, .gitignore
├── p0/ … p6/            pipeline code, one directory per phase (Python + 2 shell/C helpers)
├── data/
│   ├── facts/           the real fused KB shipped with the repo (~45 MB)
│   ├── schema/          frozen fact schema (schema.sql)
│   └── census/          FRR census (json + md + png)
├── docs/
│   ├── POC-DESIGN.md    design contract, phase gates
│   ├── reports/         P0–P6 phase reports (P6 = eval + KPI book)
│   └── img/             architecture + phase diagrams
└── examples/responses/  raw JSON captured from the shipped KB (sources for the curls above)
```

## Documentation

- Design & phase gates: [`docs/POC-DESIGN.md`](docs/POC-DESIGN.md)
- Evaluation method, P/R table, honesty notes: [`docs/reports/P6-REPORT.md`](docs/reports/P6-REPORT.md)
- KPI book (indexing stages, storage, cache economics): `p6/kpis.json` + `docs/reports/P6-REPORT.md` §4
- Raw responses backing every curl above: [`examples/responses/`](examples/responses/)
