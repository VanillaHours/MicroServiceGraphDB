#!/usr/bin/env python3
"""P5 server — /query + /slice endpoints over the in-RAM KB map.

Layers:
  KB map      (kbmap.KB)     P2 graph + P3 clusters + P4 OKF, loaded once
  router v0   (router)       rule-based, 6 intents, no LLM
  backends    (intents)      impact / path / explain / callers / docs
  instrument  (slice.SliceEngine)  scoped CFG/DFG/liveness, memoized by
                             (content-hash(scope), tool ver)  [P5 design]
  query cache (Service.qcache)  (question, intent, kb fingerprint)-keyed;
                             repeat Q = cache hit (exit gate #3)

Endpoints:
  GET  /health              kb stats + cache stats
  POST /query               {question, intent?, max_hops?, call_depth?}
  POST /slice               {file, function}  or  {code_id}
  POST /admin/cache/clear   drop query cache (slices persist on disk)

CLI:
  python3 server.py --serve [--port 8915]
  python3 server.py --ask "who handles ZEBRA_ROUTE_ADD"
  python3 server.py --slice zebra/zapi_msg.c zread_route_add
"""
import argparse
import hashlib
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import intents as B
from kbmap import KB
from router import INTENTS, classify
from slice import SliceEngine, render_slice

DEFAULT_PORT = 8915

# which linked mention should drive each entity intent (most specific first)
PRIO = {
    "impact": ["yang", "zapi", "code", "svc", "nb", "yang-module"],
    "explain": ["code", "yang", "zapi", "nb", "svc", "yang-module"],
    "callers": ["zapi", "code", "svc", "nb", "yang", "yang-module"],
    "docs": ["svc", "yang-module", "yang", "zapi", "code", "nb"],
}


def pick_primary(mentions, intent):
    order = PRIO.get(intent)
    if order:
        for k in order:
            for m in mentions:
                if m.kind == k:
                    return m
    return mentions[0] if mentions else None


class Service:
    def __init__(self, load=True):
        self.kb = KB() if load else None
        self.engine = SliceEngine() if load else None
        self.qcache = {}
        self.qstats = {"hits": 0, "misses": 0}
        self.lock = threading.Lock()
        self.started = time.time()

    # ------------------------------------------------------------ /query
    def query(self, question, intent=None, max_hops=8, call_depth=10):
        t0 = time.time()
        norm = " ".join(question.lower().split())
        key = hashlib.sha256(json.dumps(
            [norm, intent, max_hops, call_depth, self.kb.fingerprint]).encode()).hexdigest()
        with self.lock:
            hit = self.qcache.get(key)
            if hit is not None:
                self.qstats["hits"] += 1
                out = json.loads(json.dumps(hit))    # deep copy
                out["meta"]["cache_hit"] = True
                out["meta"]["latency_ms"] = round((time.time() - t0) * 1000, 2)
                out["meta"]["cache_key"] = key
                return out
            self.qstats["misses"] += 1

        resp = self._query_uncached(question, intent, max_hops, call_depth, t0)
        resp["meta"]["cache_key"] = key
        with self.lock:
            self.qcache[key] = json.loads(json.dumps(resp))
        return resp

    def _query_uncached(self, question, intent, max_hops, call_depth, t0):
        mentions = self.kb.resolve_mentions(question)
        route = classify(question, mentions, explicit_intent=intent)
        it = route["intent"]
        base = {"ok": True, "question": question, "intent": it,
                "routed": route,
                "entities": [m.to_json() for m in mentions],
                "meta": {"latency_ms": None, "cache_hit": False,
                         "fingerprint": self.kb.fingerprint}}
        if it is None:
            base.update(ok=False, error=route.get("note", "no intent matched"),
                        suggestions=INTENTS)
        elif it == "path":
            res = self._path(mentions, question, max_hops)
            if res.get("error") and res.get("clarify"):
                base.update(ok=False, error=res["error"], intent="path")
            else:
                base["answer"] = res
                base["text"] = B.render(res)
        elif it == "slice":
            scope = self._resolve_scope(mentions)
            if scope is None:
                base.update(ok=False, intent="slice",
                            error="slice needs a function (e.g. 'slice "
                                  "zread_route_add in zebra/zapi_msg.c') or "
                                  "POST /slice with file+function")
            else:
                res = self.engine.slice(scope["file"], scope["function"])
                base["answer"] = {"scope": res["scope"], "tool_ver": res["tool_ver"],
                                  "cache": res["cache"],
                                  "cfg_summary": {k: res["cfg"][k]
                                                  for k in ("n_blocks", "n_edges")},
                                  "dfg_summary": {"n_defs": len(res["dfg"]["defs"]),
                                                  "n_chains": res["dfg"]["n_chains"],
                                                  "undef_uses": len(res["dfg"]["undef_uses"])},
                                  "full": res}
                base["text"] = render_slice(res)
        elif it == "docs":
            if not mentions:
                base["answer"] = B.run_docs(self.kb, mentions, question=question)
                base["text"] = B.render(base["answer"])
            else:
                res = B.run_docs(self.kb, mentions, question=question)
                base["answer"] = res
                base["text"] = B.render(res)
        else:                                            # impact/explain/callers
            m = pick_primary(mentions, it)
            if m is None:
                base.update(ok=False, error=f"{it} needs an entity; none linked "
                            f"from the question")
            else:
                ids = m.ids
                if it == "impact":
                    res = B.run_impact(self.kb, ids, call_depth=call_depth)
                elif it == "explain":
                    res = B.run_explain(self.kb, ids)
                else:
                    res = B.run_callers(self.kb, ids)
                base["answer"] = res
                base["text"] = B.render(res)
        base["meta"]["latency_ms"] = round((time.time() - t0) * 1000, 2)
        return base

    def _path(self, mentions, question, max_hops):
        # "from X to Y": heuristics — first two entity groups in order
        groups = []
        for m in mentions:
            if not groups or groups[-1][0] is not m:
                groups.append((m, [m]))
            else:
                groups[-1][1].append(m)
        if len(groups) < 2:
            return {"intent": "path", "clarify": True,
                    "error": "path needs two endpoints, e.g. 'path from svc:bgpd "
                             "to svc:zebra'"}
        src, dst = groups[0][0], groups[1][0]
        return B.run_path(self.kb, src.ids, dst.ids, max_hops=max_hops)

    def _resolve_scope(self, mentions):
        for m in mentions:
            if m.kind == "code":
                nid = m.ids[0]
                f = self.kb.code_file.get(nid)
                if f:
                    return {"file": f, "function": self.kb.graph.nodes[nid]["label"],
                            "code_id": nid}
        return None

    # ------------------------------------------------------------ /slice
    def slice_api(self, file=None, function=None, code_id=None, force=False):
        t0 = time.time()
        if code_id and not (file and function):
            f = self.kb.code_file.get(code_id)
            if not f:
                return {"ok": False, "error": f"no defining file known for {code_id}"}
            file, function = f, self.kb.graph.nodes[code_id]["label"]
        if not (file and function):
            return {"ok": False, "error": "POST /slice needs {file, function} "
                    "or {code_id}"}
        try:
            res = self.engine.slice(file, function, force=force)
        except (FileNotFoundError, LookupError, ValueError) as e:
            return {"ok": False, "error": str(e)}
        return {"ok": True, "scope": res["scope"], "tool_ver": res["tool_ver"],
                "cfg": res["cfg"], "dfg": res["dfg"],
                "liveness": res["liveness"], "cache": res["cache"],
                "text": render_slice(res),
                "meta": {"latency_ms": round((time.time() - t0) * 1000, 2),
                         "cache_hit": res["cache"]["hit"],
                         "fingerprint": self.kb.fingerprint}}

    # ------------------------------------------------------------ /health
    def health(self):
        return {"status": "ok", "uptime_s": round(time.time() - self.started, 1),
                "kb": self.kb.stats(),
                "slice_engine": dict(self.engine.stats),
                "query_cache": {**self.qstats, "entries": len(self.qcache)}}


