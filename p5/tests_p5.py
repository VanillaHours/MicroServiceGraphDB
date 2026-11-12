#!/usr/bin/env python3
"""P5 tests — router goldens, entity linking, backends, slice invariants,
cache behavior, HTTP e2e. Run: python3 tests_p5.py  (exit code = failures)."""
import json
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from server import Service, make_handler, DEFAULT_PORT  # noqa: E402
from http.server import ThreadingHTTPServer             # noqa: E402
import router                                           # noqa: E402

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail and not cond else ""))


# ------------------------------------------------------------ T1 router
def t1_router():
    print("T1 router goldens (rule-based, no LLM)")
    gold = [
        ("who handles ZEBRA_ROUTE_ADD?", "callers"),
        ("who calls zclient_route_send", "callers"),
        ("list the senders of ZEBRA_FEC_UPDATE", "callers"),
        ("show the path from svc:bgpd to svc:zebra", "path"),
        ("how does ospfd reach zebra", "path"),
        ("what is the impact of yang:frr-bgp-route-map:ipv4-address", "impact"),
        ("what happens if ZEBRA_INTERFACE_ADD changes", "impact"),
        ("which daemons are affected if I remove frr-ripd:ripd/instance/default-metric", "impact"),
        ("slice zread_route_add in zebra/zapi_msg.c", "slice"),
        ("show the dataflow in bgp_zebra_announce_table", "slice"),
        ("where does the value of api come from in zread_route_add", "slice"),
        ("what are the responsibilities of bgpd?", "docs"),
        ("documentation for zebra", "docs"),
        ("give me an overview of the ospfd cluster", "docs"),
        ("explain code:zebra::zread_route_add", "explain"),
        ("what is zapi:ZEBRA_INTERFACE_ADD", "explain"),
        ("tell me about staticd", "explain"),
    ]
    for q, want in gold:
        r = router.classify(q)
        check(f"  {q[:52]!r} -> {want}", r["intent"] == want,
              f"got {r['intent']} scores={r['scores']}")
    # explicit intent overrides
    r = router.classify("hello world", explicit_intent="docs")
    check("explicit intent override", r["intent"] == "docs" and r["explicit"] is True)
    r = router.classify("who handles ZEBRA_ROUTE_ADD", explicit_intent="bogus")
    check("unknown explicit intent rejected", r["intent"] is None)


# ------------------------------------------------------------ T2 linking
def t2_linking(svc):
    print("T2 entity linking")
    kb = svc.kb
    m = kb.resolve_mentions("who handles ZEBRA_ROUTE_ADD")
    check("zapi enum links", any(x.ids == ["zapi:ZEBRA_ROUTE_ADD"] for x in m))
    m = kb.resolve_mentions("what are the responsibilities of bgpd?")
    check("service with punctuation links", [x.kind for x in m] == ["svc"]
          and m[0].ids == ["svc:bgpd"])
    m = kb.resolve_mentions("path from svc:bgpd to svc:zebra")
    kinds = [x.kind for x in m]
    check("qualified svc ids link", kinds == ["svc", "svc"])
    m = kb.resolve_mentions("explain zread_route_add")
    check("bare function links to code node",
          m and m[0].ids[0] == "code:zebra::zread_route_add")
    m = kb.resolve_mentions("impact of yang:frr-bgp-route-map:ipv4-address")
    check("yang leaf linkable", any("yang:frr-bgp-route-map:ipv4-address" in x.ids
                                    for x in m))
    check("defining file known for zread_route_add",
          kb.code_file.get("code:zebra::zread_route_add") == "zebra/zapi_msg.c")
    check("code node domain resolves via svc bridge",
          kb.domain_of("code:zebra::zread_route_add") is not None)


