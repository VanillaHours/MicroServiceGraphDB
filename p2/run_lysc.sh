#!/usr/bin/env bash
# P2: build + run the libyang lysc path emitter over all FRR-shipped YANG models.
set -euo pipefail
ROOT="${MSG_ROOT:-$(cd "$(dirname "$0")/.." && pwd)/data}"
P2="$(cd "$(dirname "$0")" && pwd)"
OUT=$ROOT/facts/p2

mkdir -p "$OUT"

# 1. compile
gcc -O2 -I "$ROOT/deps/usr/include" "$P2/lysc_paths.c" \
    -L "$ROOT/deps/usr/lib" -lyang -Wl,-rpath,"$ROOT/deps/usr/lib" \
    -o "$P2/lysc_paths" 2>&1 | head -20
test -x "$P2/lysc_paths"

# 2. module list: 45 root frr-*.yang + 13 yang/ietf/*.yang (P1 covered root only;
#    ietf-key-chain is the join target of 26 NB entries).
#    Load order matters: ietf-* must be implemented BEFORE frr-* compiles
#    (frr-logging defaults an identityref into ietf-syslog-types), and
#    frr-deviations-* must precede their targets.
{
  for f in "$ROOT"/src/frr-10.7.1/yang/ietf/[i]*.yang \
           "$ROOT"/src/frr-10.7.1/yang/ietf/frr-deviations-*.yang \
           $(ls "$ROOT"/src/frr-10.7.1/yang/*.yang | xargs rg --files-without-match "^submodule "); do
    # line = "<module> [feature1 feature2 ...]" — features passed explicitly
    # (libyang "*" wildcard did not enable them; if-feature'd subtrees would
    # be pruned and FRR NB xpaths into those subtrees would not join)
    feats=$(rg -N "^\s+feature\s+" "$f" 2>/dev/null | awk '{print $2}' | tr '\n' ' ')
    printf "%s %s\n" "$(basename "$f" .yang)" "$feats" | sed 's/ *$//'
  done
} > "$OUT/modules.txt"

echo "modules to load: $(wc -l < "$OUT/modules.txt")"

# 3. run (stderr = load report, stdout suppressed: output goes to file via freopen)
SEARCH="$ROOT/src/frr-10.7.1/yang:$ROOT/src/frr-10.7.1/yang/ietf:$ROOT/deps/usr/share/yang/modules/libyang"
"$P2/lysc_paths" "$SEARCH" "$OUT/lysc_paths.jsonl" < "$OUT/modules.txt"

echo "emitted rows: $(wc -l < "$OUT/lysc_paths.jsonl")"
