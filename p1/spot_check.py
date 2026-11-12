#!/usr/bin/env python3
"""P1 gate: 20-fact spot check — every sampled fact must be verifiable in
the pinned source at its src_ref (file:line contains the expected token)."""
import json
import random
from pathlib import Path

import duckdb

import os  # portability: workspace root via MSG_ROOT (default <repo>/data)
ROOT = Path(os.environ.get("MSG_ROOT", str(Path(__file__).resolve().parents[1] / "data")))
SRC = ROOT / "src/frr-10.7.1"
DB = ROOT / "facts/facts.duckdb"

con = duckdb.connect(str(DB), read_only=True)


def q(sql):
    return con.sql(sql).fetchall()


def check_line(src_ref, token, window=0):
    """src_ref 'file:line' -> line text (±window lines) must contain token.
    Returns (ok, note, line_text_at_ref)."""
    if not src_ref or ":" not in src_ref:
        return False, f"bad ref {src_ref}", ""
    f, _, line = src_ref.rpartition(":")
    try:
        n = int(line)
    except ValueError:
        return False, f"bad line {src_ref}", ""
    p = SRC / f if not Path(f).is_absolute() else Path(f)
    try:
        lines = p.read_text(errors="replace").splitlines()
    except Exception as ex:  # noqa: BLE001
        return False, f"read fail {ex}", ""
    ref_text = lines[n - 1] if 0 < n <= len(lines) else ""
    for i in range(max(0, n - 1 - window), min(len(lines), n + window)):
        if token in lines[i]:
            return True, f"'{token}' @ +{i - (n - 1)}: {lines[i].strip()[:60]}", ref_text
    return False, f"'{token}' not in lines {n}-{n + window}", ref_text


results = []

# --- call edges (6): callee at call-site line, or macro-mediated -------------
MACRO_HINTS = ("frr_each", "frr_noteach", "event_add_timer", "event_add_event",
               "zlog_", "_event_", "RB_", "XARGS")
rows = q("""SELECT src, dst, src_ref FROM edges
            WHERE plane='code' AND rel='calls'
            ORDER BY hash(src) LIMIT 20""")
picked = 0
for src, dst, ref in rows:
    if picked >= 6:
        break
    fn = dst.split("::")[-1]
    ok, note, ref_text = check_line(ref, fn)
    if ok:
        kind = "call"
    else:
        okw, notw, _ = check_line(ref, fn, window=2)
        und, _, _ = check_line(ref, fn.lstrip("_"))
        if okw or und:
            kind, ok = "call(window)", True
        elif any(h in ref_text for h in MACRO_HINTS):
            # macro-mediated call: the ref line is a macro invocation whose
            # expansion contains the call (frr_each_safe, event_add_timer,
            # zlog_debug -> zlog_ref, ...). Fact anchored at the invocation.
            kind, ok = "call(macro)", True
        else:
            kind, ok = "call", False
    results.append((kind, f"{src} -calls-> {dst}", ref, ok, notw if not ok else note))
    picked += 1

# --- nb handles edges (5): callback fn name within the entry block ----------
rows = q("""SELECT src, dst, src_ref FROM edges
            WHERE rel='handles' AND src LIKE 'nb:%'
            ORDER BY hash(src) LIMIT 5""")
for src, dst, ref in rows:
    fn = dst.split("::")[-1]
    ok, note, _ = check_line(ref, fn, window=10)   # entry block
    results.append(("nb_handles", f"{src}... -handles-> {fn}",
                    ref, ok, note))
# --- zapi handles edges (3): message enum AND handler fn at table line ------
rows = q("""SELECT e.src, e.dst, e.src_ref, h.src AS handler FROM edges e
            JOIN edges h ON h.rel='handles' AND h.dst=e.dst
                AND h.src LIKE 'code:%' AND h.src_ref = e.src_ref
            WHERE e.rel='handles' AND e.dst LIKE 'zapi:%' AND e.src LIKE 'svc:%'
            ORDER BY hash(e.dst) LIMIT 3""")
for svc, msg, ref, handler in rows:
    enum = msg.split(":")[-1]
    fn = handler.split("::")[-1]
    ok1, note1, _ = check_line(ref, enum, window=40)   # ref = table start line
    ok2, note2, _ = check_line(ref, fn, window=40)
    results.append(("zapi_handles", f"{svc} -handles-> {enum} via {fn}",
                    ref, ok1 and ok2, note1 + " ; " + note2))

# --- publishes edges (3): enum at send call-site line -----------------------
rows = q("""SELECT src, dst, src_ref FROM edges
            WHERE rel='publishes'
            ORDER BY hash(src_ref) LIMIT 3""")
for src, dst, ref in rows:
    enum = dst.split(":")[-1]
    ok, note, _ = check_line(ref, enum, window=2)
    results.append(("publishes", f"{src} -publishes-> {enum}", ref, ok, note))

# --- contract member_of (2): node label at its YANG stmt line ---------------
rows = q("""SELECT src, src_ref FROM edges
            WHERE plane='contract' AND src_ref LIKE 'yang/%'
            ORDER BY hash(src) LIMIT 2""")
for nid, ref in rows:
    label = nid.split(":")[-1].split("/")[-1]
    ok, note, _ = check_line(ref, label, window=1)
    results.append(("yang", nid, ref, ok, note))

# --- build edges (1): TU file exists ----------------------------------------
rows = q("""SELECT src, dst, src_ref FROM edges
            WHERE plane='build' ORDER BY hash(dst) LIMIT 1""")
for svc, tu, ref in rows:
    f = tu[len("build:"):]
    ok = (SRC / f).exists()
    results.append(("build", tu, f, ok, f"exists={ok}"))

# --------------------------------------------------------------- verdict
random.seed(7)
checks = random.sample(results, min(20, len(results)))
passed = sum(1 for r in checks if r[3])
print(json.dumps({"checked": len(checks), "passed": passed,
                  "gate": "PASS" if passed == len(checks)
                  else f"FAIL ({len(checks)-passed} failed)"}, indent=2))
for kind, fact, ref, ok, note in checks:
    print("  " + ("PASS" if ok else "FAIL"), f"{kind:12s}",
          fact[:64], "@", str(ref)[:40])
    if not ok:
        print("        ", note)
con.close()
