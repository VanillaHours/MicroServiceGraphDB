#!/usr/bin/env python3
"""P5 /slice instrument — scoped CFG + DFG + liveness for ONE function.

Design (POC-DESIGN.md §2 mode 2): the instrument computes control/dataflow on
demand for a single function, memoized by (content-hash(scope), tool version),
never persisted globally as a graph. Reuses the P1 parse setup (clang.cindex +
compile_commands.json flags) — "the same tool" family.

CFG   : statement-level basic blocks with then/else/loop/switch/return/goto edges
DFG   : reaching-definitions worklist over the CFG -> per-use def chains
LIVE  : backward live-variable sets per block (params live-in at entry)

Var identity: referenced decl USR for plain vars; "base->field" / "base.field"
access paths for member lvalues (v0 granularity, documented in P5-REPORT).
"""
import hashlib
import json
import time
from pathlib import Path

import clang.cindex as ci

TOOL_VER = "p5-slice/1.0.0+clang18"
import os  # portability: workspace root via MSG_ROOT (default <repo>/data)
ROOT = Path(os.environ.get("MSG_ROOT", str(Path(__file__).resolve().parents[1] / "data")))
SRC = Path(os.environ.get("MSG_SRC", str(ROOT / "src/frr-10.7.1")))
CC_PATH = Path(os.environ.get("MSG_CC", str(ROOT / "compile_commands.json")))

import glob  # noqa: E402
import sys   # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "p1"))
import clang_facts  # noqa: E402  (P1 sanitize_args, reused verbatim)

def _find_libclang():
    """Locate the libclang shared library (pip libclang wheel or system LLVM)."""
    if os.environ.get("MSG_LIBCLANG"):
        return os.environ["MSG_LIBCLANG"]
    try:
        import clang as _clang_pkg
        cand = sorted(glob.glob(os.path.join(
            os.path.dirname(_clang_pkg.__file__), "native", "*.so*")))
        if cand:
            return cand[0]
    except ImportError:
        pass
    for _pat in ("/usr/lib/llvm-*/lib/libclang.so*",
                 "/usr/lib/x86_64-linux-gnu/libclang-*.so*"):
        cand = sorted(glob.glob(_pat))
        if cand:
            return cand[0]
    raise RuntimeError("libclang shared library not found; pip install "
                       "libclang or set MSG_LIBCLANG")


ci.conf.set_library_file(_find_libclang())
ci.conf.set_compatibility_check(False)

K = ci.CursorKind
CTRL_KINDS = {K.IF_STMT, K.WHILE_STMT, K.DO_STMT, K.FOR_STMT, K.SWITCH_STMT,
              K.RETURN_STMT, K.BREAK_STMT, K.CONTINUE_STMT, K.GOTO_STMT,
              K.LABEL_STMT, K.CASE_STMT, K.DEFAULT_STMT}
_COMPOUND_OPS = {"+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=", "<<=", ">>="}


def _spell(c, cap=140):
    try:
        txt = " ".join(t.spelling for t in c.get_tokens())
        return txt[:cap]
    except Exception:
        return ""


def _root(c):
    """Root access path: 'x', 'x->f', 'x.f', 'x->f.g', '*p', 'a[i]'."""
    if c.kind == K.DECL_REF_EXPR:
        r = c.referenced
        return (r.spelling if r is not None else c.spelling) or c.spelling
    if c.kind == K.MEMBER_REF_EXPR:
        op = "->"
        for t in c.get_tokens():
            if t.spelling == "->":
                break
            if t.spelling == ".":
                op = "."
                break
        base = None
        for ch in c.get_children():
            base = ch
            break
        if base is None:
            return c.spelling or "?"
        return f"{_root(base)}{op}{c.spelling}"
    if c.kind == K.UNARY_OPERATOR:
        toks = [t.spelling for t in c.get_tokens()]
        if toks and toks[0] == "*":
            for ch in c.get_children():
                return f"*{_root(ch)}"
    if c.kind == K.ARRAY_SUBSCRIPT_EXPR:
        for ch in c.get_children():
            return f"{_root(ch)}[...]"
    return c.spelling or "?"


def _is_var_ref(c):
    if c.kind != K.DECL_REF_EXPR:
        return False
    r = c.referenced
    return r is not None and r.kind in (K.VAR_DECL, K.PARM_DECL)


