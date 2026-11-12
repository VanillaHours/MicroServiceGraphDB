---
page_id: adrs/README.md
okf_level: meta
claims: none
verified: none
---

# ADR ingest

Architecture Decision Records are **authored** knowledge: human-readable
decision statements anchored to citations the verifier can check. The store
started empty per POC-DESIGN; the first AUTHORED facts (ADR-0001..0003) are
ingested from FRR's own documentation (doc/user/*.rst), quote-validated by
the P4 verifier.

## Ingest rules

1. Every claim sentence ends with an atom chip [aXXXXXXX] defined in
   skeleton/adrs/<slug>.json.
2. Decision statements carry D-anchors: doc path + verbatim quote; the
   verifier whitespace-normalizes and greps the quote in the cited file.
3. Consequence statements carry machine refs: E (fused edge), S (stat),
   F (finding pointer), C (cluster), N (node).
4. Front matter: status (accepted/proposed), provenance: authored,
   verified: full once every claim resolves.
5. Unanchored claims are stripped and the page is stamped verified: partial.

## Format

See TEMPLATE.md.