# ---------------------------------------------------------------- HTTP
def make_handler(service):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):                        # quiet
            pass

        def _send(self, code, obj):
            body = json.dumps(obj, indent=1).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/health":
                self._send(200, service.health())
            else:
                self._send(404, {"error": f"unknown path {self.path}"})

        def do_POST(self):
            n = int(self.headers.get("Content-Length") or 0)
            try:
                req = json.loads(self.rfile.read(n) or b"{}")
            except json.JSONDecodeError:
                return self._send(400, {"error": "bad JSON"})
            if self.path == "/query":
                self._send(200, service.query(
                    req.get("question", ""), intent=req.get("intent"),
                    max_hops=req.get("max_hops", 8),
                    call_depth=req.get("call_depth", 10)))
            elif self.path == "/slice":
                self._send(200, service.slice_api(
                    file=req.get("file"), function=req.get("function"),
                    code_id=req.get("code_id"), force=req.get("force", False)))
            elif self.path == "/admin/cache/clear":
                with service.lock:
                    service.qcache.clear()
                self._send(200, {"ok": True, "cleared": "query cache"})
            else:
                self._send(404, {"error": f"unknown path {self.path}"})

    return Handler


def serve(port=DEFAULT_PORT):
    svc = Service()
    httpd = ThreadingHTTPServer(("127.0.0.1", port), make_handler(svc))
    print(f"P5 server ready on http://127.0.0.1:{port}  "
          f"(kb load {svc.kb.load_ms}ms, fingerprint {svc.kb.fingerprint})",
          flush=True)
    httpd.serve_forever()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--serve", action="store_true")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--ask")
    ap.add_argument("--intent")
    ap.add_argument("--slice", nargs=2, metavar=("FILE", "FUNCTION"))
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if a.serve:
        serve(a.port)
        return 0
    svc = Service()
    if a.ask:
        out = svc.query(a.ask, intent=a.intent)
        print(out["text"] if not a.json else json.dumps(out, indent=1))
        print(f"\n[{out.get('intent')} | {out['meta']['latency_ms']}ms | "
              f"cache_hit={out['meta']['cache_hit']} | "
              f"confidence={out['routed']['confidence']}]")
    elif a.slice:
        out = svc.slice_api(file=a.slice[0], function=a.slice[1])
        print(out["text"] if not a.json else json.dumps(out, indent=1))
    else:
        ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
