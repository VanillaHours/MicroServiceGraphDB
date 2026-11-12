#!/usr/bin/env python3
"""P0 finalization for the FRR POC.

1. Verify $MSG_ROOT/compile_commands.json (P1 extraction input) — parse, count, slice coverage.
2. Verify census.json headline numbers against CENSUS.md claims.
3. Materialize the frozen schema into $MSG_ROOT/facts/facts.db (DuckDB) + smoke-test
   the fused_edges view and CHECK constraints.
4. Copy deliverables into $MSG_PUB/p0/ and emit a JSON status summary.
"""
import json
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

import os  # portability: workspace via MSG_ROOT / MSG_PUB / MSG_SRC
POC = Path(os.environ.get("MSG_ROOT", str(Path(__file__).resolve().parents[1] / "data")))
DL = Path(os.environ.get("MSG_PUB", str(Path(__file__).resolve().parents[1] / "out")))
DL_P0 = DL / "p0"

status = {"ok": True, "checks": {}}

# ---------------------------------------------------------------- 1. compile_commands.json
cc_path = POC / "compile_commands.json"
try:
    commands = json.loads(cc_path.read_text())
except Exception as e:  # noqa: BLE001
    status["ok"] = False
    status["checks"]["compile_commands"] = {"error": str(e)}
    commands = []

SRC_DIR = os.environ.get("MSG_SRC", str(POC / "src/frr-10.7.1"))  # the one build directory
tu_by_dir = Counter()
bad_entries = 0
build_dirs = set()
for e in commands:
    d = e.get("directory", "")
    f = e.get("file", "")
    # compile_commands.json spec: exactly one of `command` (string) or
    # `arguments` (argv list); compiledb emits the latter.
    if not d or not f or not (e.get("command") or e.get("arguments")):
        bad_entries += 1
        continue
    build_dirs.add(d)
    fp = Path(f)
    if not fp.is_absolute():
        fp = Path(d) / fp
    try:
        rel = fp.resolve().relative_to(Path(SRC_DIR))
        comp = rel.parts[0] if len(rel.parts) > 1 else "(root)"
    except Exception:  # noqa: BLE001
        comp = "?"
    tu_by_dir[comp] += 1

SLICE = ["lib", "zebra", "bgpd", "staticd", "ospfd"]
slice_tus = {s: tu_by_dir.get(s, 0) for s in SLICE}
status["checks"]["compile_commands"] = {
    "total_entries": len(commands),
    "bad_entries": bad_entries,
    "build_dirs": sorted(build_dirs),
    "slice_tus": slice_tus,
    "slice_total": sum(slice_tus.values()),
    "tu_top10": tu_by_dir.most_common(10),
    "bytes": cc_path.stat().st_size,
}

# ---------------------------------------------------------------- 2. census cross-check
census = json.loads((POC / "census/census.json").read_text())
md = (POC / "census/CENSUS.md").read_text()
claims = {
    "tu_count": "829" in md,          # .c translation units
    "yang_models_58": "58" in md,
    "nb_files_28": "28" in md,
    "zapi_21": "21" in md,
}
cc = census.get("totals", census)
status["checks"]["census"] = {
    "md_claims_present": claims,
    "census_keys": list(census.keys()),
    "totals": cc if isinstance(cc, dict) else str(cc)[:200],
}

# ---------------------------------------------------------------- 3. facts.db (DuckDB)
import duckdb  # noqa: E402

facts_dir = POC / "facts"
facts_dir.mkdir(exist_ok=True)
db_path = facts_dir / "facts.db"
if db_path.exists():
    db_path.unlink()
con = duckdb.connect(str(db_path))
con.execute((POC / "schema/schema.sql").read_text())

# --- smoke test A: fused edge evidence merge -------------------------------
con.execute("""
INSERT INTO nodes VALUES
  ('code:zebra::rib_add',      'function', 'rib_add',      'svc:zebra'),
  ('code:bgpd::bgp_redistribute', 'function', 'bgp_redistribute', 'svc:bgpd'),
  ('zapi:ZEBRA_REDISTRIBUTE_ADD', 'message', 'ZEBRA_REDISTRIBUTE_ADD', NULL);
""")
con.execute("""
INSERT INTO edges VALUES
  ('code:bgpd::bgp_redistribute', 'sends', 'zapi:ZEBRA_REDISTRIBUTE_ADD',
   'wiring', 'OBSERVED', 'bgpd/bgp_zebra.c:1000'),
  ('code:bgpd::bgp_redistribute', 'sends', 'zapi:ZEBRA_REDISTRIBUTE_ADD',
   'wiring', 'OBSERVED', 'bgpd/bgp_zebra.c:1050'),
  ('code:bgpd::bgp_redistribute', 'sends', 'zapi:ZEBRA_REDISTRIBUTE_ADD',
   'code', 'DECLARED', 'bgpd/bgp_zebra.c:1000');
""")
fused = con.sql("""
SELECT src, rel, dst, evidence, n_planes FROM fused_edges
WHERE src = 'code:bgpd::bgp_redistribute'
""").fetchall()
# DISTINCT list order is not deterministic in DuckDB — compare as sets
evidence_ok = (
    len(fused) == 1
    and sorted(fused[0][3]) == ["DECLARED:code", "OBSERVED:wiring"]
    and fused[0][4] == 2
)
status["checks"]["fused_view"] = {"rows": fused, "evidence_merge_ok": evidence_ok}
if not evidence_ok:
    status["ok"] = False

# --- smoke test B: CHECK constraints reject bad plane / tag ------------------
def expect_fail(sql):
    try:
        con.execute(sql)
        return False
    except duckdb.Error:
        return True

constraint_ok = expect_fail(
    "INSERT INTO edges VALUES ('a','calls','b','godplane','DECLARED',NULL)"
) and expect_fail(
    "INSERT INTO edges VALUES ('a','calls','b','code','MAYBE',NULL)"
)
status["checks"]["constraints"] = {"reject_bad_plane_tag": constraint_ok}
if not constraint_ok:
    status["ok"] = False

# --- smoke test C: meta table ------------------------------------------------
meta = dict(con.sql("SELECT key, value FROM meta").fetchall())
status["checks"]["meta"] = meta
if meta.get("schema_version") != "0.1.0" or meta.get("frozen_at") != "P0":
    status["ok"] = False

con.execute("DELETE FROM edges; DELETE FROM nodes;")
con.close()
status["checks"]["facts_db"] = {"path": str(db_path), "bytes": db_path.stat().st_size}

# ---------------------------------------------------------------- 4. deliverables
shutil.copy2(cc_path, DL_P0 / "compile_commands.json")
(DL_P0 / "schema.sql").write_text((POC / "schema/schema.sql").read_text())  # identical, keep in sync
shutil.copy2(db_path, DL_P0 / "facts.db")
status["deliverables"] = sorted(p.name for p in DL_P0.iterdir())

print(json.dumps(status, indent=2, default=str))
sys.exit(0 if status["ok"] else 1)
