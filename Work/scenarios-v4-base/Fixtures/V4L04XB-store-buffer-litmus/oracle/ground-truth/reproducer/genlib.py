"""Derived-artifact generator for the V4L04X store-buffer litmus roots.

Everything the oracle asserts is COMPUTED here from machines.py (exhaustive
enumeration) + corpus.py (program definitions). generate.py in each bundle
calls build_form() and writes byte-identical artifacts, so tests can prove
the shipped oracle equals the reproducer output.
"""

from __future__ import annotations

import json
from typing import Any

from corpus import BASE_PROGRAMS, FRONTIER_PROGRAMS
from machines import SB_A, SB_B, SC, enumerate_finals, observation_holds

CLASS_BOTH = "both"
CLASS_A_ONLY = "a-only"
CLASS_B_ONLY = "b-only"
CLASS_NEITHER = "neither"

FORMS = {
    "base": {
        "scenario_id": "V4L04XB-store-buffer-litmus",
        "programs": BASE_PROGRAMS,
        "verdict_points": 2.75,
    },
    "frontier": {
        "scenario_id": "V4L04XF-store-buffer-litmus",
        "programs": FRONTIER_PROGRAMS,
        "verdict_points": 2.2,
    },
}
SET_POINTS = 8
GATE_POINTS = 4

# Competent-probe error profile: the strongest plausible imperfect reasoner —
# treats SB-B as "almost SB-A" on the forwarding-only outcomes (misses that
# no-forwarding kills them) and mishandles one forced-write-back window and
# one fence/race composite. Keys are observation IDs, values the wrong class.
COMPETENT_ERRORS = {
    "base": {
        "P05-O1": CLASS_B_ONLY,
        "P11-O1": CLASS_BOTH,
        "P13-O1": CLASS_BOTH,
        "P14-O1": CLASS_BOTH,
    },
    "frontier": {
        "P03-O1": CLASS_BOTH,
        "P04-O2": CLASS_BOTH,
        "P11-O1": CLASS_NEITHER,
        "P12-O1": CLASS_BOTH,
        "P17-O2": CLASS_B_ONLY,
    },
}


def render_op(op: list[Any]) -> str:
    return " ".join(str(part) for part in op)


def render_threads(threads: list[list[list[Any]]]) -> str:
    lines = []
    for index, program in enumerate(threads, start=1):
        lines.append(f"thread T{index}:")
        for op in program:
            lines.append(f"  {render_op(op)}")
    return "\n".join(lines)


def render_claims(obs: dict[str, int]) -> str:
    return " and ".join(f"{key} = {value}" for key, value in obs.items())


def compute_form(form: str) -> dict[str, Any]:
    """Enumerate every program on SB-A / SB-B / SC and classify observations."""
    config = FORMS[form]
    programs = []
    for index, (author_id, spec) in enumerate(config["programs"], start=1):
        program_id = f"P{index:02d}"
        threads = spec["threads"]
        finals_a = enumerate_finals(threads, SB_A)
        finals_b = enumerate_finals(threads, SB_B)
        finals_sc = enumerate_finals(threads, SC)
        observations = {}
        for obs_name, claims in spec["obs"].items():
            obs_id = f"{program_id}-{obs_name}"
            in_a = any(observation_holds(f, claims) for f in finals_a)
            in_b = any(observation_holds(f, claims) for f in finals_b)
            in_sc = any(observation_holds(f, claims) for f in finals_sc)
            if in_a and in_b:
                cls = CLASS_BOTH
            elif in_a:
                cls = CLASS_A_ONLY
            elif in_b:
                cls = CLASS_B_ONLY
            else:
                cls = CLASS_NEITHER
            observations[obs_id] = {
                "claims": dict(claims),
                "claims_text": render_claims(claims),
                "class": cls,
                "reachable_sb_a": in_a,
                "reachable_sb_b": in_b,
                "reachable_sc": in_sc,
            }
        divergent = any(
            entry["class"] in (CLASS_A_ONLY, CLASS_B_ONLY) for entry in observations.values()
        )
        programs.append({
            "program_id": program_id,
            "author_id": author_id,
            "family": spec["family"],
            "threads_text": render_threads(threads),
            "observations": observations,
            "divergent": divergent,
        })
    return {"form": form, "scenario_id": config["scenario_id"], "programs": programs}


def observation_ids(computed: dict[str, Any]) -> list[str]:
    return [
        obs_id
        for program in computed["programs"]
        for obs_id in program["observations"]
    ]


def expected_classes(computed: dict[str, Any]) -> dict[str, str]:
    return {
        obs_id: entry["class"]
        for program in computed["programs"]
        for obs_id, entry in program["observations"].items()
    }


def divergent_ids(computed: dict[str, Any]) -> list[str]:
    return [program["program_id"] for program in computed["programs"] if program["divergent"]]


def _dump(obj: Any) -> str:
    return json.dumps(obj, indent=1, ensure_ascii=False) + "\n"


