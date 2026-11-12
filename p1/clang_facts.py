#!/usr/bin/env python3
"""P1 clang facts extractor — one parse pass per TU, five collectors.

Collectors (each reports coverage separately):
  decl     : functions, structs, enums, typedefs -> code:<dir>::<symbol> nodes
  call     : CALL_EXPR -> (caller calls callee, code, DECLARED, file:line)
  nb_reg   : frr_yang_module_info tables -> nb:<svc>:<xpath> handler tables,
             (nb handles code:fn) + (svc registers nb) wiring edges
  zapi_reg : zclient_handler tables ([ZEBRA_MSG] = fn)
             -> (svc handles zapi:MSG) + (code:fn handles zapi:MSG) wiring edges
  type     : ZEBRA_* message enum (lib/zclient.h) -> zapi:<MSG> nodes;
             send-fn bodies -> (code:fn publishes zapi:MSG) wiring edges

Usage: python3 clang_facts.py [--slice-dir lib,zebra,bgpd,staticd,ospfd]
                              [--out OUTDIR] [--limit N] [--verbose]
"""
import argparse
import gc
import glob
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

import clang.cindex as ci

# ---------------------------------------------------------------- paths
import os  # portability: workspace root via MSG_ROOT (default <repo>/data)
ROOT = Path(os.environ.get("MSG_ROOT", str(Path(__file__).resolve().parents[1] / "data")))
SRC = ROOT / "src/frr-10.7.1"
CC_PATH = ROOT / "compile_commands.json"
GCC_INC = glob.glob("/usr/lib/gcc/x86_64-linux-gnu/*/include")[0]
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


SO = _find_libclang()  # pip libclang wheel or system LLVM

ci.conf.set_library_file(SO)
ci.conf.set_compatibility_check(False)

DIRS = ["lib", "zebra", "bgpd", "staticd", "ospfd"]

# functions that take the ZEBRA_* message enum as (an early) argument
SEND_HELPER_FNS = {"zclient_create_header", "zebra_message_send"}


# ---------------------------------------------------------------- helpers
def rel_path(abs_or_rel: str) -> str:
    p = Path(abs_or_rel)
    if not p.is_absolute():
        p = (SRC / p).resolve()
    try:
        return str(p.relative_to(SRC))
    except ValueError:
        return str(p)


def dir_of(rel: str) -> str | None:
    head = rel.split("/", 1)[0]
    return head if head in DIRS else None


def top_dir_of(rel: str) -> str | None:
    """First path component for any in-tree file (slice or not)."""
    parts = rel.split("/", 1)
    if len(parts) == 1 or parts[0].startswith("."):
        return None
    return parts[0]


def sanitize_args(argv: list[str], base_dir: Path, src_file: str) -> list[str]:
    """compiledb argv -> libclang parse args (absolute includes, no dep flags,
    no trailing input-file token)."""
    out, skip_next = [], False
    src_name = Path(src_file).name
    for i, a in enumerate(argv):
        if i == 0:                      # compiler binary
            continue
        if skip_next:
            skip_next = False
            continue
        if a in ("-o", "-MF", "-MT", "-MQ"):
            skip_next = True
            continue
        if a in ("-c", "-MD", "-MP", "-MMD") or a.endswith(".o") or a.endswith(".lo"):
            continue
        # the input translation unit itself (relative or absolute)
        if a == src_file or a == src_name or a.endswith("/" + src_name):
            continue
        out.append(a)
    # absolutize include paths relative to the build dir
    fixed = []
    for a in out:
        if a.startswith("-I") and not a.startswith("-I/"):
            fixed.append("-I" + str((base_dir / a[2:]).resolve()))
        elif a.startswith("-isystem") and not a.startswith("-isystem/"):
            fixed.append("-isystem" + str((base_dir / a[8:]).resolve()))
        else:
            fixed.append(a)
    fixed += [f"-isystem{GCC_INC}", "-Wno-everything", "-ferror-limit=0"]
    return fixed


def _dd():
    return defaultdict(int)


