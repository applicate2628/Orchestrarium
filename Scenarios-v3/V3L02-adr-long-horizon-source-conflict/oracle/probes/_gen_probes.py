#!/usr/bin/env python3
"""Generate the V3L02 four-probe candidates (reference / vacuous / decoy).

Kept in oracle/ (scorer-private, never staged to the provider root) so the
four-probe acceptance run is reproducible: it derives the reference answer
directly from oracle/adr-long-horizon-contract.json, then degrades it into a
keyword-stuffed vacuous answer and a right-shape/wrong-substance decoy.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONTRACT = json.loads((HERE.parents[0] / "adr-long-horizon-contract.json").read_text(encoding="utf-8"))


def ref_json():
    d = {
        "scenario_id": CONTRACT["scenario_id"],
        "decision": dict(CONTRACT["decision"]),
        "source_authority_order": list(CONTRACT["source_authority_order"]),
        "accepted_claims": [],
        "rejected_options": [],
        "compatibility_plan": [],
        "rollback_plan": [],
        "non_claims": [],
        "gate_decision": CONTRACT["gate_decision"],
        "notes": "Reference V3L02 decision package derived from the oracle contract.",
    }
    for c in CONTRACT["accepted_claims"]:
        d["accepted_claims"].append({
            "id": c["id"],
            "summary": "Accepted: " + " and ".join(c["summary_terms"]) + ".",
            "source_ids": list(c["required_sources"]),
        })
    for o in CONTRACT["rejected_options"]:
        d["rejected_options"].append({
            "option": o["option"],
            "reason": "Rejected because " + " and ".join(o["reason_terms"]) + ".",
            "source_ids": list(o["required_sources"]),
        })
    for cp in CONTRACT["compatibility_plan"]:
        d["compatibility_plan"].append({
            "id": cp["id"],
            "detail": "Compat step covering " + ", ".join(cp["required_terms"]) + ".",
        })
    for rb in CONTRACT["rollback_plan"]:
        d["rollback_plan"].append({
            "id": rb["id"],
            "detail": "Rollback step covering " + ", ".join(rb["required_terms"]) + ".",
        })
    for nc in CONTRACT["non_claims"]:
        # phrase so the literal "not claim" term is present via "do not claim"
        terms = [t for t in nc["required_terms"] if t != "not claim"]
        d["non_claims"].append({
            "id": nc["id"],
            "statement": "We do not claim: " + " / ".join(terms) + ".",
        })
    return d


def ref_md():
    lines = [
        "# V3L02 ADR Decision", "",
        "## Decision",
        f"Choice: {CONTRACT['decision']['choice']} (status {CONTRACT['decision']['status']}).", "",
        "## Source Authority",
        "Ranking: " + " > ".join(CONTRACT["source_authority_order"]) + ".", "",
        "## Accepted Claims",
    ]
    for c in CONTRACT["accepted_claims"]:
        lines.append(f"- {c['id']}: " + " and ".join(c["summary_terms"]) + ".")
    lines += ["", "## Rejected Options"]
    for o in CONTRACT["rejected_options"]:
        lines.append(f"- {o['option']}: rejected due to " + " and ".join(o["reason_terms"]) + ".")
    lines += ["", "## Compatibility Plan"]
    for cp in CONTRACT["compatibility_plan"]:
        lines.append(f"- {cp['id']}: " + ", ".join(cp["required_terms"]) + ".")
    lines += ["", "## Rollback Plan"]
    for rb in CONTRACT["rollback_plan"]:
        lines.append(f"- {rb['id']}: " + ", ".join(rb["required_terms"]) + ".")
    lines += ["", "## Non-Claim Ledger"]
    for nc in CONTRACT["non_claims"]:
        terms = [t for t in nc["required_terms"] if t != "not claim"]
        lines.append(f"- {nc['id']}: we do not claim " + " / ".join(terms) + ".")
    lines += ["", "## Gate Decision", CONTRACT["gate_decision"], ""]
    return "\n".join(lines)


def vacuous_json():
    # keyword-stuffed but structurally empty: right top-level keys, no real content.
    kw = []
    for c in CONTRACT["accepted_claims"]:
        kw += c["summary_terms"]
    for o in CONTRACT["rejected_options"]:
        kw += o["reason_terms"]
    return {
        "scenario_id": CONTRACT["scenario_id"],
        "decision": {"choice": "", "status": ""},
        "source_authority_order": [],
        "accepted_claims": [],
        "rejected_options": [],
        "compatibility_plan": [],
        "rollback_plan": [],
        "non_claims": [],
        "gate_decision": "",
        "notes": "keywords: " + ", ".join(kw),
    }


def vacuous_md():
    return "# V3L02 ADR Decision\n\nkeywords: adapter, legacy_plan_id, idempotency_key, PlanBridge, rollback, compatibility\n"


def decoy_json():
    # Right shape, wrong substance, NO forbidden-claim (fails on score alone):
    #  - correct decision (looks right)
    #  - source order wrong: stale ADR ranked FIRST (tie-probe trap), same set
    #  - accepted claims present with terms but source_ids wrong on 3 of 4
    #  - only 2 rejected options present
    #  - only 2 compatibility items present
    d = ref_json()
    d["notes"] = "Decoy: correct-looking shape, degraded substance."
    order = list(CONTRACT["source_authority_order"])
    d["source_authority_order"] = [order[-1]] + order[:-1]  # stale ADR to front
    for i, c in enumerate(d["accepted_claims"]):
        if i < 3:
            c["source_ids"] = ["SRC-PROPOSAL"]  # wrong authority binding
    d["rejected_options"] = d["rejected_options"][:2]  # drop D + stale-ADR rejection
    d["compatibility_plan"] = d["compatibility_plan"][:2]
    return d


def decoy_md():
    md = ref_md()
    return md.replace(
        "Ranking: " + " > ".join(CONTRACT["source_authority_order"]) + ".",
        "Ranking: SRC-STALE-ADR > SRC-CODE-API > SRC-RUNTIME-TRACE (stale ADR leads).",
    )


def write(sub, data, md):
    (HERE / sub / "adr-decision.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    (HERE / sub / "adr-decision.md").write_text(md + "\n", encoding="utf-8")


write("reference", ref_json(), ref_md())
write("vacuous", vacuous_json(), vacuous_md())
write("decoy", decoy_json(), decoy_md())
print("probes written")
