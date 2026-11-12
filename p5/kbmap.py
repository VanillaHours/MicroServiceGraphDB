#!/usr/bin/env python3
"""P5 KB map — the in-RAM map the server answers from ("ms answers from in-RAM map").

Loads, once at startup:
  P2  facts.duckdb  -> Graph (fused adjacency with evidence)   [scripts/p2/kb.py]
  P3  clusters.jsonl / profiles.jsonl / *_assignments / packs/ -> cluster layer
  P4  okf-bundle/manifest.json + pages                       -> published-doc layer

Builds entity-linking indexes (mention text -> KB node ids) and a content
fingerprint (sha256 over the P4 manifest input hashes + the fact DB stat) that
keys the query/slice caches.
"""
import hashlib
import json
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "p2"))
from kb import Graph, connect  # noqa: E402  (P2 query engine, reused verbatim)

import os  # portability: workspace root via MSG_ROOT (default <repo>/data)
ROOT = Path(os.environ.get("MSG_ROOT", str(Path(__file__).resolve().parents[1] / "data")))
DEFAULT_DB = ROOT / "facts/p2/facts.duckdb"
FACTS3 = ROOT / "facts/p3"
OKF = ROOT / "facts/p4/okf-bundle"

SERVICE_ALIASES = {
    "bgpd": "svc:bgpd", "bgp": "svc:bgpd", "zebra": "svc:zebra",
    "ospfd": "svc:ospfd", "ospf": "svc:ospfd", "staticd": "svc:staticd",
    "static": "svc:staticd", "lib": "svc:lib",
}

_ID_SPLIT = re.compile(r"[\s,;:()\"'?!,]+")
_ALLCAPS = re.compile(r"^[A-Z][A-Z0-9_]{3,}$")
_YANGMOD = re.compile(r"^frr-[a-z0-9-]+$")

# English words / intent words that must never become entities
STOPWORDS = {
    "path", "from", "who", "what", "where", "why", "how", "the", "show",
    "explain", "slice", "impact", "callers", "docs", "documentation",
    "does", "are", "for", "and", "with", "about", "tell", "give", "list",
    "all", "this", "that", "which", "when", "between", "call", "calls",
    "handles", "handled", "publishes", "sends", "side", "effects", "affect",
    "affected", "affects", "break", "breaks", "change", "remove", "delete",
    "value", "come", "comes", "dataflow", "lifetime", "control", "flow",
    "document", "architecture", "design", "responsibilities", "purpose",
    "overview", "what's", "happens", "there", "here", "have", "has", "get",
    "set", "can", "will", "into", "onto", "over", "under", "used", "using",
    "send", "received", "receives", "register", "registers", "table",
    "message", "messages", "function", "leaf", "container", "model", "models",
    "yang", "code", "svc", "zapi", "nb", "note", "changes", "changed",
}


class Mention:
    __slots__ = ("text", "ids", "kind")

    def __init__(self, text, ids, kind):
        self.text, self.ids, self.kind = text, ids, kind

    def to_json(self):
        return {"mention": self.text, "kind": self.kind, "ids": self.ids[:8],
                "n_ids": len(self.ids)}


def _tokenize(text):
    return [t for t in _ID_SPLIT.split(text) if len(t) >= 3]


