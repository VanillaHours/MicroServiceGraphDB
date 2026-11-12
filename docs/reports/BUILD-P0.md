# P0 Build Report — FRR 10.7.1 on Debian 13 (glibc 2.41), no root

**Result: BUILD SUCCEEDED.** Full FRR tree, all daemons. `compile_commands.json` captured (740 TUs) — the P1 extraction input.

## Pins

| artifact | pin | integrity |
|---|---|---|
| FRR source | `frr_10.7.1.orig.tar.xz` (= upstream tag `frr-10.7.1`) | sha256 `b8fd6590f0f53ccd661e8c3e3a0d997f9014b62c8ed03a42e51e93291373ae52` |
| libyang | v2.1.148, vendored cmake build into `poc/deps/usr` | satisfies FRR's `>= 2.1.128` |
| bootstrap tools | bison 3.8.2, flex 2.6.4, libtool 2.6.2, m4 1.4.21 — Debian `.deb`s extracted to `poc/deps/usr` | no root needed |
| readline/ncurses | **pinned 8.2-6 / 6.5+20250216-2** | pool newest (8.3 / 6.6) are sid builds vs glibc 2.42 → link failure on 2.41 |

## Environment fixes discovered (all encoded in `build.sh`)

1. **deb extraction prefix**: `dpkg-deb -x` into `deps/` (not `deps/usr/`) — debs carry their own `./usr/`.
2. **libtoolize relocation**: baked `/usr/share/libtool` + `/usr/share/aclocal` paths sed-patched to the vendored prefix.
3. **bison data**: `BISON_PKGDATADIR=$ROOT/deps/usr/share/bison` (baked default unreachable without root).
4. **`--disable-vtysh` breaks frr-10.7.1**: `lib/vty.c` uses `VTYSH_READ` unguarded → build vtysh normally (readline vendored instead).
5. **protobuf**: configure auto-enables qpb/fpm protobuf but `protoc-c` is not vendored → `--disable-protobuf --disable-protoc`.
6. **clippy**: links `libpython3.12.so` → its dir (uv-managed python) prepended to `LD_LIBRARY_PATH`.
7. **GNU make trap**: `make zebra` with a `zebra/` directory present = "nothing to be done", exit 0, zero compilation. Always `make -j2` (all) or explicit file targets.

## Build state

- 1035 objects, all daemons linked (`zebra/.libs/zebra` 7.7 MB, `bgpd/.libs/bgpd` 14.7 MB)
- `compile_commands.json`: 740 compile commands (full tree; `poc/compile_commands.json`)
- logs: `configure.log`, `full-build.log` in `poc/`

## Reproduce

```bash
bash tools/build_frr_p0.sh deps       # python tools + vendored bootstrap tools + libyang
bash tools/build_frr_p0.sh configure  # bootstrap.sh + configure (final flag set)
bash tools/build_frr_p0.sh capture    # compiledb -n make -B -> compile_commands.json
```

(The real build is `make -j2` in the source tree after `configure`; CI note: run it as one job — ~10–25 min on 2 cores.)

## P0 exit-gate status

| gate | status |
|---|---|
| Build reproducible | **PASS** — script stages `deps → configure → (make) → capture`; pins + fixes encoded |
| Schema v0 committed | **PASS** — `schema/schema.sql` v0.1.0, verified in DuckDB (fused-edge view merges evidence lists) |
| Census published | **PASS** — `census/CENSUS.md` + `census_loc.png` + `census.json` |
