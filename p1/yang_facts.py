#!/usr/bin/env python3
"""P1 YANG contract extractor (pyang Python API) — FRR models -> yang: nodes.

Emits:
  nodes  yang:<module>:<data-path>   kind=yang-node
         data-path = module-relative schema data path without keys,
         e.g. yang:frr-zebra:zebra/state/max-multipath
  edges  child member_of parent (contract, DECLARED, file:line)

Data-plane statements only: container/list/leaf/leaf-list/rpc/notification
plus choice/case (kept for path completeness).
"""
import json
import sys
from pathlib import Path

from pyang import context, repository
from pyang.statements import Statement

import os  # portability: workspace root via MSG_ROOT (default <repo>/data)
ROOT = Path(os.environ.get("MSG_ROOT", str(Path(__file__).resolve().parents[1] / "data")))
SRC = ROOT / "src/frr-10.7.1"
YANG_DIR = SRC / "yang"
OUT = ROOT / "facts/p1"

DATA_KINDS = {"container", "list", "leaf", "leaf-list", "rpc", "notification"}
# NB: choice/case are deliberately excluded — libyang data paths (and NB
# xpaths) never contain choice/case segments; we still descend through them.


def ref_of(stmt) -> str:
    """pyang Position -> src_ref relative to the FRR tree root."""
    p = str(stmt.pos) if stmt.pos else ""
    if "/frr-10.7.1/" in p:
        return p.split("/frr-10.7.1/", 1)[1]
    return p


def walk_stmt(stmt: Statement, module_name: str, parent_path: str,
              nodes: dict, edges: list):
    for sub in stmt.substmts:
        kw = sub.keyword
        kw_name = kw[1] if isinstance(kw, tuple) else kw
        if kw_name not in DATA_KINDS:
            # augment/uses/grouping: descend, no node emitted
            walk_stmt(sub, module_name, parent_path, nodes, edges)
            continue
        name = sub.arg
        path = f"{parent_path}/{name}" if parent_path else name
        nid = f"yang:{module_name}:{path}"
        line = ref_of(sub)
        if nid not in nodes:
            nodes[nid] = {"kind": "yang-node", "label": name, "service": None}
            if parent_path:
                edges.append({"src": nid, "rel": "member_of",
                              "dst": f"yang:{module_name}:{parent_path}",
                              "plane": "contract", "tag": "DECLARED",
                              "src_ref": line})
        walk_stmt(sub, module_name, path, nodes, edges)


def main():
    search = ":".join([str(YANG_DIR),
                       str(SRC / "libyang/models"),
                       str(SRC / "lib")])
    repo = repository.FileRepository(search)
    ctx = context.Context(repo)

    models = sorted(YANG_DIR.glob("*.yang"))
    nodes, edges = {}, []
    cov = {"models": 0, "failed": [], "modules_emitted": []}

    for m in models:
        text = m.read_text(errors="replace")
        try:
            mod = ctx.add_module(str(m), text)
        except Exception as ex:  # noqa: BLE001
            cov["failed"].append(f"{m.name}: {ex}")
            continue
        if mod is None:
            cov["failed"].append(m.name)
            continue
        # skip imported copies (add_module of an import returns the same Module
        # object as when we add the defining file later — dedupe by module name)
        modname = mod.arg
        if modname in cov["modules_emitted"]:
            continue
        walk_stmt(mod, modname, "", nodes, edges)
        cov["modules_emitted"].append(modname)
        cov["models"] += 1

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "yang_nodes.jsonl").write_text(
        "\n".join(json.dumps({"id": k, **v}) for k, v in nodes.items()))
    (OUT / "yang_edges.jsonl").write_text(
        "\n".join(json.dumps(e) for e in edges))
    cov["nodes"] = len(nodes)
    cov["edges"] = len(edges)
    (OUT / "yang_coverage.json").write_text(json.dumps(cov, indent=2))
    print(json.dumps(cov, indent=2))


if __name__ == "__main__":
    main()