def build_output_schema(computed: dict[str, Any]) -> str:
    verdict_property = {
        "type": "object",
        "required": ["value", "unit"],
        "additionalProperties": False,
        "properties": {
            "value": {"type": "string", "minLength": 1, "maxLength": 32},
            "unit": {"type": "string", "minLength": 1, "maxLength": 32},
        },
    }
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "required": ["scenario_id", "verdicts", "divergent_program_ids", "equivalence_gate"],
        "additionalProperties": False,
        "properties": {
            "scenario_id": {"const": computed["scenario_id"]},
            "verdicts": {
                "type": "object",
                "additionalProperties": False,
                "properties": {obs_id: verdict_property for obs_id in observation_ids(computed)},
            },
            "divergent_program_ids": {
                "type": "array",
                "maxItems": len(computed["programs"]),
                "uniqueItems": True,
                "items": {"type": "string", "minLength": 1, "maxLength": 16},
            },
            "equivalence_gate": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "machines_verdict": {"type": "string", "minLength": 1, "maxLength": 16},
                },
            },
            "narrative": {"type": "string", "maxLength": 4000},
        },
    }
    return _dump(schema)


def build_rubric(computed: dict[str, Any], form: str) -> str:
    verdict_points = FORMS[form]["verdict_points"]
    atoms = []
    for obs_id, cls in expected_classes(computed).items():
        atoms.append({
            "id": obs_id,
            "type": "case_fraction",
            "weight": verdict_points,
            "candidate_path": "verdicts",
            "id_field": "item_id",
            "value_field": "value",
            "casefold_ids": True,
            "casefold_values": True,
            "case_weights": {obs_id: 1},
            "expected": {obs_id: cls},
        })
    rubric = {
        "schema_version": "v4-rubric-1",
        "scenario_id": computed["scenario_id"],
        "candidate_artifact": "litmus-answer.json",
        "score": {
            "max_points": 100,
            "pass_threshold": 80,
            "partial_threshold": 50,
            "integrity_penalty_cap": 15,
            "wrong_commitment_cap": 40,
        },
        "components": [
            {
                "id": "verdicts",
                "weight": round(verdict_points * len(atoms), 2),
                "semantic": True,
                "atoms": atoms,
            },
            {
                "id": "divergent-programs",
                "weight": SET_POINTS,
                "semantic": True,
                "atoms": [
                    {
                        "id": "divergent-set",
                        "type": "set_f1",
                        "weight": SET_POINTS,
                        "candidate_path": "divergent_program_ids",
                        "casefold": True,
                        "expected": divergent_ids(computed),
                    }
                ],
            },
            {
                "id": "equivalence-gate",
                "weight": GATE_POINTS,
                "semantic": True,
                "atoms": [
                    {
                        "id": "machines-verdict",
                        "type": "categorical",
                        "weight": GATE_POINTS,
                        "candidate_path": "equivalence_gate.machines_verdict",
                        "casefold": True,
                        "expected": "diverge",
                        "commitment": True,
                    }
                ],
            },
        ],
        "integrity_events": [],
    }
    return _dump(rubric)


def _candidate(computed: dict[str, Any], classes: dict[str, str],
               divergent: list[str], gate: str | None,
               narrative: str | None = None) -> dict[str, Any]:
    answer: dict[str, Any] = {
        "scenario_id": computed["scenario_id"],
        "verdicts": {
            obs_id: {"value": cls, "unit": "class"} for obs_id, cls in classes.items()
        },
        "divergent_program_ids": divergent,
        "equivalence_gate": {} if gate is None else {"machines_verdict": gate},
    }
    if narrative is not None:
        answer["narrative"] = narrative
    return answer


def _divergent_from_classes(computed: dict[str, Any], classes: dict[str, str]) -> list[str]:
    result = []
    for program in computed["programs"]:
        if any(
            classes.get(obs_id) in (CLASS_A_ONLY, CLASS_B_ONLY)
            for obs_id in program["observations"]
        ):
            result.append(program["program_id"])
    return result


def build_reference(computed: dict[str, Any]) -> dict[str, Any]:
    return _candidate(
        computed, expected_classes(computed), divergent_ids(computed), "diverge"
    )