# ---------------------------------------------------------------- extractor
class ClangFacts:
    def __init__(self):
        self.nodes = {}                       # id -> {kind,label,service}
        self.edges = []                       # (src,rel,dst,plane,tag,src_ref)
        self.by_label = defaultdict(list)     # symbol -> [node ids]
        self.cov = defaultdict(_dd)
        self.detail = defaultdict(_dd)
        self._id_seen = set()
        self._id_file_seen = set()   # (node id, defining file) pairs
        self.phase = "decls"         # pass 1 = decls only, pass 2 = facts

    # -- registry ------------------------------------------------------
    def add_node(self, nid, kind, label, service, cover, count_cov=True) -> bool:
        """Register node; returns True if newly created."""
        if nid in self._id_seen:
            return False
        self._id_seen.add(nid)
        self.nodes[nid] = {"kind": kind, "label": label, "service": service}
        if count_cov:
            self.cov[cover]["nodes"] += 1
        return True

    def add_edge(self, src, rel, dst, plane, tag, ref, cover):
        self.edges.append((src, rel, dst, plane, tag, ref))
        self.cov[cover]["edges"] += 1

    # -- decl ----------------------------------------------------------
    def collect_decl(self, cursor, tu_dir):
        k = cursor.kind
        name = cursor.spelling
        if not name:
            return
        kind = {ci.CursorKind.FUNCTION_DECL: "function",
                ci.CursorKind.STRUCT_DECL: "struct",
                ci.CursorKind.ENUM_DECL: "enum",
                ci.CursorKind.TYPEDEF_DECL: "type"}[k]
        f = rel_path(str(cursor.location.file)) if cursor.location.file else "?"
        if not f.startswith(tu_dir + "/"):
            return        # decl from another dir's header: its own dir owns it
        nid = f"code:{tu_dir}::{name}"
        if (nid, f) in self._id_file_seen:
            return                    # same symbol re-encountered in same TU
        if nid in self._id_seen:
            # same dir, different file -> file-qualified canonical id
            stem = Path(f).stem
            nid = f"code:{tu_dir}::{stem}::{name}"
            self.detail["decl"]["collisions"] += 1
        self._id_file_seen.add((nid, f))
        if self.add_node(nid, kind, name, f"svc:{tu_dir}", "decl"):
            self.by_label[name].append(nid)

    # -- call (semantic resolution via cursor.referenced) -----------------
    def collect_call(self, cursor, tu_dir, enclosing, ref_file):
        if cursor.kind != ci.CursorKind.CALL_EXPR or enclosing is None:
            return
        callee = cursor.referenced
        if callee is None or callee.kind != ci.CursorKind.FUNCTION_DECL:
            self.detail["call"]["unresolved_ptr"] += 1   # fn-pointer call
            return
        if callee.location.file is None:
            self.detail["call"]["unresolved_nofile"] += 1
            return
        rel = rel_path(str(callee.location.file))
        if rel.startswith("/") or rel.startswith(".."):
            self.detail["call"]["external"] += 1         # system headers etc.
            return
        tdir = top_dir_of(rel)
        if tdir is None:
            self.detail["call"]["external"] += 1
            return
        name = callee.spelling
        dst = f"code:{tdir}::{name}"
        # create the target node on demand (pass-1 decl set may miss it)
        self.add_node(dst, "function", name, f"svc:{tdir}", "call")
        ref = f"{rel_path(str(ref_file))}:{cursor.location.line}"
        self.add_edge(f"code:{tu_dir}::{enclosing}", "calls", dst,
                      "code", "DECLARED", ref, "call")

    # -- nb_reg ----------------------------------------------------------
    def _designated_fields(self, init_cursor):
        """{(field, value_node) or (None, value_node)} for init list children.
        clang tokenizes `.xpath` as two tokens ('.', 'xpath')."""
        for child in init_cursor.get_children():
            field = None
            toks = [t.spelling for t in child.get_tokens()][:4]
            if toks:
                if toks[0] == "." and len(toks) >= 2:
                    field = toks[1]
                elif toks[0].startswith(".") and len(toks[0]) > 1:
                    field = toks[0][1:]
                if field and field.endswith("="):
                    field = field[:-1]
            yield field, child

    def _string_value(self, node):
        for sub in node.walk_preorder():
            if sub.kind == ci.CursorKind.STRING_LITERAL:
                return sub.spelling.strip('"')
        return None

    def _fn_ref(self, node):
        """First DECL_REF_EXPR spelling reachable under node."""
        for sub in node.walk_preorder():
            if sub.kind == ci.CursorKind.DECL_REF_EXPR:
                return sub.spelling
        return None

    def _fn_target(self, node, tu_dir):
        """Semantic fn target id from a DECL_REF_EXPR (decl file's dir)."""
        ref = node.referenced
        if ref is not None and ref.location.file is not None:
            rel = rel_path(str(ref.location.file))
            if not rel.startswith("/"):
                td = top_dir_of(rel)
                if td:
                    return f"code:{td}::{ref.spelling}", ref.spelling
        return f"code:{tu_dir}::{node.spelling}", node.spelling

    def collect_nb_reg(self, cursor, tu_dir, ref_file):
        if cursor.kind != ci.CursorKind.INIT_LIST_EXPR:
            return
        xpath_val, cbs_node = None, None
        for field, val in self._designated_fields(cursor):
            if field == "xpath":
                xpath_val = self._string_value(val)
            elif field == "cbs":
                cbs_node = val
        if not xpath_val or cbs_node is None:
            return
        # the callback init list is nested one level below the designated
        # `.cbs = {...}` child (UNEXPOSED_EXPR -> INIT_LIST_EXPR)
        cb_list = None
        for sub in cbs_node.walk_preorder():
            if sub.kind == ci.CursorKind.INIT_LIST_EXPR:
                cb_list = sub
                break
        self.detail["nb_reg"]["tables"] += 1
        nb_id = f"nb:{tu_dir}:{xpath_val.lstrip('/')}"
        svc = f"svc:{tu_dir}"
        ref = f"{rel_path(str(ref_file))}:{cursor.location.line}"
        self.add_node(nb_id, "handler-table", xpath_val, svc, "nb_reg")
        self.add_edge(svc, "registers", nb_id, "wiring", "DECLARED", ref,
                      "nb_reg")
        if cb_list is None:
            self.detail["nb_reg"]["cb_list_missing"] += 1
            return
        for field, val in self._designated_fields(cb_list):
            fn_node = self._first_decl_ref(val)
            if fn_node is None or not field:
                self.detail["nb_reg"]["cb_unresolved"] += 1
                continue
            fn_id, fn = self._fn_target(fn_node, tu_dir)
            if fn_id not in self._id_seen:
                self.add_node(fn_id, "function", fn, f"svc:{tu_dir}",
                              "nb_reg")
            self.add_edge(nb_id, "handles", fn_id, "wiring", "DECLARED", ref,
                          "nb_reg")

    # -- zapi_reg --------------------------------------------------------
    def _first_decl_ref(self, node):
        """First DECL_REF_EXPR cursor under node (returns cursor, not name)."""
        for sub in node.walk_preorder():
            if sub.kind == ci.CursorKind.DECL_REF_EXPR:
                return sub
        return None

    def collect_zapi_reg(self, cursor, tu_dir, ref_file):
        if cursor.kind != ci.CursorKind.INIT_LIST_EXPR:
            return
        if "zclient_handler" not in cursor.type.spelling:
            return
        svc = f"svc:{tu_dir}"
        self.detail["zapi_reg"]["tables"] += 1
        ref = f"{rel_path(str(ref_file))}:{cursor.location.line}"
        for child in cursor.get_children():
            idx_name = None
            fn_node = None
            for sub in child.walk_preorder():
                if sub.kind == ci.CursorKind.DECL_REF_EXPR:
                    if idx_name is None:
                        idx_name = sub.spelling
                    fn_node = sub
            if not idx_name or fn_node is None or \
                    not idx_name.startswith("ZEBRA_") or \
                    fn_node.spelling == idx_name:
                self.detail["zapi_reg"]["entry_unresolved"] += 1
                continue
            msg = f"zapi:{idx_name}"
            self.add_node(msg, "message", idx_name, None, "type")
            fn_id, fn = self._fn_target(fn_node, tu_dir)
            if fn_id not in self._id_seen:
                self.add_node(fn_id, "function", fn, svc, "zapi_reg")
            self.add_edge(svc, "handles", msg, "wiring", "DECLARED", ref,
                          "zapi_reg")
            self.add_edge(fn_id, "handles", msg, "wiring", "DECLARED", ref,
                          "zapi_reg")

    # -- type --------------------------------------------------------------
    def collect_type(self, cursor, tu_dir, ref_file, enclosing):
        # (a) ZEBRA_* message enumerators — only from lib/zclient.h
        if cursor.kind == ci.CursorKind.ENUM_DECL and \
                ref_file is not None and \
                Path(rel_path(str(ref_file))).name == "zclient.h":
            for en in cursor.get_children():
                if en.kind == ci.CursorKind.ENUM_CONSTANT_DECL and \
                        en.spelling.startswith("ZEBRA_"):
                    self.add_node(f"zapi:{en.spelling}", "message",
                                  en.spelling, None, "type")
            return
        # (b) send-side publishes — enum ref may sit under implicit casts
        if cursor.kind == ci.CursorKind.CALL_EXPR and enclosing:
            callee = cursor.referenced
            if callee is None or callee.spelling not in SEND_HELPER_FNS:
                return
            for arg in cursor.get_children():
                for sub in arg.walk_preorder():
                    if sub.kind == ci.CursorKind.DECL_REF_EXPR and \
                            sub.spelling.startswith("ZEBRA_"):
                        msg = f"zapi:{sub.spelling}"
                        self.add_node(msg, "message", sub.spelling, None,
                                      "type")
                        self.add_edge(
                            f"code:{tu_dir}::{enclosing}", "publishes", msg,
                            "wiring", "DECLARED",
                            f"{rel_path(str(ref_file))}:{cursor.location.line}",
                            "type")
                        self.detail["type"]["publishes"] += 1

    # -- walker ------------------------------------------------------------
    def walk(self, cursor, tu_dir, enclosing=None, ref_file=None, depth=0):
        if depth > 60:
            return
        k = cursor.kind
        if ref_file is None and cursor.location.file:
            ref_file = cursor.location.file
        if k in (ci.CursorKind.FUNCTION_DECL, ci.CursorKind.STRUCT_DECL,
                 ci.CursorKind.ENUM_DECL, ci.CursorKind.TYPEDEF_DECL):
            self.collect_decl(cursor, tu_dir)
            if self.phase == "decls":
                # pass 1: symbol table only; recurse into functions for decls
                for ch in cursor.get_children():
                    self.walk(ch, tu_dir, enclosing, ref_file, depth + 1)
                return
            if k == ci.CursorKind.FUNCTION_DECL:
                old = enclosing
                enclosing = cursor.spelling
                for ch in cursor.get_children():
                    self.walk(ch, tu_dir, enclosing, ref_file, depth + 1)
                return
        if k == ci.CursorKind.INIT_LIST_EXPR:
            self.collect_nb_reg(cursor, tu_dir, ref_file)
            self.collect_zapi_reg(cursor, tu_dir, ref_file)
        self.collect_type(cursor, tu_dir, ref_file, enclosing)
        self.collect_call(cursor, tu_dir, enclosing, ref_file)
        for ch in cursor.get_children():
            self.walk(ch, tu_dir, enclosing, ref_file, depth + 1)

    # -- driver --------------------------------------------------------------
    def merge_result(self, res):
        """Merge a worker's (nodes, edges, detail, cov) payload into self.
        cov comes from the worker (already counted there) — no re-count."""
        for nid, (kind, label, service, _cover) in res["nodes"].items():
            if self.add_node(nid, kind, label, service, _cover,
                             count_cov=False) and \
                    kind in ("function", "struct", "enum", "type"):
                self.by_label[label].append(nid)
        self.edges.extend(res["edges"])
        for stage, vals in res["detail"].items():
            for k, v in vals.items():
                if isinstance(v, (int, float)):
                    self.detail[stage][k] += v
                else:
                    self.detail[stage][k] = v
        for stage, vals in res["cov"].items():
            for k, v in vals.items():
                self.cov[stage][k] += v

    def run(self, entries, verbose=False):
        """Two-pass extraction. Every TU parses inside a short-lived forked
        child: a libclang crash or hang loses only that TU (recorded as a
        skip in the coverage ledger, never silently)."""
        t0 = time.time()
        n = len(entries)

        # pass 1: symbol table (decls only)
        workdir = ROOT / "facts/p1/work"
        workdir.mkdir(parents=True, exist_ok=True)
        skipped = {}
        for i, e in enumerate(entries):
            res, err = run_isolated(e, "decls", None, workdir)
            if err:
                skipped[e["file"]] = err
                continue
            if res:
                self.merge_result(res)
            if verbose and (i + 1) % 25 == 0:
                print(f"  [decls] {i+1}/{n} ({time.time()-t0:.0f}s) "
                      f"nodes={len(self.nodes)}", file=sys.stderr)
        # one retry round for transient failures
        for f, err in list(skipped.items()):
            e = next(x for x in entries if x["file"] == f)
            res, err2 = run_isolated(e, "decls", None, workdir)
            if err2:
                continue          # keep the original error
            del skipped[f]
            if res:
                self.merge_result(res)
        if skipped:
            self.detail["decl"]["skipped_files"] = skipped
            self.detail["decl"]["skip_count"] = len(skipped)

        # pass 2: fact edges with the complete symbol table
        import pickle
        label_snapshot = dict(self.by_label)
        label_path = ROOT / "facts/p1/work/labels.pkl"
        label_path.parent.mkdir(parents=True, exist_ok=True)
        with open(label_path, "wb") as fh:
            pickle.dump(label_snapshot, fh, protocol=pickle.HIGHEST_PROTOCOL)
        skipped2 = {}
        for i, e in enumerate(entries):
            res, err = run_isolated(e, "facts", label_path, workdir)
            if err:
                skipped2[e["file"]] = err
                continue
            if res:
                self.merge_result(res)
            if verbose and (i + 1) % 25 == 0:
                print(f"  [facts] {i+1}/{n} ({time.time()-t0:.0f}s) "
                      f"nodes={len(self.nodes)} edges={len(self.edges)}",
                      file=sys.stderr)
        for f, err in list(skipped2.items()):
            e = next(x for x in entries if x["file"] == f)
            res, err2 = run_isolated(e, "facts", label_path, workdir)
            if err2:
                continue
            del skipped2[f]
            if res:
                self.merge_result(res)
        if skipped2:
            self.detail["facts"]["skipped_files"] = skipped2
            self.detail["facts"]["skip_count"] = len(skipped2)
        return time.time() - t0


