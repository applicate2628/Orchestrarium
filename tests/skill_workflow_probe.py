"""Explicit local model probe; never invoked by ordinary test discovery."""
import argparse
from datetime import datetime, timezone
import hashlib
import ipaddress
import json
import math
import os
import re
from pathlib import Path
import subprocess
import sys
import tempfile
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from policy_text_contract import selected_unit

ROOT = Path(__file__).resolve().parents[1]
CASES = Path(__file__).with_name("fixtures") / "skill-workflow-cases.json"
MATRIX = CASES.with_name("workflow-qualification-matrix-20261127.json")
RESOLVE_ARGS = [
    "--ordinary-native-action", "resolve", "--task-class", "exploration",
    "--role", "analyst", "--host-controls", "explicit", "--caller-rationale",
    "Local fixture, read only.", "--approved-scope-json", '{"read":true}',
]


def load_cases():
    return json.loads(CASES.read_text(encoding="utf-8"))


def endpoint(url):
    u = urlsplit(url)
    if (u.scheme != "http" or not u.hostname or u.username is not None
            or u.path not in ("", "/") or u.query or u.fragment or u.port is None
            or not ipaddress.ip_address(u.hostname).is_loopback):
        raise ValueError("provide an explicit HTTP loopback address and port")
    return f"http://{u.netloc}/v1/chat/completions"


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def make_payload(model, messages):
    return dict(model=model, messages=messages, stream=True, temperature=0,
                seed=7, cache_prompt=False,
                chat_template_kwargs={"enable_thinking": False})


def read_stream(lines):
    answer = []
    done, finish, reasoning = False, None, False
    for line in lines:
        if not line.startswith(b"data:"):
            continue
        data = line.removeprefix(b"data:").strip()
        if data == b"[DONE]":
            done = True
            break
        row = json.loads(data)
        if "error" in row:
            return "incomplete:server", None
        for choice in row.get("choices", []):
            delta = choice.get("delta", {})
            reasoning |= bool(delta.get("reasoning_content"))
            answer.append(delta.get("content") or "")
            finish = choice.get("finish_reason") or finish
    if not done:
        return "incomplete:no-done", None
    if reasoning:
        return "incomplete:mode-mismatch", None
    answer = "".join(answer).strip()
    if finish != "stop" or not answer:
        return f"incomplete:{finish or 'empty'}", None
    return "complete", answer


def ask(url, model, messages, idle_seconds):
    req = Request(url, data=json.dumps(make_payload(model, messages)).encode(),
                  headers={"Content-Type": "application/json"})
    try:
        with build_opener(ProxyHandler({}), NoRedirect()).open(req, timeout=idle_seconds) as stream:
            return read_stream(stream)
    except (URLError, OSError, ValueError, TypeError, AttributeError):
        return "incomplete:transport-or-stream", None


def resolve(args, catalog):
    cmd = [sys.executable, "-B", str(ROOT / "scripts/resolve-agents-mode.py"),
           "--provider", "codex", "--json", *args]
    return json.loads(subprocess.check_output(cmd, input=json.dumps(catalog).encode(), cwd=ROOT))


def user(text):
    return {"role": "user", "content": text}


def field(answer, key):
    if not answer:
        return None
    try:
        if answer.startswith(chr(96) * 3):
            answer = answer.split("\n", 1)[1].rsplit(chr(96) * 3, 1)[0]
        return json.loads(answer).get(key)
    except (ValueError, AttributeError, IndexError):
        return None


def pack_catalog():
    rows = []
    paths = {}
    for path in sorted((ROOT / "src.codex" / "skills").glob("*/SKILL.md")):
        lines = path.read_text(encoding="utf-8-sig").splitlines()
        desc = next((x[13:].strip().strip('"') for x in lines[:8] if x.startswith("description: ")), None)
        if desc:
            name = path.parent.name
            identity = f"pack:{name}"
            rows.append(dict(id=identity, name=name, description=desc, source="pack", available=True))
            paths[identity] = path
    return rows, paths


