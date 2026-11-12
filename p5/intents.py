#!/usr/bin/env python3
"""P5 intent backends — impact / path / explain / callers / docs.

Every answer carries evidence (rel + peer + tag:plane + src_ref) drawn from the
fused graph; docs answers additionally anchor to P3 pack files (sha256 from the
P4 manifest) and P4 OKF pages. No answer without an anchor.
"""
import json
import re
from collections import defaultdict

EVID_CAP = 40


def _ev(edges, cap=EVID_CAP):
    """Compress adjacency rows into evidence items."""
    out = []
    for d, o, r, ev, refs in edges[:cap]:
        out.append({"rel": r, "dir": d, "peer": o,
                    "evidence": ev[:3],
                    "src_ref": (refs[0] if refs else None)})
    return out


def _svc_of(kb, nid):
    if nid.startswith("svc:"):
        return nid                                  # daemon nodes ARE services
    return kb.graph.nodes.get(nid, {}).get("service")


# --------------------------------------------------------------- impact
def run_impact(kb, ids, call_depth=10):
    nid = ids[0]
    g = kb.graph
    if nid.startswith("zapi:"):
        # P6 eval-driven mode: "what happens if message M changes" =
        # who sends M, who handles M, which services are on either side
        handlers, senders, ev = [], [], []
        for d, o, r, e, refs in g.adj.get(nid, []):
            if r == "handles" and d == "in":
                handlers.append({"node": o, "service": _svc_of(kb, o),
                                 "src_ref": refs[0] if refs else None})
                ev.append({"rel": r, "dir": d, "peer": o, "evidence": e[:2],
                           "src_ref": refs[0] if refs else None})
            elif r == "publishes" and d == "in":
                senders.append({"node": o, "service": _svc_of(kb, o),
                                "src_ref": refs[0] if refs else None})
                ev.append({"rel": r, "dir": d, "peer": o, "evidence": e[:2],
                           "src_ref": refs[0] if refs else None})
        svcs = sorted({(x["service"] or "") for x in handlers + senders} - {""})
        return {"intent": "impact", "target": nid, "mode": "zapi-change",
                "handlers": handlers, "senders": senders,
                "daemons_affected": svcs,
                "handler_services": sorted({x["service"] for x in handlers
                                            if x["service"]}),
                "sender_services": sorted({x["service"] for x in senders
                                           if x["service"]}),
                "evidence": ev}
    if nid.startswith("yang:"):
        memo_key = (nid, call_depth)
        cached = kb._impact_memo.get(memo_key)
        if cached is not None:
            out = json.loads(json.dumps(cached))
            out["memoized"] = True
            return out
        res = g.impact(nid, call_depth=call_depth)
        ev = []
        # anchor: nb entry implements the (family) yang node
        for e in res["nb_entries"][:8]:
            for d, o, r, ee, refs in g.adj.get(e["nb"], []):
                if r == "implements" and o == e["via"]:
                    ev.append({"rel": "implements", "peer": e["nb"],
                               "evidence": ee[:2],
                               "src_ref": refs[0] if refs else None})
        # anchor: nb entry dispatches to a code callback
        for c in res["callbacks"][:8]:
            ev.append({"rel": "handles", "peer": c["cb"],
                       "evidence": ["DECLARED:wiring"],
                       "src_ref": c["refs"][0] if c["refs"] else None})
        out = {"intent": "impact", "target": nid, "mode": "yang-leaf",
               "family_size": res["family_size"],
               "nb_entries": [e["nb"] for e in res["nb_entries"]],
               "callbacks": [c["cb"] for c in res["callbacks"]],
               "daemons": res["daemons"],
               "zapi_side_effects": {m: v["handled_by"]
                                     for m, v in res["zapi_side_effects"].items()},
               "memoized": False,
               "evidence": ev}
        kb._impact_memo[memo_key] = json.loads(json.dumps(out))
        return out
    # generic reverse-dependency closure for code / svc / zapi targets
    dep, seen = [], {nid}
    frontier = [(nid, 0)]
    while frontier:
        cur, depth = frontier.pop(0)
        if depth >= call_depth:
            continue
        for d, o, r, _ev_, _rf in g.adj.get(cur, []):
            if d != "in" or r != "calls":
                continue
            if o not in seen and o.startswith("code:"):
                seen.add(o)
                dep.append({"caller": o, "via": cur, "depth": depth + 1})
                frontier.append((o, depth + 1))
                if len(dep) >= 300:
                    break
    # side effects: messages this code publishes and their handler services
    msgs = {}
    for d, o, r, _e, refs in g.adj.get(nid, []):
        if d == "out" and r == "publishes" and o.startswith("zapi:"):
            hnd = [x for dd, x, rr, _e2, _r2 in g.adj.get(o, [])
                   if rr == "handles" and x.startswith("svc:")]
            msgs[o] = {"handled_by": hnd,
                       "src_ref": refs[0] if refs else None}
    daemons = sorted({_svc_of(kb, nid) or "", *(_svc_of(kb, d["caller"]) or ""
                                            for d in dep),
                      *(s for m in msgs.values() for s in m["handled_by"])} - {""})
    ev = _ev([e for e in g.adj.get(nid, []) if e[2] in ("calls", "publishes")])
    return {"intent": "impact", "target": nid, "mode": "reverse-closure",
            "direct_callers": [d["caller"] for d in dep if d["depth"] == 1],
            "transitive_callers": len(dep),
            "daemons_affected": daemons,
            "zapi_side_effects": msgs,
            "evidence": ev}