def run_isolated(e, phase, label_path, workdir, timeout=240):
    """Parse one TU in a fresh subprocess (file I/O, no fork hazards).
    Returns (payload, error_reason)."""
    import subprocess
    task = workdir / f"task.json"
    out = workdir / "result.json"
    task.write_text(json.dumps({"entry": e, "phase": phase,
                                "label_path": str(label_path) if label_path else None}))
    if out.exists():
        out.unlink()
    try:
        r = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--worker",
             str(task), str(out)],
            timeout=timeout, capture_output=True, text=True)
    except subprocess.TimeoutExpired:
        return None, "timeout"
    if r.returncode != 0:
        tail = (r.stderr or "")[-200:].strip().replace("\n", " | ")
        return None, f"crash(exit={r.returncode}): {tail}"
    if not out.exists():
        return None, "no-result"
    return json.loads(out.read_text()), None


def _worker_main(task_path: str, out_path: str):
    task = json.loads(Path(task_path).read_text())
    e = task["entry"]
    phase = task["phase"]
    ex = ClangFacts()
    ex.phase = phase
    if task.get("label_path"):
        import pickle
        ex.by_label.update(pickle.load(open(task["label_path"], "rb")))
    p = Path(e["file"]) if Path(e["file"]).is_absolute() else SRC / e["file"]
    detail = {"decl": {}, "facts": {}}
    cov = {}
    if not p.exists():
        detail[phase]["missing_files"] = 1
        Path(out_path).write_text(json.dumps(
            {"nodes": {}, "edges": [], "detail": detail, "cov": cov}))
        return
    tu_dir = dir_of(e["file"])
    if tu_dir is None:
        Path(out_path).write_text(json.dumps(
            {"nodes": {}, "edges": [], "detail": detail, "cov": cov}))
        return
    index = ci.Index.create()
    tu = index.parse(str(p),
                     args=sanitize_args(e["arguments"], Path(e["_dir"]),
                                        e["file"]),
                     options=0x1000)  # CXTranslationUnit_KeepGoing
    if phase == "decls":
        if [d for d in tu.diagnostics if d.severity >= 3]:
            detail["decl"]["tu_with_errors"] = 1
        ex.walk(tu.cursor, tu_dir)
        cov["decl"] = {"tus": 1}
    else:
        ex.walk(tu.cursor, tu_dir)
        cov["facts"] = {"tus": 1}
    Path(out_path).write_text(json.dumps(
        {"nodes": {k: (v["kind"], v["label"], v["service"], _cover_of(k, v))
                   for k, v in ex.nodes.items()},
         "edges": ex.edges,
         "detail": {k: dict(v) for k, v in ex.detail.items()},
         "cov": {k: dict(v) for k, v in ex.cov.items()}}))


