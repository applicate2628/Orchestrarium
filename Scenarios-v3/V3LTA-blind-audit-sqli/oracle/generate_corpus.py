#!/usr/bin/env python3
"""V3LTA blind-audit corpus generator (F2, working-audit family).

Deterministically emits a wide-shallow audit corpus of 80 small handler files under
``inputs/corpus/`` and the HIDDEN ground-truth manifest ``oracle/corpus-truth.json``.

ONE planted defect class only: **SQL injection** — a request-derived (tainted) value flows
into a SQL string that is passed to ``.execute(...)``. The corpus mixes three populations:

  * DEFECT  (20 files): tainted value interpolated into a SQL string -> execute. TRUE positive.
  * DECOY   (15 files): visually similar (f-string / % / .format / concat near a query) but SAFE
                        (interpolation is on a validated constant, on a log line, or on constants;
                        the user value is always a bound / qmark parameter). Flagging one is a FP.
  * CLEAN   (45 files): parameterized queries, ORM calls, or pure non-DB logic. Flagging one is a FP.

The generator records, per defect, the exact ``build`` and ``execute`` line numbers and an
``acceptable_lines`` window (build..execute padded by +/-1). The verifier scores candidate findings
against this manifest by (file-basename, line-in-window). Nothing here is executed at score time; the
corpus is audit TEXT only.

Determinism: fixed SEED. Files are written in binary mode (LF) per repo Windows hygiene. Re-running
reproduces byte-identical corpus + manifest. This file lives under oracle/ (stripped from the
provider-visible staging, H2) so the defect logic and manifest never reach the candidate.
"""
from __future__ import annotations

import json
import random
from pathlib import Path

SEED = 20260712
N_FILES = 80
N_DEFECT = 20
N_DECOY = 15
# clean = N_FILES - N_DEFECT - N_DECOY = 45
ASPECT = "sql-injection"

ORACLE_DIR = Path(__file__).resolve().parent
BUNDLE_ROOT = ORACLE_DIR.parent
CORPUS_DIR = BUNDLE_ROOT / "inputs" / "corpus"
TRUTH_PATH = ORACLE_DIR / "corpus-truth.json"


# --- defect templates -----------------------------------------------------------------------------
# Each returns (lines, build_marker, exec_marker, tainted_source, shape, evidence_terms).
# build_marker / exec_marker are the substrings used to locate the build/execute lines after fillers
# are prepended, so recorded line numbers stay correct regardless of filler count.

def defect_fstring_select(name: str):
    lines = [
        f"def get_orders_{name}(req, conn):",
        '    user_id = req.args.get("user_id")',
        "    cur = conn.cursor()",
        '    query = f"SELECT * FROM orders WHERE user_id = {user_id}"',
        "    cur.execute(query)",
        "    return cur.fetchall()",
    ]
    return lines, 'query = f"SELECT', "cur.execute(query)", "req.args.get", "fstring-select", ["fstring", "user_id"]


def defect_percent_delete(name: str):
    lines = [
        f"def purge_session_{name}(payload, conn):",
        '    token = payload["token"]',
        "    cur = conn.cursor()",
        "    sql = \"DELETE FROM sessions WHERE token = '%s'\" % token",
        "    cur.execute(sql)",
    ]
    return lines, "sql = \"DELETE", "cur.execute(sql)", "payload[", "percent-delete", ["%", "token"]


def defect_format_update(name: str):
    lines = [
        f"def rename_user_{name}(body, conn):",
        '    name = body["name"]',
        '    uid = body["id"]',
        "    q = \"UPDATE users SET name = '{}' WHERE id = {}\".format(name, uid)",
        "    conn.cursor().execute(q)",
    ]
    return lines, "q = \"UPDATE", "conn.cursor().execute(q)", "body[", "format-update", [".format", "uid"]


def defect_concat_select(name: str):
    lines = [
        f"def find_logs_{name}(params, conn):",
        '    username = params["username"]',
        "    stmt = \"SELECT * FROM logs WHERE user = '\" + username + \"'\"",
        "    conn.execute(stmt)",
    ]
    return lines, "stmt = \"SELECT", "conn.execute(stmt)", "params[", "concat-select", ["concat", "username"]