def build_probes(computed: dict[str, Any], form: str) -> dict[str, dict[str, Any]]:
    truth = expected_classes(computed)
    reference = build_reference(computed)

    competent_classes = dict(truth)
    for obs_id, wrong in COMPETENT_ERRORS[form].items():
        if obs_id not in competent_classes:
            raise KeyError(f"competent error targets unknown observation {obs_id}")
        if competent_classes[obs_id] == wrong:
            raise ValueError(f"competent error for {obs_id} equals the truth")
        competent_classes[obs_id] = wrong
    competent = _candidate(
        computed,
        competent_classes,
        _divergent_from_classes(computed, competent_classes),
        "diverge",
    )

    # Decoy: a textbook-TSO reasoner who treats SB-B as identical to SB-A
    # (ignores capacity + no-forwarding). Sees no divergence anywhere and
    # leaves the equivalence gate unanswered.
    decoy_classes = {}
    for program in computed["programs"]:
        for obs_id, entry in program["observations"].items():
            decoy_classes[obs_id] = CLASS_BOTH if entry["reachable_sb_a"] else CLASS_NEITHER
    decoy = _candidate(computed, decoy_classes, [], None)

    vacuous = _candidate(computed, {}, [], None)

    def _flip_case(token: str) -> str:
        return token.upper()

    alternate = {
        "scenario_id": computed["scenario_id"],
        "verdicts": {
            obs_id: {"value": _flip_case(cls), "unit": "Class"}
            for obs_id, cls in truth.items()
        },
        "divergent_program_ids": [pid.lower() for pid in divergent_ids(computed)],
        "equivalence_gate": {"machines_verdict": "DIVERGE"},
    }

    paraphrase = _candidate(
        computed,
        truth,
        divergent_ids(computed),
        "diverge",
        narrative=(
            "Exhaustively enumerated all interleavings of every program under both "
            "machine definitions; classes follow from the reachable final-state sets."
        ),
    )

    overclaim = _candidate(
        computed,
        truth,
        [program["program_id"] for program in computed["programs"]],
        "agree",
    )

    return {
        "reference": reference,
        "competent": competent,
        "vacuous": vacuous,
        "decoy": decoy,
        "alternate-valid": alternate,
        "paraphrase": paraphrase,
        "overclaim": overclaim,
    }


def build_ground_truth_index(computed: dict[str, Any], form: str) -> str:
    class_counts: dict[str, int] = {}
    for cls in expected_classes(computed).values():
        class_counts[cls] = class_counts.get(cls, 0) + 1
    index = {
        "schema_version": "l04x-ground-truth-1",
        "scenario_id": computed["scenario_id"],
        "form": form,
        "derivation": (
            "Every class below is computed by exhaustive breadth-first enumeration "
            "of the full configuration space of both machines (reproducer/machines.py); "
            "reachable AND unreachable verdicts are machine-checked, never hand-asserted. "
            "reproducer/generate.py regenerates every derived artifact byte-identically."
        ),
        "machines": {
            "SB-A": "unbounded FIFO store buffer, store-to-load forwarding (newest own entry)",
            "SB-B": "capacity-2 FIFO store buffer with forced oldest write-back inside the "
                    "overflowing store action, no store-to-load forwarding",
        },
        "class_vocabulary": [CLASS_BOTH, CLASS_A_ONLY, CLASS_B_ONLY, CLASS_NEITHER],
        "points": {
            "verdict": FORMS[form]["verdict_points"],
            "set": SET_POINTS,
            "gate": GATE_POINTS,
        },
        "class_counts": class_counts,
        "divergent_program_ids": divergent_ids(computed),
        "machines_verdict": "diverge",
        "programs": {
            program["program_id"]: {
                "author_id": program["author_id"],
                "family": program["family"],
                "threads": program["threads_text"],
                "divergent": program["divergent"],
                "observations": {
                    obs_id: {
                        "claims": entry["claims_text"],
                        "class": entry["class"],
                        "reachable_sb_a": entry["reachable_sb_a"],
                        "reachable_sb_b": entry["reachable_sb_b"],
                        "reachable_sc": entry["reachable_sc"],
                    }
                    for obs_id, entry in program["observations"].items()
                },
            }
            for program in computed["programs"]
        },
    }
    return _dump(index)


def build_programs_md(computed: dict[str, Any]) -> str:
    lines = [
        "# Litmus programs and observations",
        "",
        "Instruction syntax and machine semantics: `machine-spec.md` (same",
        "directory). Registers are per thread; `Tn.rk = c` in an observation",
        "claims the FINAL value of register `rk` of thread `Tn` in a complete",
        "run; a bare `v = c` claims the final shared-memory value of `v`. An",
        "observation holds only if ALL of its claims hold simultaneously in",
        "the same complete run.",
        "",
        "Classify every observation ID on both machines (see `task.md`).",
        "",
    ]
    for program in computed["programs"]:
        lines.append(f"## {program['program_id']}")
        lines.append("")
        lines.append("```")
        lines.append(program["threads_text"])
        lines.append("```")
        lines.append("")
        lines.append("| Observation | Claim |")
        lines.append("|---|---|")
        for obs_id, entry in program["observations"].items():
            lines.append(f"| `{obs_id}` | `{entry['claims_text']}` |")
        lines.append("")
    return "\n".join(lines) + ""


def build_form(form: str) -> dict[str, Any]:
    """Return {relative_path: text} for every derived artifact of one form."""
    computed = compute_form(form)
    probes = build_probes(computed, form)
    artifacts = {
        "inputs/output-schema.json": build_output_schema(computed),
        "inputs/sources/programs.md": build_programs_md(computed),
        "oracle/rubric.json": build_rubric(computed, form),
        "oracle/reference-answer.json": _dump(build_reference(computed)),
        "oracle/ground-truth/index.json": build_ground_truth_index(computed, form),
    }
    for name, candidate in probes.items():
        artifacts[f"oracle/probes/{name}.json"] = _dump(candidate)
    return artifacts
