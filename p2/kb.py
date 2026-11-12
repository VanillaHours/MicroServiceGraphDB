#!/usr/bin/env python3
"""P2 query CLI — explain / path / impact / stats over the fused fact base.

POC-DESIGN.md §6 deliverable: "query CLI (explain/path/impact)". Reads
$MSG_ROOT/facts/p2/facts.duckdb (schema v0.1.0, phase=P2). Every answer carries its
evidence (plane:tag + src_ref) — no unanchored answers.

  kb.py stats
  kb.py explain <node-id>
  kb.py path <src> <dst>            # shortest path, undirected, evidence per hop
  kb.py impact <yang-id>            # daemons + callbacks + zapi side-effects
"""
import argparse
import json
import sys
from collections import defaultdict, deque
from pathlib import Path

import duckdb

import os  # portability: workspace root via MSG_ROOT (default <repo>/data)
DEFAULT_DB = str(Path(os.environ.get("MSG_ROOT", str(Path(__file__).resolve().parents[1] / "data"))) / "facts/p2/facts.duckdb")


def connect(db):
    con = duckdb.connect(db, read_only=True)
    return con


class Graph:
    """Fused graph in RAM (Tier-1): adjacency over distinct (src,rel,dst) with
    aggregated evidence. ~54k edges — comfortably inside the 1-2 GB budget."""

    def __init__(self, con):
        rows = con.execute("""
            select src, rel, dst, list(distinct tag || ':' || plane),
                   list(distinct src_ref), count(distinct plane)
            from edges group by src, rel, dst""").fetchall()
        self.adj = defaultdict(list)          # id -> [(dir, other, rel, ev, refs)]
        self.nodes = {}
        for nid, kind, label, service in con.execute(
                "select id, kind, label, service from nodes").fetchall():
            self.nodes[nid] = {"kind": kind, "label": label, "service": service}
        for s, r, d, ev, refs, np_ in rows:
            ev = sorted(ev)
            self.adj[s].append(("out", d, r, ev, refs))
            self.adj[d].append(("in", s, r, ev, refs))
        self.raw_edge_count = con.execute("select count(*) from edges").fetchone()[0]
        self.fused_edge_count = len(rows)

    def path(self, src, dst, max_hops=8):
        """BFS undirected over fused edges; returns hop list with evidence."""
        if src not in self.nodes or dst not in self.nodes:
            return None
        prev = {src: None}
        q = deque([src])
        while q:
            cur = q.popleft()
            if cur == dst:
                break
            if len(prev) > 200000:            # safety cap
                break
            hops = 0
            probe = cur
            while prev.get(probe):
                probe = prev[probe][0] if isinstance(prev[probe], tuple) else prev[probe]
                hops += 1
            if hops >= max_hops:
                continue
            for dirn, other, rel, ev, refs in self.adj.get(cur, []):
                if other not in prev:
                    prev[other] = (cur, dirn, rel, ev, refs)
                    q.append(other)
        if dst not in prev or dst == src:
            return None
        hops = []
        cur = dst
        while prev[cur] is not None:
            frm, dirn, rel, ev, refs = prev[cur]
            hops.append({"from": frm, "to": cur, "dir": dirn, "rel": rel,
                         "evidence": ev, "refs": refs})
            cur = frm
        hops.reverse()
        return hops

    def yang_family(self, yang_id):
        """leaf + ancestors (member_of closure upward)."""
        fam = [yang_id]
        seen = {yang_id}
        frontier = [yang_id]
        while frontier:
            nxt = []
            for nid in frontier:
                for dirn, other, rel, _ev, _r in self.adj.get(nid, []):
                    # member_of edges run child -> parent (child is src)
                    if dirn == "out" and rel == "member_of" \
                            and other not in seen and other.startswith("yang:"):
                        seen.add(other)
                        fam.append(other)
                        nxt.append(other)
            frontier = nxt
        return fam

    def impact(self, yang_id, call_depth=10, node_cap=60000):
        """YANG leaf -> nb entries -> callbacks -> daemons + zapi side-effects.

        Cross-service reachability (merge rule 3): from each callback, walk
        `calls` edges up to `call_depth`; functions holding `publishes` edges
        yield zapi messages, which yield the services that handle them.
        """
        fam = self.yang_family(yang_id)
        nbs = []
        for nid in fam:
            for dirn, other, rel, ev, refs in self.adj.get(nid, []):
                if dirn == "in" and rel == "implements":
                    nbs.append({"nb": other, "via": nid,
                                "ancestors": nid != yang_id})
        cbs, daemons = [], set()
        for e in nbs:
            for dirn, other, rel, ev, refs in self.adj.get(e["nb"], []):
                if dirn == "out" and rel == "handles" and other.startswith("code:"):
                    cbs.append({"cb": other, "nb": e["nb"], "refs": refs})
                if dirn == "in" and rel == "registers" and other.startswith("svc:"):
                    daemons.add(other)
        for c in cbs:
            svc = self.nodes.get(c["cb"], {}).get("service")
            if svc:
                daemons.add(svc)

        # zapi side effects: BFS over calls from the callbacks
        msgs = {}
        visited = set()
        frontier = [(c["cb"], 0) for c in cbs]
        seen_cb = {c["cb"] for c in cbs}
        while frontier and len(visited) < node_cap:
            cur, depth = frontier.pop(0)
            if depth >= call_depth or cur in visited:
                continue
            visited.add(cur)
            for dirn, other, rel, _ev, _r in self.adj.get(cur, []):
                if rel == "publishes" and other.startswith("zapi:"):
                    hnd = [o for dd, o, rr, _e, _rf in self.adj.get(other, [])
                           if rr == "handles" and o.startswith("svc:")]
                    msgs[other] = {"handled_by": sorted(hnd)}
                if rel == "calls" and depth + 1 <= call_depth \
                        and other.startswith("code:") and other not in seen_cb:
                    frontier.append((other, depth + 1))
        return {"yang": yang_id, "family_size": len(fam), "nb_entries": nbs,
                "callbacks": cbs, "daemons": sorted(daemons),
                "zapi_side_effects": msgs,
                "reachability": {"call_depth": call_depth,
                                 "nodes_visited": len(visited)}}