# ------------------------------------------------------------ T3 callers
def t3_callers(svc):
    print("T3 callers backend (P2 exit-gate flow, re-checked)")
    r = svc.query("who handles ZEBRA_ROUTE_ADD")
    a = r["answer"]
    check("sender services include bgpd",
          "svc:bgpd" in a.get("sender_services", []), str(a.get("sender_services")))
    check("handler services include zebra",
          "svc:zebra" in a.get("handler_services", []))
    check("handler fn is zread_route_add",
          any("zread_route_add" in h["node"] for h in a.get("handlers", [])))
    check("evidence carries src_ref", all(e.get("src_ref") for e in a["evidence"]))
    r2 = svc.query("who calls zclient_route_send")
    a2 = r2["answer"]
    senders = {c["node"] for c in a2.get("callers", [])}
    check("bgp_zebra_announce_actual among callers",
          "code:bgpd::bgp_zebra_announce_actual" in senders)
    check("ospf_zebra_add among callers",
          "code:ospfd::ospf_zebra_add" in senders)


# ------------------------------------------------------------ T4 path
def t4_path(svc):
    print("T4 path backend")
    r = svc.query("path from svc:bgpd to svc:zebra")
    a = r["answer"]
    check("2-hop ZAPI flow found", a.get("hops") == 2, str(a))
    check("message is ZEBRA_ROUTE_ADD", a.get("via") == "zapi:ZEBRA_ROUTE_ADD")
    rels = [h["rel"] for h in a["path"]]
    check("pattern publishes->handles", rels == ["publishes", "handles"], str(rels))
    check("per-hop evidence present", len(a["evidence"]) == 2
          and all(e["src_ref"] for e in a["evidence"]))
    r2 = svc.query("path from svc:bgpd to svc:bgpd")
    check("degenerate path clarified", r2["ok"] is False)


# ------------------------------------------------------------ T5 impact
def t5_impact(svc):
    print("T5 impact backend")
    r = svc.query("what is the impact of yang:frr-bgp-route-map:ipv4-address")
    a = r["answer"]
    check("daemons include bgpd", "svc:bgpd" in a["daemons"])
    check("callbacks non-empty", len(a["callbacks"]) >= 2)
    check("zapi side effects found", len(a["zapi_side_effects"]) >= 3)
    check("evidence anchored", len(a["evidence"]) >= 3)
    t0 = time.time()
    r2 = svc.query("impact of yang:frr-bgp-route-map:ipv4-address please")
    dt = (time.time() - t0) * 1000
    check(f"KB-memoized impact re-ask fast ({dt:.1f}ms)",
          dt < 50 and r2["answer"]["memoized"] is True)


# ------------------------------------------------------------ T6 slice
def t6_slice(svc):
    print("T6 slice instrument (CFG/DFG/liveness, memoized)")
    r = svc.slice_api(file="zebra/zapi_msg.c", function="zread_route_add")
    check("slice ok", r["ok"] is True)
    cfg, dfg, lv = r["cfg"], r["dfg"], r["liveness"]
    check("cfg has entry/exit", cfg["entry"] == 0 and cfg["exit"] == 1)
    check("blocks >= 30 for zread_route_add", cfg["n_blocks"] >= 30,
          str(cfg["n_blocks"]))
    check("edges kinds include then/loop",
          {"then", "loop-true", "exit-false"} <= {e["kind"] for e in cfg["edges"]})
    check("exit block has no successors",
          all(e["from"] != cfg["exit"] for e in cfg["edges"]))
    params = [p["name"] for p in r["scope"]["params"]]
    check("params from ZAPI_HANDLER_ARGS expansion",
          set(params) == {"client", "hdr", "msg", "zvrf"}, str(params))
    check("def-use chains non-empty", dfg["n_chains"] > 20)
    chain_ok = any(c["use"] == "s" and c["defs"] for c in dfg["chains"])
    check("s (stream) chain resolves to a def", chain_ok)
    check("params live at entry subset", set(lv["params_live_at_entry"])
          <= {p["name"] for p in r["scope"]["params"]})
    check("msg is live at entry", "msg" in lv["params_live_at_entry"])
    r2 = svc.slice_api(file="zebra/zapi_msg.c", function="zread_route_add")
    check("slice memoized on repeat", r2["cache"]["hit"] is True)
    r3 = svc.slice_api(code_id="code:bgpd::bgp_zebra_announce_table")
    check("slice via code_id resolves file",
          r3["ok"] and r3["scope"]["file"] == "bgpd/bgp_zebra.c")
    latches = [e for e in r3["cfg"]["edges"] if e["kind"] == "latch"]
    check("announce_table has loop back-edges", len(latches) >= 1)
    bad = svc.slice_api(file="zebra/zapi_msg.c", function="no_such_fn")
    check("unknown function -> clarify error", bad["ok"] is False)


