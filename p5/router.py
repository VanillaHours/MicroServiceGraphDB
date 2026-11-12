#!/usr/bin/env python3
"""P5 router v0 — rule-based intent classification over the KB (no LLM).

Six intents (POC-DESIGN.md P5 note):
  impact  — what breaks / who is affected when X changes
  path    — how do X and Y connect (evidence-carried hop list)
  explain — what is X / show X's relations
  callers — who calls X / who sends / who handles message M
  slice   — dataflow / control-flow / lifetime inside function F (/slice)
  docs    — documentation, responsibilities, architecture (P3 packs + P4 OKF)

The classifier is a transparent weighted-keyword scorer: every decision ships
its fired rules and scores, so the S1-model router can later drop in behind the
same interface and be A/B-compared (design note, P5).
"""
import re

INTENTS = ["slice", "callers", "impact", "path", "docs", "explain"]  # tie-break order

# (intent, regex, weight) — first match per rule wins, all fires recorded
RULES = [
    ("slice", r"\bslice\b", 3),
    ("slice", r"\bdataflow\b|\bdata flow\b", 3),
    ("slice", r"\bdef-?use\b", 3),
    ("slice", r"\bcontrol flow\b|\bcfg\b", 3),
    ("slice", r"\blifetime\b|\bliveness\b|\blive range\b", 3),
    ("slice", r"where does\b.+\b(value|variable|param\w*|pointer|buffer)\b", 3),
    ("slice", r"\b(variable|param\w*|value)\b.{0,24}\b(set|assigned|originat|defined)\b", 2),
    ("slice", r"\bflows? (through|of|into)\b", 2),
    ("slice", r"\breaching definition", 3),

    ("callers", r"who calls\b", 3),
    ("callers", r"\bcaller", 3),
    ("callers", r"\bcall sites?\b", 3),
    ("callers", r"who sends?\b", 3),
    ("callers", r"\bsenders?\b", 3),
    ("callers", r"who handles\b", 3),
    ("callers", r"\bhandled by\b|\bhandled via\b", 3),
    ("callers", r"\bhandlers?\b", 2),
    ("callers", r"\bdispatch", 2),
    ("callers", r"publish(es|ed)? by\b", 3),
    ("callers", r"who registers\b|\bregistered by\b", 3),
    ("callers", r"who produces\b|\bproduced by\b", 3),
    ("callers", r"who consumes\b|\bconsumed by\b", 3),
    ("callers", r"who emits\b", 3),

    ("impact", r"\bimpact", 3),
    ("impact", r"\baffect", 3),
    ("impact", r"what happens if\b", 3),
    ("impact", r"if we (change|remove|delete|drop|rename)\b", 3),
    ("impact", r"\bbreak", 2),
    ("impact", r"who uses\b|\bused by\b|\busers of\b", 2),
    ("impact", r"side effects?\b", 2),
    ("impact", r"\bripple", 3),
    ("impact", r"\bdependen", 2),
    ("impact", r"\bdelete\b|\bremove\b", 1),

    ("path", r"\bpath\b", 3),
    ("path", r"\bfrom\b.+\bto\b", 2),
    ("path", r"\bbetween\b.+\band\b", 2),
    ("path", r"how does\b.+\b(reach|talk|send|communicate|connect)", 3),
    ("path", r"\bhops?\b", 2),
    ("path", r"message flow", 3),
    ("path", r"\bconnect", 2),
    ("path", r"who does\b.+\bgo through\b", 3),
    ("path", r"route.{0,20}\b(between|from|to)\b", 2),

    ("docs", r"\bdocs?\b", 3),
    ("docs", r"\bdocumentation\b", 3),
    ("docs", r"\barchitecture\b", 3),
    ("docs", r"\bdesign(ed)?\b", 2),
    ("docs", r"responsib", 3),
    ("docs", r"\bpurpose\b|\brole\b", 2),
    ("docs", r"what does\b.+\bdo\b", 2),
    ("docs", r"\boverview\b", 3),
    ("docs", r"high[- ]level\b", 2),
    ("docs", r"\badrs?\b", 3),
    ("docs", r"\bdecision\b", 2),
    ("docs", r"\bwhy\b", 2),
    ("docs", r"who owns\b", 3),
    ("docs", r"\bcluster\b", 2),
    ("docs", r"\bsummar(y|ize|ise)\b", 2),
    ("docs", r"\bwhere is\b.+\b(stored|configured|kept|saved)\b", 3),

    ("explain", r"\bexplain\b", 3),
    ("explain", r"what is\b|\bwhat are\b", 2),
    ("explain", r"tell me about\b", 3),
    ("explain", r"\bshow\b", 1),
    ("explain", r"\bdetails?\b", 2),
    ("explain", r"\bdescribe\b", 3),
    ("explain", r"\binfo(rmation)?\b", 2),
]

_COMPILED = [(i, re.compile(p, re.I), w) for i, p, w in RULES]


def classify(question, mentions=None, explicit_intent=None, max_rules=40):
    """Return {intent, confidence, scores, rules_fired, mentions, notes}.

    mentions: list of kbmap.Mention (already linked) used for sanity notes only
    — classification itself is keyword-driven, entity-independent (so it stays
    deterministic and testable).
    """
    scores = {i: 0 for i in INTENTS}
    fired = []
    if explicit_intent:
        ei = explicit_intent.lower().strip()
        if ei in INTENTS:
            return {"intent": ei, "confidence": 1.0, "scores": {i: (10 if i == ei else 0)
                                                                for i in INTENTS},
                    "rules_fired": [["explicit", ei]], "explicit": True}
        return {"intent": None, "confidence": 0.0, "scores": scores,
                "rules_fired": [], "explicit": False,
                "note": f"unknown explicit intent {explicit_intent!r}"}
    for intent, rx, w in _COMPILED:
        m = rx.search(question)
        if m:
            scores[intent] += w
            fired.append([intent, m.group(0)[:40]])
            if len(fired) >= max_rules:
                break

    if not fired or all(v == 0 for v in scores.values()):
        return {"intent": None, "confidence": 0.0, "scores": scores,
                "rules_fired": fired,
                "note": "no intent rule matched; try /impact /path /explain "
                        "/callers /slice /docs prefix or name an entity"}

    best = max(INTENTS, key=lambda i: scores[i])
    ordered = sorted(INTENTS, key=lambda i: -scores[i])
    second = ordered[1] if len(ordered) > 1 else best
    conf = scores[best] / (scores[best] + max(scores[second], 1e-9))
    return {"intent": best, "confidence": round(conf, 3), "scores": scores,
            "rules_fired": fired}
