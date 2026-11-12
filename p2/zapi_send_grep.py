#!/usr/bin/env python3
"""P2 zapi_send_grep — wrapper-mediated ZAPI send sites (grep fallback class).

P1's send-side extractor caught enums at `zclient_create_header` call sites.
It structurally missed the wrapper pattern: a daemon passes the enum as the
FIRST ARGUMENT of a lib ZAPI wrapper:

    bgpd/bgp_zebra.c:1741:  return zclient_route_send(ZEBRA_ROUTE_ADD, ...);

This extractor scans the slice dirs for `<wrapper>(<ZEBRA_*>` call sites where
the wrapper is a lib/zebra function present in the fact base (zsend*/zclient*/
zapi* naming + zebra_redistribute_send), and emits SERVICE-level publishes
edges (the enclosing function is deliberately not resolved — grep class, same
schema convention as the P1 macro fallback: tag=DECLARED, grep-verified site
list kept alongside). Per-site file:line references go to
zapi_send_grep_sites.json; edges use src_ref='fusion:send-grep'.
"""
import json
import re
import sys
from pathlib import Path

import duckdb

import os  # portability: workspace root via MSG_ROOT (default <repo>/data)
ROOT = Path(os.environ.get("MSG_ROOT", str(Path(__file__).resolve().parents[1] / "data")))
SRC = ROOT / "src/frr-10.7.1"
OUT = ROOT / "facts/p2"
SLICE_DIRS = ["lib", "zebra", "bgpd", "staticd", "ospfd"]

CALL_RE = re.compile(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\(\s*(ZEBRA_[A-Z0-9_]+)\b")
WRAPPER_RE = re.compile(r"^(zsend|zclient|zapi)")


def main() -> int:
    con = duckdb.connect(str(ROOT / "facts/facts.duckdb"), read_only=True)
    known = {i: i.split(":")[1] for (i,) in con.execute(
        "select id from nodes where id like 'code:%'").fetchall()}
    names = {}
    for nid, d in known.items():
        names[nid.split("::")[1]] = d
    # the message namespace is authoritative (P1 type facts): route-type enums
    # like ZEBRA_ROUTE_BGP are wrapper arguments but NOT messages
    msgs = {r[0][len("zapi:"):] for r in con.execute(
        "select id from nodes where id like 'zapi:%'").fetchall()}
    con.close()

    sites, edges = [], []
    seen_svc = set()
    for d in SLICE_DIRS:
        for f in sorted((SRC / d).rglob("*.c")):
            text = f.read_text(errors="replace")
            for ln, line in enumerate(text.splitlines(), 1):
                for m in CALL_RE.finditer(line):
                    fn, msg = m.group(1), m.group(2)
                    if not WRAPPER_RE.match(fn) and fn != "zebra_redistribute_send":
                        continue
                    if fn not in names or names[fn] not in ("lib", "zebra"):
                        continue
                    if msg not in msgs:
                        continue          # route-type / other enum, not a message
                    rel = str(f.relative_to(SRC))
                    sites.append({"file": rel, "line": ln, "wrapper": fn,
                                  "msg": msg})
                    key = (f"svc:{d}", f"zapi:{msg}")
                    if key not in seen_svc:
                        seen_svc.add(key)
                        edges.append({"src": f"svc:{d}", "rel": "publishes",
                                      "dst": f"zapi:{msg}", "plane": "wiring",
                                      "tag": "DECLARED",
                                      "src_ref": "fusion:send-grep"})

    (OUT / "zapi_send_grep_sites.json").write_text(json.dumps(sites, indent=2))
    (OUT / "zapi_send_grep_edges.jsonl").write_text(
        "\n".join(json.dumps(e) for e in edges))
    cov = {
        "sites": len(sites),
        "svc_edges": len(edges),
        "by_dir": {d: sum(1 for s in sites if s["file"].startswith(d + "/"))
                   for d in SLICE_DIRS if any(s["file"].startswith(d + "/")
                                              for s in sites)},
        "messages": sorted({s["msg"] for s in sites}),
    }
    (OUT / "zapi_send_grep_coverage.json").write_text(json.dumps(cov, indent=2))
    print(json.dumps(cov, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
