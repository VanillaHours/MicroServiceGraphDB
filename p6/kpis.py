#!/usr/bin/env python3
"""P6 KPI collector — one machine-readable KPI book for the POC.

Sections: indexing (stage-wise wall time + RAM + throughput) · storage (bytes
per artifact, KB-to-source ratio) · coverage (planes, joins, extractors) ·
answer quality (P/R eval + phase gates) · value (findings, joins grep cannot
do, determinism, cache economics).
Sources: recorded phase reports, fresh measurements (stage_timings.json,
eval_results.json), filesystem du. No invented numbers.
"""
import json
from pathlib import Path

import os  # portability: workspace root via MSG_ROOT (default <repo>/data)
ROOT = Path(os.environ.get("MSG_ROOT", str(Path(__file__).resolve().parents[1] / "data")))
DL = Path(os.environ.get("MSG_PUB", str(Path(__file__).resolve().parents[1] / "out")))
P6 = ROOT / "facts/p6"

timings = json.loads((P6 / "stage_timings.json").read_text())
evalr = json.loads((P6 / "eval_results.json").read_text())
agg = evalr["aggregate"]


def du(p):
    p = Path(p)
    if p.is_file():
        return p.stat().st_size
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())


# ---------------------------------------------------------------- indexing
census_loc = 1371970          # p0/CENSUS.md, code-bearing files repo-wide
slice_loc = 577163 + 12711    # bgpd+lib+zebra+ospfd (census loc_top) + staticd (source count)
t = timings["measured_today_2026-11-12"]
stages = [
    {"stage": "P0 build+schema freeze", "input": "frr-10.7.1 full repo",
     "wall": timings["recorded_at_phase_close"]["P0_build"]["wall_min"] + " min (2 cores, recorded)",
     "output": "compile_commands.json (836 KB), schema v0.1.0"},
    {"stage": "P1 extractors", "input": "356 TUs (lib,zebra,bgpd,ospfd,staticd)",
     "wall": "~8.5 min (recorded)", "throughput": "~42 TU/min",
     "output": "facts.duckdb 30,092 nodes / 81,750 edges"},
    {"stage": "P2 fusion", "input": "P1 facts + zapi_srv + lysc paths",
     "wall_s": t["P2_fusion_fuse.py"]["wall_s"],
     "max_rss_gb": t["P2_fusion_fuse.py"]["max_rss_gb"],
     "throughput": "13,908 fused edges/s",
     "output": "30,229 nodes / 54,246 fused edges, graph.json"},
    {"stage": "P3 clustering (Leiden sweep L1+L2+L3)", "input": "fused graph",
     "wall_s": t["P3_cluster.py"]["wall_s"],
     "max_rss_gb": t["P3_cluster.py"]["max_rss_gb"],
     "throughput": "~4,900 nodes/s (30,229-node code graph, 26 gamma points)",
     "output": "203 clusters (5+5+193), sweep.json"},
    {"stage": "P3 profiles+packs", "input": "clusters + graph + findings",
     "wall_s": t["P3_profile.py"]["wall_s"],
     "max_rss_gb": t["P3_profile.py"]["max_rss_gb"],
     "output": "203 no-LLM profiles, 5 domain packs"},
    {"stage": "P4 OKF publish (skeleton+render+verify)", "input": "P2+P3 facts",
     "wall_s": t["P4_publish_run_p4.py"]["wall_s"],
     "max_rss_gb": t["P4_publish_run_p4.py"]["max_rss_gb"],
     "output": "16 bundle pages, 454 anchored claims, 0 stripped"},
    {"stage": "P5 KB map load (serve-time)", "input": "P2 db + P3 + P4 bundle",
     "wall_ms": t["P5_kbmap_load_ms"]["median_ms"],
     "runs_ms": t["P5_kbmap_load_ms"]["runs_ms"],
     "output": "in-RAM map + entity indexes, fingerprint"},
]
cold_total = round(510 + 3.9 + 5.6 + 0.8 + 0.4, 1)   # P1..P4, excluding P0 build

# ----------------------------------------------------------------- storage
storage = {
    "facts_p2_duckdb": du(ROOT / "facts/p2/facts.duckdb"),
    "graph_json": du(ROOT / "facts/p2/graph.json"),
    "findings_json": du(ROOT / "facts/p2/findings.json"),
    "p3_artifacts": du(ROOT / "facts/p3") - du(ROOT / "facts/p3/packs"),
    "p3_packs": du(ROOT / "facts/p3/packs"),
    "p4_okf_bundle": du(ROOT / "facts/p4/okf-bundle"),
    "p4_skeleton": du(ROOT / "facts/p4/skeleton"),
    "p5_slice_cache": du(ROOT / "facts/p5/cache"),
    "p6_eval_artifacts": du(ROOT / "facts/p6"),
    "compile_commands": du(ROOT / "compile_commands.json"),
}
kb_total = sum(v for k, v in storage.items()
               if k not in ("compile_commands", "p6_eval_artifacts"))