class _Stmt:
    __slots__ = ("cursor", "kind", "spell", "line", "defs", "uses")

    def __init__(self, cursor):
        self.cursor = cursor
        self.kind = cursor.kind.name
        self.line = cursor.location.line
        self.spell = _spell(cursor)
        self.defs = []                      # [(var, kind)]
        self.uses = []                      # [var]


class _Block:
    __slots__ = ("id", "stmts", "succ", "pred", "tag")

    def __init__(self, bid, tag=""):
        self.id, self.tag = bid, tag
        self.stmts = []
        self.succ = []                      # [(dst, edge-kind)]
        self.pred = []


class CFGBuilder:
    """Statement-level CFG over one function body."""

    def __init__(self):
        self.blocks = []
        self.edges = []
        self.entry = self._new("entry")
        self.exit = self._new("exit")
        self.cur = self.entry
        self.labels = {}
        self.pending_goto = []
        self.unreachable_skipped = 0

    def _new(self, tag=""):
        b = _Block(len(self.blocks), tag)
        self.blocks.append(b)
        return b

    def _edge(self, a, b, kind):
        if a is None or b is None:
            return
        self.edges.append((a.id, b.id, kind))
        a.succ.append((b.id, kind))
        b.pred.append((a.id, kind))

    def _stmt(self, c):
        if self.cur is None:
            self.unreachable_skipped += 1
            return None
        s = _Stmt(c)
        self.cur.stmts.append(s)
        return s

    # ------------------------------------------------------------ walk
    def build(self, fn_cursor):
        body = next((ch for ch in fn_cursor.get_children()
                     if ch.kind == K.COMPOUND_STMT), None)
        if body is None:
            raise ValueError(f"function {fn_cursor.spelling} has no body here")
        self._walk(body, {}, "body")
        if self.cur is not None:
            self._edge(self.cur, self.exit, "fallthrough")
        for src_blk, label in self.pending_goto:
            tgt = self.labels.get(label)
            if tgt is not None:
                self._edge(self.blocks[src_blk], tgt, "goto")
        return self.blocks, self.edges

    def _walk(self, c, ctx, tag=""):
        k = c.kind
        if k == K.COMPOUND_STMT:
            for ch in c.get_children():
                self._walk(ch, ctx)
        elif k == K.IF_STMT:
            ch = list(c.get_children())
            cond, then = ch[0], ch[1]
            els = ch[2] if len(ch) > 2 else None
            self._stmt(cond)
            cond_blk = self.cur
            merge = self._new("if-merge")
            tb = self._new("then")
            self._edge(cond_blk, tb, "then")
            self.cur = tb
            self._walk(then, ctx)
            if self.cur is not None:
                self._edge(self.cur, merge, "fallthrough")
            if els is not None:
                eb = self._new("else")
                self._edge(cond_blk, eb, "else")
                self.cur = eb
                self._walk(els, ctx)
                if self.cur is not None:
                    self._edge(self.cur, merge, "fallthrough")
            else:
                self._edge(cond_blk, merge, "no-else")
            self.cur = merge
        elif k == K.WHILE_STMT:
            ch = list(c.get_children())
            hb = self._new("while-head")
            self._edge(self.cur, hb, "next")
            self._stmt(ch[0])
            xb = self._new("while-exit")
            self._edge(hb, xb, "exit-false")
            bb = self._new("while-body")
            self._edge(hb, bb, "loop-true")
            self.cur = bb
            inner = dict(ctx, **{"break": xb, "continue": hb})
            self._walk(ch[1], inner)
            if self.cur is not None:
                self._edge(self.cur, hb, "latch")
            self.cur = xb
        elif k == K.FOR_STMT:
            ch = list(c.get_children())             # init, cond, incr, body
            init, cond, incr, body = (ch + [None, None, None, None])[:4]
            if init is not None:
                self._stmt(init)
            hb = self._new("for-head")
            self._edge(self.cur, hb, "next")
            if cond is not None and cond.kind != K.NULL_STMT:
                self._stmt(cond)
            xb = self._new("for-exit")
            self._edge(hb, xb, "exit-false")
            bb = self._new("for-body")
            self._edge(hb, bb, "loop-true")
            self.cur = bb
            ib = self._new("for-incr")
            inner = dict(ctx, **{"break": xb, "continue": ib})
            if body is not None:
                self._walk(body, inner)
            if self.cur is not None:
                self._edge(self.cur, ib, "to-incr")
            if incr is not None and incr.kind != K.NULL_STMT:
                self.cur = ib
                self._stmt(incr)
            self._edge(ib, hb, "latch")
            self.cur = xb
        elif k == K.DO_STMT:
            ch = list(c.get_children())
            db = self._new("do-body")
            self._edge(self.cur, db, "next")
            self.cur = db
            cb = self._new("do-cond")
            xb = self._new("do-exit")
            inner = dict(ctx, **{"break": xb, "continue": cb})
            self._walk(ch[0], inner)
            if self.cur is not None:
                self._edge(self.cur, cb, "cond")
            self.cur = cb
            self._stmt(ch[1])
            self._edge(cb, db, "loop-true")
            self._edge(cb, xb, "exit-false")
            self.cur = xb
        elif k == K.SWITCH_STMT:
            ch = list(c.get_children())
            cond = ch[0]
            self._stmt(cond)
            cond_blk = self.cur
            merge = self._new("switch-merge")
            inner = dict(ctx, **{"break": merge, "continue": ctx.get("continue")})
            body = ch[1]
            for st in (body.get_children() if body.kind == K.COMPOUND_STMT
                       else [body]):
                if st.kind in (K.CASE_STMT, K.DEFAULT_STMT):
                    cb = self._new("case")
                    self._edge(cond_blk, cb, "case")
                    if self.cur is not None:
                        self._edge(self.cur, cb, "fallthrough")
                    self.cur = cb
                    self._stmt(st)
                else:
                    self._walk(st, inner)
            if self.cur is not None:
                self._edge(self.cur, merge, "fallthrough")
            self.cur = merge
        elif k == K.CASE_STMT or k == K.DEFAULT_STMT:
            self._stmt(c)                           # bare case outside compound
        elif k == K.RETURN_STMT:
            self._stmt(c)
            self._edge(self.cur, self.exit, "return")
            self.cur = None
        elif k == K.BREAK_STMT:
            self._stmt(c)
            tgt = ctx.get("break")
            if tgt is not None:
                self._edge(self.cur, tgt, "break")
            self.cur = None
        elif k == K.CONTINUE_STMT:
            self._stmt(c)
            tgt = ctx.get("continue")
            if tgt is not None:
                self._edge(self.cur, tgt, "continue")
            self.cur = None
        elif k == K.GOTO_STMT:
            self._stmt(c)
            label = c.spelling
            self.pending_goto.append((self.cur.id, label))
            self.cur = None
        elif k == K.LABEL_STMT:
            lb = self._new("label")
            if self.cur is not None:
                self._edge(self.cur, lb, "fallthrough")
            self.cur = lb
            self._stmt(c)
            self.labels[c.spelling] = lb
        elif k == K.NULL_STMT:
            pass
        else:
            self._stmt(c)


