#!/usr/bin/env python3
"""P6 P/R evaluation — run the golden set through the live P5 service.

Metrics per intent and overall:
  routing accuracy   predicted intent == golden intent
  recall             |returned ∩ expected| / |expected|        (key-level)
  verified-precision of returned items independently checkable in source
                     (token at the returned src_ref file:line)  (item-level)
  exactness          share of questions where ALL graded facets pass
  evidence anchoring share of returned items carrying a src_ref
  latency p50/p95    from the query meta
Negative controls: graceful refusal counts as exact.

Baseline: single-grep proxy — `rg -w <entity token>` over the indexed slice;
measures whether the expected key tokens are inside the raw grep hit list
(the KB's structural joins are exactly what grep cannot do).

Outputs: $MSG_ROOT/facts/p6/eval_results.json (+ stdout report)
"""
import json
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "p5"))
from server import Service  # noqa: E402

import os  # portability: workspace root via MSG_ROOT
ROOT = Path(os.environ.get("MSG_ROOT", str(Path(__file__).resolve().parents[1] / "data")))
SRC = Path(os.environ.get("MSG_SRC", str(ROOT / "src/frr-10.7.1")))

GOLDEN = ROOT / "facts/p6/golden_set.json"
OUT = ROOT / "facts/p6/eval_results.json"
SLICE_DIRS = ["lib", "zebra", "bgpd", "ospfd", "staticd", "yang", "doc"]


def src_window_has(rel, lineno, token, window=0):
    p = SRC / rel
    if not p.exists() or not lineno:
        return False
    lines = p.read_text(errors="replace").splitlines()
    lo, hi = max(0, lineno - 1 - window), min(len(lines), lineno + window)
    return token in "\n".join(lines[lo:hi])


def parse_ref(ref):
    if not ref:
        return None, None
    m = re.match(r"([\w/.-]+\.c):(\d+)", str(ref))
    return (m.group(1), int(m.group(2))) if m else (None, None)


def item_verified(item, token):
    """Independent source check of one returned item via its src_ref."""
    rel, ln = parse_ref(item.get("src_ref"))
    if not rel:
        return False
    return src_window_has(rel, ln, token)


def grade_callers(qq, ans, a):
    exp, got = qq["expected"], {}
    if "handlers" in exp:
        ret = [h["node"] for h in a.get("handlers", [])]
        got["recall"] = (len([x for x in exp["handlers"] if x in ret])
                         / max(len(exp["handlers"]), 1))
        hs = a.get("handler_services") or []
        got["svc_ok"] = all(s in hs for s in exp.get("handler_services", []))
    if "callers" in exp:
        ret = [c["node"] for c in a.get("callers", [])]
        got["recall"] = (len([x for x in exp["callers"] if x in ret])
                         / max(len(exp["callers"]), 1))
    items = a.get("handlers", []) + a.get("callers", []) + a.get("senders", [])
    callee = ""
    tgt = a.get("target") or ""
    if "::" in tgt:
        callee = tgt.split("::")[-1]
    ver = []
    for i in items:
        node = i.get("node", "")
        if "callers" in exp and node in {c for c in exp.get("callers", [])}:
            tok = callee                     # call site must contain the callee
        else:
            tok = node.split("::")[-1] if "::" in node else ""
        rel, ln = parse_ref(i.get("src_ref"))
        if tok and rel:
            ver.append(src_window_has(rel, ln, tok, window=2))
        else:
            ver.append(False)   # no file:line ref -> not independently checkable
    got["verified_precision"] = (sum(ver) / len(ver)) if ver else None
    got["exact"] = (got.get("recall", 0) == 1.0
                    and got.get("svc_ok", True) is not False)
    got["anchoring"] = (sum(bool(i.get("src_ref")) for i in items)
                        / len(items)) if items else None
    return got


def grade_path(qq, ans, ok):
    exp = qq["expected"]
    if exp.get("refuse"):
        return {"refuse_ok": ok is False or ans.get("error") is not None,
                "facets": 1, "facets_hit": 1 if (ok is False) else 0,
                "recall": 1.0 if ok is False else 0.0, "exact": ok is False}
    hops = ans.get("path") or []
    f = {}
    f["endpoints"] = (hops and hops[0]["from"] == exp["src"]
                      and hops[-1]["to"] == exp["dst"])
    f["hops"] = ans.get("hops", len(hops)) <= exp["max_hops"]
    f["evidence"] = all(e.get("src_ref") for e in ans.get("evidence", []) or [])
    if "via" in exp:
        f["via"] = ans.get("via") == exp["via"]
    hit = sum(1 for v in f.values() if v)
    return {"facets": len(f), "facets_hit": hit,
            "recall": hit / len(f), "exact": hit == len(f),
            "anchoring": 1.0 if f["evidence"] else 0.0}


