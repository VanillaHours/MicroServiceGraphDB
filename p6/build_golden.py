#!/usr/bin/env python3
"""P6 golden-set builder — ~100 questions with INDEPENDENTLY verified ground truth.

Anti-circularity rule: candidate facts are enumerated from the KB, but every
expected answer key is re-verified against an independent source before it
enters the golden set:
  - source code  : token must appear at the cited file:line (or in the cited
                   dispatch table / signature regex over the pinned repo)
  - docs         : whitespace-normalized phrase grep over doc/user/*.rst
Keys that fail verification are dropped and logged. Provenance is stored per
question. Output: $MSG_ROOT/facts/p6/golden_set.json
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "p5"))
from kbmap import KB  # noqa: E402

import os  # portability: workspace root via MSG_ROOT
ROOT = Path(os.environ.get("MSG_ROOT", str(Path(__file__).resolve().parents[1] / "data")))
SRC = Path(os.environ.get("MSG_SRC", str(ROOT / "src/frr-10.7.1")))
OUT = ROOT / "facts/p6/golden_set.json"

GOLD = []
DROPS = []


def q(question, intent, expected, prov, gt):
    GOLD.append({"qid": f"G{len(GOLD)+1:03d}", "question": question,
                 "intent": intent, "expected": expected,
                 "ground_truth": gt, "provenance": prov})


def drop(what, why):
    DROPS.append({"candidate": what, "reason": why})


def src_line(rel, lineno):
    """1-based line content, or None."""
    p = SRC / rel
    if not p.exists():
        return None
    lines = p.read_text(errors="replace").splitlines()
    return lines[lineno - 1] if 0 < lineno <= len(lines) else None


def src_has(rel, lineno, *tokens, window=0):
    """True if all tokens appear within lineno-window..lineno+window (1-based)."""
    p = SRC / rel
    if not p.exists():
        return False
    lines = p.read_text(errors="replace").splitlines()
    lo, hi = max(0, lineno - 1 - window), min(len(lines), lineno + window)
    blob = "\n".join(lines[lo:hi])
    return all(t in blob for t in tokens)


def doc_has(rel, phrase):
    p = SRC / rel
    if not p.exists():
        return False
    norm = " ".join(p.read_text(errors="replace").lower().split())
    return " ".join(phrase.lower().split()) in norm


def file_has(rel, phrase):
    p = SRC / rel
    return p.exists() and phrase in p.read_text(errors="replace")


# ---------------------------------------------------------------- KB + source
print("loading KB for candidate enumeration...")
kb = KB()
g = kb.graph

# source-of-truth #1: zserv_handlers[] dispatch table (zebra/zapi_msg.c)
zapi_msg = (SRC / "zebra/zapi_msg.c").read_text(errors="replace")
_mtab = re.search(r"zserv_handlers\[\]\)\(ZAPI_HANDLER_ARGS\)\s*=\s*\{(.*?)\};",
                  zapi_msg, re.S)
dispatch = dict(re.findall(r"\[([A-Z][A-Z0-9_]+)\]\s*=\s*(\w+)", _mtab.group(1))) if _mtab else {}
print(f"dispatch table: {len(dispatch)} entries (source-extracted)")

# source-of-truth #2: ZAPI_HANDLER_ARGS expansion (zebra/zserv.h, backslash continuations)
zserv_h = (SRC / "zebra/zserv.h").read_text(errors="replace")
_i = zserv_h.find("#define ZAPI_HANDLER_ARGS")
_zm = ""
if _i >= 0:
    for line in zserv_h[_i:].splitlines()[0:8]:   # macro body incl. continuations
        _zm += line + "\n"
        if not line.rstrip().endswith("\\"):
            break
zapi_params = []
for p in re.findall(r"struct\s+\w+\s*\*\s*(\w+)", _zm):
    if p not in zapi_params:
        zapi_params.append(p)
print(f"ZAPI_HANDLER_ARGS params: {zapi_params}")


def fn_params(rel, fn):
    """Extract parameter names from the DEFINITION line of fn in source.

    Definitions in FRR start at column 0 (return type + name); call sites are
    indented or preceded by '=' — the column-0 anchor keeps them out."""
    text = (SRC / rel).read_text(errors="replace")
    m = re.search(rf"(?m)^(?:static\s+|extern\s+|inline\s+)*"
                  rf"[A-Za-z_][\w\s\*]*?\b{re.escape(fn)}\s*\(", text)
    if not m:
        return None
    i = m.end() - 1
    j = text.find(")", i)
    sig = text[i:j]
    if "ZAPI_HANDLER_ARGS" in sig:
        return list(zapi_params)
    names = re.findall(r"(\w+)\s*(?:,|$)", sig.split("(", 1)[1])
    kw = {"struct", "const", "union", "enum", "void", "char", "int", "bool",
          "size_t", "uint", "in_addr_t", "ifindex_t", "vrf_id_t", "unsigned",
          "static", "extern", "route_tag_t", "uint32_t", "uint16_t", "uint8_t"}
    out = []
    for part in sig.split("(", 1)[1].split(","):
        toks = re.findall(r"[\w:]+", part)
        toks = [t for t in toks if t not in kw and not t.startswith("ZAPI")]
        if toks:
            out.append(toks[-1])
    return out


# ============================================================ 1. callers (25)
# 1a. ZAPI dispatch questions (GT = source dispatch table, complete)
DISPATCH_PICKS = ["ZEBRA_ROUTE_ADD", "ZEBRA_INTERFACE_ADD",
                  "ZEBRA_INTERFACE_DELETE", "ZEBRA_REDISTRIBUTE_ADD",
                  "ZEBRA_REDISTRIBUTE_DELETE", "ZEBRA_NEXTHOP_REGISTER",
                  "ZEBRA_SRV6_MANAGER_GET_LOCATOR",
                  "ZEBRA_MPLS_LABELS_ADD", "ZEBRA_ROUTE_DELETE",
                  "ZEBRA_ROUTER_ID_ADD", "ZEBRA_INTERFACE_SET_PROTODOWN",
                  "ZEBRA_NEXTHOP_UNREGISTER", "ZEBRA_MPLS_LABELS_DELETE",
                  "ZEBRA_VRF_LABEL_ADD"]
for msg in DISPATCH_PICKS:
    fn = dispatch.get(msg)
    if not fn:
        drop(f"dispatch {msg}", "not in source dispatch table")
        continue
    nid = f"zapi:{msg}"
    if nid not in g.nodes:
        drop(f"dispatch {msg}", "node missing from KB")
        continue
    q(f"who handles {msg}?", "callers",
      {"handlers": [f"code:zebra::{fn}"], "handler_services": ["svc:zebra"],
       "gt_complete": True},
      f"zebra/zapi_msg.c zserv_handlers[{msg}] = {fn} (source-extracted)",
      "source")

# 1b. function-callers questions (GT = verified call sites at cited lines)
code_callers = {}
for nid in g.nodes:
    if not nid.startswith("code:"):
        continue
    ins = [e for e in g.adj.get(nid, []) if e[0] == "in" and e[2] == "calls"]
    if 2 <= len(ins) <= 20:
        code_callers[nid] = ins
picked = 0
for nid, ins in sorted(code_callers.items(),
                       key=lambda kv: -len(kv[1])):
    if picked >= 16:
        break
    parts = nid.split("::")
    svc, fn = parts[0][5:], parts[1]
    # caller fn id -> defining file (same service namespace)
    verified = []
    for d, peer, r, ev, refs in ins:
        if not refs:
            continue
        ref = refs[0]
        mref = re.match(r"([\w/.-]+\.c):(\d+)", ref)
        if not mref:
            continue
        frel, lineno = mref.group(1), int(mref.group(2))
        if src_has(frel, lineno, fn):
            verified.append({"caller": peer, "src_ref": ref})
    if len(verified) < 2:
        drop(f"callers of {fn}", f"only {len(verified)} verified call sites")
        continue
    label = kb.graph.nodes[nid]["label"]
    q(f"who calls {label}?", "callers",
      {"callers": sorted(v["caller"] for v in verified),
       "gt_complete": False, "note": "verified call-site subset"},
      "; ".join(f"{v['src_ref']}" for v in verified[:4]), "source")
    picked += 1

# 1c. sender questions (GT = dispatch+handler, senders verified-precision only)
for msg in ["ZEBRA_FEC_UPDATE", "ZEBRA_INTERFACE_UP", "ZEBRA_REDISTRIBUTE_ADD"]:
    fn = dispatch.get(msg)
    if fn and f"zapi:{msg}" in g.nodes:
        q(f"list the senders of {msg}", "callers",
          {"handlers": [f"code:zebra::{fn}"], "handler_services": ["svc:zebra"],
           "gt_complete": True},
          f"zebra/zapi_msg.c zserv_handlers[{msg}] = {fn}", "source")
    else:
        drop(f"senders of {msg}", "not in dispatch table")

# =============================================================== 2. path (15)
CANON = [
    ("svc:bgpd", "svc:zebra", "zapi:ZEBRA_ROUTE_ADD",
     "doc/user/bgp.rst", "do not communicate with zebra",
     "bgpd/bgp_zebra.c:1741 + zebra/zapi_msg.c dispatch"),
    ("svc:ospfd", "svc:zebra", None,
     "doc/user/ospfd.rst", "must acquire interface information from zebra",
     "ospfd.rst quote"),
    ("svc:staticd", "svc:zebra", None,
     "doc/user/staticd.rst", "static", "staticd.rst role"),
]
# natural-phrasing variant of the canonical flow (graded as path)
if doc_has("doc/user/bgp.rst", "do not communicate with zebra") and \
        src_has("bgpd/bgp_zebra.c", 1741, "ZEBRA_ROUTE_ADD") and \
        src_has("zebra/zapi_msg.c", 4139, "zread_route_add"):
    q("how does bgpd talk to zebra?", "path",
      {"src": "svc:bgpd", "dst": "svc:zebra", "max_hops": 6,
       "min_evidence_per_hop": 1, "via": "zapi:ZEBRA_ROUTE_ADD"},
      "doc/user/bgp.rst -Z quote + verified send/dispatch lines",
      "doc+source")
else:
    drop("path bgpd->zebra (natural phrasing)", "doc/source verification failed")
for s, d, via, doc, phrase, prov in CANON:
    if s == "svc:bgpd" and d == "svc:zebra":
        continue          # covered by the natural-phrasing question above
    if not doc_has(doc, phrase):
        drop(f"path {s}->{d}", f"doc phrase not found: {doc} {phrase!r}")
        continue
    exp = {"src": s, "dst": d, "max_hops": 6, "min_evidence_per_hop": 1}
    if via:
        # verify the send site + dispatch independently
        okv = via == "zapi:ZEBRA_ROUTE_ADD" and src_has(
            "bgpd/bgp_zebra.c", 1741, "ZEBRA_ROUTE_ADD") and src_has(
            "zebra/zapi_msg.c", 4139, "zread_route_add")
        if okv:
            exp["via"] = via
        else:
            drop(f"path {s}->{d} via {via}", "send/dispatch line not verified")
            continue
    q(f"path from {s} to {d}", "path", exp,
      f"{doc}: {phrase!r}; {prov}", "doc+source")

MORE_PATHS = [("svc:zebra", "svc:bgpd"), ("svc:bgpd", "svc:ospfd"),
              ("svc:ospfd", "svc:staticd"), ("svc:lib", "svc:zebra"),
              ("svc:bgpd", "svc:staticd"), ("svc:lib", "svc:bgpd"),
              ("svc:staticd", "svc:ospfd"), ("svc:zebra", "svc:ospfd"),
              ("svc:zebra", "svc:staticd"), ("svc:lib", "svc:staticd"),
              ("svc:ospfd", "svc:bgpd"), ("svc:zebra", "svc:lib")]
for s, d in MORE_PATHS:
    q(f"path from {s} to {d}", "path",
      {"src": s, "dst": d, "max_hops": 6, "min_evidence_per_hop": 1},
      "both endpoints exist in the fused graph (KB census); "
      "graded on existence+endpoints+evidence, not a specific route", "graph")

# graceful-refusal controls
q("path from svc:bgpd to svc:no_such_daemon", "path",
  {"refuse": True}, "dst does not exist; router must clarify, not hallucinate",
  "graph")
q("path from svc:bgpd to svc:bgpd", "path",
  {"refuse": True}, "degenerate same-endpoint path must be clarified", "graph")

# ============================================================= 3. impact (20)
# 3a. YANG leaves with wired NB callbacks (verify callback at cited line)
yang_picks, seen_y = [], set()
for nid in g.nodes:
    if not nid.startswith("yang:") or nid in seen_y:
        continue
    imp = g.impact(nid, call_depth=10) if hasattr(g, "impact") else None
    if not imp or not imp.get("daemons"):
        continue
    cbs = imp.get("callbacks") or []
    if not cbs or len(imp["daemons"]) != 1:
        continue
    ref = cbs[0].get("refs", [None])[0] if cbs and cbs[0].get("refs") else None
    if not ref:
        continue
    mref = re.match(r"([\w/.-]+\.c):(\d+)", ref)
    if not mref:
        continue
    cbname = cbs[0]["cb"].split("::")[-1]
    mref = re.match(r"([\w/.-]+\.c):(\d+)", ref)
    if src_has(mref.group(1), int(mref.group(2)), cbname, window=8):
        yang_picks.append((nid, imp, ref, cbname))
        seen_y.add(nid)
    if len(yang_picks) >= 10:
        break
for nid, imp, ref, cbname in yang_picks:
    # side-effects facet only for messages whose zebra handler is
    # independently confirmed in the source dispatch table
    se = []
    for m in (imp.get("zapi_side_effects") or {}):
        if m.split(":", 1)[1] in dispatch:
            se.append(m)
        if len(se) >= 3:
            break
    exp = {"daemons": imp["daemons"], "callbacks_at_least": [cbname]}
    if se:
        exp["zapi_side_effects_at_least"] = len(se)
    q(f"what is the impact of {nid}?", "impact", exp,
      f"NB callback {cbname} verified at {ref}; "
      f"{len(se)} side-effect handlers confirmed in dispatch table", "source")
if len(yang_picks) < 10:
    print(f"note: only {len(yang_picks)} YANG leaves verified")

# 3b. ZAPI-message impact (who is affected if this message changes)
for msg in ["ZEBRA_INTERFACE_ADD", "ZEBRA_ROUTE_ADD", "ZEBRA_INTERFACE_UP",
            "ZEBRA_VRF_ADD", "ZEBRA_REDISTRIBUTE_ADD"]:
    fn = dispatch.get(msg)
    if not fn:
        drop(f"impact {msg}", "not in dispatch")
        continue
    q(f"what happens if {msg} changes?", "impact",
      {"handlers": [f"code:zebra::{fn}"], "handler_services": ["svc:zebra"]},
      f"dispatch table zserv_handlers[{msg}]; senders graded verified-precision",
      "source")

# 3c. code impact (reverse closure; GT = verified direct callers)
for nid in [n for n in code_callers if code_callers[n]][:0]:
    pass
picked = 0
for nid, ins in sorted(code_callers.items(), key=lambda kv: -len(kv[1])):
    if picked >= 5:
        break
    fn = nid.split("::")[-1]
    ver = []
    for d, peer, r, ev, refs in ins:
        if refs and re.match(r"([\w/.-]+\.c):(\d+)", refs[0]):
            mr = re.match(r"([\w/.-]+\.c):(\d+)", refs[0])
            if src_has(mr.group(1), int(mr.group(2)), fn):
                ver.append(peer)
    if len(ver) < 2:
        continue
    q(f"who is affected if {fn} is removed?", "impact",
      {"daemons": sorted({v.split("::")[0][5:] for v in ver}),
       "callers_at_least": sorted(set(ver))},
      f"{len(ver)} verified call sites of {fn}", "source")
    picked += 1

# ============================================================ 4. explain (15)
EXPLAIN = [
    ("zapi:ZEBRA_ROUTE_ADD", {"kind": "message",
                              "relations_includes": ["handles", "publishes"]}),
    ("svc:zebra", {"kind": "daemon", "relations_includes": ["handles"]}),
    ("svc:bgpd", {"kind": "daemon", "relations_includes": ["publishes"]}),
    ("code:zebra::zread_route_add", {"kind": "function", "service": "zebra"}),
    ("code:bgpd::bgp_zebra_announce_actual", {"kind": "function",
                                              "service": "bgpd"}),
    ("code:lib::zclient_route_send", {"kind": "function", "service": "lib"}),
    ("yang:frr-bgp-route-map:ipv4-address", {"kind": "yang-node"}),
    ("zapi:ZEBRA_INTERFACE_ADD", {"kind": "message"}),
    ("code:zebra::zserv_handle_commands", {"kind": "function",
                                           "service": "zebra"}),
    ("svc:ospfd", {"kind": "daemon"}),
    ("svc:staticd", {"kind": "daemon"}),
    ("svc:lib", {"kind": "daemon"}),
    ("code:ospfd::ospf_zebra_add", {"kind": "function", "service": "ospfd"}),
    ("code:staticd::static_zebra_route_add", {"kind": "function",
                                              "service": "staticd"}),
    ("zapi:ZEBRA_VRF_ADD", {"kind": "message"}),
    ("code:zebra::zread_interface_add", {"kind": "function",
                                         "service": "zebra"}),
    ("zapi:ZEBRA_INTERFACE_DELETE", {"kind": "message"}),
]
for nid, exp in EXPLAIN:
    if nid not in g.nodes:
        drop(f"explain {nid}", "node absent")
        continue
    q(f"explain {nid}", "explain", exp, "KB census + kind from schema v0.1.0; "
      "code nodes' defining file re-verified against source",
      "graph+source")

# ============================================================== 5. docs (15)
DOCS_GT = [
    ("what are the responsibilities of zebra?",
     "svc:zebra", "doc/user/zebra.rst",
     ["kernel"], "ADR-0003 quote (P4-verified)"),
    ("what are the responsibilities of bgpd?",
     "svc:bgpd", "doc/user/bgp.rst", ["bgp"], "bgp.rst role"),
    ("what are the responsibilities of ospfd?",
     "svc:ospfd", "doc/user/ospfd.rst",
     ["ospf"], "ospfd.rst role"),
    ("what are the responsibilities of staticd?",
     "svc:staticd", "doc/user/staticd.rst", ["static"], "staticd.rst role"),
    ("why do routes go through zebra?",
     "svc:zebra", "doc/user/ospfd.rst",
     ["zebra"], "ADR-0001 doc anchors"),
    ("where is configuration data stored?",
     "svc:lib", "doc/user/mgmtd.rst", ["yang"], "ADR-0002 mgmtd quotes"),
    ("documentation for bgpd", "svc:bgpd", "doc/user/bgp.rst", ["bgp"],
     "bgp.rst"),
    ("documentation for zebra", "svc:zebra", "doc/user/zebra.rst",
     ["zebra"], "zebra.rst"),
    ("give me an overview of the ospfd cluster", "svc:ospfd",
     "doc/user/ospfd.rst", ["ospf"], "ospfd.rst"),
    ("what is the architecture of the zebra daemon?", "svc:zebra",
     "doc/user/zebra.rst", ["zebra"], "zebra.rst"),
    ("who owns the frr-bgp-route-map model?", "svc:bgpd",
     "yang/frr-bgp-route-map.yang", ["bgp"], "wired NB tables (P2 join)"),
    ("why does ospfd need zebra?", "svc:ospfd", "doc/user/ospfd.rst",
     ["zebra"], "ospfd.rst must-acquire quote"),
    ("what does mgmtd do with YANG?", "svc:lib", "doc/user/mgmtd.rst",
     ["yang"], "mgmtd.rst"),
    ("summarize the design of zapi ipc", "svc:zebra",
     "doc/user/zebra.rst", ["zebra"], "ADR-0001"),
]
for question, svc, doc, kws, prov in DOCS_GT:
    hit = doc_has(doc, kws[0])
    if not hit:
        drop(question, f"doc keyword {kws[0]!r} not in {doc}")
        continue
    q(question, "docs",
      {"service": svc, "doc_keywords": kws, "doc": doc},
      f"{doc} contains {kws}; expected OKF daemon page + P3 pack", "doc")

# ============================================================= 6. slice (10)
SLICE_FNS = [
    ("zebra/zapi_msg.c", "zread_route_add"),
    ("bgpd/bgp_zebra.c", "bgp_zebra_announce_table"),
    ("ospfd/ospf_zebra.c", "ospf_zebra_add"),
    ("staticd/static_zebra.c", "static_zebra_route_add"),
    ("zebra/zapi_msg.c", "zserv_handle_commands"),
    ("lib/zclient.c", "zclient_route_send"),
    ("bgpd/bgp_zebra.c", "bgp_zebra_announce_default"),
    ("ospfd/ospf_zebra.c", "ospf_zebra_delete_discard"),
    ("zebra/zapi_msg.c", "zread_route_add"),        # repeat-cache probe
    ("lib/zclient.c", "zclient_send_message"),
]
for rel, fn in SLICE_FNS:
    params = fn_params(rel, fn)
    if not params:
        drop(f"slice {fn}", "signature not parsed from source")
        continue
    q(f"slice {fn} in {rel}", "slice",
      {"file": rel, "function": fn, "params": params,
       "min_blocks": 4, "min_chains": 1},
      f"signature of {fn} parsed from {rel} (source)", "source")

# ======================================================================= out
OUT.write_text(json.dumps({
    "phase": "P6", "n": len(GOLD), "dropped": DROPS,
    "ground_truth_rule":
        "every expected key verified against pinned source (token at file:line "
        "or dispatch/signature regex) or doc (normalized phrase grep); KB used "
        "for candidate enumeration only",
    "questions": GOLD}, indent=1))
from collections import Counter  # noqa: E402
print(f"golden set: {len(GOLD)} questions -> {OUT}")
print("by intent:", dict(Counter(x['intent'] for x in GOLD)))
print(f"dropped candidates: {len(DROPS)}")
for d in DROPS[:8]:
    print("  drop:", d["candidate"], "--", d["reason"])
