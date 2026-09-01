#!/usr/bin/env python3
"""Generate the four-probe reference / adversarial candidate answers for V3LTA from the ground truth.

Emits, under oracle/reference-candidates/<name>/answer.json (HIDDEN; oracle/ is stripped from provider
staging), the deterministic probe candidates used to validate the discriminator:

  reference        -> all 20 defects located, 0 FP            -> PASS (recall 1.0, precision 1.0)
  breadth-triager  -> 16 defects, 1 decoy FP                  -> PASS (recall 0.8, precision ~0.94)
  vacuous-keyword  -> keyword-stuffed, no located findings    -> FAIL (recall 0, precision below floor)
  shotgun          -> flags all 80 files                      -> FAIL (precision collapses to 0.25)
  decoy-follower   -> right shape, flags safe decoy files     -> FAIL (precision below floor)
  over-analyzer    -> depth-first: only defects in first 12   -> FAIL (recall below threshold; precision 1.0)

The last two are the discriminator's teeth: decoy-follower is the "right shape / wrong substance"
adversarial probe; over-analyzer vs breadth-triager is the near-peer separation (a high-precision deep
model that did not cover breadth under the fixed budget FAILS while a breadth-first auditor PASSES).
"""
from __future__ import annotations

import json
from pathlib import Path

ORACLE_DIR = Path(__file__).resolve().parent
TRUTH_PATH = ORACLE_DIR / "corpus-truth.json"
OUT_DIR = ORACLE_DIR / "reference-candidates"
ASPECT = "sql-injection"


def mid_line(defect: dict) -> int:
    # cite a line guaranteed to be inside the acceptable window
    return defect["execute_line"]


def write(name: str, findings: list[dict], gate: str = "REVISE"):
    d = OUT_DIR / name
    d.mkdir(parents=True, exist_ok=True)
    answer = {"aspect": ASPECT, "gate_decision": gate, "findings": findings}
    (d / "answer.json").write_bytes((json.dumps(answer, indent=2) + "\n").encode("utf-8"))


def main() -> int:
    truth = json.loads(TRUTH_PATH.read_text(encoding="utf-8"))
    defects = truth["defects"]
    decoys = truth["decoys"]
    clean = truth["clean"]

    # reference: every defect, correct line, no FP
    write(
        "reference",
        [
            {"file": d["file"], "line": mid_line(d), "evidence": f"{d['shape']} via {d['tainted_source']}"}
            for d in defects
        ],
    )

    # breadth-triager: 16 defects + 1 decoy FP -> realistic PASS
    triager = [
        {"file": d["file"], "line": mid_line(d), "evidence": d["shape"]}
        for d in defects[:16]
    ]
    triager.append({"file": decoys[0]["file"], "line": 6, "evidence": "looks like an f-string in a query"})
    write("breadth-triager", triager)

    # vacuous-keyword: aspect right, findings stuffed with keywords but locating nothing real
    write(
        "vacuous-keyword",
        [
            {"file": "corpus/", "line": 0,
             "evidence": "SQL injection vulnerability: tainted user input flows unsafely into execute() "
                         "across the codebase; multiple unsafe string-built queries present"},
            {"file": "entire-corpus", "line": 1,
             "evidence": "injection risk, unsanitized input, string concatenation, format, f-string, unsafe"},
        ],
    )

    # shotgun: flag ALL 80 files -- correct line on the 20 defects, line 1 on the other 60
    shotgun = []
    defect_files = {d["file"]: mid_line(d) for d in defects}
    for entry in defects + decoys + clean:
        f = entry["file"]
        line = defect_files.get(f, 1)
        shotgun.append({"file": f, "line": line, "evidence": "flagged"})
    write("shotgun", shotgun)

    # decoy-follower: right SHAPE (real files, plausible lines), wrong SUBSTANCE (safe decoys flagged)
    follower = [
        {"file": d["file"], "line": mid_line(d), "evidence": d["shape"]}
        for d in defects[:9]
    ]
    for dc in decoys[:8]:
        follower.append({"file": dc["file"], "line": 6, "evidence": "string formatting near a SQL query looks unsafe"})
    write("decoy-follower", follower)

    # over-analyzer: depth-first -> only defects whose file index is in the first 12 corpus files
    def corpus_index(rel: str) -> int:
        return int(Path(rel).stem[1:])
    early = [d for d in defects if corpus_index(d["file"]) <= 12]
    write(
        "over-analyzer",
        [
            {"file": d["file"], "line": mid_line(d),
             "evidence": f"deep analysis of {d['shape']}: full taint trace, exploit sketch, remediation"}
            for d in early
        ],
    )

    print(f"Reference candidates -> {OUT_DIR}")
    print(f"  reference={len(defects)} findings; over-analyzer covers {len(early)} early defects")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
