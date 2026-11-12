#!/usr/bin/env python3
"""P2 fusion — merge wiring planes, run the two validation joins, export graph.

Inputs
  $MSG_ROOT/facts/facts.duckdb    P1 fact base (30,092 nodes / 81,750 edges)
  $MSG_ROOT/facts/p2/zapi_srv_edges.jsonl   zebra server-side dispatch (zapi_srv.py)
  $MSG_ROOT/facts/p2/lysc_paths.jsonl       libyang compiled schema paths (lysc_paths)

Operations (POC-DESIGN.md merge rules + P1 §4 carry-forward)
  1. copy P1 DB -> $MSG_ROOT/facts/p2/facts.duckdb
  2. insert zapi_srv edges (zebra gains its handles side)
  3. nb<->yang join #1: NB libyang-schema-xpath  ->  contract node
        candidate ladder: schema-exact -> schema-bare -> data-bare
        missing yang nodes are added (libyang-expanded contract plane)
  4. svc-level publishes aggregation (code:fn -> svc)   [join #2 support]
  5. discrepancy findings (dead wiring, dropped-on-wire, etc.)
  6. extractor_coverage ledger + meta phase=P2
  7. graph.json export (nodes + fused edges with sorted evidence lists)
"""
import json
import hashlib
import shutil
import sys
from collections import defaultdict
from pathlib import Path

import duckdb

import os  # portability: workspace root via MSG_ROOT (default <repo>/data)
ROOT = Path(os.environ.get("MSG_ROOT", str(Path(__file__).resolve().parents[1] / "data")))
P1_DB = ROOT / "facts/facts.duckdb"
P2_DIR = ROOT / "facts/p2"
P2_DB = P2_DIR / "facts.duckdb"
DOWNLOAD = Path(os.environ.get("MSG_PUB", str(Path(__file__).resolve().parents[1] / "out"))) / "p2"

PREFIX_RE = None  # built lazily


def strip_prefixes(path: str) -> str:
    """'frr-routing:routing/frr-staticd:staticd/x' -> 'routing/staticd/x'"""
    segs = []
    for seg in path.strip("/").split("/"):
        if ":" in seg:
            seg = seg.split(":", 1)[1]
        segs.append(seg)
    return "/".join(segs)


def run_id(*paths: Path) -> str:
    h = hashlib.sha256()
    for p in paths:
        h.update(p.read_bytes() if p.suffix != ".duckdb" else str(p.stat().st_mtime_ns).encode())
    return h.hexdigest()[:16]


def q(con: duckdb.DuckDBPyConnection, sql: str, params=None):
    return con.execute(sql, params).fetchall()