# --------------------------------------------------------------- path
def _adj(g, nid):
    return g.adj.get(nid, [])


def _zapi_flow_path(kb, s, d):
    """Preferred 2-hop pattern: s -publishes-> msg <-handles- d (request) or
    s -handles-> msg <-publishes- d (notification). Returns hop list or None.
    Deterministic: lexicographically first common message, ROUTE-ish first."""
    g = kb.graph
    for rel_out, rel_in in (("publishes", "handles"), ("handles", "publishes")):
        common = []
        for _dd, o, r, _e, _rf in _adj(g, s):
            if r != rel_out or not o.startswith("zapi:"):
                continue
            if any(dd == "in" and peer == d and rr == rel_in
                   for dd, peer, rr, _e2, _r2 in _adj(g, o)):
                common.append(o)
        if common:
            common.sort(key=lambda m: (0 if "ROUTE" in m else 1, m))
            msg = common[0]
            hops = []
            for frm, rel, mid in ((s, rel_out, msg),):
                for dd, o, r, ev, refs in _adj(g, frm):
                    if r == rel and o == mid:
                        hops.append({"from": frm, "to": mid, "dir": "out",
                                     "rel": rel, "evidence": ev, "refs": refs})
                        break
            for dd, o, r, ev, refs in _adj(g, msg):
                if r == rel_in and o == d:
                    hops.append({"from": msg, "to": d, "dir": "in",
                                 "rel": rel_in, "evidence": ev, "refs": refs})
                    break
            return hops, msg
    return None, None


def run_path(kb, src_ids, dst_ids, max_hops=8):
    g = kb.graph
    # 1. preferred direct ZAPI flow (evidence-dense, 2 hops)
    for s in src_ids:
        for d in dst_ids:
            hops, msg = _zapi_flow_path(kb, s, d)
            if hops:
                ev = [{"hop": i + 1, "rel": h["rel"], "dir": h["dir"],
                       "evidence": h["evidence"],
                       "src_ref": (h["refs"][0] if h["refs"] else None)}
                      for i, h in enumerate(hops)]
                return {"intent": "path", "src": s, "dst": d, "via": msg,
                        "hops": len(hops),
                        "path": [{"from": h["from"], "to": h["to"],
                                  "rel": h["rel"], "dir": h["dir"]}
                                 for h in hops],
                        "evidence": ev}
    # 2. generic BFS fallback over all pairs
    best = None
    tried = []
    for s in src_ids:
        for d in dst_ids:
            hops = g.path(s, d, max_hops=max_hops)
            tried.append([s, d])
            if hops is not None and (best is None or len(hops) < len(best[1])):
                best = ([s, d], hops)
    if best is None:
        return {"intent": "path", "src": src_ids, "dst": dst_ids,
                "error": f"no path within {max_hops} hops",
                "pairs_tried": tried[:6], "evidence": []}
    [s, d], hops = best
    ev = [{"hop": i + 1, "rel": h["rel"], "dir": h["dir"], "evidence": h["evidence"],
           "src_ref": (h["refs"][0] if h["refs"] else None)}
          for i, h in enumerate(hops)]
    return {"intent": "path", "src": s, "dst": d, "hops": len(hops),
            "path": [{"from": h["from"], "to": h["to"], "rel": h["rel"],
                      "dir": h["dir"]} for h in hops],
            "evidence": ev}