def defect_inline_execute(name: str):
    # build and execute on the SAME line (build_line == execute_line)
    lines = [
        f"def count_items_{name}(request, conn):",
        '    kind = request.query["kind"]',
        "    return conn.execute(f\"SELECT COUNT(*) FROM items WHERE kind = '{kind}'\").fetchone()",
    ]
    return lines, "return conn.execute(f\"SELECT", "return conn.execute(f\"SELECT", "request.query[", "inline-fstring-execute", ["fstring", "kind"]


DEFECT_TEMPLATES = [
    defect_fstring_select,
    defect_percent_delete,
    defect_format_update,
    defect_concat_select,
    defect_inline_execute,
]


# --- decoy templates (SAFE but visually similar) --------------------------------------------------

def decoy_validated_table(name: str):
    lines = [
        "ALLOWED_TABLES = {\"orders\": \"orders\", \"items\": \"items\"}",
        "",
        f"def read_row_{name}(req, conn):",
        '    table = ALLOWED_TABLES[req.args.get("kind")]  # validated whitelist -> constant',
        '    item_id = req.args.get("id")',
        '    query = f"SELECT * FROM {table} WHERE id = ?"  # f-string only on validated constant',
        "    conn.execute(query, (item_id,))  # user value is a bound parameter",
    ]
    return lines, "validated-table-fstring", "f-string interpolates only a whitelisted constant table name; the user value is a bound qmark parameter"


def decoy_format_logging(name: str):
    lines = [
        f"def audit_login_{name}(payload, conn, logger):",
        '    username = payload["username"]',
        '    logger.info("login attempt for user %s" % username)  # format targets the LOG line',
        '    conn.execute("SELECT 1 FROM users WHERE name = ?", (username,))  # parameterized',
    ]
    return lines, "format-on-log", "the %-format targets a logging call, not the SQL string; the query is parameterized"


def decoy_concat_constants(name: str):
    lines = [
        "SCHEMA = \"app\"",
        "",
        f"def list_invoices_{name}(params, conn):",
        '    account = params["account"]',
        "    stmt = \"SELECT * FROM \" + SCHEMA + \".invoices WHERE account = %s\"  # concat of constants",
        "    conn.execute(stmt, (account,))  # user value is a bound parameter",
    ]
    return lines, "concat-constants", "string concatenation joins only module constants; the user value is passed as a bound parameter"


def decoy_named_param_fstring(name: str):
    lines = [
        f"def search_docs_{name}(req, conn):",
        '    term = req.form["q"]',
        '    query = f"SELECT * FROM docs WHERE body LIKE :term"  # no user value in the f-string',
        '    conn.execute(query, {"term": f"%{term}%"})  # user value bound as :term',
    ]
    return lines, "named-param-fstring", "the f-string on the query contains no user interpolation (only a bound :term placeholder); the user value is a bound parameter"


DECOY_TEMPLATES = [
    decoy_validated_table,
    decoy_format_logging,
    decoy_concat_constants,
    decoy_named_param_fstring,
]


# --- clean templates (obviously safe) -------------------------------------------------------------

def clean_qmark(name: str):
    return [
        f"def get_user_{name}(req, conn):",
        '    uid = req.args.get("id")',
        '    return conn.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()',
    ], "parameterized-qmark"


def clean_orm(name: str):
    return [
        f"def get_active_{name}(session, req):",
        '    status = req.args.get("status", "active")',
        "    return session.query(User).filter_by(status=status).all()",
    ], "orm-filter-by"


def clean_pure(name: str):
    return [
        f"def normalize_{name}(payload):",
        '    name = payload.get("name", "").strip().lower()',
        '    return {"name": name, "length": len(name)}',
    ], "pure-no-db"


def clean_named(name: str):
    return [
        f"def update_flag_{name}(body, conn):",
        "    conn.execute(",
        '        "UPDATE flags SET enabled = :enabled WHERE id = :id",',
        '        {"enabled": body["enabled"], "id": body["id"]},',
        "    )",
    ], "named-params"


