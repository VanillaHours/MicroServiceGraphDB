#!/usr/bin/env bash
# FRR POC — P0 build pipeline (no root required)
# Pins: FRR frr-10.7.1 (Debian orig tarball) + libyang2 v2.1.148 (vendored build)
# Stages: deps (python tools + vendored bootstrap tools + libyang) | frr (bootstrap, configure, build)
# Usage: build.sh deps|configure|slice|capture
set -euo pipefail

ROOT="${MSG_ROOT:-$(cd "$(dirname "$0")/.." && pwd)/data}"
DL=$ROOT/downloads
SRC=$ROOT/src
DEPS=$ROOT/deps/usr
FRR_DIR=$SRC/frr-10.7.1
LIBYANG_VER=v2.1.148
export PATH=$DEPS/bin:$PATH
export PKG_CONFIG_PATH=$DEPS/lib/pkgconfig:${PKG_CONFIG_PATH:-}
export ACLOCAL_PATH=$DEPS/share/aclocal
PYLIB=$(python3 -c "import sysconfig; print(sysconfig.get_config_var('LIBDIR'))")
export LD_LIBRARY_PATH=$PYLIB:$DEPS/lib:$DEPS/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}
export BISON_PKGDATADIR=$ROOT/deps/usr/share/bison

log() { echo -e "\n=== [$(date +%H:%M:%S)] $* ==="; }

fetch_latest_deb() { # $1=pool-subdir $2=pkgname -> prints path of downloaded deb
    local sub=$1 name=$2 deb
    deb=$(curl -sSL "https://deb.debian.org/debian/pool/main/$sub/" \
        | grep -oP "href=\"${name}_[^\"]*_(amd64|all)\.deb\"" \
        | sed 's/href="//; s/"$//' | sort -V | tail -1)
    [ -n "$deb" ] || { echo "no amd64 deb found for $name in $sub" >&2; return 1; }
    echo "  fetch $deb"
    curl -sSL -o "$DL/$deb" "https://deb.debian.org/debian/pool/main/$sub/$deb"
    dpkg-deb -x "$DL/$deb" "$ROOT/deps"
}

fetch_deb_ver() { # $1=pool-subdir $2=pkgname $3=version-suffix
    local sub=$1 name=$2 ver=$3 deb
    deb="${name}_${ver}_amd64.deb"; [ -f "$DL/$deb" ] || deb="${name}_${ver}_all.deb"
    echo "  fetch $deb"
    curl -sSL -o "$DL/$deb" "https://deb.debian.org/debian/pool/main/$sub/$deb"
    dpkg-deb -x "$DL/$deb" "$ROOT/deps"
}

stage_deps() {
    log "stage: python tools (cmake, compiledb)"
    pip install --quiet --no-input cmake compiledb

    log "stage: vendored bootstrap tools (bison, flex, libtool, m4)"
    mkdir -p "$DEPS"
    fetch_latest_deb "b/bison"  "bison"
    fetch_latest_deb "f/flex"   "flex"
    fetch_latest_deb "f/flex"   "libfl-dev"
    fetch_latest_deb "libt/libtool" "libtool"
    fetch_latest_deb "m/m4"     "m4"
    fetch_latest_deb "e/elfutils" "libelf1t64"
    fetch_latest_deb "e/elfutils" "libelf-dev"
    # NOTE: pinned to trixie-era versions; pool's newest (6.6/8.3) are sid builds
    # requiring glibc 2.42 > sandbox 2.41 (cfgetospeed@GLIBC_2.42 link failure).
    fetch_deb_ver "r/readline" "libreadline-dev"  "8.2-6"
    fetch_deb_ver "r/readline" "libreadline8t64"  "8.2-6"
    fetch_deb_ver "r/readline" "readline-common"  "8.2-6"
    fetch_deb_ver "n/ncurses"  "libncurses-dev"   "6.5+20250216-2"
    fetch_deb_ver "n/ncurses"  "libtinfo6"        "6.5+20250216-2"
    fetch_deb_ver "n/ncurses"  "libncurses6"      "6.5+20250216-2"
    # relocate libtoolize's baked-in /usr/share paths to our prefix
    sed -i -e "s|/usr/share/libtool|$ROOT/deps/usr/share/libtool|g" \
           -e "s|/usr/share/aclocal|$ROOT/deps/usr/share/aclocal|g" \
        "$ROOT/deps/usr/bin/libtoolize" 2>/dev/null || true
    which bison flex libtoolize m4 | sed 's/^/  /'
    bison --version | head -1; flex --version | head -1

    log "stage: libyang2 $LIBYANG_VER (vendored cmake build)"
    mkdir -p "$SRC"
    [ -d "$SRC/libyang" ] || {
        curl -sSL -o "$DL/libyang-$LIBYANG_VER.tar.gz" \
            "https://github.com/CESNET/libyang/archive/refs/tags/$LIBYANG_VER.tar.gz"
        tar -xzf "$DL/libyang-$LIBYANG_VER.tar.gz" -C "$SRC"
        mv "$SRC/libyang-${LIBYANG_VER#v}" "$SRC/libyang"
    }
    cmake -S "$SRC/libyang" -B "$SRC/libyang/build" \
        -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$DEPS" \
        -DCMAKE_POLICY_VERSION_MINIMUM=3.5 -DENABLE_TESTS=OFF > /dev/null
    cmake --build "$SRC/libyang/build" -j"$(nproc)" > /dev/null
    cmake --install "$SRC/libyang/build" > /dev/null
    pkg-config --modversion libyang
}

stage_configure() {
    log "stage: FRR bootstrap + configure"
    [ -d "$FRR_DIR" ] || { mkdir -p "$SRC"; tar -xf "$DL/frr-10.7.1.orig.tar.xz" -C "$SRC"; }
    cd "$FRR_DIR"
    ./bootstrap.sh
    CPPFLAGS="-I$DEPS/include" LDFLAGS="-L$DEPS/lib -L$DEPS/lib/x86_64-linux-gnu" \
    ./configure --prefix="$ROOT/frr-install" \
        --enable-doc=no --enable-doc-html=no --enable-snmp=no \
        --enable-capabilities=no --disable-ospfclient --disable-protobuf --disable-protoc \
        > "$ROOT/configure.log" 2>&1 || { tail -40 "$ROOT/configure.log"; exit 1; }
    tail -5 "$ROOT/configure.log"
}

stage_slice() {
    log "stage: full build (do NOT pass directory names as targets — make treats them as up-to-date files)"
    cd "$FRR_DIR"
    make -j"$(nproc)" 2>&1 | tee "$ROOT/build.log" | tail -4
    log "built: $(find . -name '*.o' | wc -l) objects; binaries in */.libs/"
}

stage_capture() {
    log "stage: capture full-tree compile_commands.json (dry run, no execution)"
    cd "$FRR_DIR"
    compiledb -n make -B > /dev/null 2>&1 || compiledb make -B > /dev/null 2>&1
    python3 - <<'EOF'
import json, collections
cc = json.load(open("compile_commands.json"))
cnt = collections.Counter(e["directory"].split("/frr-10.7.1/")[-1].split("/")[0] for e in cc)
print(f"compile_commands.json: {len(cc)} TUs")
for k, v in cnt.most_common(10):
    print(f"  {k:20s} {v}")
EOF
}

case "${1:-all}" in
    deps)      stage_deps ;;
    configure) stage_configure ;;
    slice)     stage_slice ;;
    capture)   stage_capture ;;
    all)       stage_deps; stage_configure; stage_slice; stage_capture ;;
    *) echo "usage: $0 deps|configure|slice|capture|all"; exit 2 ;;
esac