def _cover_of(nid_key, v):
    if v["kind"] == "handler-table":
        return "nb_reg"
    if v["kind"] == "message":
        return "type"
    return "decl"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slice-dir", default=",".join(DIRS))
    ap.add_argument("--out", default=str(ROOT / "facts/p1"))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--worker", nargs=2, metavar=("TASK", "OUT"),
                    help=argparse.SUPPRESS)
    a = ap.parse_args()

    if a.worker:
        _worker_main(a.worker[0], a.worker[1])
        return

    slice_dirs = set(a.slice_dir.split(","))
    cc = json.loads(CC_PATH.read_text())
    for e in cc:
        e["_dir"] = e["directory"]
    entries = [e for e in cc if dir_of(e["file"]) in slice_dirs]
    if a.limit:
        entries = entries[:a.limit]
    print(f"extracting {len(entries)} TUs from {sorted(slice_dirs)}",
          file=sys.stderr)

    ex = ClangFacts()
    dt = ex.run(entries, verbose=a.verbose)

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "nodes.jsonl").write_text(
        "\n".join(json.dumps({"id": k, **v}) for k, v in ex.nodes.items()))
    (out / "edges.jsonl").write_text(
        "\n".join(json.dumps(
            {"src": s, "rel": r, "dst": d, "plane": p, "tag": t,
             "src_ref": rf}) for s, r, d, p, t, rf in ex.edges))
    cov = {k: dict(v) for k, v in ex.cov.items()}
    det = {k: dict(v) for k, v in ex.detail.items()}
    (out / "coverage.json").write_text(json.dumps(
        {"runtime_s": round(dt, 1), "tus_total": len(entries),
         "slice_dirs": sorted(slice_dirs), "coverage": cov, "detail": det,
         "nodes_total": len(ex.nodes), "edges_total": len(ex.edges)},
        indent=2))
    print(json.dumps({"runtime_s": round(dt, 1), "nodes": len(ex.nodes),
                      "edges": len(ex.edges), "coverage": cov,
                      "detail": det}, indent=2))


if __name__ == "__main__":
    main()