def evaluate(case, model):
    rows, paths = pack_catalog()
    search_args = ["--skill-query", case["query"]]
    if "group" in case:
        search_args += ["--skill-group", case["group"]]
    choices = resolve(search_args, rows)["skills"]
    expected = f"pack:{case['skill']}"
    result = dict(expected=expected, offered=[r["id"] for r in choices],
                  read="not-run", task_response="not-run", task_verdict="ungraded")
    if expected not in result["offered"]:
        result["selection"] = "resolver-miss"
        return result
    status, answer = model([user(case["task"] + "\nChoose one listed skill or null. "
                                 "Return only JSON with skill_id.\n" + json.dumps(choices))])
    if status != "complete":
        result["selection"] = status
        return result
    selected = field(answer, "skill_id")
    result["selected"] = selected
    if selected != expected:
        result["selection"] = "wrong-or-none"
        return result
    decision = resolve(RESOLVE_ARGS + ["--worker-skill-id", selected], rows)
    ref = decision.get("invocation", {}).get("taskSkill")
    if not ref or ref["id"] != selected or ref["source"] != "pack":
        result["selection"] = "worker-unavailable"
        return result
    result["selection"] = "confirmed"
    task = case["task"] + "\nGive a concrete next step and a test."
    msg = user(task + "\nLead offers this skill: " + json.dumps(ref)
               + '. Request it with JSON key open_skill and the exact id, or answer directly.')
    status, request = model([msg])
    if status != "complete":
        result["read"] = status
        return result
    if field(request, "open_skill") != selected:
        result["read"] = "not-requested"
        result["direct_answer"] = request
        return result
    data = paths[selected].read_bytes()
    result["read"] = "confirmed"
    result["skill_sha256"] = hashlib.sha256(data).hexdigest()
    status, answer = model([msg, {"role": "assistant", "content": request},
                            user("Exact skill read result:\n" + data.decode("utf-8-sig")
                                 + "\nAnswer the original task now. Do not invoke tools.")])
    result.update(task_response=status, task_answer=answer)
    return result


def first_read_pair(case, model):
    """Record the first request and resulting harness open, not model uptake."""
    skill = case["skill"]
    if not isinstance(skill, str) or re.fullmatch(r"[a-z0-9][a-z0-9_-]*", skill) is None:
        raise ValueError("invalid first-read fixture skill name")
    path = ROOT / "src.codex" / "skills" / skill / "SKILL.md"
    alias = f".agents/skills/{skill}/SKILL.md"
    confirmed_digest = None
    shared = {"role": "system", "content": (
        "You have a local read-only file tool. To invoke it, return exactly one line "
        "beginning READ_FILE followed by the path, and nothing else. The harness "
        "will then read the file. If you do not need to inspect a file, answer normally. "
        f"Optional project guidance available: {skill} ({case['skill_summary']}), at {alias}."
    )}
    arms = {}
    for arm, addition in (("baseline", ""), ("workflow", f"\n\nApproved inputs: Read {alias} before diagnosing.")):
        status, answer = model([shared, user(case["task"] + addition)])
        row = dict(response=status, answer=answer, read="not-evaluated",
                   content_delivered_to_model=False)
        if status == "complete":
            lines = answer.strip().splitlines()
            parts = lines[0].split(maxsplit=1) if len(lines) == 1 else []
            requested = parts[1].strip().strip("\"'").strip(chr(96)).replace("\\", "/") if len(parts) == 2 else ""
            if parts[:1] == ["READ_FILE"] and requested.removeprefix("./") == alias:
                row["requested_path"] = alias
                try:
                    digest = hashlib.sha256(path.read_bytes()).hexdigest()
                except OSError:
                    row["read_evidence"] = "harness-open-failed"
                else:
                    if confirmed_digest is not None and confirmed_digest != digest:
                        row["read_evidence"] = "fixture-changed"
                    else:
                        confirmed_digest = digest
                        row.update(read="confirmed", read_evidence="harness-open-after-request",
                                   skill_sha256=digest)
            else:
                row["read"] = "not-requested"
        arms[arm] = row
    before, after = (arms[k]["read"] for k in ("baseline", "workflow"))
    if "not-evaluated" in (before, after):
        contrast = "incomplete"
    elif after == "confirmed":
        contrast = "both-read" if before == "confirmed" else "baseline-miss-workflow-read"
    else:
        contrast = "baseline-only" if before == "confirmed" else "neither-read"
    return {"contrast": contrast, "arms": arms}


def load_matrix_cases(data=None):
    rows = json.loads(MATRIX.read_bytes() if data is None else data)["matrix"]
    return {row["id"]: row for row in rows if row["kind"] == "workflow" and "input" in row
            and (row["id"].startswith("bugfix-") or "workflow_evidence" in row or row.get("goal_rule")
                 or "assignment_catalog" in row or "ordinary_hook_replay" in row)}


def run_matrix_pair(case, model, work_dir=None):
    if "assignment_catalog" in case:
        return assignment_pair(case, model)
    goal_rule = case.get("goal_rule")
    ordinary = "ordinary_hook_replay" in case
    if not goal_rule and not ordinary and "workflow_evidence" not in case:
        return diagnosis_pair(case, model)
    result = {"arms": {}}
    if ordinary:
        preamble = ordinary_preflight(case, work_dir)
        result["preflight"] = {"hook": "quiet", "task_skill": None}
    if goal_rule:
        shared = (ROOT / "shared/AGENTS.shared.md").read_text(encoding="utf-8")
        owner = selected_unit(shared, "Core delegation principles", "Goal resumption and hold currency (binding).")
        if not owner:
            raise RuntimeError("the binding Goal resumption rule was not found")
        result["owner_sha256"] = hashlib.sha256(owner.encode()).hexdigest()
    for arm in ("baseline", "workflow"):
        stimulus = dict(case["input"])
        frames = []
        if arm == "workflow":
            if goal_rule:
                frames.append({"role": "system", "content": owner})
            elif ordinary:
                frames.append({"role": "system", "content": preamble})
            else:
                stimulus["inventory"] = case["workflow_evidence"]
        status, answer = model(frames + [user(json.dumps(stimulus, ensure_ascii=False))])
        result["arms"][arm] = dict(run_id=case["run_ids"][arm], response=status, answer=answer,
                                   verdict="ungraded")
    return result