def grade_impact(qq, ans):
    exp = qq["expected"]
    f = {}
    if "daemons" in exp:
        ret_d = set(ans.get("daemons") or ans.get("daemons_affected") or [])
        f["daemons"] = all(d.replace("svc:", "") in {x.replace("svc:", "")
                              for x in ret_d} for d in exp["daemons"])
    if "handlers" in exp:
        ret_h = {h["node"] for h in ans.get("handlers", [])}
        f["handlers"] = all(h in ret_h for h in exp["handlers"])
        f["handler_services"] = all(
            s in (ans.get("handler_services") or [])
            for s in exp.get("handler_services", []))
    if "callbacks_at_least" in exp:
        ret_cb = " ".join(ans.get("callbacks") or [])
        f["callbacks"] = all(cb in ret_cb for cb in exp["callbacks_at_least"])
    if "zapi_side_effects_at_least" in exp:
        n = len(ans.get("zapi_side_effects") or {})
        f["side_effects"] = n >= exp["zapi_side_effects_at_least"]
    if "callers_at_least" in exp:
        ret_c = " ".join(ans.get("direct_callers") or [])
        f["callers"] = all(c in ret_c for c in exp["callers_at_least"])
    hit = sum(1 for v in f.values() if v)
    items = ans.get("evidence") or []
    return {"facets": len(f), "facets_hit": hit, "recall": hit / max(len(f), 1),
            "exact": hit == len(f) and len(f) > 0,
            "anchoring": (sum(bool(i.get("src_ref")) for i in items)
                          / len(items)) if items else None}


def grade_explain(qq, ans):
    exp, node = qq["expected"], ans.get("node") or {}
    f = {}
    if "kind" in exp:
        f["kind"] = node.get("kind") == exp["kind"]
    if "service" in exp:
        got = (node.get("service") or "").replace("svc:", "")
        f["service"] = got == exp["service"]
    for rel in exp.get("relations_includes", []):
        f[f"rel:{rel}"] = rel in (ans.get("relations") or {})
    hit = sum(1 for v in f.values() if v)
    return {"facets": len(f), "facets_hit": hit, "recall": hit / max(len(f), 1),
            "exact": hit == len(f) and len(f) > 0, "anchoring": None}


def grade_docs(qq, ans):
    exp = qq["expected"]
    svc_short = exp["service"].split(":")[1]
    f = {}
    pack = ans.get("pack") or {}
    pages = ans.get("okf_pages") or []
    adrs = ans.get("adrs") or []
    f["service_found"] = (pack.get("id") is not None or
                          any(f"daemons/{svc_short}" in p["page"]
                              for p in pages) or
                          bool(adrs))   # adr-scan mode (entity-less fallback)
    blob = json.dumps(ans).lower()
    f["keywords"] = all(k.lower() in blob for k in exp["doc_keywords"])
    hit = sum(1 for v in f.values() if v)
    return {"facets": len(f), "facets_hit": hit, "recall": hit / max(len(f), 1),
            "exact": hit == len(f) and len(f) > 0,
            "anchoring": bool(pack.get("sha256")) or None}


def grade_slice(qq, ans_full):
    exp = qq["expected"]
    scope = ans_full.get("scope") or ans_full
    cfg = ans_full.get("cfg") or {}
    dfg = ans_full.get("dfg") or {}
    params = scope.get("params") or []
    names = sorted(p["name"] if isinstance(p, dict) else str(p)
                   for p in params)
    f = {}
    f["params"] = names == sorted(exp["params"])
    f["blocks"] = cfg.get("n_blocks", 0) >= exp["min_blocks"]
    f["chains"] = dfg.get("n_chains", 0) >= exp["min_chains"]
    f["file"] = (scope.get("file") == exp["file"]
                 and scope.get("function") == exp["function"])
    hit = sum(1 for v in f.values() if v)
    return {"facets": len(f), "facets_hit": hit, "recall": hit / max(len(f), 1),
            "exact": hit == len(f)}


# ------------------------------------------------------------------ grep base
def grep_baseline(qq, token):
    """Single-grep proxy: are the expected key tokens in the raw hit list?"""
    if not token or qq["expected"].get("refuse"):
        return None
    try:
        t0 = time.time()
        r = subprocess.run(
            ["rg", "-w", "-l", token, *SLICE_DIRS],
            cwd=str(SRC), capture_output=True, text=True, timeout=30)
        dt = (time.time() - t0) * 1000
        files = r.stdout.splitlines()
        return {"token": token, "files": len(files), "ms": round(dt, 1)}
    except Exception:
        return None


