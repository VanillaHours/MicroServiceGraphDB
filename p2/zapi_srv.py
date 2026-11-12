#!/usr/bin/env python3
"""P2 zapi_srv — zebra's SERVER-side ZAPI dispatch table extractor.

FRR clients send ZAPI messages; zebra dispatches them through one
designated-initializer table:

    void (*const zserv_handlers[])(ZAPI_HANDLER_ARGS) = {
        [ZEBRA_ROUTE_ADD] = zread_route_add,
        ...
    };                                     (zebra/zapi_msg.c)

P1's zapi_reg covered the client-side `zclient_handler` tables only, which is
why zebra had no `handles` edges. This grep extractor (same fact schema,
tag=DECLARED, src_ref=file:line — the P1 macro-fallback convention) closes the
server side so the fusion can build real client->server message paths.

Emits JSONL edges:
    code:zebra::<fn>  -handles->  zapi:<MSG>   (fn level)
    svc:zebra         -handles->  zapi:<MSG>   (svc level, deduped)
"""
import json
import re
import sys
from pathlib import Path

import os  # portability: workspace root via MSG_ROOT (default <repo>/data)
ROOT = Path(os.environ.get("MSG_ROOT", str(Path(__file__).resolve().parents[1] / "data")))
SRC = Path(os.environ.get("MSG_SRC", str(ROOT / "src/frr-10.7.1")))
OUT = ROOT / "facts/p2"

TABLE_RE = re.compile(
    r"void\s*\(\*const\s+zserv_handlers\s*\[\]\)\s*\(ZAPI_HANDLER_ARGS\)\s*=\s*\{")
ENTRY_RE = re.compile(r"\[\s*(ZEBRA_[A-Z0-9_]+)\s*\]\s*=\s*([A-Za-z_][A-Za-z0-9_]*)")
NULL_RE = re.compile(r"\[\s*(ZEBRA_[A-Z0-9_]+)\s*\]\s*=\s*NULL")


def main() -> int:
    text = (SRC / "zebra/zapi_msg.c").read_text(errors="replace")
    lines = text.splitlines()

    m = TABLE_RE.search(text)
    if not m:
        print("FATAL: zserv_handlers table not found", file=sys.stderr)
        return 1
    start_line = text[: m.start()].count("\n") + 1

    # brace-match the initializer from its opening '{'
    depth = 0
    end_line = None
    for i in range(m.end() - 1, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                end_line = text[:i].count("\n") + 1
                break
    if end_line is None:
        print("FATAL: table end not found", file=sys.stderr)
        return 1

    entries, nulls = [], []
    for ln in range(start_line, end_line + 1):
        line = lines[ln - 1]
        for em in NULL_RE.finditer(line):
            nulls.append((em.group(1), ln))
        for em in ENTRY_RE.finditer(line):
            entries.append((em.group(1), em.group(2), ln))

    edges = []
    seen_svc = set()
    for msg, fn, ln in entries:
        edges.append({"src": f"code:zebra::{fn}", "rel": "handles",
                      "dst": f"zapi:{msg}", "plane": "wiring",
                      "tag": "DECLARED", "src_ref": f"zebra/zapi_msg.c:{ln}"})
        key = msg
        if key not in seen_svc:
            seen_svc.add(key)
            edges.append({"src": "svc:zebra", "rel": "handles",
                          "dst": f"zapi:{msg}", "plane": "wiring",
                          "tag": "DECLARED",
                          "src_ref": f"zebra/zapi_msg.c:{start_line}"})

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "zapi_srv_edges.jsonl").write_text(
        "\n".join(json.dumps(e) for e in edges))

    cov = {
        "table": f"zebra/zapi_msg.c:{start_line}-{end_line}",
        "entries": len(entries),
        "null_entries": [n for n, _ in nulls],
        "messages": len(seen_svc),
        "fns": len({fn for _, fn, _ in entries}),
        "fn_edges": sum(1 for e in edges if e["src"].startswith("code:")),
        "svc_edges": sum(1 for e in edges if e["src"] == "svc:zebra"),
    }
    (OUT / "zapi_srv_coverage.json").write_text(json.dumps(cov, indent=2))
    print(json.dumps(cov, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