# ------------------------------------------------------------ def/use
def _assign_pairs(stmt):
    """Yield (lhs_cursor, rhs_cursor, compound:bool) for assignments in stmt."""
    out = []
    for c in stmt.cursor.walk_preorder():
        if c.kind != K.BINARY_OPERATOR:
            continue
        toks = [t.spelling for t in c.get_tokens()]
        op_idx, compound = None, False
        for i, t in enumerate(toks):
            if t == "=" and (i == 0 or toks[i - 1] not in
                             {"=", "!", "<", ">", "+", "-", "*", "/", "%",
                              "&", "|", "^", "<<", ">>"}) \
                    and (i + 1 >= len(toks) or toks[i + 1] != "="):
                op_idx, compound = i, False
                break
            if t in _COMPOUND_OPS:
                op_idx, compound = i, True
                break
        if op_idx is None:
            continue
        ch = list(c.get_children())
        if len(ch) >= 2:
            out.append((ch[0], ch[-1], compound))
    return out


def _incdec(stmt):
    out = []
    for c in stmt.cursor.walk_preorder():
        if c.kind != K.UNARY_OPERATOR:
            continue
        toks = [t.spelling for t in c.get_tokens()]
        if "++" in toks or "--" in toks:
            for ch in c.get_children():
                out.append(ch)
    return out


