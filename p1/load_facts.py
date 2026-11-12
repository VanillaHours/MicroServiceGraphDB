#!/usr/bin/env python3
"""P1 fact loader — JSONL extractor outputs -> facts.duckdb (frozen schema).

Bulk-loads via DuckDB read_json (newline-delimited), dedups by primary keys,
drops edges with unknown endpoints, and writes one extractor_coverage row per
(extractor, plane) with a content-hash run_id.
"""
import hashlib
import json
from pathlib import Path

import duckdb

import os  # portability: workspace root via MSG_ROOT (default <repo>/data)
ROOT = Path(os.environ.get("MSG_ROOT", str(Path(__file__).resolve().parents[1] / "data")))
FACTS = ROOT / "facts/p1"
SCHEMA = ROOT / "schema/schema.sql"
DB_PATH = ROOT / "facts/facts.duckdb"


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16]


def run_id_of(files: list[Path]) -> str:
    h = hashlib.sha256()
    for f in files:
        h.update(f.read_bytes())
    return h.hexdigest()[:16]


def j(p: Path) -> str:
    return str(p).replace("'", "''")


def main():
    node_files = [f for f in (FACTS / "nodes.jsonl", FACTS / "yang_nodes.jsonl",
                              FACTS / "build_nodes.jsonl") if f.exists()]
    edge_files = [f for f in (FACTS / "edges.jsonl", FACTS / "yang_edges.jsonl",
                              FACTS / "build_edges.jsonl") if f.exists()]

    if DB_PATH.exists():
        DB_PATH.unlink()
    con = duckdb.connect(str(DB_PATH))
    con.execute(SCHEMA.read_text())

    for f in node_files:
        con.execute(f"""
            INSERT OR IGNORE INTO nodes (id, kind, label, service)
            SELECT id, kind, coalesce(label, ''), service
            FROM read_json('{j(f)}', format='newline_delimited',
                           columns={{'id':'VARCHAR','kind':'VARCHAR',
                                     'label':'VARCHAR','service':'VARCHAR'}})
        """)
    for f in edge_files:
        con.execute(f"""
            INSERT OR IGNORE INTO edges (src, rel, dst, plane, tag, src_ref)
            SELECT src, rel, dst, plane, tag, coalesce(src_ref, '')
            FROM read_json('{j(f)}', format='newline_delimited',
                           columns={{'src':'VARCHAR','rel':'VARCHAR','dst':'VARCHAR',
                                     'plane':'VARCHAR','tag':'VARCHAR','src_ref':'VARCHAR'}})
        """)

    # referential integrity: drop edges whose endpoints have no node
    dropped = con.execute("""
        SELECT count(*) FROM edges
        WHERE src NOT IN (SELECT id FROM nodes)
           OR dst NOT IN (SELECT id FROM nodes)
    """).fetchall()[0][0]
    con.execute("""
        DELETE FROM edges
        WHERE src NOT IN (SELECT id FROM nodes)
           OR dst NOT IN (SELECT id FROM nodes)
    """)

    # coverage ledger — unique counts computed from the loaded tables
    n_code_nodes = con.execute(
        "SELECT count(*) FROM nodes WHERE id LIKE 'code:%'").fetchall()[0][0]
    n_nb_nodes = con.execute(
        "SELECT count(*) FROM nodes WHERE id LIKE 'nb:%'").fetchall()[0][0]
    n_zapi_nodes = con.execute(
        "SELECT count(*) FROM nodes WHERE id LIKE 'zapi:%'").fetchall()[0][0]
    n_call_edges = con.execute(
        "SELECT count(*) FROM edges WHERE plane = 'code'").fetchall()[0][0]
    n_wiring_edges = con.execute(
        "SELECT count(*) FROM edges WHERE plane = 'wiring'").fetchall()[0][0]

    cov_rows = []
    rid_clang = run_id_of([FACTS / "nodes.jsonl", FACTS / "edges.jsonl"])
    if n_code_nodes or n_call_edges:
        cov_rows.append(("clang-facts", "code",
                         n_code_nodes + n_call_edges, rid_clang))
    if n_wiring_edges or n_nb_nodes or n_zapi_nodes:
        cov_rows.append(("clang-facts", "wiring",
                         n_wiring_edges + n_nb_nodes + n_zapi_nodes,
                         rid_clang))
    yang_cov = json.loads((FACTS / "yang_coverage.json").read_text())
    rid_yang = run_id_of([FACTS / "yang_nodes.jsonl",
                          FACTS / "yang_edges.jsonl"])
    cov_rows.append(("pyang", "contract",
                     yang_cov["nodes"] + yang_cov["edges"], rid_yang))
    build_cov = json.loads((FACTS / "build_coverage.json").read_text())
    rid_build = run_id_of([FACTS / "build_nodes.jsonl",
                           FACTS / "build_edges.jsonl"])
    cov_rows.append(("build-mapper", "build",
                     build_cov["nodes"] + build_cov["edges"], rid_build))
    con.executemany(
        "INSERT OR REPLACE INTO extractor_coverage VALUES (?, ?, ?, ?)",
        cov_rows)

    db_nodes = con.sql("SELECT count(*) FROM nodes").fetchall()[0][0]
    db_edges = con.sql("SELECT count(*) FROM edges").fetchall()[0][0]
    by_plane = con.sql(
        "SELECT plane, tag, count(*) FROM edges GROUP BY 1, 2 ORDER BY 1, 2"
    ).fetchall()
    per_dir = con.sql("""
        SELECT regexp_extract(id, '^code:([a-z0-9_]+)::', 1) AS dir, count(*)
        FROM nodes WHERE id LIKE 'code:%' GROUP BY 1 ORDER BY 2 DESC
    """).fetchall()
    summary = {
        "node_files": [f.name for f in node_files],
        "edge_files": [f.name for f in edge_files],
        "edges_referential_drop": dropped,
        "db_nodes": db_nodes,
        "db_edges": db_edges,
        "edges_by_plane_tag": [list(x) for x in by_plane],
        "code_nodes_by_dir": [list(x) for x in per_dir],
        "coverage_ledger": cov_rows,
        "db_path": str(DB_PATH),
    }
    con.close()
    (FACTS / "load_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
