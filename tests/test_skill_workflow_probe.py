import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).parent
spec = importlib.util.spec_from_file_location("skill_workflow_probe", HERE / "skill_workflow_probe.py")
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def response(text, finish="stop", done=True):
    payload = {"choices": [{"delta": {"content": text}, "finish_reason": finish}]}
    wire = b"data: " + json.dumps(payload).encode() + b"\n\n"
    return io.BytesIO(wire + (b"data: [DONE]\n\n" if done else b""))


class SkillWorkflowProbeTests(unittest.TestCase):
    def test_completion_requires_terminal_marker_and_stop(self):
        self.assertEqual(probe.read_stream(response("OK")), ("complete", "OK"))
        self.assertEqual(probe.read_stream(response("partial", "length")), ("incomplete:length", None))
        self.assertEqual(probe.read_stream(response("partial", done=False)), ("incomplete:no-done", None))

    def test_only_loopback_and_no_arbitrary_answer_cap(self):
        self.assertEqual(probe.endpoint("http://127.0.0.1:18843"), "http://127.0.0.1:18843/v1/chat/completions")
        for host in ("http://example.com", "http://localhost@other:1", "http://127.0.0.1:1/api"):
            with self.subTest(host=host), self.assertRaises(ValueError):
                probe.endpoint(host)
        self.assertNotIn("max_tokens", probe.make_payload("local", [{"role": "user", "content": "Task"}]))

    def test_cli_idle_timeout_is_opt_in(self):
        args = [
            "probe", "--case", "bugfix-first-read", "--local-endpoint", "http://127.0.0.1:18843",
            "--model", "local", "--out", "not-written.json",
        ]
        def pair(_case, model):
            model([probe.user("fixture")])
            return {"contrast": "both-read"}
        for flags, expected in (([], None), (["--idle-seconds", "45"], 45.0)):
            with self.subTest(flags=flags), patch.object(probe.sys, "argv", args + flags), \
                    patch.object(probe, "first_read_pair", side_effect=pair), \
                    patch.object(probe, "ask") as ask, \
                    patch.object(probe, "recording_model", side_effect=lambda _path, _metadata, fn: fn), \
                    patch.object(probe.Path, "open", autospec=True) as open_path:
                fixture_stream = io.StringIO(json.dumps({"bugfix-first-read": {"mode": "first-read"}}))
                open_path.side_effect = [fixture_stream, io.StringIO(), io.BytesIO(b"fixture")]
                self.assertEqual(probe.main(), 1)
                self.assertEqual(ask.call_args.args[-1], expected)

    def test_interruption_keeps_prior_request_and_marks_unfinished_one(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "case.json"
            args = [
                "probe", "--case", "bugfix-first-read", "--local-endpoint", "http://127.0.0.1:18843",
                "--model", "local", "--out", str(path),
            ]
            with patch.object(probe.sys, "argv", args), patch.object(
                probe, "ask", side_effect=[("complete", "baseline answer"), KeyboardInterrupt]
            ), self.assertRaises(KeyboardInterrupt):
                probe.main()
            ledger = path.with_suffix(".progress.jsonl")
            rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
            self.assertEqual([(r["request"], r["state"]) for r in rows],
                             [(1, "started"), (1, "returned"), (2, "started")])
            self.assertEqual(rows[1]["response"], "complete")
            self.assertEqual(rows[1]["answer"], "baseline answer")
            self.assertEqual(path.read_text(encoding="utf-8"), "")

    def test_matrix_diagnosis_pair_carries_identical_evidence_and_no_rubric(self):
        cases = probe.load_matrix_cases()
        case = cases["bugfix-one-start"]
        observed = []
        def model(messages):
            observed.append(messages)
            return "complete", "synthetic answer"
        result = probe.diagnosis_pair(case, model)
        self.assertEqual([r["run_id"] for r in result["arms"].values()], list(case["run_ids"].values()))
        self.assertTrue(all(r["verdict"] == "ungraded" for r in result["arms"].values()))
        self.assertEqual(observed[0][-1], observed[1][-1])
        self.assertIn("receipt-802", observed[0][-1]["content"])
        for frame in observed:
            self.assertNotIn(case["criteria"], json.dumps(frame))
        skill = (probe.ROOT / "src.codex/skills/bug-hunting/SKILL.md").read_bytes().decode()
        self.assertNotIn(skill, observed[0][0]["content"])
        self.assertEqual(observed[1][0]["content"].count(skill), 1)

    def test_matrix_cli_returns_no_grade_for_transport_success(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "case.json"
            args = ["probe", "--matrix-diagnosis", "bugfix-two-starts", "--local-endpoint",
                    "http://127.0.0.1:18843", "--model", "local", "--out", str(out)]
            with patch.object(probe.sys, "argv", args), patch.object(
                probe, "ask", side_effect=[("complete", "baseline"), ("complete", "workflow")]
            ) as ask:
                self.assertEqual(probe.main(), 0)
            self.assertEqual(ask.call_count, 2)
            result = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(len(result["fixture_sha256"]), 64)
            self.assertFalse(result["thinking"])
            self.assertEqual([r["verdict"] for r in result["arms"].values()], ["ungraded"] * 2)
            ledger = out.with_suffix(".progress.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual([json.loads(row)["state"] for row in ledger],
                             ["started", "returned", "started", "returned"])
            self.assertEqual(json.loads(ledger[-1])["run_ids"], result["run_ids"])

    def test_matrix_batch_keeps_incomplete_case_and_runs_the_rest(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "batch"
            ids = ["bugfix-one-start", "bugfix-two-starts", "census-known", "census-unknown"]
            args = ["probe", "--matrix-batch", *ids, "--local-endpoint", "http://127.0.0.1:18843",
                    "--model", "local", "--out", str(out)]
            answers = [("incomplete:length", None)] + [("complete", "test only")] * 7
            with patch.object(probe.sys, "argv", args), patch.object(
                probe, "ask", side_effect=answers
            ) as ask:
                self.assertEqual(probe.main(), 2)
                self.assertEqual(ask.call_count, 8)
                with self.assertRaises(SystemExit):
                    probe.main()
                self.assertEqual(ask.call_count, 8)
            saved_ids = set()
            for case_id in ids:
                path = out / (case_id + ".json")
                result = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(result["case"], case_id)
                self.assertEqual([r["verdict"] for r in result["arms"].values()], ["ungraded"] * 2)
                saved_ids.update(r["run_id"] for r in result["arms"].values())
                self.assertEqual(len(path.with_suffix(".progress.jsonl").read_text(encoding="utf-8").splitlines()), 4)
            self.assertEqual(len(saved_ids), 8)
            self.assertEqual(json.loads((out / "bugfix-one-start.json").read_text(encoding="utf-8"))
                             ["arms"]["baseline"]["response"], "incomplete:length")

    def test_matrix_ordinary_uses_quiet_hook_and_no_skill(self):
        case = probe.load_matrix_cases()["ordinary"]
        frames = []
        def model(messages):
            frames.append(messages)
            return "complete", "synthetic answer"
        with tempfile.TemporaryDirectory() as d:
            result = probe.run_matrix_pair(case, model, Path(d))
            bug = {**case, "input": {**case["input"], "task": case["ordinary_hook_replay"]["entry"]}}
            with self.assertRaisesRegex(RuntimeError, "was not quiet"):
                probe.run_matrix_pair(bug, model, Path(d))
            self.assertEqual(list(Path(d).iterdir()), [])
        self.assertEqual(len(frames), 2)
        self.assertEqual(frames[0][-1], frames[1][-1])
        self.assertEqual(len(frames[0]), 1)
        self.assertEqual(len(frames[1]), 2)
        self.assertNotIn("fix the broken regression", json.dumps(frames))
        self.assertEqual(result["preflight"], {"hook": "quiet", "task_skill": None})
        self.assertTrue(all(row["verdict"] == "ungraded" for row in result["arms"].values()))

    def test_matrix_assignment_checks_actual_receiving_identity(self):
        case = probe.load_matrix_cases()["installed-assignment"]
        seen = []
        def model(messages):
            seen.append(json.loads(messages[-1]["content"]))
            skill_id = "pack:review" if len(seen) == 1 else "plugin:review"
            return "complete", json.dumps({"skill_id": skill_id})
        arms = probe.run_matrix_pair(case, model)["arms"]
        self.assertEqual(seen[0]["task"], seen[1]["task"])
        self.assertEqual({row["id"] for row in seen[0]["choices"]}, {"pack:review", "plugin:review"})
        self.assertEqual({row["id"] for row in seen[1]["choices"]}, {"pack:review", "plugin:review"})
        self.assertEqual(seen[0]["choices"][0]["id"], "pack:review")
        self.assertEqual(seen[1]["choices"][0]["id"], "plugin:review")
        self.assertEqual(arms["baseline"]["assignment"]["id"], "pack:review")
        self.assertEqual(arms["workflow"]["assignment"],
                         {"id": "plugin:review", "source": "plugin", "name": "review"})
        self.assertTrue(all(r["verdict"] == "ungraded" for r in arms.values()))
        unavailable = {**case, "input": {**case["input"], "receiving_ids": ["pack:review"]}}
        refused = probe.run_matrix_pair(unavailable, lambda _: (
            "complete", '{"skill_id": "plugin:review"}'))["arms"]
        self.assertTrue(all(r["assignment"] is None for r in refused.values()))

    def test_matrix_resume_uses_shared_owner_and_does_not_change_history(self):
        from policy_text_contract import selected_unit

        case = probe.load_matrix_cases()["resume"]
        frames = []
        def model(messages):
            frames.append(messages)
            return "complete", "synthetic answer"
        result = probe.run_matrix_pair(case, model)
        self.assertEqual(len(frames[0]), 1)
        self.assertEqual(frames[0][-1], frames[1][-1])
        shared = (probe.ROOT / "shared/AGENTS.shared.md").read_text(encoding="utf-8")
        owner = selected_unit(shared, "Core delegation principles", "Goal resumption and hold currency (binding).")
        self.assertEqual(frames[1][0], {"role": "system", "content": owner})
        stimulus = json.loads(frames[1][-1]["content"])
        self.assertNotIn("criteria", stimulus)
        timeline = stimulus["event_log"]
        self.assertEqual(stimulus["recovery_summary"]["copied_from_event_id"], timeline[0]["id"])
        self.assertEqual(timeline[-1]["source"], "user")
        self.assertEqual(timeline[-1]["action"], "resume")
        self.assertEqual(timeline[0]["goal_id"], timeline[-1]["goal_id"])
        self.assertEqual(timeline[0]["scope"], timeline[-1]["scope"])
        self.assertEqual(stimulus["native_goal"]["id"], timeline[-1]["goal_id"])
        self.assertEqual([row["verdict"] for row in result["arms"].values()], ["ungraded"] * 2)

    def test_matrix_census_arm_adds_only_physical_inventory(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "case.json"
            args = ["probe", "--matrix-case", "census-unknown", "--local-endpoint",
                    "http://127.0.0.1:18843", "--model", "local", "--out", str(out)]
            seen = []
            def answer(_url, _model, messages, _idle_seconds):
                seen.append(json.loads(messages[-1]["content"]))
                return "complete", "test only"
            with patch.object(probe.sys, "argv", args), patch.object(probe, "ask", side_effect=answer):
                self.assertEqual(probe.main(), 0)
            self.assertEqual(len(seen), 2)
            self.assertNotIn("operator-note.txt", json.dumps(seen[0]))
            inventory = seen[1].pop("inventory")
            self.assertIn("operator-note.txt", [x["name"] for x in inventory["children"]])
            self.assertEqual(seen[0], seen[1])
            self.assertNotIn("criteria", seen[0])
            saved = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(saved["arms"]["workflow"]["verdict"], "ungraded")

    def test_confirmed_case_requires_actual_read_and_excludes_rubric(self):
        case = probe.load_cases()["mesh-importer"]
        target = "pack:" + case["skill"]
        choices = [{"id": target, "name": case["skill"], "source": "pack", "description": "Example"}]
        observed = []

        def model(messages):
            observed.append(json.dumps(messages))
            data = [json.dumps({"skill_id": target}), json.dumps({"open_skill": target}), "A final answer"]
            return "complete", data[len(observed) - 1]

        def resolve(args, catalog):
            if args[0] == "--skill-query":
                return {"skills": choices}
            return {"status": "resolved", "invocation": {"taskSkill": {"id": target, "source": "pack", "name": case["skill"]}}}

        with patch.object(probe, "resolve", side_effect=resolve):
            result = probe.evaluate(case, model)
        self.assertEqual(result["read"], "confirmed")
        self.assertEqual(result["task_response"], "complete")
        self.assertEqual(result["task_verdict"], "ungraded")
        self.assertEqual(len(result["skill_sha256"]), 64)
        self.assertTrue(all(case["criteria"][0] not in msg for msg in observed))

    def test_selection_does_not_count_as_read(self):
        case = probe.load_cases()["mesh-importer"]
        target = "pack:" + case["skill"]
        choices = [{"id": target}]
        answers = iter([("complete", json.dumps({"skill_id": target})),
                        ("complete", "I can answer without opening the file.")])
        def resolve(args, catalog):
            if args[0] == "--skill-query":
                return {"skills": choices}
            return {"status": "resolved", "invocation": {"taskSkill": {"id": target, "source": "pack", "name": case["skill"]}}}
        with patch.object(probe, "resolve", side_effect=resolve):
            result = probe.evaluate(case, lambda _: next(answers))
        self.assertEqual(result["read"], "not-requested")
        self.assertNotIn("skill_sha256", result)


    def test_first_read_pair_counts_contrast_not_incomplete(self):
        case = probe.load_cases()["bugfix-first-read"]
        alias = ".agents/skills/bug-hunting/SKILL.md"
        observed = []

        def model(messages):
            observed.append(messages)
            return ("complete", "READ_FILE ./src/receipts.py" if len(observed) == 1 else f"READ_FILE {alias}")

        result = probe.first_read_pair(case, model)
        self.assertEqual(result["contrast"], "baseline-miss-workflow-read")
        self.assertEqual(result["arms"]["baseline"]["read"], "not-requested")
        self.assertEqual(result["arms"]["workflow"]["read"], "confirmed")
        self.assertEqual(len(result["arms"]["workflow"]["skill_sha256"]), 64)
        self.assertEqual(observed[0][0], observed[1][0])
        self.assertTrue(observed[1][1]["content"].startswith(observed[0][1]["content"]))
        replies = iter([("incomplete:length", None), ("complete", f"READ_FILE {alias}")])
        self.assertEqual(probe.first_read_pair(case, lambda _: next(replies))["contrast"], "incomplete")
        self.assertEqual(probe.first_read_pair(case, lambda _: ("complete", f"READ_FILE {alias}"))["contrast"],
                         "both-read")


    def test_first_read_evidence_requires_terminal_exact_request_and_successful_open(self):
        case = probe.load_cases()["bugfix-first-read"]
        alias = ".agents/skills/bug-hunting/SKILL.md"
        skill = probe.ROOT / "src.codex" / "skills" / "bug-hunting" / "SKILL.md"
        expected = probe.hashlib.sha256(skill.read_bytes()).hexdigest()
        events = []
        real_read = Path.read_bytes

        def read(path):
            events.append(("read", path))
            return real_read(path)

        def compare(replies):
            events.clear()
            replies = iter(replies)

            def model(messages):
                events.append(("model", messages))
                return next(replies)

            with patch.object(Path, "read_bytes", read):
                return probe.first_read_pair(case, model)

        request = f"READ_FILE {alias}"
        result = compare([("complete", f"I opened {alias}."), ("complete", request)])
        self.assertEqual([event[0] for event in events], ["model", "model", "read"])
        self.assertEqual(events[-1], ("read", skill))
        self.assertEqual(result["arms"]["baseline"]["read"], "not-requested")
        self.assertNotIn("skill_sha256", result["arms"]["baseline"])
        self.assertEqual(result["arms"]["workflow"]["requested_path"], alias)
        self.assertEqual(result["arms"]["workflow"]["read_evidence"], "harness-open-after-request")
        self.assertEqual(result["arms"]["workflow"]["skill_sha256"], expected)
        self.assertFalse(result["arms"]["workflow"]["content_delivered_to_model"])

        result = compare([("complete", request + "\nI opened it."), ("incomplete:no-done", request)])
        self.assertEqual(result["contrast"], "incomplete")
        self.assertEqual([event[0] for event in events], ["model", "model"])
        self.assertTrue(all("skill_sha256" not in arm for arm in result["arms"].values()))

        with patch.object(Path, "read_bytes", side_effect=PermissionError) as denied:
            result = probe.first_read_pair(case, lambda _: ("complete", request))
        self.assertEqual(denied.call_count, 2)
        self.assertEqual(result["contrast"], "incomplete")
        for arm in result["arms"].values():
            self.assertEqual(arm["read_evidence"], "harness-open-failed")
            self.assertNotIn("skill_sha256", arm)


if __name__ == "__main__":
    unittest.main()
