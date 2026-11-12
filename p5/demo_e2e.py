#!/usr/bin/env python3
"""P5 E2E exit-gate demo (POC-DESIGN.md, P5 gate):

  1. structural Q in ms with evidence paths
  2. lifetime/dataflow Q via scoped slice
  3. repeat Q = cache hit

Writes the transcript to stdout and to $MSG_PUB/demo_transcript.txt.
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from server import Service                                    # noqa: E402

import os  # portability: published mirrors via MSG_PUB
OUT = Path(os.environ.get("MSG_PUB", str(Path(__file__).resolve().parents[1] / "out"))) / "demo_transcript.txt"
LINES = []


def say(s=""):
    print(s)
    LINES.append(s)


def show(svc, q, note=None):
    t0 = time.time()
    r = svc.query(q)
    wall = (time.time() - t0) * 1000
    say(f"Q: {q}")
    if note:
        say(f"   [{note}]")
    say(f"   router: intent={r['intent']} confidence={r['routed']['confidence']} "
        f"rules_fired={len(r['routed']['rules_fired'])} "
        f"entities={[m['mention'] for m in r['entities']]}")
    say(r.get("text") or f"ERROR: {r.get('error')}")
    say(f"   -> ok={r['ok']} latency={r['meta']['latency_ms']}ms "
        f"(wall {wall:.1f}ms) cache_hit={r['meta']['cache_hit']} "
        f"fingerprint={r['meta']['fingerprint']}")
    say()


def main():
    say("=" * 78)
    say("P5 EXIT-GATE DEMO — router v0 + in-RAM map + /slice instrument + cache")
    say("=" * 78)
    t0 = time.time()
    svc = Service()
    say(f"KB map loaded: {svc.kb.stats()['nodes']} nodes / "
        f"{svc.kb.stats()['edges_fused']} fused edges + 203 clusters + 14 OKF pages "
        f"in {svc.kb.load_ms}ms   fingerprint={svc.kb.fingerprint}")
    say()

    say("-" * 78)
    say("GATE 1 — structural question, millisecond answer, evidence carried")
    say("-" * 78)
    show(svc, "path from svc:bgpd to svc:zebra",
         "the P2 exit-gate flow, re-answered through the router")
    show(svc, "who handles ZEBRA_ROUTE_ADD",
         "callers intent: senders, dispatch site, handler fn")
    show(svc, "who calls zclient_route_send",
         "callers intent across 3 daemons")
    show(svc, "what is the impact of yang:frr-bgp-route-map:ipv4-address",
         "impact intent: YANG leaf -> NB callbacks -> daemons -> ZAPI side effects")

    say("-" * 78)
    say("GATE 2 — lifetime/dataflow question via the scoped /slice instrument")
    say("-" * 78)
    r = svc.query("slice zread_route_add in zebra/zapi_msg.c")
    say(f"Q: slice zread_route_add in zebra/zapi_msg.c")
    say(f"   router: intent={r['intent']} entities={[m['mention'] for m in r['entities']]}")
    say(r.get("text") or r.get("error"))
    a = r["answer"]["full"]
    say(f"   -> scope=(content-hash keyed, tool {a['tool_ver']}) "
        f"cache_key={a['cache']['key'][:12]}")
    say()
    say("Q: where does the value of api come from in zread_route_add?  "
        "[dataflow phrasing of the same scope]")
    r2 = svc.query("where does the value of api come from in zread_route_add")
    chains = [c for c in a["dfg"]["chains"] if c["use"].startswith("api")
              and c["defs"]][:2]
    for c in chains:
        defs = ", ".join(c["defs"])
        say(f"   chain: use {c['use']} @L{c['line']}  <- defs [{defs}]")
    say(f"   -> intent={r2['intent']} latency={r2['meta']['latency_ms']}ms "
        f"(dfg excerpt above from the memoized slice)")
    say()

    say("-" * 78)
    say("GATE 3 — repeat question = cache hit")
    say("-" * 78)
    show(svc, "path from svc:bgpd to svc:zebra", "repeat of gate-1 Q #1")
    show(svc, "who handles ZEBRA_ROUTE_ADD", "repeat of gate-1 Q #2")
    show(svc, "what is the impact of yang:frr-bgp-route-map:ipv4-address",
         "repeat of gate-1 Q #4 (also KB-memoized)")
    qc = svc.health()["query_cache"]
    say(f"query cache: {qc['entries']} entries, {qc['hits']} hits / "
        f"{qc['misses']} misses")
    say(f"slice cache: {svc.engine.stats}")
    say()

    say("-" * 78)
    say("ROUTER COVERAGE — all six intents (rule-based v0, no LLM)")
    say("-" * 78)
    for q, it in [("who calls zclient_route_send", "callers"),
                  ("path from svc:ospfd to svc:zebra", "path"),
                  ("explain code:zebra::zread_route_add", "explain"),
                  ("what is the impact of yang:frr-bgp-route-map:origin", "impact"),
                  ("what are the responsibilities of ospfd?", "docs"),
                  ("slice bgp_zebra_announce_table in bgpd/bgp_zebra.c", "slice")]:
        r = svc.query(q)
        say(f"  {r['intent']:8} <- {q!r}  ({r['meta']['latency_ms']}ms, "
            f"conf={r['routed']['confidence']})")
        assert r["intent"] == it, q
    say()

    say(f"demo wall time: {time.time() - t0:.1f}s (includes KB load)")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(LINES) + "\n")
    print(f"\ntranscript written to {OUT}")


if __name__ == "__main__":
    main()