def ordinary_preflight(case, work_dir):
    catalog, _ = pack_catalog()
    decision = resolve(RESOLVE_ARGS + ["--repo-root", str(ROOT)], catalog)
    invocation = decision.get("invocation", {})
    if decision.get("status") != "resolved" or decision.get("taskContext") or invocation.get("taskSkill"):
        raise RuntimeError("ordinary fixture did not resolve without a task skill")
    replay = case["ordinary_hook_replay"]
    rows = [
        {"type": "response_item", "payload": {"type": "message", "role": "user",
         "content": [{"type": "input_text", "text": case["input"]["task"]}]}},
        {"type": "function_call_output", "output": replay["entry"]},
    ]
    with tempfile.TemporaryDirectory(dir=work_dir) as scratch:
        transcript = Path(scratch) / "ordinary.jsonl"
        transcript.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
        script = ROOT / "src.codex/skills/lead/scripts/check-bugfix-discipline.py"
        envelope = {"transcript_path": str(transcript), "tool_name": replay["tool_name"]}
        completed = subprocess.run([sys.executable, "-B", str(script)], input=json.dumps(envelope),
                                   capture_output=True, text=True, encoding="utf-8", cwd=scratch)
    if completed.returncode or completed.stdout or completed.stderr:
        raise RuntimeError("ordinary bugfix hook replay was not quiet")
    return invocation["promptPreamble"]


def assignment_pair(case, model):
    data = case["input"]
    catalog = case["assignment_catalog"]
    ranked = resolve(["--skill-query", data["query"], "--skill-group", data["group"]], catalog)["skills"]
    offered = [row for row in catalog if row["available"]]
    receiver = [row for row in catalog if row["id"] in data["receiving_ids"]]
    arms = {}
    for arm, choices in (("baseline", offered), ("workflow", ranked)):
        choices = [{key: row[key] for key in ("id", "name", "source", "description")}
                   for row in choices]
        status, answer = model([user(json.dumps({"task": data["task"], "choices": choices}))])
        selected = field(answer, "skill_id") if status == "complete" else None
        assignment = None
        if any(selected == row["id"] for row in choices):
            decision = resolve(RESOLVE_ARGS + ["--worker-skill-id", selected], receiver)
            assignment = decision.get("invocation", {}).get("taskSkill")
        arms[arm] = dict(run_id=case["run_ids"][arm], response=status, answer=answer,
                         offered=[row["id"] for row in choices], assignment=assignment,
                         verdict="ungraded")
    return {"arms": arms}


def diagnosis_pair(case, model):
    catalog, _ = pack_catalog()
    args = RESOLVE_ARGS + ["--repo-root", str(ROOT)]
    baseline = resolve(args, catalog)
    workflow = resolve(args + ["--task-action", "diagnose-defect"], catalog)
    context = workflow.get("taskContext", {})
    if (baseline.get("status") != "resolved" or workflow.get("status") != "resolved"
            or baseline.get("taskContext") or context.get("status") != "attached"):
        raise RuntimeError("diagnosis comparison did not resolve the expected pair")
    stimulus = user(json.dumps(case["input"], ensure_ascii=False))
    arms = {}
    for arm, selected in (("baseline", baseline), ("workflow", workflow)):
        preamble = selected["invocation"]["promptPreamble"]
        status, answer = model([{"role": "system", "content": preamble}, stimulus])
        arms[arm] = dict(run_id=case["run_ids"][arm], response=status, answer=answer,
                         verdict="ungraded")
    return {"task_context": context, "arms": arms}


def recording_model(path, metadata, model):
    request = 0

    def record(state, mode, **values):
        row = {**metadata, "request": request, "state": state,
               "utc": datetime.now(timezone.utc).isoformat(), **values}
        with path.open(mode, encoding="utf-8") as ledger:
            ledger.write(json.dumps(row) + "\n")
            ledger.flush()
            os.fsync(ledger.fileno())

    def invoke(messages):
        nonlocal request
        request += 1
        record("started", "x" if request == 1 else "a")
        status, answer = model(messages)
        record("returned", "a", response=status, answer=answer if status == "complete" else None)
        return status, answer

    return invoke


