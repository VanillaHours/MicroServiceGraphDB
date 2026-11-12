#!/usr/bin/env python3
"""P2 fusion tests — schema integrity, both validation joins, exit gates.

Gates (POC-DESIGN.md §4 P2):
  A. `path svc:bgpd svc:zebra` resolves via a real ZAPI edge
  B. YANG-leaf impact lists daemons + callbacks
Plus the P1-carried join bar: nb<->yang >= 90% (we assert == 100%).

Run:  python3 scripts/p2/tests_fusion.py
Exit 0 iff all tests pass.
"""
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).parent))
from kb import Graph, connect  # noqa: E402

import os  # portability: workspace root via MSG_ROOT (default <repo>/data)
ROOT = Path(os.environ.get("MSG_ROOT", str(Path(__file__).resolve().parents[1] / "data")))
DB = str(ROOT / "facts/p2/facts.duckdb")
P2 = ROOT / "facts/p2"

results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  [{detail}]" if detail else ""))


def main() -> int:
    con = connect(DB)
    g = Graph(con)
    print("== T1 schema integrity ==")
    n_edges, n_pk = con.execute("""
        select count(*), count(distinct (src, rel, dst, plane, src_ref))
        from edges""").fetchone()
    check("edges PK-unique", n_edges == n_pk, f"{n_edges} rows")
    orphans = con.execute("""
        select count(*) from edges e
        where e.src not in (select id from nodes)
           or e.dst not in (select id from nodes)""").fetchone()[0]
    check("edges referentially closed", orphans == 0, f"{orphans} dangling")

    print("== T2 evidence well-formedness ==")
    bad = con.execute("""
        select count(*) from (
            select src, rel, dst, list(distinct tag || ':' || plane) as ev
            from edges group by src, rel, dst)
        where len(ev) = 0 or array_position(ev, 'DECLARED:wiring') is null
          and array_position(ev, 'DECLARED:code') is null
          and array_position(ev, 'DECLARED:contract') is null
          and array_position(ev, 'BUILD:build') is null""").fetchone()[0]
    check("every fused edge has valid evidence", bad == 0)

    print("== T3 join #1: nb<->yang ==")
    n_nb = con.execute("select count(*) from nodes where id like 'nb:%'").fetchone()[0]
    n_impl = con.execute(
        "select count(distinct src) from edges where rel='implements'").fetchone()[0]
    check("nb entries >= 90% joined (gate bar)", n_impl / n_nb >= 0.90,
          f"{n_impl}/{n_nb}")
    check("nb entries 100% joined (P2 result)", n_impl == n_nb,
          f"{n_impl}/{n_nb}")
    # yang nodes the join resolves to must exist in the contract plane
    miss = con.execute("""
        select count(*) from edges e
        where e.rel='implements' and e.dst not in
          (select id from nodes where id like 'yang:%')""").fetchone()[0]
    check("join targets are contract nodes", miss == 0)

    print("== T4 join resolution spot-check (independent recomputation) ==")
    rows = [json.loads(l) for l in (P2 / "lysc_paths.jsonl").read_text().splitlines()]
    by_yang = {}
    for r in rows:
        by_yang[f"yang:{r['module']}:{r['bare']}"] = r
    sample = con.execute("""
        select e.src, e.dst from edges e where e.rel='implements'
        order by random() limit 10""").fetchall()
    ok = 0
    for nb_id, yang_id in sample:
        r = by_yang.get(yang_id)
        if r is None:
            continue
        # the resolved schema path must contain the nb xpath's final segment
        parts = nb_id.split(":", 3)
        leaf = parts[3].split("/")[-1].split(":")[-1]
        if r["schema_path"].rstrip("/").endswith(leaf):
            ok += 1
    check("10 sampled joins resolve to nodes ending in the nb leaf name",
          ok >= 9, f"{ok}/10 (yang ids built from libyang bare paths)")

    print("== T5 join #2: zapi handlers + senders ==")
    zr = con.execute("""
        select count(*) from edges where rel='handles'
          and dst='zapi:ZEBRA_ROUTE_ADD' and src='svc:zebra'""").fetchone()[0]
    check("zebra handles ZEBRA_ROUTE_ADD (server table)", zr >= 1)
    fn = con.execute("""
        select count(*) from edges where rel='handles'
          and dst='zapi:ZEBRA_ROUTE_ADD' and src='code:zebra::zread_route_add'""").fetchone()[0]
    check("fn-level: zread_route_add handles ZEBRA_ROUTE_ADD", fn == 1)
    bp = con.execute("""
        select count(*) from edges where rel='publishes'
          and dst='zapi:ZEBRA_ROUTE_ADD' and src='svc:bgpd'""").fetchone()[0]
    check("bgpd publishes ZEBRA_ROUTE_ADD (svc-level)", bp == 1)
    grep_sites = json.loads((P2 / "zapi_send_grep_sites.json").read_text())
    check("bgpd route send site is real (bgp_zebra.c:1741)",
          any(s["file"] == "bgpd/bgp_zebra.c" and s["line"] == 1741
              and s["msg"] == "ZEBRA_ROUTE_ADD" for s in grep_sites))
    # message namespace discipline: no edge points at an unknown zapi id
    unknown = con.execute("""
        select count(*) from edges e
        where e.dst like 'zapi:%' and e.dst not in
          (select id from nodes)""").fetchone()[0]
    check("all zapi edge targets are message nodes", unknown == 0)

    print("== T6 gate A: path svc:bgpd -> svc:zebra via real ZAPI edge ==")
    hops = g.path("svc:bgpd", "svc:zebra", max_hops=4)
    via_zapi = hops is not None and len(hops) == 2 and \
        hops[0]["to"].startswith("zapi:") and \
        any(h["rel"] == "publishes" for h in hops) and \
        any(h["rel"] == "handles" for h in hops)
    check("2-hop path bgpd -> zapi:* -> zebra exists", via_zapi,
          f"{hops[0]['to'] if hops else 'none'}")

    print("== T7 gate B: YANG-leaf impact lists daemons + callbacks ==")
    # (a) the augment case from the P1 report
    imp = g.impact("yang:frr-staticd:staticd/route-list/prefix")
    check("staticd route-list/prefix -> svc:staticd",
          "svc:staticd" in imp["daemons"], str(imp["daemons"]))
    check("staticd route-list/prefix -> callbacks", len(imp["callbacks"]) >= 1,
          f"{len(imp['callbacks'])} cbs")
    check("staticd impact reaches zapi side effects",
          len(imp["zapi_side_effects"]) >= 5,
          f"{len(imp['zapi_side_effects'])} msgs")
    # (b) a random sample of joined yang ids must yield daemon+callbacks
    joined = con.execute("""
        select distinct dst from edges where rel='implements'
        order by random() limit 25""").fetchall()
    good = 0
    for (yid,) in joined:
        imp = g.impact(yid, call_depth=6)
        if imp["daemons"] and imp["callbacks"]:
            good += 1
    check(">=80% of joined yang leaves have daemon+callback impact",
          good >= 20, f"{good}/25")

    print("== T8 graph.json consistency ==")
    graph = json.loads((P2 / "graph.json").read_text())
    check("graph node count matches DB",
          len(graph["nodes"]) == con.execute(
              "select count(*) from nodes").fetchone()[0])
    check("graph fused edge count matches view",
          len(graph["edges"]) == con.execute(
              "select count(*) from fused_edges").fetchone()[0])
    ev_sorted = all(e["evidence"] == sorted(e["evidence"])
                    for e in graph["edges"][:500])
    check("evidence lists deterministic (sorted)", ev_sorted)

    print("== T9 findings ledger ==")
    f = json.loads((P2 / "findings.json").read_text())
    dead_db = con.execute("""
        select count(*) from edges r
        where r.rel='registers' and r.src like 'svc:%'
          and not exists (
            select 1 from edges h join nodes cb on cb.id = h.dst
            where h.src = r.dst and h.rel='handles'
              and h.src like 'nb:%' and cb.service = r.src)""").fetchone()[0]
    check("dead-registration count matches DB",
          len(f["dead_wiring"]["registrations_without_callbacks"]) == dead_db,
          f"{dead_db}")
    check("dropped/orphan ledgered",
          len(f["zapi"]["dropped_on_wire"]) >= 1 and
          len(f["zapi"]["orphan_handlers_no_sender_in_slice"]) >= 1,
          f"dropped={len(f['zapi']['dropped_on_wire'])} "
          f"orphan={len(f['zapi']['orphan_handlers_no_sender_in_slice'])}")

    n_fail = sum(1 for _, ok, _ in results if not ok)
    print(f"\n{len(results) - n_fail}/{len(results)} passed"
          + ("  — ALL GREEN" if n_fail == 0 else f"  — {n_fail} FAILURES"))
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