# ----------------------------------------------------------------- quality
intents = agg["intents"]
quality = {
    "golden_set": {
        "n": agg["n_questions"],
        "gt_rule": "every expected key verified against pinned source "
                   "(token at file:line, dispatch/signature regex) or FRR doc "
                   "(normalized phrase grep); KB used for candidate enumeration "
                   "only",
        "gt_sources": json.loads(
            (P6 / "golden_set.json").read_text()) and {},
    },
    "routing_accuracy": agg["routing_accuracy"],
    "exact_answers": agg["exact_answers"],
    "latency_ms": agg["latency_ms"],
    "cache_repeat_hits": agg["cache_probe_hits"],
    "per_intent": intents,
    "phase_gates": {
        "P2_join_nb_yang": "426/426 (100%)",
        "P3_recall_vs_docs": "12/12 = 1.00 (bar 0.8)",
        "P4_claim_anchoring": "454/454, 0 stripped, 14/14 verified:full",
        "P5_exit_gates": "3/3 demo gates PASS",
        "P5_tests": "69/69", "P4_tests": "9/9", "P3_tests": "9/9",
        "P2_tests": "22/22",
    },
}
gs = json.loads((P6 / "golden_set.json").read_text())
from collections import Counter  # noqa: E402
quality["golden_set"]["gt_sources"] = dict(
    Counter(q["ground_truth"] for q in gs["questions"]))
quality["golden_set"]["by_intent"] = dict(
    Counter(q["intent"] for q in gs["questions"]))

# ------------------------------------------------------------------- value
value = {
    "structural_joins_beyond_grep": {
        "cross_service_zapi_flows": 111,
        "two_hop_hub_join": "svc:bgpd -publishes-> zapi:MSG <-handles- svc:zebra "
                            "resolved with per-hop evidence in 0.2-0.3ms; grep "
                            "cannot express this join in one command",
        "yang_leaf_to_zapi_side_effects": "82 side-effect messages for a bgpd "
                                          "route-map leaf via NB callbacks + "
                                          "call closure (grep_files_median=0)",
        "nb_yang_contract_join": "426/426 via libyang compiled paths",
    },
    "findings_surfaced": {"dead_registrations": 4, "dropped_on_wire": 7,
                          "orphan_handlers": 44},
    "grep_baseline": {
        "note": "single rg -w over the indexed slice; files_median per intent "
                "(raw noise to inspect; no evidence typing, no joins)",
        "files_median": {k: v.get("grep_files_median") for k, v
                         in intents.items()},
        "impact_grep_files_median": intents["impact"]["grep_files_median"],
    },
    "cache_economics": {
        "query_cache": "repeat Q 0.05-0.06ms vs 0.2-553ms cold (up to ~4 orders "
                       "of magnitude on impact)",
        "slice_cache": "495.8ms cold compute -> memoized hit; keyed by "
                       "(content-hash(scope), tool ver); 2 artifacts on disk",
        "kb_memo": "yang impact memoized per (id,depth): 553ms -> 0.1ms",
    },
    "determinism": {
        "P4_bundle": "byte-identical rebuild (tests T1)",
        "P6_end_to_end_rerun": timings["determinism_check"]["content_equality"]
        + "; 59/63 artifacts byte-identical, 4 volatile by design "
          "(duckdb layout, mtime-derived run_id/fingerprint)",
        "P3_cluster_ids": "seed-stable (min ARI 1.0 across seeds)",
    },
    "footprint": {
        "kb_bytes_total": kb_total,
        "kb_bytes_per_source_kloc": round(kb_total / (slice_loc / 1000)),
        "slice_loc_indexed": slice_loc,
        "repo_loc_census": census_loc,
    },
}

kpis = {"indexing_stages": stages, "cold_reindex_p1_to_p4_s": cold_total,
        "storage_bytes": storage, "quality": quality, "value": value,
        "eval_driven_fixes": [
            "intents.run_impact: new zapi-change mode (message impact = senders+handlers)",
            "kbmap linker: top-level decl preferred over nested duplicates",
            "kbmap linker: module mentions no longer swallow leaf ids (seen-marking)",
            "intents.run_docs: entity-less ADR keyword fallback over OKF bundle",
            "router: +1 docs rule ('where is X stored/configured') -> 65 rules",
        ]}
P6.mkdir(parents=True, exist_ok=True)
(P6 / "kpis.json").write_text(json.dumps(kpis, indent=1))
print("kpis.json written")
print("KB total:", round(kb_total / 1e6, 1), "MB |",
      round(kb_total / (slice_loc / 1000)), "bytes/KLOC")
print("exact:", agg["exact_answers"], "| routing:", agg["routing_accuracy"])
print("cold reindex P1->P4:", cold_total, "s")