def write_matrix_case(out_path, row, fixture_sha256, model_name, invoke):
    metadata = {"case": row["id"], "model": model_name, "thinking": False,
                "fixture_sha256": fixture_sha256, "run_ids": row["run_ids"]}
    with out_path.open("x", encoding="utf-8") as out:
        model = recording_model(out_path.with_suffix(".progress.jsonl"), metadata, invoke)
        result = run_matrix_pair(row, model, out_path.parent)
        json.dump({**metadata, **result}, out, indent=2)
        out.write("\n")
    return all(arm["response"] == "complete" for arm in result["arms"].values())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    cases = load_cases()
    selector = parser.add_mutually_exclusive_group(required=True)
    selector.add_argument("--case", choices=sorted(cases))
    selector.add_argument("--matrix-case", "--matrix-diagnosis", help="Prepared paired workflow fixture ID")
    selector.add_argument("--matrix-batch", nargs="+", metavar="CASE",
                          help="Explicit prepared case IDs; --out is a new directory")
    parser.add_argument("--local-endpoint", required=True, help="Already running, explicitly authorized HTTP loopback server")
    parser.add_argument("--model", required=True)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--idle-seconds", type=float,
                        help="Optional socket idle timeout; unset waits for completion or interruption")
    parser.add_argument("--compare", action="store_true", help="Optional matched task-only pair; does not score the answers")
    args = parser.parse_args()
    if args.idle_seconds is not None and (not math.isfinite(args.idle_seconds) or args.idle_seconds <= 0):
        parser.error("idle timeout must be positive")
    try:
        url = endpoint(args.local_endpoint)
    except ValueError as exc:
        parser.error(str(exc))
    if args.matrix_case or args.matrix_batch:
        ids = args.matrix_batch or [args.matrix_case]
        fixture = MATRIX.read_bytes()
        matrix = load_matrix_cases(fixture)
        if args.compare or any(case_id not in matrix for case_id in ids):
            parser.error("expected prepared matrix case IDs without --compare")
        if len(ids) != len(set(ids)):
            parser.error("matrix case IDs must not repeat")
        if args.matrix_batch:
            try:
                args.out.mkdir()
            except FileExistsError:
                parser.error("matrix batch requires a new output directory")
            outputs = [args.out / (case_id + ".json") for case_id in ids]
        else:
            outputs = [args.out]
        fixture_sha256 = hashlib.sha256(fixture).hexdigest()
        def invoke(messages):
            return ask(url, args.model, messages, args.idle_seconds)
        results = [write_matrix_case(path, matrix[case_id], fixture_sha256, args.model, invoke)
                   for case_id, path in zip(ids, outputs)]
        return 0 if all(results) else 2
    case = cases[args.case]
    model = recording_model(
        args.out.with_suffix(".progress.jsonl"),
        {"case": args.case, "model": args.model, "thinking": False},
        lambda messages: ask(url, args.model, messages, args.idle_seconds),
    )
    if case.get("mode") == "first-read":
        with args.out.open("x", encoding="utf-8") as out:
            result = first_read_pair(case, model)
            json.dump({"case": args.case, "model": args.model, "thinking": False,
                       "fixture_sha256": hashlib.sha256(CASES.read_bytes()).hexdigest(),
                       **result}, out, indent=2)
            out.write("\n")
        if result["contrast"] == "incomplete":
            return 2
        return int(result["contrast"] != "baseline-miss-workflow-read")
    with args.out.open("x", encoding="utf-8") as out:
        result = evaluate(case, model)
        if args.compare and result["read"] == "confirmed":
            task = case["task"] + "\nGive a concrete next step and a test."
            data = pack_catalog()[1][result["selected"]].read_bytes()
            if hashlib.sha256(data).hexdigest() != result["skill_sha256"]:
                raise RuntimeError("skill changed before paired evaluation")
            pair = {}
            for arm, skill in (("baseline", ""), ("with_skill", "\n\nWorkflow skill:\n" + data.decode("utf-8-sig"))):
                status, answer = model([user(task + skill)])
                pair[arm] = {"response": status, "answer": answer, "verdict": "ungraded"}
            result["comparison"] = pair
        json.dump({"case": args.case, "model": args.model, "thinking": False,
                   "fixture_sha256": hashlib.sha256(CASES.read_bytes()).hexdigest(), **result},
                  out, indent=2)
        out.write("\n")
    stages = [result[k] for k in ("selection", "read", "task_response")]
    stages.extend(arm["response"] for arm in result.get("comparison", {}).values())
    if any(stage.startswith("incomplete:") for stage in stages):
        return 2
    return int(result["read"] != "confirmed" or result["task_response"] != "complete")


if __name__ == "__main__":
    raise SystemExit(main())