CLEAN_TEMPLATES = [clean_qmark, clean_orm, clean_pure, clean_named]


HEADER_COMMENTS = [
    "# service handler module",
    "# auto-registered route",
    "# repository access helper",
    "# request handler",
    "# data access layer",
    "# internal endpoint",
]


def with_fillers(rng: random.Random, body_lines: list[str]) -> list[str]:
    """Prepend a seeded number of header/comment filler lines to scatter defect line numbers."""
    n = rng.randint(0, 5)
    fillers = [rng.choice(HEADER_COMMENTS)]
    for _ in range(n):
        fillers.append(f"# note: {rng.choice(['revised', 'reviewed', 'legacy', 'stable', 'wip'])} path")
    return fillers + [""] + body_lines + [""]


def locate(lines: list[str], marker: str) -> int:
    for idx, line in enumerate(lines, start=1):
        if marker in line:
            return idx
    raise RuntimeError(f"marker not found: {marker!r}")


def main() -> int:
    rng = random.Random(SEED)
    CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    # clear any stale corpus files
    for stale in CORPUS_DIR.glob("h*.py"):
        stale.unlink()

    roles = ["defect"] * N_DEFECT + ["decoy"] * N_DECOY + ["clean"] * (N_FILES - N_DEFECT - N_DECOY)
    rng.shuffle(roles)

    defects: list[dict] = []
    decoys: list[dict] = []
    clean: list[dict] = []

    defect_i = decoy_i = clean_i = 0
    for i, role in enumerate(roles, start=1):
        fname = f"h{i:03d}.py"
        rel = f"corpus/{fname}"
        stem = f"{i:03d}"
        if role == "defect":
            tmpl = DEFECT_TEMPLATES[defect_i % len(DEFECT_TEMPLATES)]
            defect_i += 1
            body, build_marker, exec_marker, tainted, shape, ev = tmpl(stem)
            lines = with_fillers(rng, body)
            build_line = locate(lines, build_marker)
            exec_line = locate(lines, exec_marker)
            lo = min(build_line, exec_line) - 1
            hi = max(build_line, exec_line) + 1
            acceptable = [n for n in range(lo, hi + 1) if n >= 1]
            defects.append({
                "id": f"D{len(defects) + 1:02d}",
                "file": rel,
                "shape": shape,
                "tainted_source": tainted,
                "build_line": build_line,
                "execute_line": exec_line,
                "acceptable_lines": acceptable,
                "evidence_terms": ev,
            })
        elif role == "decoy":
            tmpl = DECOY_TEMPLATES[decoy_i % len(DECOY_TEMPLATES)]
            decoy_i += 1
            body, shape, reason = tmpl(stem)
            lines = with_fillers(rng, body)
            decoys.append({"file": rel, "shape": shape, "reason": reason})
        else:
            tmpl = CLEAN_TEMPLATES[clean_i % len(CLEAN_TEMPLATES)]
            clean_i += 1
            body, shape = tmpl(stem)
            lines = with_fillers(rng, body)
            clean.append({"file": rel, "shape": shape})

        text = "\n".join(lines).rstrip("\n") + "\n"
        (CORPUS_DIR / fname).write_bytes(text.encode("utf-8"))

    truth = {
        "generated_by": "oracle/generate_corpus.py",
        "seed": SEED,
        "aspect": ASPECT,
        "counts": {
            "total": N_FILES,
            "defect": len(defects),
            "decoy": len(decoys),
            "clean": len(clean),
        },
        "defects": defects,
        "decoys": decoys,
        "clean": clean,
    }
    TRUTH_PATH.write_bytes((json.dumps(truth, indent=2) + "\n").encode("utf-8"))

    print(f"Wrote {N_FILES} corpus files to {CORPUS_DIR}")
    print(f"defects={len(defects)} decoys={len(decoys)} clean={len(clean)}")
    print(f"Ground truth -> {TRUTH_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