def analyze_stmt(s):
    """Fill s.defs / s.uses: (var, kind) defs, plain var uses."""
    defs, uses = [], []
    seen_def, seen_use = set(), set()

    def use(c):
        if not _is_var_ref(c):
            return
        v = _root(c)
        if v in seen_def:                        # LHS of plain assign: not a read
            return
        if v not in seen_use:
            seen_use.add(v)
            uses.append(v)

    def deff(c, kind):
        v = _root(c)
        if v and v not in seen_def:
            seen_def.add(v)
            defs.append((v, kind))

    for lhs, rhs, compound in _assign_pairs(s):
        if compound:
            use(lhs)                             # += reads before writing
        deff(lhs, "assign" + ("-op" if compound else ""))
        for c in rhs.walk_preorder():
            use(c)
            if c.kind == K.MEMBER_REF_EXPR:
                base = next(c.get_children(), None)
                if base is not None:
                    use(base)
    for c in _incdec(s):
        deff(c, "incdec")
        use(c)
    for c in s.cursor.walk_preorder():
        if c.kind == K.VAR_DECL:
            for ch in c.get_children():          # initializer expressions
                for x in ch.walk_preorder():
                    use(x)
        elif c.kind == K.CALL_EXPR:
            for arg in c.get_children():
                if arg.kind in (K.DECL_REF_EXPR, K.MEMBER_REF_EXPR):
                    use(arg)
    # plain statements (conditions, returns, bare exprs): every var ref is a
    # use unless it was already captured as a def above
    for c in s.cursor.walk_preorder():
        use(c)
        if c.kind == K.MEMBER_REF_EXPR:
            base = next(c.get_children(), None)
            if base is not None:
                use(base)
    s.defs, s.uses = defs, uses