class KB:
    def __init__(self, db=DEFAULT_DB, facts3=FACTS3, okf=OKF):
        t0 = time.time()
        con = connect(str(db))
        self.graph = Graph(con)
        con.close()
        self.db = Path(db)

        # ---- P3 cluster layer
        fd = Path(facts3)
        self.clusters = [json.loads(l) for l in
                         (fd / "clusters.jsonl").read_text().splitlines()]
        self.cluster_by_id = {c["id"]: c for c in self.clusters}
        self.profiles = {p["id"]: p for p in
                         (json.loads(l) for l in
                          (fd / "profiles.jsonl").read_text().splitlines())}
        self.bb_assign = json.loads((fd / "backbone_assignments.json").read_text())
        self.code_assign = json.loads((fd / "code_assignments.json").read_text())
        self.packs_dir = fd / "packs"

        # ---- P4 OKF layer
        okf = Path(okf)
        self.okf_manifest = json.loads((okf / "manifest.json").read_text())
        self.okf_dir = okf

        # ---- fingerprint (cache keys change when any input changes)
        h = hashlib.sha256()
        h.update(json.dumps(self.okf_manifest.get("inputs_sha256", {}),
                            sort_keys=True).encode())
        st = self.db.stat()
        h.update(f"{self.db}:{st.st_size}:{st.st_mtime_ns}".encode())
        self.fingerprint = h.hexdigest()[:16]

        # ---- entity-linking indexes
        self._build_indexes()
        self._impact_memo = {}          # (yang-id, depth) -> impact result
        self.load_ms = round((time.time() - t0) * 1000, 1)

    # ---------------------------------------------------------- indexes
    def _build_indexes(self):
        self._zapi_ids = {n for n in self.graph.nodes if n.startswith("zapi:")}
        self._yang_ids = {n for n in self.graph.nodes if n.startswith("yang:")}
        self._nb_ids = {n for n in self.graph.nodes if n.startswith("nb:")}
        self._svc_ids = {n for n in self.graph.nodes if n.startswith("svc:")}
        self.label_to_ids = defaultdict(list)
        self.suffix_to_ids = defaultdict(list)     # id tail after '::' or ':'
        self.yang_module_nodes = defaultdict(list)  # module -> [yang ids]
        for nid, meta in self.graph.nodes.items():
            lbl = (meta.get("label") or "").strip().lower()
            if lbl:
                self.label_to_ids[lbl].append(nid)
            for tail in (nid.split("::")[-1], nid.split(":")[-1]):
                if len(tail) >= 3:
                    self.suffix_to_ids.setdefault(tail.lower(), []).append(nid)
            if nid.startswith("yang:"):
                mod = nid.split(":")[1] if nid.count(":") >= 2 else ""
                self.yang_module_nodes[mod].append(nid)
        for k in self.yang_module_nodes:
            self.yang_module_nodes[k].sort()
        # yang path segments: last segment and last two segments of the xpath
        self.yang_seg_to_ids = defaultdict(list)
        for nid in self._yang_ids:
            segs = nid.split(":", 2)[-1].split("/")
            for tail in ([segs[-1]] if len(segs) >= 2 else []) + \
                        (["/".join(segs[-2:])] if len(segs) >= 3 else []):
                if len(tail) >= 5 and tail.lower() not in STOPWORDS:
                    self.yang_seg_to_ids[tail.lower()].append(nid)
        # defining file per code node: most common file among its edge refs
        self.code_file = {}
        for nid in self.graph.nodes:
            if not nid.startswith("code:"):
                continue
            votes = defaultdict(int)
            for _d, _o, _r, _ev, refs in self.graph.adj.get(nid, []):
                for ref in refs or []:
                    f = ref.rsplit(":", 1)[0] if ref and ":" in ref else ref
                    if f and "/" in f and not f.startswith(("http", "rg:")):
                        votes[f] += 1
            if votes:
                self.code_file[nid] = max(votes, key=votes.get)

        self._stop = STOPWORDS

    # ---------------------------------------------------------- linking
    def resolve_mentions(self, text, cap_ids=8):
        """Token-level entity linking. Returns ordered unique Mentions."""
        out, seen = [], set()

        def add(mtext, ids, kind, mark_seen=True):
            uniq = [i for i in dict.fromkeys(ids) if i not in seen][:cap_ids]
            if not uniq:
                return False
            if mark_seen:
                seen.update(uniq)
            out.append(Mention(mtext, uniq, kind))
            return True

        for tok in _tokenize(text):
            low = tok.lower()
            if low in self._stop:
                continue
            # 1. explicit, fully-qualified ids
            if tok in self.graph.nodes:
                add(tok, [tok], tok.split(":")[0])
                continue
            # 2. services by alias
            if low in SERVICE_ALIASES and SERVICE_ALIASES[low] in self._svc_ids:
                add(tok, [SERVICE_ALIASES[low]], "svc")
                continue
            # 3. ZAPI message enums (bare or prefixed)
            cand = tok if tok.startswith("zapi:") else (
                f"zapi:{tok}" if _ALLCAPS.match(tok) else None)
            if cand and cand in self._zapi_ids:
                add(tok, [cand], "zapi")
                continue
            # 4. yang paths: full xpath tail, then last-segment fallback
            matched = False
            for key in (low.split(":", 1)[-1], low):
                y = [i for i in self.suffix_to_ids.get(key, [])
                     if i.startswith("yang:")]
                if y:
                    matched = add(tok, y, "yang")
                    break
            if not matched and len(low) >= 5:
                y = self.yang_seg_to_ids.get(low, [])
                if len(y) <= cap_ids:
                    matched = add(tok, y, "yang")
            if matched:
                continue
            # 5. yang module mention (token is frr-*)
            #    does NOT mark ids seen: module-level mentions must not block
            #    later specific-leaf tokens (P6 eval catch: 'alias' leaf was
            #    swallowed by the alphabetically-early module mention)
            if _YANGMOD.match(low) and low in self.yang_module_nodes:
                if add(tok, self.yang_module_nodes[low], "yang-module",
                       mark_seen=False):
                    continue
            # 6. code / nb symbols by label or id tail
            ids = self.label_to_ids.get(low) or self.suffix_to_ids.get(low, [])
            codey = [i for i in ids if i.startswith(("code:", "nb:"))]
            if codey:
                # P6 eval fix: prefer the top-level decl (fewest '::' scopes) —
                # nested duplicates (fn recorded inside an enclosing fn) carry
                # no wiring and would break callers/slice resolution
                codey.sort(key=lambda i: (i.count("::"), len(i)))
                add(tok, codey, "code")
                continue
            # 7. any-node label fallback (structs, enums, tus, daemons)
            anyids = self.label_to_ids.get(low, [])
            if len(anyids) == 1:
                add(tok, anyids, anyids[0].split(":")[0])
        return out

    def clusters_of(self, nid):
        """Cluster memberships of a node across levels (P3 kb 'of' logic)."""
        found = {}
        if nid in self.bb_assign:
            for lvl in ("L1", "L2"):
                cid = self.bb_assign[nid].get(lvl)
                if cid:
                    found[cid] = lvl
        if nid in self.code_assign:
            found[self.code_assign[nid]] = "L3"
        return [{"id": c, "level": l, "label": self.cluster_by_id[c]["label"]}
                for c, l in found.items() if c in self.cluster_by_id]

    def domain_of(self, nid):
        """L1 domain pack id containing the node. Backbone nodes are assigned
        directly; L3 module clusters parent to svc:X -- bridge through it."""
        cid = self.bb_assign.get(nid, {}).get("L1")
        if cid:
            return cid
        cur = self.code_assign.get(nid)
        for _ in range(6):                                   # bounded climb
            if cur in self.bb_assign:
                return self.bb_assign[cur].get("L1")
            c = self.cluster_by_id.get(cur)
            if not c:
                return None
            nxt = c.get("parent")
            if nxt and nxt.startswith("svc:"):
                return self.bb_assign.get(nxt, {}).get("L1")
            cur = nxt
        # fallback: yang node not assigned directly -> match its module against
        # cluster profiles' yang_modules, climb that cluster to its L1
        if nid.startswith("yang:"):
            mod = nid.split(":")[1]
            for c in self.clusters:
                if mod in self.profiles.get(c["id"], {}).get("yang_modules", {}):
                    walk = c["id"]
                    for _ in range(6):
                        cc = self.cluster_by_id.get(walk)
                        if not cc:
                            break
                        if cc.get("level") == "L1":
                            return walk
                        walk = cc.get("parent")
        return None

    def stats(self):
        return {
            "nodes": len(self.graph.nodes),
            "edges_fused": self.graph.fused_edge_count,
            "edges_raw": self.graph.raw_edge_count,
            "clusters": len(self.clusters),
            "packs": sorted(p.name for p in self.packs_dir.glob("*.json")),
            "okf_pages": len(self.okf_manifest.get("pages", {})),
            "fingerprint": self.fingerprint,
            "load_ms": self.load_ms,
        }