# --------------------------------------------------------------- explain
def run_explain(kb, ids):
    nid = ids[0]
    g = kb.graph
    grouped = defaultdict(lambda: {"count": 0, "peers": []})
    for d, o, r, ev, refs in g.adj.get(nid, []):
        grp = grouped[r]
        grp["count"] += 1
        if len(grp["peers"]) < 12:
            grp["peers"].append({"dir": d, "peer": o,
                                 "evidence": ev[:2],
                                 "src_ref": refs[0] if refs else None})
    return {"intent": "explain", "target": nid,
            "node": {"kind": g.nodes[nid]["kind"], "label": g.nodes[nid]["label"],
                     "service": g.nodes[nid]["service"]},
            "clusters": kb.clusters_of(nid),
            "domain": kb.domain_of(nid),
            "relations": {k: v for k, v in sorted(grouped.items())}}


# --------------------------------------------------------------- callers
def run_callers(kb, ids):
    nid = ids[0]
    g = kb.graph
    out = {"intent": "callers", "target": nid, "mode": nid.split(":")[0]}
    ev = []

    def scan(rel_wanted, direction):
        rows = []
        for d, o, r, e, refs in g.adj.get(nid, []):
            if d == direction and r == rel_wanted:
                rows.append({"node": o, "service": _svc_of(kb, o),
                             "src_ref": refs[0] if refs else None})
                if refs:
                    ev.append({"rel": r, "dir": d, "peer": o, "evidence": e[:2],
                               "src_ref": refs[0] if refs else None})
        return rows

    if nid.startswith("code:"):
        out["callers"] = scan("calls", "in")
        handlers = scan("handles", "out")            # zapi msgs this fn serves
        out["serves_messages"] = [h["node"] for h in handlers]
        senders = {}
        for h in handlers:
            for d, o, r, e, refs in g.adj.get(h["node"], []):
                if d == "in" and r == "publishes":
                    senders.setdefault(h["node"], set()).add(o)
        out["messages_from"] = {m: sorted(s) for m, s in senders.items()}
        out["nb_paths_served"] = [h["node"] for h in scan("handles", "in")
                                  if h["node"].startswith("nb:")]
    elif nid.startswith("zapi:"):
        out["senders"] = scan("publishes", "in")
        out["handlers"] = scan("handles", "in")
        out["sender_services"] = sorted({s["service"] for s in out["senders"]
                                         if s["service"]})
        out["handler_services"] = sorted({s["service"] for s in out["handlers"]
                                          if s["service"]})
    elif nid.startswith("svc:"):
        msgs = scan("handles", "out")
        out["handles_messages"] = [m["node"] for m in msgs]
        pub = scan("publishes", "out")
        out["publishes_messages"] = [m["node"] for m in pub]
        peers = set()
        for m in msgs + pub:
            for d, o, r, e, refs in g.adj.get(m["node"], []):
                if o.startswith("svc:") and o != nid and r in ("handles", "publishes"):
                    peers.add(o)
        out["zapi_peers"] = sorted(peers)
    elif nid.startswith("nb:"):
        out["callbacks"] = scan("handles", "out")
        out["registered_by"] = scan("registers", "in")
    else:
        out["note"] = "callers is defined for code:/zapi:/svc:/nb: entities"
        out["related"] = _ev(g.adj.get(nid, []))
    out["evidence"] = ev
    return out


# --------------------------------------------------------------- docs
_MD_HEAD = re.compile(r"^#{1,3} ", re.M)
_DOCS_STOP = {"what", "does", "where", "is", "the", "how",
              "why", "summarize", "with", "for", "and", "about"}


def _docs_adr_scan(kb, question):
    """Entity-less docs fallback: keyword scan over the P4 ADR pages."""
    toks = [t for t in re.findall(r"[a-z0-9_-]{3,}", question.lower())
            if t not in _DOCS_STOP]
    out = {"intent": "docs", "target": None, "mode": "adr-scan",
           "clusters": [], "pack": None, "okf_pages": [], "adrs": [],
           "evidence": []}
    if not toks or not kb.okf_dir.exists():
        return out
    for p in sorted((kb.okf_dir / "adrs").glob("ADR-*.md")):
        try:
            t = p.read_text()
        except OSError:
            continue
        low = p.name.lower() + " " + t.lower()
        hits = [tok for tok in toks if tok in low]
        if hits:
            out["adrs"].append({"adr": p.name, "matched": hits,
                                "excerpt": t[:400]})
            out["evidence"].append({"source": str(p), "type": "P4 OKF ADR",
                                    "matched": hits})
    return out