class SliceEngine:
    def __init__(self, cache_dir=ROOT / "facts/p5/cache/slices",
                 src_root=SRC, cc_path=CC_PATH):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.src_root = Path(src_root)
        if not Path(cc_path).is_file():   # graceful: the 5 query
            self._cc, self._flags, self._tu = {}, {}, {}  # intents run
            self.stats = {"parses": 0, "computes": 0, "hits": 0,
                          "cc_missing": str(cc_path)}  # without slice;
            return                         # set MSG_CC to enable
        cc = json.loads(Path(cc_path).read_text())
        self._cc = {e["file"]: e for e in cc}
        self._flags = {}
        self._tu = {}                           # file -> (tu, flags_digest)
        self.stats = {"parses": 0, "computes": 0, "hits": 0}

    # ------------------------------------------------------------ flags/parse
    def flags_for(self, rel_file):
        if rel_file in self._flags:
            return self._flags[rel_file]
        entry = self._cc.get(rel_file) or self._cc.get(str(self.src_root / rel_file))
        if entry is None:
            key = next((k for k in self._cc if k.endswith(rel_file)), None)
            entry = self._cc.get(key) if key else None
        if entry is None:
            raise FileNotFoundError(f"no compile command for {rel_file}")
        args = clang_facts.sanitize_args(entry["arguments"],
                                         Path(entry["directory"]), entry["file"])
        self._flags[rel_file] = args
        return args

    def _parse(self, rel_file):
        args = self.flags_for(rel_file)
        import hashlib as _h
        fdig = _h.sha256(" ".join(args).encode()).hexdigest()[:12]
        cached = self._tu.get(rel_file)
        if cached and cached[1] == fdig:
            return cached[0]
        idx = ci.Index.create()
        tu = idx.parse(str(self.src_root / rel_file), args=args)
        self._tu[rel_file] = (tu, fdig)
        self.stats["parses"] += 1
        return tu

    def find_function(self, rel_file, function):
        tu = self._parse(rel_file)
        main = str(self.src_root / rel_file)
        best = None
        for c in tu.cursor.walk_preorder():
            if c.kind != K.FUNCTION_DECL or c.spelling != function:
                continue
            fl = c.location.file
            if fl is None:
                continue
            if c.is_definition():
                best = c
                if str(fl) == main:
                    break
        if best is None:
            raise LookupError(f"function {function!r} not found in {rel_file}")
        return tu, best

    # ------------------------------------------------------------ public
    def slice(self, rel_file, function, force=False):
        src = self.src_root / rel_file
        content = src.read_bytes()
        args = self.flags_for(rel_file)
        import hashlib as _h
        fdig = _h.sha256(" ".join(args).encode()).hexdigest()[:12]
        key = _h.sha256(content + fdig.encode() + function.encode()
                        + TOOL_VER.encode()).hexdigest()
        cpath = self.cache_dir / f"{key}.json"
        if cpath.exists() and not force:
            self.stats["hits"] += 1
            out = json.loads(cpath.read_text())
            out["cache"] = {"hit": True, "key": key, "path": str(cpath),
                            "tool_ver": TOOL_VER}
            return out

        t0 = time.time()
        tu, fn = self.find_function(rel_file, function)
        cfg = CFGBuilder()
        blocks, edges = cfg.build(fn)

        # params as entry defs (bindings have no get_parameters; scan children)
        params = [(p.spelling, p.type.spelling)
                  for p in fn.get_children() if p.kind == K.PARM_DECL]

        # statement records + analysis
        blk_out = []
        all_defs = []                            # dicts
        def_id = 0
        for b in blocks:
            stmts = []
            for si, s in enumerate(b.stmts):
                analyze_stmt(s)
                for var, kind in s.defs:
                    all_defs.append({"id": f"d{def_id}", "var": var,
                                     "block": b.id, "stmt": si,
                                     "line": s.line, "kind": kind})
                    def_id += 1
                stmts.append({"kind": s.kind, "line": s.line,
                              "spell": s.spell, "defs": s.defs,
                              "uses": s.uses})
            blk_out.append({"id": b.id, "tag": b.tag, "stmts": stmts,
                            "succ": b.succ, "pred": b.pred})
        # params: defs at entry (block 0), stmt -1
        param_defs = []
        for p, pt in params:
            param_defs.append({"id": f"d{def_id}", "var": p, "block": 0,
                               "stmt": -1, "line": fn.location.line,
                               "kind": "param", "type": pt})
            def_id += 1
        all_defs = param_defs + all_defs

        dfg, liveness = self._dataflow(blk_out, all_defs)
        out = {
            "scope": {"file": rel_file, "function": function,
                      "line_span": [fn.extent.start.line, fn.extent.end.line],
                      "params": [{"name": p, "type": t} for p, t in params]},
            "tool_ver": TOOL_VER,
            "cfg": {"entry": 0, "exit": 1, "n_blocks": len(blk_out),
                    "n_edges": len(edges),
                    "blocks": blk_out,
                    "edges": [{"from": a, "to": b, "kind": k}
                              for a, b, k in edges]},
            "dfg": dfg,
            "liveness": liveness,
            "meta": {"compute_ms": round((time.time() - t0) * 1000, 1),
                     "unreachable_stmts_skipped": cfg.unreachable_skipped,
                     "cache_key": key},
            "cache": {"hit": False, "key": key, "path": str(cpath),
                      "tool_ver": TOOL_VER},
        }
        self.stats["computes"] += 1
        cpath.write_text(json.dumps(out, indent=1))
        return out

    # ------------------------------------------------------------ dataflow
    def _dataflow(self, blocks, all_defs):
        by_var = {}
        for d in all_defs:
            by_var.setdefault(d["var"], []).append(d)

        # per-block gen: last def per var in block order (entry block's param
        # defs carry stmt=-1 so statement defs override them)
        ordered = {}
        for d in all_defs:
            ordered.setdefault(d["block"], []).append(d)
        gen = {}
        for b in blocks:
            g = {}
            for d in ordered.get(b["id"], []):
                g[d["var"]] = d["id"]
            gen[b["id"]] = g

        preds = {b["id"]: [p for p, _k in b["pred"]] for b in blocks}
        succs = {b["id"]: [s for s, _k in b["succ"]] for b in blocks}
        use_in = {}                              # per-block upward-exposed uses
        defd = {}                                # per-block def'd vars
        for b in blocks:
            uv, dfs = set(), set()
            for st in b["stmts"]:
                for u in st["uses"]:
                    if u not in dfs:             # use before local def
                        uv.add(u)
                for v, _k in st["defs"]:
                    dfs.add(v)
            # NOTE: params are function INPUTS, not entry-block instructions;
            # they stay out of defd so their value is live-in at entry
            use_in[b["id"]], defd[b["id"]] = uv, dfs

        # reaching definitions
        rd_in = {b["id"]: set() for b in blocks}
        rd_out = {b["id"]: set() for b in blocks}
        def_site_by_id = {d["id"]: d for d in all_defs}
        kill_pre = {}                            # def id -> ids killed
        for did, d in def_site_by_id.items():
            kill_pre[did] = {x["id"] for x in by_var[d["var"]]
                             if x["id"] != did}
        changed = True
        rounds = 0
        while changed and rounds < 100:
            changed, rounds = False, rounds + 1
            for b in blocks:
                i = set()
                for p in preds[b["id"]]:
                    i |= rd_out[p]
                o = set()
                for v, did in gen[b["id"]].items():
                    o.add(did)
                    o -= kill_pre[did]
                # defs in-block also kill earlier defs of same var arriving in
                killed = set()
                for did in o:
                    killed |= kill_pre[did]
                o |= (i - killed)
                if i != rd_in[b["id"]] or o != rd_out[b["id"]]:
                    rd_in[b["id"]], rd_out[b["id"]] = i, o
                    changed = True

        # chains: per use -> reaching def ids (local defs win; params only
        # when no local def reaches the use)
        chains = []
        for b in blocks:
            block_defs = ordered.get(b["id"], [])
            for st in b["stmts"]:
                at = st_index(b["stmts"], st)
                for u in st["uses"]:
                    strict = [d["id"] for d in block_defs
                              if d["var"] == u and d["kind"] != "param"
                              and d["stmt"] < at]
                    pdefs = [d["id"] for d in block_defs
                             if d["var"] == u and d["kind"] == "param"]
                    if strict:
                        srcs = strict
                    elif pdefs:
                        srcs = pdefs
                    else:
                        srcs = [did for did in rd_in[b["id"]]
                                if def_site_by_id[did]["var"] == u]
                    chains.append({"use": u, "block": b["id"],
                                   "line": st["line"],
                                   "stmt": st["spell"][:80],
                                   "defs": srcs[:8],
                                   "n_defs": len(srcs)})
        # liveness (backward)
        live_in = {b["id"]: set() for b in blocks}
        live_out = {b["id"]: set() for b in blocks}
        changed, rounds = True, 0
        while changed and rounds < 100:
            changed, rounds = False, rounds + 1
            for b in reversed(blocks):
                lo = set()
                for s in succs[b["id"]]:
                    lo |= live_in[s]
                li = use_in[b["id"]] | (lo - defd[b["id"]])
                if lo != live_out[b["id"]] or li != live_in[b["id"]]:
                    live_out[b["id"]], live_in[b["id"]] = lo, li
                    changed = True
        dfg = {"defs": all_defs,
               "chains": chains,
               "n_chains": len(chains),
               "undef_uses": [c for c in chains if not c["defs"]]}
        liveness = {"live_in": {str(b["id"]): sorted(live_in[b["id"]])
                                for b in blocks},
                    "live_out": {str(b["id"]): sorted(live_out[b["id"]])
                                 for b in blocks},
                    "params_live_at_entry": sorted(
                        {d["var"] for d in all_defs if d["kind"] == "param"}
                        & live_in[0])}
        return dfg, liveness