def cmd_stats(con, args):
    g = Graph(con)
    out = {
        "nodes": len(g.nodes),
        "edges_raw": g.raw_edge_count,
        "edges_fused": g.fused_edge_count,
        "nodes_by_kind": dict(con.execute(
            "select kind, count(*) from nodes group by 1 order by 2 desc").fetchall()),
        "edges_by_plane_tag": dict(con.execute(
            "select plane || ':' || tag, count(*) from edges group by 1 order by 2 desc").fetchall()),
        "meta": dict(con.execute("select key, value from meta").fetchall()),
    }
    return out


def cmd_explain(con, args):
    g = Graph(con)
    nid = args.node
    if nid not in g.nodes:
        return {"error": f"unknown node id: {nid}"}
    edges = con.execute("""
        select rel, case when src = ? then 'out' else 'in' end as dir,
               case when src = ? then dst else src end as other,
               plane, tag, src_ref
        from edges where src = ? or dst = ? order by rel, dir, other""",
        [nid, nid, nid, nid]).fetchall()
    grouped = defaultdict(lambda: {"count": 0, "peers": []})
    for rel, dirn, other, plane, tag, ref in edges:
        grp = grouped[rel]
        grp["count"] += 1
        if len(grp["peers"]) < 12:
            grp["peers"].append({"dir": dirn, "peer": other,
                                 "evidence": f"{tag}:{plane}", "src_ref": ref})
    return {"node": {"id": nid, **g.nodes[nid]}, "relations": dict(grouped)}


def cmd_path(con, args):
    g = Graph(con)
    hops = g.path(args.src, args.dst, max_hops=args.max_hops)
    if hops is None:
        return {"error": f"no path {args.src} -> {args.dst} "
                         f"within {args.max_hops} hops"}
    return {"src": args.src, "dst": args.dst, "hops": len(hops), "path": hops}


