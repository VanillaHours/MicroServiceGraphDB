-- ============================================================================
-- FRR POC — Fact Schema v0.1.0 (FROZEN at P0)
-- Any change after this point requires a version bump in meta + a migration note.
--
-- Canonical ID scheme:
--   code:<dir>::<symbol>       e.g. code:zebra::rib_add          (functions, structs)
--   svc:<dir>                  e.g. svc:bgpd                     (daemon / service)
--   yang:<module>:<node-path>  e.g. yang:frr-zebra:route         (contract plane)
--   zapi:<MESSAGE_NAME>        e.g. zapi:ZEBRA_INTERFACE_ADD     (wiring plane)
--   nb:<dir>:<yang-path>       e.g. nb:bgpd:frr-bgp:bgp/neighbors (NB handler tables)
--   adr:<id>                   e.g. adr:0001                     (human plane)
--   cluster:<slug>             e.g. cluster:bgp-fabric           (analytics artifacts)
--
-- Provenance: every edge row is one evidence item.
--   plane: code|contract|wiring|build|runtime|human
--   tag:   DECLARED|CONFIGURED|OBSERVED|AUTHORED|BUILD
--   Authority order for reads: OBSERVED > CONFIGURED > DECLARED (AUTHORED for "why")
-- ============================================================================

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
INSERT OR REPLACE INTO meta VALUES ('schema_version', '0.1.0');
INSERT OR REPLACE INTO meta VALUES ('frozen_at', 'P0');
INSERT OR REPLACE INTO meta VALUES ('frr_tag', 'frr-10.7.1');
INSERT OR REPLACE INTO meta VALUES ('frr_tarball_sha256',
    'b8fd6590f0f53ccd661e8c3e3a0d997f9014b62c8ed03a42e51e93291373ae52');
INSERT OR REPLACE INTO meta VALUES ('id_scheme', 'code|svc|yang|zapi|nb|adr|cluster');

CREATE TABLE IF NOT EXISTS nodes (
    id      TEXT PRIMARY KEY,          -- canonical ID (scheme above)
    kind    TEXT NOT NULL,             -- function|struct|enum|daemon|yang-node|message|handler-table|adr|cluster
    label   TEXT NOT NULL,             -- human-readable
    service TEXT                        -- owning svc:<dir> when applicable, else NULL
);

CREATE TABLE IF NOT EXISTS edges (
    src     TEXT NOT NULL,             -- node id
    rel     TEXT NOT NULL,             -- calls|imports|publishes|handles|sends|typed_as|generated_from|registers|decided|member_of
    dst     TEXT NOT NULL,             -- node id
    plane   TEXT NOT NULL CHECK (plane IN ('code','contract','wiring','build','runtime','human')),
    tag     TEXT NOT NULL CHECK (tag IN ('DECLARED','CONFIGURED','OBSERVED','AUTHORED','BUILD')),
    src_ref TEXT,                      -- file:line | trace id | meeting note path
    PRIMARY KEY (src, rel, dst, plane, src_ref)
);

-- A fused edge = same (src, rel, dst) seen from multiple planes.
-- Evidence list per edge; authority applied at read time.
CREATE VIEW IF NOT EXISTS fused_edges AS
SELECT src, rel, dst,
       list(DISTINCT tag || ':' || plane)             AS evidence,
       count(DISTINCT plane)                          AS n_planes
FROM edges
GROUP BY src, rel, dst;

-- P2 discrepancy queries (declared but never observed, etc.) build on fused_edges;
-- their exact predicates are fused-mode concerns, deliberately NOT frozen here.

-- Extractor coverage ledger (per P1): one row per (extractor, plane) with the
-- fact count it produced, so silent gaps are visible in every rebuild.
CREATE TABLE IF NOT EXISTS extractor_coverage (
    extractor TEXT NOT NULL,           -- clang-facts|pyang|build-mapper|trace-ingester
    plane     TEXT NOT NULL,
    facts     INTEGER NOT NULL,
    run_id    TEXT NOT NULL,           -- content-hash of inputs
    PRIMARY KEY (extractor, plane, run_id)
);