def run_docs(kb, mentions, question=""):
    """Documentation answer: P3 packs + cluster profiles + P4 OKF pages.

    P6 addition: entity-less questions (no linked mention) fall back to an
    ADR keyword scan over the P4 bundle — the no-anchor rule still holds
    (every hit is a bundle page with its own anchors)."""
    # pick the most structured entity for doc lookup
    prio = {"svc": 0, "yang": 1, "zapi": 2, "yang-module": 3, "code": 4}
    m = min(mentions, key=lambda x: prio.get(x.kind, 9)) if mentions else None
    if m is None:
        return _docs_adr_scan(kb, question)
    nid = m.ids[0]
    out = {"intent": "docs", "target": nid, "clusters": [], "pack": None,
           "okf_pages": [], "adrs": [], "evidence": []}

    for c in kb.clusters_of(nid) or ():
        prof = kb.profiles.get(c["id"], {})
        out["clusters"].append({
            "id": c["id"], "level": c["level"], "label": c["label"],
            "roles": prof.get("roles", []),
            "functionality": prof.get("functionality", [])[:3],
            "yang_modules": prof.get("yang_modules", {}),
            "zapi_msgs": prof.get("zapi_msgs", [])[:12],
        })

    dom = kb.domain_of(nid)
    if dom:
        pj = kb.packs_dir / f"{dom}.json"
        pmd = kb.packs_dir / f"{dom}.md"
        prof = kb.profiles.get(dom, {})
        pack = {"id": dom, "label": prof.get("label", kb.cluster_by_id[dom]["label"]),
                "functionality": prof.get("functionality", []),
                "roles": prof.get("roles", []),
                "boundary_edges": prof.get("boundary_edges", []),
                "md": str(pmd), "sha256": kb.okf_manifest.get(
                    "inputs_sha256", {}).get(f"p3/packs/{dom}.json")}
        out["pack"] = pack
        out["evidence"].append({"source": str(pmd), "type": "P3 domain pack",
                                "sha256": pack["sha256"]})

    # OKF bundle pages: daemon pages for svc, cluster pages for cluster ids,
    # ADR keyword scan
    cluster_ids = {c["id"] for c in kb.clusters_of(nid)} | ({dom} if dom else set())
    svc_name = nid.split(":")[1] if nid.startswith("svc:") else None
    for page_id, meta in kb.okf_manifest.get("pages", {}).items():
        real_id = meta.get("page_id", f"{page_id}.md")
        text = None
        try:
            text = (kb.okf_dir / real_id).read_text()
        except OSError:
            continue
        if svc_name:
            hit = real_id.endswith(f"daemons/{svc_name}.md")
        else:
            tok = nid.split(":")[-1].split("/")[-1].lower()
            hit = tok in text.lower()
        if not hit:
            continue
        out["okf_pages"].append({"page": page_id, "okf_level": meta.get("okf_level"),
                                 "atoms": meta.get("atoms"),
                                 "excerpt": text[:600]})
        if len(out["okf_pages"]) >= 3:
            break
    for adr_meta in kb.okf_manifest.get("pages", {}).items():
        pass  # ADRs covered by the loop above via keyword hit
    tok = nid.split(":")[-1].split("/")[-1].lower()
    for p in sorted((kb.okf_dir / "adrs").glob("ADR-*.md")):
        try:
            t = p.read_text()
        except OSError:
            continue
        if tok and tok in t.lower():
            out["adrs"].append({"adr": p.name, "excerpt": t[:400]})
    if out["okf_pages"] or out["adrs"]:
        out["evidence"].append({"source": str(kb.okf_dir), "type": "P4 OKF bundle",
                                "verified": kb.okf_manifest.get("verify")})
    return out


BACKENDS = {"impact": run_impact, "path": run_path, "explain": run_explain,
            "callers": run_callers, "docs": run_docs}