def main() -> int:
    P2_DIR.mkdir(parents=True, exist_ok=True)
    DOWNLOAD.mkdir(parents=True, exist_ok=True)

    # ---------------------------------------------------------------- 1. copy
    if P2_DB.exists():
        P2_DB.unlink()
    shutil.copy(P1_DB, P2_DB)
    con = duckdb.connect(str(P2_DB))
    con.execute("PRAGMA memory_limit='4GB'")
    n0 = q(con, "select (select count(*) from nodes), (select count(*) from edges)")[0]
    print(f"P1 base: {n0[0]} nodes / {n0[1]} edges")

    rid = run_id(P1_DB, P2_DIR / "zapi_srv_edges.jsonl", P2_DIR / "lysc_paths.jsonl",
                 P2_DIR / "zapi_send_grep_edges.jsonl")

    # ------------------------------------------------------- 2. zapi_srv edges
    zsrv = [json.loads(l) for l in
            (P2_DIR / "zapi_srv_edges.jsonl").read_text().splitlines()]
    # ensure fn nodes exist (zebra fns were in the P1 slice, but be safe)
    fn_ids = sorted({e["src"] for e in zsrv if e["src"].startswith("code:")})
    existing = set(x[0] for x in q(con, "select id from nodes"))
    added_fn = [i for i in fn_ids if i not in existing]
    for i in added_fn:
        con.execute("insert into nodes values (?,?,?,?)",
                    [i, "function", i.split("::")[1], "svc:zebra"])
    for e in zsrv:
        con.execute("insert or ignore into edges values (?,?,?,?,?,?)",
                    [e["src"], e["rel"], e["dst"], e["plane"], e["tag"],
                     e["src_ref"]])
    print(f"zapi_srv: {len(zsrv)} edges, {len(added_fn)} fn nodes added")

    # ------------------------------ 2b. wrapper-mediated send sites (grep)
    sgr = [json.loads(l) for l in
           (P2_DIR / "zapi_send_grep_edges.jsonl").read_text().splitlines()]
    for e in sgr:
        con.execute("insert or ignore into edges values (?,?,?,?,?,?)",
                    [e["src"], e["rel"], e["dst"], e["plane"], e["tag"],
                     e["src_ref"]])
    print(f"zapi_send_grep: {len(sgr)} svc-level edges")

    # ------------------------------------------------- 3. nb<->yang join (#1)
    rows = [json.loads(l) for l in
            (P2_DIR / "lysc_paths.jsonl").read_text().splitlines()]

    idx_schema = {}        # '/mod:path' -> row   (libyang LYSC_PATH_LOG form)
    idx_schema_bare = {}   # prefix-stripped schema path -> row
    idx_data_bare = {}     # prefix-stripped data path -> row

    def put(idx, key, r):
        """Insert with libyang-resolution semantics: FRR NB xpaths are resolved
        at runtime by libyang's tolerant data-path parser, which (a) can only
        land on DATA nodes, and (b) takes the FIRST match in schema order when
        several data nodes share a path shape (e.g. own-tree leaf vs augment
        leaves named alike). We mirror both rules, so a hit here is what FRR
        itself would resolve to. Rows arrive in compiled (schema) order."""
        if key not in idx:
            idx[key] = r
            return
        prev = idx[key]
        if prev["nodetype"] in ("choice", "case") and \
                r["nodetype"] not in ("choice", "case"):
            idx[key] = r                 # data node wins over schema-only node
        # otherwise: first (schema-order) row stays

    n_amb = 0
    for r in rows:
        for idx, key in ((idx_schema, r["schema_path"]),
                         (idx_schema_bare, "/" + strip_prefixes(r["schema_path"])),
                         (idx_data_bare, "/" + strip_prefixes(r["data_path"]))):
            if key in idx and idx[key] is not r:
                n_amb += 1
            put(idx, key, r)

    # FRR NB xpaths are hand-written and drop an ARBITRARY SUBSET of the
    # choice/case segments (outer kept, inner dropped, per table author).
    # Enumerate every keep/drop variant of each schema path (bounded 2^k).
    # Segment qualification is RECOMPUTED per variant (libyang qualifies a
    # segment when its module differs from the nearest kept parent), so
    # `frr-bgp-route-map:list-name` style keys become producible.
    seginfo = {(r["tree_module"], r["schema_path"]): r for r in rows}
    idx_flex = {}          # stripped variants (qualification-insensitive)
    idx_flex_raw = {}      # variants with recomputed qualification
    n_var = 0
    for r in rows:
        segs = r["schema_path"].split("/")          # segs[0] == ''
        cc_pos = []
        for d in range(1, len(segs)):
            pref = "/".join(segs[: d + 1])
            node = seginfo.get((r["tree_module"], pref))
            if node and node["nodetype"] in ("choice", "case"):
                cc_pos.append(d)
        combos = ([()] if cc_pos else [])
        if len(cc_pos) <= 4:
            import itertools
            combos = [c for k in range(0, len(cc_pos) + 1)
                      for c in itertools.combinations(cc_pos, k)]
        else:
            combos = [(), tuple(cc_pos)]            # keep-all / drop-all
        seen_v = set()
        for combo in combos:
            drop = set(combo)
            kept = [i for i in range(len(segs)) if i not in drop]
            vpath = ""
            prev_mod = None
            for d in kept:
                if d == 0:
                    continue                        # leading ''
                info = seginfo.get((r["tree_module"], "/".join(segs[: d + 1])))
                if info is None:            # rpc input/output pseudo-nodes
                    info = {"module": r["module"], "nodetype": "other"}
                name = segs[d].split(":", 1)[1] if ":" in segs[d] else segs[d]
                if d == kept[1] or info["module"] != prev_mod:
                    name = f"{info['module']}:{name}"
                vpath += "/" + name
                prev_mod = info["module"]
            if vpath in seen_v:
                continue
            seen_v.add(vpath)
            n_var += 1
            put(idx_flex_raw, vpath, r)
            put(idx_flex, "/" + strip_prefixes(vpath), r)
    print(f"lysc index: {len(rows)} rows, "
          f"{len(idx_schema)}/{len(idx_schema_bare)}/{len(idx_data_bare)} keys, "
          f"{len(idx_flex)} flex-variant keys ({n_var} variants), "
          f"{n_amb} collisions resolved by first-data-node rule")

    loaded_mods = {r["module"] for r in rows}
    nb_nodes = q(con, "select id, service from nodes where id like 'nb:%' "
                      "order by id")
    existing = set(x[0] for x in q(con, "select id from nodes"))

    strategy = defaultdict(int)
    hits, misses, yang_added = [], [], []
    for (nb_id, _svc) in nb_nodes:
        parts = nb_id.split(":", 3)
        if len(parts) != 4:
            misses.append({"id": nb_id, "reason": "malformed-id"})
            continue
        _, _dir, module, path = parts
        row = None
        strat_used = None
        for strat, key in (
                # libyang qualifies the first segment as "module:name" — the
                # exact literal form FRR NB tables store
                ("schema-exact", f"/{module}:{path}"),
                ("flex-raw", f"/{module}:{path}"),
                ("flex-bare", "/" + strip_prefixes(f"/{module}:{path}")),
                ("schema-bare", "/" + strip_prefixes(f"/{module}:{path}")),
                ("data-bare", "/" + strip_prefixes(f"/{module}:{path}"))):
            if strat == "schema-exact":
                cand = idx_schema.get(key)
            elif strat == "flex-raw":
                cand = idx_flex_raw.get(key)
            elif strat == "flex-bare":
                cand = idx_flex.get(key)
            elif strat == "schema-bare":
                cand = idx_schema_bare.get(key)
            else:
                cand = idx_data_bare.get(key)
            if cand is not None:
                row, strat_used = cand, strat
                strategy[strat] = strategy[strat] + 1
                break
        if row is None:
            reason = ("module-not-in-context" if module not in loaded_mods
                      else "no-path-match")
            misses.append({"id": nb_id, "reason": reason})
            continue
        yang_id = f"yang:{row['module']}:{row['bare']}"
        if yang_id not in existing:
            existing.add(yang_id)
            yang_added.append(yang_id)
            con.execute("insert into nodes values (?,?,?,?)",
                        [yang_id, "yang-node", row["name"], None])
        con.execute("insert or ignore into edges values "
                    "(?,'implements',?,'contract','DECLARED',"
                    "'fusion:nb-yang-join')", [nb_id, yang_id])
        hits.append({"nb": nb_id, "yang": yang_id, "strategy": strat_used})

    n_nb = len(nb_nodes)
    pct = 100.0 * len(hits) / n_nb if n_nb else 0.0
    print(f"nb-yang join: {len(hits)}/{n_nb} ({pct:.1f}%) "
          f"strategies={dict(strategy)} misses={len(misses)} "
          f"yang-nodes-added={len(yang_added)}")

    # ---------------------------------------- 4. svc-level publishes (join #2)
    svc_pub = q(con, """
        select n.service, e.dst, count(*) as fn_cnt
        from edges e join nodes n on n.id = e.src
        where e.rel = 'publishes' and e.src like 'code:%' and n.service is not null
        group by 1, 2""")
    for svc, msg, _cnt in svc_pub:
        con.execute("insert or ignore into edges values "
                    "(?,'publishes',?,'wiring','DECLARED','fusion:svc-pub')",
                    [svc, msg])
    print(f"svc-publishes: {len(svc_pub)} derived edges")

    # ------------------------------------------------------- 5. findings
    def svc_side(rel):
        d = defaultdict(set)
        for s, m in q(con, f"select src, dst from edges where rel='{rel}' "
                           f"and src like 'svc:%'"):
            d[m].add(s)
        return d

    pub, hnd = svc_side("publishes"), svc_side("handles")
    all_msgs = set(pub) | set(hnd)
    dropped = sorted(m for m in pub if m not in hnd)          # nobody handles
    orphan = sorted(m for m in hnd if m not in pub)           # nobody in slice sends
    flows = sorted((m, s, h) for m in all_msgs for s in pub.get(m, [])
                   for h in hnd.get(m, []) if s != h)

    # dead wiring at REGISTRATION level: svc registers an NB entry but that
    # svc's table provides no callback for it (shared tables register the same
    # node id from several daemons, so node-level deadness is too coarse)
    dead_pairs = q(con, """
        select r.src, r.dst, r.src_ref from edges r
        where r.rel = 'registers' and r.src like 'svc:%'
          and not exists (
            select 1 from edges h join nodes cb on cb.id = h.dst
            where h.src = r.dst and h.rel = 'handles'
              and h.src like 'nb:%' and cb.service = r.src)""")

    findings = {
        "nb_yang_join": {
            "total_nb": n_nb, "hits": len(hits), "misses": misses,
            "pct": round(pct, 1), "strategies": dict(strategy),
            "yang_nodes_added": yang_added,
        },
        "zapi": {
            "dropped_on_wire": dropped,
            "orphan_handlers_no_sender_in_slice": orphan,
            "cross_svc_flows": [{"msg": m, "from": s, "to": h}
                                for m, s, h in flows],
        },
        "dead_wiring": {
            "registrations_without_callbacks":
                [{"svc": s, "nb": n, "table": ref} for s, n, ref in dead_pairs],
        },
    }
    (P2_DIR / "findings.json").write_text(json.dumps(findings, indent=2))
    print(f"findings: dropped={len(dropped)} orphan={len(orphan)} "
          f"flows={len(flows)} dead-registrations={len(dead_pairs)}")

    # --------------------------------------------- 6. ledger + meta
    led = [
        ("zapi-srv", "wiring", len(zsrv)),
        ("zapi-send-grep", "wiring", len(sgr)),
        ("libyang-paths", "contract", len(rows)),
        ("fusion-nb-yang", "contract", len(hits)),
        ("fusion-svc-pub", "wiring", len(svc_pub)),
    ]
    for ext, plane, cnt in led:
        con.execute("insert or replace into extractor_coverage values (?,?,?,?)",
                    [ext, plane, cnt, rid])
    con.execute("insert or replace into meta values ('phase', 'P2')")
    con.execute("insert or replace into meta values ('p2_fused_at', current_date || '')")
    con.execute("insert or replace into meta values ('nb_yang_join_pct', ?)",
                [str(round(pct, 1))])
    con.execute("insert or replace into meta values ('p2_run_id', ?)", [rid])

    # ------------------------------------------------- 7. graph.json export
    nodes = q(con, "select id, kind, label, service from nodes order by id")
    fused = q(con, """
        select src, rel, dst,
               list(distinct tag || ':' || plane) as ev,
               count(distinct plane) as np
        from edges group by src, rel, dst order by src, rel, dst""")
    graph = {
        "meta": {
            "schema_version": "0.1.0",
            "phase": "P2",
            "frr_tag": "frr-10.7.1",
            "run_id": rid,
            "nodes": len(nodes),
            "edges_raw": n0[1] + len(zsrv) + len(sgr) + len(hits) + len(svc_pub),
            "edges_fused": len(fused),
            "note": "evidence lists are sorted 'TAG:plane' items; "
                    "authority order OBSERVED > CONFIGURED > DECLARED",
        },
        "nodes": [{"id": i, "kind": k, "label": l, "service": s}
                  for i, k, l, s in nodes],
        "edges": [{"src": s, "rel": r, "dst": d,
                   "evidence": sorted(e), "n_planes": np}
                  for s, r, d, e, np in fused],
    }
    out_graph = P2_DIR / "graph.json"
    out_graph.write_text(json.dumps(graph))
    print(f"graph.json: {len(nodes)} nodes / {len(fused)} fused edges "
          f"({out_graph.stat().st_size/1e6:.1f} MB)")

    # summary for the report
    summary = {
        "run_id": rid,
        "nodes": len(nodes),
        "edges_raw": graph["meta"]["edges_raw"],
        "edges_fused": len(fused),
        "zapi_srv": {"entries": len(zsrv)},
        "zapi_send_grep": {"svc_edges": len(sgr),
                           "sites": len(json.loads(
                               (P2_DIR / "zapi_send_grep_sites.json").read_text()))},
        "nb_yang_join": {"hits": len(hits), "total": n_nb,
                         "pct": round(pct, 1),
                         "strategies": dict(strategy),
                         "yang_nodes_added": len(yang_added),
                         "misses": len(misses)},
        "svc_publishes": len(svc_pub),
        "findings_counts": {"dropped_on_wire": len(dropped),
                            "orphan_handlers": len(orphan),
                            "cross_svc_flows": len(flows),
                            "dead_registrations": len(dead_pairs)},
        "multi_plane_edges": sum(1 for *_x, np in
                                 [(f[0], f[1], f[2], f[3], f[4]) for f in fused]
                                 if np > 1),
    }
    (P2_DIR / "fusion_summary.json").write_text(json.dumps(summary, indent=2))
    con.close()
    print("fuse: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