def st_index(stmts, st):
    for i, s in enumerate(stmts):
        if s is st:
            return i
    return 10 ** 9


def render_slice(res, max_lines=40):
    """Text rendering for demo transcript."""
    sc = res["scope"]
    L = [f"slice {sc['function']}  ({sc['file']}:{sc['line_span'][0]}-{sc['line_span'][1]})"
         f"  tool={res['tool_ver']}  cache_hit={res['cache']['hit']}"]
    c = res["cfg"]
    L.append(f"  CFG: {c['n_blocks']} blocks / {c['n_edges']} edges "
             f"(entry 0 -> exit {c['exit']})  compute {res['meta']['compute_ms']}ms")
    d = res["dfg"]
    L.append(f"  DFG: {len(d['defs'])} defs, {d['n_chains']} use-chains, "
             f"{len(d['undef_uses'])} possibly-undef uses")
    L.append(f"  params: {', '.join(p['name'] for p in sc['params'])}")
    L.append("  blocks (tag, stmts):")
    for b in c["blocks"][:14]:
        tag = f" [{b['tag']}]" if b["tag"] else ""
        heads = [f"{s['kind'].replace('_STMT','')}@{s['line']}" for s in b["stmts"][:3]]
        L.append(f"    B{b['id']}{tag}: {len(b['stmts'])} stmts  {'; '.join(heads)}"
                 + (" ..." if len(b["stmts"]) > 3 else ""))
    if len(c["blocks"]) > 14:
        L.append(f"    ... {len(c['blocks']) - 14} more blocks")
    L.append("  sample def-use chains:")
    shown = 0
    for ch in d["chains"]:
        if shown >= 6:
            break
        if ch["defs"]:
            dd = ", ".join(ch["defs"])
            L.append(f"    {ch['use']} @L{ch['line']}  <- defs [{dd}]  |{ch['stmt'][:46]}")
            shown += 1
    if d["undef_uses"]:
        L.append(f"  possibly-undef uses: "
                 + ", ".join(f"{u['use']}@L{u['line']}" for u in d["undef_uses"][:4]))
    lv = res["liveness"]
    L.append(f"  params live at entry: {', '.join(lv['params_live_at_entry']) or '(none)'}")
    return "\n".join(L[:max_lines])