def render(res, max_lines=28):
    """Compact text rendering for CLI/demo transcripts."""
    if res.get("error"):
        return f"ERROR: {res['error']}"
    it = res.get("intent")
    L = []
    if it == "impact":
        L.append(f"impact of {res['target']}  (mode: {res['mode']})")
        if res.get("mode") == "zapi-change":
            for key in ("handlers", "senders"):
                if res.get(key):
                    L.append(f"  {key} ({len(res[key])}):")
                    for s in res[key][:6]:
                        loc = f"  @{s['src_ref']}" if s.get("src_ref") else ""
                        own = f" [{s['service']}]" if s.get("service") else ""
                        L.append(f"    {s['node']}{own}{loc}")
        if res.get("daemons"):
            L.append("  daemons: " + ", ".join(res["daemons"]))
        if res.get("daemons_affected"):
            L.append("  daemons affected: " + ", ".join(res["daemons_affected"]))
        if res.get("callbacks"):
            L.append(f"  callbacks: {len(res['callbacks'])}  e.g. " +
                     ", ".join(res["callbacks"][:4]))
        if res.get("transitive_callers"):
            L.append(f"  transitive callers: {res['transitive_callers']}"
                     f"  direct: {len(res.get('direct_callers', []))}")
        if res.get("zapi_side_effects"):
            L.append("  zapi side effects:")
            for msg, h in list(res["zapi_side_effects"].items())[:6]:
                who = h if isinstance(h, list) else h.get("handled_by", [])
                L.append(f"    {msg} -> handled by {', '.join(who) or '?'}")
        L.append(f"  evidence items: {len(res.get('evidence', []))}")
    elif it == "path":
        via = f"  via {res['via']} (ZAPI flow)" if res.get("via") else ""
        L.append(f"path {res['src']} -> {res['dst']}  ({res['hops']} hops){via}")
        for h in res["path"]:
            arrow = f"-{h['rel']}->" if h["dir"] == "out" else f"<-{h['rel']}-"
            L.append(f"  {h['from']} {arrow} {h['to']}")
        L.append(f"  evidence items: {len(res.get('evidence', []))} (per-hop tag:plane + src_ref)")
    elif it == "explain":
        n = res["node"]
        L.append(f"{res['target']}  kind={n['kind']} service={n['service']}")
        if res.get("clusters"):
            L.append("  clusters: " + ", ".join(
                f"{c['id']}({c['level']})" for c in res["clusters"]))
        if res.get("domain"):
            L.append(f"  domain pack: {res['domain']}")
        for rel, info in res["relations"].items():
            L.append(f"  {rel} ({info['count']})")
            for p in info["peers"][:4]:
                L.append(f"    {p['dir']:3} {p['peer']}  [{','.join(p['evidence'])}] {p['src_ref']}")
    elif it == "callers":
        L.append(f"callers of {res['target']}  (mode: {res['mode']})")
        for key in ("callers", "senders", "handlers"):
            if res.get(key):
                L.append(f"  {key} ({len(res[key])}):")
                for s in res[key][:6]:
                    L.append(f"    {s['node']}" +
                             (f"  [{s['service']}]" if s.get("service") else "") +
                             (f"  @{s['src_ref']}" if s.get("src_ref") else ""))
        for key in ("serves_messages", "handles_messages", "publishes_messages",
                    "sender_services", "handler_services", "zapi_peers",
                    "nb_paths_served", "registered_by", "callbacks"):
            if res.get(key):
                v = res[key]
                L.append(f"  {key}: {', '.join(map(str, v[:8]))}"
                         + (" ..." if len(v) > 8 else ""))
        if res.get("messages_from"):
            for msg, snds in list(res["messages_from"].items())[:4]:
                L.append(f"  message {msg} sent by: {', '.join(snds)}")
        L.append(f"  evidence items: {len(res.get('evidence', []))}")
    elif it == "docs":
        L.append(f"docs for {res['target']}")
        if res.get("pack"):
            p = res["pack"]
            L.append(f"  domain pack {p['id']} '{p['label']}'  sha256={str(p.get('sha256'))[:12]}")
            for f in p.get("functionality", [])[:2]:
                L.append(f"    - {f}")
        for c in res.get("clusters", [])[:4]:
            L.append(f"  {c['level']} {c['id']} {c['label']} roles={','.join(c['roles'])}")
            for f in c.get("functionality", [])[:1]:
                L.append(f"    - {f}")
        for pg in res.get("okf_pages", []):
            L.append(f"  OKF {pg['okf_level']} page {pg['page']} atoms={pg['atoms']}")
        for a in res.get("adrs", []):
            L.append(f"  ADR {a['adr']}")
        L.append(f"  evidence: {len(res.get('evidence', []))} anchored sources")
    else:
        import json as _json
        return _json.dumps(res, indent=2)[:1500]
    return "\n".join(L[:max_lines])