# ------------------------------------------------------------ T7 cache
def t7_cache(svc):
    print("T7 query cache (repeat Q = cache hit)")
    svc.query("documentation for zebra")            # warm
    a = svc.query("documentation for zebra")
    check("repeat query cache_hit", a["meta"]["cache_hit"] is True)
    check("latency drops on hit", a["meta"]["latency_ms"] < 5)
    b = svc.query("DOCUMENTATION  FOR  ZEBRA")      # normalization -> same key
    check("whitespace/case normalization hits cache",
          b["meta"]["cache_hit"] is True)
    c = svc.query("documentation for bgpd")
    check("different question = miss", c["meta"]["cache_hit"] is False)


# ------------------------------------------------------------ T8 docs
def t8_docs(svc):
    print("T8 docs backend (P3 packs + P4 OKF, sha-anchored)")
    r = svc.query("what are the responsibilities of bgpd?")
    a = r["answer"]
    check("domain pack found", a["pack"] and a["pack"]["id"] == "D3063a0b0")
    check("pack sha256 anchored", bool(a["pack"].get("sha256")))
    check("functionality from no-LLM profile", len(a["pack"]["functionality"]) >= 1)
    r2 = svc.query("documentation for zebra")
    check("OKF pages referenced for svc",
          any("daemons/zebra" in p["page"] for p in r2["answer"]["okf_pages"]),
          str([p["page"] for p in r2["answer"]["okf_pages"]]))


# ------------------------------------------------------------ T9 HTTP e2e
def t9_http():
    print("T9 HTTP e2e (real sockets)")
    svc = Service()
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(svc))
    port = httpd.server_address[1]
    th = threading.Thread(target=httpd.serve_forever, daemon=True)
    th.start()
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=10) as resp:
            h = json.loads(resp.read())
            check("GET /health 200", resp.status == 200
                  and h["kb"]["nodes"] > 30000)
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/query",
            data=json.dumps({"question": "who handles ZEBRA_ROUTE_ADD"}).encode(),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            a = json.loads(resp.read())
            check("POST /query 200 + intent",
                  resp.status == 200 and a["intent"] == "callers")
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/slice",
            data=json.dumps({"file": "zebra/zapi_msg.c",
                             "function": "zread_route_add"}).encode(),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            s = json.loads(resp.read())
            check("POST /slice 200", resp.status == 200 and s["ok"]
                  and s["cfg"]["n_blocks"] >= 30)
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/query",
            data=json.dumps({"question": "who handles ZEBRA_ROUTE_ADD"}).encode(),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            a2 = json.loads(resp.read())
            check("HTTP repeat query cache hit", a2["meta"]["cache_hit"] is True)
        # bad path -> 404
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/nope", timeout=5)
            check("unknown path 404", False)
        except urllib.error.HTTPError as e:
            check("unknown path 404", e.code == 404)
    finally:
        httpd.shutdown()


def main():
    t0 = time.time()
    print("loading KB map (in-RAM)...")
    svc = Service()
    print(f"  loaded in {svc.kb.load_ms}ms  fingerprint={svc.kb.fingerprint}")
    t1_router()
    t2_linking(svc)
    t3_callers(svc)
    t4_path(svc)
    t5_impact(svc)
    t6_slice(svc)
    t7_cache(svc)
    t8_docs(svc)
    t9_http()
    dt = time.time() - t0
    print(f"\n{len(PASS)} passed, {len(FAIL)} failed  ({dt:.1f}s)")
    if FAIL:
        print("FAILED:", *FAIL, sep="\n  - ")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