def cmd_impact(con, args):
    g = Graph(con)
    if args.yang not in g.nodes:
        return {"error": f"unknown node id: {args.yang}"}
    return g.impact(args.yang, call_depth=args.call_depth)


def render(res, as_json=False):
    if as_json:
        return json.dumps(res, indent=2)
    if "error" in res:
        return f"ERROR: {res['error']}"
    if "nodes_by_kind" in res:                                   # stats
        lines = [f"nodes {res['nodes']}  edges raw {res['edges_raw']}  "
                 f"fused {res['edges_fused']}"]
        lines.append(f"meta: phase={res['meta'].get('phase')} "
                     f"schema={res['meta'].get('schema_version')} "
                     f"nb_yang_join={res['meta'].get('nb_yang_join_pct')}%")
        for k, v in res["nodes_by_kind"].items():
            lines.append(f"  {k:16} {v}")
        for k, v in sorted(res["edges_by_plane_tag"].items(),
                           key=lambda x: -x[1]):
            lines.append(f"  {k:22} {v}")
        return "\n".join(lines)
    if "relations" in res:                                       # explain
        n = res["node"]
        lines = [f"{n['id']}  kind={n['kind']} service={n['service']} "
                 f"label={n['label']}"]
        for rel, info in sorted(res["relations"].items()):
            lines.append(f"  {rel} ({info['count']})")
            for p in info["peers"]:
                lines.append(f"    {p['dir']:3} {p['peer']}"
                             f"  [{p['evidence']}] {p['src_ref']}")
        return "\n".join(lines)
    if "path" in res:                                            # path
        lines = [f"path {res['src']} -> {res['dst']}  ({res['hops']} hops)"]
        cur = res["src"]
        for h in res["path"]:
            arrow = f"-{h['rel']}[{'|'.join(h['evidence'])}]->"
            if h["dir"] == "in":
                arrow = f"<-{h['rel']}[{'|'.join(h['evidence'])}]-"
            lines.append(f"  {cur}")
            lines.append(f"    {arrow}")
            cur = h["to"]
        lines.append(f"  {cur}")
        return "\n".join(lines)
    if "nb_entries" in res:                                      # impact
        lines = [f"impact of {res['yang']} "
                 f"(yang family size {res['family_size']}, "
                 f"visited {res['reachability']['nodes_visited']} fns)"]
        lines.append("  daemons:")
        for d in res["daemons"]:
            lines.append(f"    {d}")
        lines.append(f"  nb entries ({len(res['nb_entries'])}):")
        for e in res["nb_entries"]:
            tag = " (ancestor container)" if e["ancestors"] else ""
            lines.append(f"    {e['nb']}{tag}")
        lines.append(f"  callbacks ({len(res['callbacks'])}):")
        for c in res["callbacks"][:20]:
            lines.append(f"    {c['cb']}  @{c['refs'][0] if c['refs'] else '?'}")
        if res["zapi_side_effects"]:
            lines.append("  zapi side effects (within call depth):")
            for m, info in sorted(res["zapi_side_effects"].items()):
                lines.append(f"    {m}  handled by {', '.join(info['handled_by']) or '?'}")
        return "\n".join(lines)
    return json.dumps(res, indent=2)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=DEFAULT_DB)
    ap.add_argument("--json", action="store_true", help="machine output")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("stats")
    p = sub.add_parser("explain"); p.add_argument("node")
    p = sub.add_parser("path"); p.add_argument("src"); p.add_argument("dst")
    p.add_argument("--max-hops", type=int, default=8)
    p = sub.add_parser("impact"); p.add_argument("yang")
    p.add_argument("--call-depth", type=int, default=10)
    args = ap.parse_args(argv)

    con = connect(args.db)
    fn = {"stats": cmd_stats, "explain": cmd_explain,
          "path": cmd_path, "impact": cmd_impact}[args.cmd]
    res = fn(con, args)
    print(render(res, as_json=args.json))
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