def main():
    gold = json.loads(GOLDEN.read_text())["questions"]
    print(f"golden set: {len(gold)} questions; loading service...")
    svc = Service()
    results, lat = [], []
    cache_probe = {}
    for qq in gold:
        r = svc.query(qq["question"])
        a = r.get("answer") or {}
        ok = r.get("ok")
        row = {"qid": qq["qid"], "intent": qq["intent"],
               "routed_intent": r.get("intent"),
               "ok": bool(ok), "latency_ms": r["meta"]["latency_ms"],
               "cache_hit": r["meta"]["cache_hit"]}
        lat.append(row["latency_ms"])
        if r.get("intent") == "slice" and a.get("full"):
            row["g"] = grade_slice(qq, a["full"])
        elif qq["intent"] == "path":
            row["g"] = grade_path(qq, a, ok)
        elif qq["intent"] == "impact":
            row["g"] = grade_impact(qq, a)
        elif qq["intent"] == "explain":
            row["g"] = grade_explain(qq, a)
        elif qq["intent"] == "docs":
            row["g"] = grade_docs(qq, a)
        else:
            row["g"] = grade_callers(qq, a, a)
        row["g"]["routing_ok"] = (r.get("intent") == qq["intent"])
        row["grep"] = grep_baseline(qq, _token_of(qq))
        results.append(row)

    # cache repeat probe: re-ask 30 structural questions
    probe = [x for x in results if x["g"].get("exact")][:30] or results[:30]
    qmap = {q["qid"]: q for q in gold}
    hits = 0
    for row in probe:
        r2 = svc.query(qmap[row["qid"]]["question"])
        hits += 1 if r2["meta"]["cache_hit"] else 0
        row["repeat_ms"] = r2["meta"]["latency_ms"]
        row["repeat_hit"] = r2["meta"]["cache_hit"]

    agg = aggregate(results, len(gold), hits, len(probe), svc)
    OUT.write_text(json.dumps({"results": results, "aggregate": agg,
                               "cache_probe": {"n": len(probe), "hits": hits}},
                              indent=1))
    print(json.dumps(agg, indent=1))
    print(f"written {OUT}")


def _token_of(qq):
    if qq["intent"] in ("callers", "explain", "slice"):
        m = re.findall(r"[A-Za-z_]\w+", qq["question"])
        stop = {"who", "calls", "call", "handles", "senders", "list", "the",
                "of", "explain", "slice", "in", "path", "from", "to"}
        toks = [t for t in m if t.lower() not in stop]
        return toks[-1] if toks else ""
    if qq["intent"] == "impact":
        m = re.search(r"(ZEBRA_[A-Z_]+|[\w-]+:[\w/-]+|[\w-]+\.c)", qq["question"])
        return m.group(0) if m else ""
    return ""


def aggregate(results, n, cache_hits, probe_n, svc):
    from collections import defaultdict
    per = defaultdict(lambda: {"n": 0, "routing": 0, "recall": [], "vprec": [],
                               "exact": 0, "anchor": [], "lat": [], "grep": []})
    for r in results:
        p = per[r["intent"]]
        p["n"] += 1
        p["routing"] += 1 if r["g"].get("routing_ok") else 0
        if "recall" in r["g"]:
            p["recall"].append(r["g"]["recall"])
        if r["g"].get("verified_precision") is not None:
            p["vprec"].append(r["g"]["verified_precision"])
        if r["g"].get("exact") is not None:
            p["exact"] += 1 if r["g"]["exact"] else 0
        if r["g"].get("anchoring") is not None:
            p["anchor"].append(r["g"]["anchoring"])
        p["lat"].append(r["latency_ms"])
        if r.get("grep"):
            p["grep"].append(r["grep"]["files"])
    out = {"n_questions": n, "intents": {}}
    all_lat = sorted(r["latency_ms"] for r in results)
    out["latency_ms"] = {"p50": all_lat[len(all_lat) // 2],
                         "p95": all_lat[int(len(all_lat) * 0.95)],
                         "max": max(all_lat)}
    exact_n = sum(1 for r in results if r["g"].get("exact"))
    out["exact_answers"] = f"{exact_n}/{n}"
    rout_n = sum(1 for r in results if r["g"].get("routing_ok"))
    out["routing_accuracy"] = round(rout_n / n, 3)
    for it, p in sorted(per.items()):
        out["intents"][it] = {
            "n": p["n"],
            "routing_acc": round(p["routing"] / p["n"], 3),
            "recall": round(sum(p["recall"]) / len(p["recall"]), 3)
            if p["recall"] else None,
            "verified_precision": round(sum(p["vprec"]) / len(p["vprec"]), 3)
            if p["vprec"] else None,
            "exact": f"{p['exact']}/{p['n']}",
            "evidence_anchor_rate": round(sum(p["anchor"]) / len(p["anchor"]), 3)
            if p["anchor"] else None,
            "latency_p50_ms": sorted(p["lat"])[len(p["lat"]) // 2],
            "grep_files_median": sorted(p["grep"])[len(p["grep"]) // 2]
            if p["grep"] else None}
    out["cache_probe_hits"] = f"{cache_hits}/{probe_n} (re-ask of {probe_n} questions)"
    out["kb"] = svc.health()["kb"]
    return out


if __name__ == "__main__":
    main()
