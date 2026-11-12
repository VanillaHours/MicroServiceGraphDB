# P0 Report — Baseline & Contracts (CLOSED)

**Date:** 2026-11-12 · **Source pin:** `frr-10.7.1` (upstream tag, via Debian orig tarball,
sha256 `b8fd6590…3ae52`) · **Verdict: all three P0 exit gates PASS.**

This report consolidates the P0 deliverables into one place. Build narrative lives in
`BUILD-P0.md`; census detail lives in `CENSUS.md`.

## 1. Exit gates

| Gate (from POC-DESIGN.md §4) | Status | Evidence |
|---|---|---|
| Build reproducible in CI | **PASS** | `build_frr_p0.sh` — staged (`deps → configure → slice → capture`), pins + 7 environment fixes encoded; build ran to 1035 objects / all daemons linked (`zebra` 7.7 MB, `bgpd` 14.7 MB) |
| Schema v0 committed | **PASS** | `schema.sql` v0.1.0 frozen; materialized as `facts.db` (DuckDB) and smoke-tested: fused-edge evidence merge, `n_planes` counting, CHECK constraints reject bad `plane`/`tag`, `meta` carries `schema_version=0.1.0`, `frozen_at=P0` |
| Census published | **PASS** | `CENSUS.md` + `census.json` + `census_loc.png`; cross-checked against the JSON machine output — all headline numbers match |

## 2. What P0 produced

| Artifact | What it is | Feeds |
|---|---|---|
| `compile_commands.json` | 740 compile commands, full tree, captured via `compiledb -n make -B` (dry run — same command lines bear would have intercepted). 100% spec-valid entries (`directory` + `file` + `arguments`). | P1 clang extractor input |
| `schema.sql` | Fact schema v0.1.0, FROZEN: `nodes`, `edges` (plane/tag provenance, CHECK-enforced), `fused_edges` view, `extractor_coverage` ledger | All later phases |
| `facts.db` | DuckDB database materialized from `schema.sql` (empty of facts — schema + meta only) | P1 fact inserts |
| `CENSUS.md` / `census.json` / `census_loc.png` | Repo census: 829 `.c` TUs, 1,371,970 LOC, 58 YANG models (28,021 lines), 28 `nb_cb_*` files, 21 unique ZAPI messages | P1–P3 scoping |
| `BUILD-P0.md` | Build narrative: pins, environment fixes, reproduce steps | Rebuilds / CI |
| `build_frr_p0.sh` | Copy of the pinned build script (canonical copy: `poc/tools/build_frr_p0.sh`) | Reproduce / restore |

## 3. Extraction universe (POC slice)

`compile_commands.json` is build-grounded: it lists only what actually compiles, which is
exactly the extraction universe P1 should follow (not the file tree). Per-directory TU
counts inside the POC slice (`lib/ + zebra/ + bgpd/ + staticd/ + ospfd/`):

| dir | compiled TUs | census `.c` files | delta meaning |
|---|---|---|---|
| `lib` | 141 | 144 | 3 files not compiled in this config |
| `zebra` | 83 | 91 | conditionally-compiled / noinst files |
| `bgpd` | 80 | 86 | same |
| `staticd` | 12 | — | |
| `ospfd` | 40 | 41 | |
| **slice total** | **356** | | **48% of the 740-TU tree** |

The remaining 384 TUs (pimd, isisd, ldpd, tests, …) are extracted later only if a query
reaches them — Tier-1 facts stay inside the RAM budget by construction.

## 4. Environment losses & restore (sandbox recycle)

The working tree under `poc/` lost `src/` (FRR sources), `deps/` (vendored libyang +
bootstrap tools), and the build logs in the sandbox recycle. Nothing intellectual was
lost — all pins and fixes are encoded in `build_frr_p0.sh`, and the two P1-critical
artifacts (`compile_commands.json`, `facts.db`) survived and are now in `download/frr-poc/p0/`.

Restore for P1 (recreates the tree at the exact path `compile_commands.json` references,
so the captured JSON stays valid without re-capture):

```bash
cd /home/z/my-project/poc
bash tools/build_frr_p0.sh deps        # cmake, compiledb, vendored bison/flex/libtool/m4 + libyang 2.1.148
bash tools/build_frr_p0.sh configure   # extracts tarball → poc/src/frr-10.7.1 + bootstrap + configure
bash tools/build_frr_p0.sh slice       # full build (optional for extraction, needed for runtime facts)
```

## 5. P1 handoff — what the extractors hit first

1. **`nb_reg`** (contract↔wiring join #1): the 28 `nb_cb_*` files, entry points
   `zebra/zebra_nb.h`, `staticd/static_nb.h`, `bgpd/bgp_routemap_nb.h` — match the
   `FRR_CFG_NB_*` / `.callbacks =` init tables, emit `nb:<svc>:<yang-path>` → callback fns.
2. **`zapi_reg`** (join #2): the 28 `zclient->*_cb = fn` assignment sites (lib 26, zebra 2)
   plus `zclient_send_*` call sites (21 unique messages) → `svc:<d>` `handles`/`sends`
   `zapi:<MSG>` edges.
3. **`decl`**: 356 slice TUs → `code:<dir>::<symbol>` function/struct facts via
   clang ASTMatchers, per-TU, keyed off `compile_commands.json`.
4. **`pyang`**: 58 YANG models → `yang:<module>:<path>` contract nodes.

Each extractor writes a `extractor_coverage` row per run — silent gaps stay visible.

## 6. Verification ledger (this closeout)

- `compile_commands.json`: 740 entries, 0 malformed, single build dir `poc/src/frr-10.7.1`.
- `facts.db`: reopened post-copy; fused view merged two `OBSERVED:wiring` rows + one
  `DECLARED:code` row into one edge with `evidence=[DECLARED:code, OBSERVED:wiring]`,
  `n_planes=2`; CHECK constraints rejected `'godplane'` and `'MAYBE'`; smoke rows deleted
  after test.
- Census: CENSUS.md ↔ census.json spot-checked (829 / 1,371,970 / 58 / 28,021 / 28 / 21).
