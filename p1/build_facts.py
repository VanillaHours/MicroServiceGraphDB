#!/usr/bin/env python3
"""P1 build mapper — compile_commands.json -> build-plane facts.

Emits:
  nodes  svc:<dir>                 kind=daemon   (one per slice dir)
  nodes  build:<dir>/<file>        kind=tu       (one per compiled TU)
  edges  (svc:<dir> compiles build:<file>, build, BUILD, src_ref=file:0)
"""
import json
from pathlib import Path

import os  # portability: workspace root via MSG_ROOT (default <repo>/data)
ROOT = Path(os.environ.get("MSG_ROOT", str(Path(__file__).resolve().parents[1] / "data")))
SRC = ROOT / "src/frr-10.7.1"
CC_PATH = ROOT / "compile_commands.json"
OUT = ROOT / "facts/p1"

DIRS = ["lib", "zebra", "bgpd", "staticd", "ospfd"]


def dir_of(rel: str):
    head = rel.split("/", 1)[0]
    return head if head in DIRS else None


def main():
    cc = json.loads(CC_PATH.read_text())
    nodes, edges = {}, []

    for d in DIRS:
        nodes[f"svc:{d}"] = {"kind": "daemon", "label": d, "service": None}

    n_tus = 0
    for e in cc:
        rel = e["file"]
        if dir_of(rel) is None:
            continue
        nid = f"build:{rel}"
        if nid not in nodes:
            nodes[nid] = {"kind": "tu", "label": rel, "service": f"svc:{dir_of(rel)}"}
            edges.append({"src": f"svc:{dir_of(rel)}", "rel": "compiles",
                          "dst": nid, "plane": "build", "tag": "BUILD",
                          "src_ref": rel})
            n_tus += 1

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "build_nodes.jsonl").write_text(
        "\n".join(json.dumps({"id": k, **v}) for k, v in nodes.items()))
    (OUT / "build_edges.jsonl").write_text(
        "\n".join(json.dumps(x) for x in edges))
    cov = {"tus": n_tus, "svc_nodes": len(DIRS), "nodes": len(nodes),
           "edges": len(edges)}
    (OUT / "build_coverage.json").write_text(json.dumps(cov, indent=2))
    print(json.dumps(cov, indent=2))


if __name__ == "__main__":
    main()
