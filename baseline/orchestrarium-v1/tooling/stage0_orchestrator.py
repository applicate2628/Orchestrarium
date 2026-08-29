#!/usr/bin/env python3
from __future__ import annotations

from stage0_runtime import *
from stage0_evidence import *


def _assert_both_worktrees_clean(
    *,
    baseline_root: Path,
    baseline_ref: str,
    baseline_tree: str,
    candidate_root: Path,
    candidate_ref: str,
    tools: ExternalTools,
    env: Mapping[str, str],
) -> None:
    assert_clean_worktree(
        baseline_root,
        expected_ref=baseline_ref,
        expected_tree=baseline_tree,
        tools=tools,
        env=env,
    )
    assert_clean_worktree(
        candidate_root,
        expected_ref=candidate_ref,
        tools=tools,
        env=env,
    )


def _run_verification(
    args: argparse.Namespace, workspace: VerificationWorkspace
) -> tuple[int, Path, str]:
    if not sys.platform.startswith("linux"):
        raise VerificationError(
            "Stage 0 verifier requires Linux child-subreaper and /proc containment"
        )
    baseline_root = args.baseline_root.expanduser().resolve(strict=True)
    candidate_root = args.candidate_root.expanduser().resolve(strict=True)
    if baseline_root == candidate_root:
        raise VerificationError("baseline and candidate worktrees must be distinct")
    reviewed_ref = exact_ref(args.reviewed_ref, label="reviewed ref")
    trusted_root = workspace.trusted_root
    lane_root_base = workspace.lane_root
    for private_root in (trusted_root, lane_root_base):
        if _inside(private_root, baseline_root) or _inside(private_root, candidate_root):
            raise VerificationError(
                f"private verifier root must be outside both worktrees: {private_root}"
            )

    tools = ExternalTools(
        python=args.verifier_python,
        git=args.verifier_git,
        bash=args.verifier_bash,
    )
    tools.assert_outside((baseline_root, candidate_root))
    trusted_env = build_sanitized_env(
        tools=tools, lane_root=trusted_root / "trusted-environment"
    )
    candidate_head = (
        str(_run_git(tools, trusted_env, candidate_root, "rev-parse", "HEAD"))
        .strip()
        .lower()
    )
    if candidate_head != reviewed_ref:
        raise VerificationError(
            f"candidate HEAD does not match reviewed ref: {candidate_head} != {reviewed_ref}"
        )

    pin = load_pin_from_commit(tools, trusted_env, candidate_root, reviewed_ref)
    baseline_record = pin["baseline"]
    assert isinstance(baseline_record, dict)
    baseline_ref = exact_ref(str(baseline_record["commitSha"]), label="baseline ref")
    baseline_tree = exact_ref(str(baseline_record["treeSha"]), label="baseline tree")
    if reviewed_ref == baseline_ref:
        raise VerificationError("candidate ref resolves to the pinned baseline")

    _assert_both_worktrees_clean(
        baseline_root=baseline_root,
        baseline_ref=baseline_ref,
        baseline_tree=baseline_tree,
        candidate_root=candidate_root,
        candidate_ref=reviewed_ref,
        tools=tools,
        env=trusted_env,
    )

    dispositions = trusted_root / "reviewed-dispositions.json"
    dispositions.write_bytes(
        _git_show_bytes(
            tools, trusted_env, candidate_root, reviewed_ref, DISPOSITIONS_PATH
        )
    )
    state = {"sequence": 0}
    evidence = trusted_root / "evidence"
    baseline_evidence = evidence / "baseline"
    candidate_evidence = evidence / "candidate"
    reports = trusted_root / "reports"
    logs = trusted_root / "logs"
    for directory in (baseline_evidence, candidate_evidence, reports, logs):
        directory.mkdir(parents=True, exist_ok=True)

    tooling = pin["tooling"]
    assert isinstance(tooling, dict)
    inventory_record = tooling["inventoryGenerator"]
    assert isinstance(inventory_record, dict)
    for lane, root, ref, output_dir in (
        ("baseline", baseline_root, baseline_ref, baseline_evidence),
        ("candidate", candidate_root, reviewed_ref, candidate_evidence),
    ):
        result, _record = _invoke_frozen(
            "inventoryGenerator",
            (
                "--repo-root",
                os.fspath(root),
                "--repository",
                str(baseline_record["repository"]),
                "--ref",
                ref,
                "--git-executable",
                os.fspath(tools.git),
                "--output-dir",
                os.fspath(output_dir),
                "--generator-path",
                str(inventory_record["path"]),
                "--generator-blob-sha",
                str(inventory_record["gitBlobSha"]),
                "--generator-materialization",
                str(inventory_record["materialization"]),
                "--generator-source-path",
                str(inventory_record["sourcePath"]),
            ),
            state=state,
            pin=pin,
            tools=tools,
            env=trusted_env,
            candidate_root=candidate_root,
            reviewed_ref=reviewed_ref,
            trusted_root=trusted_root,
            cwd=trusted_root,
            log_path=logs / f"inventory-{lane}.log",
            timeout_seconds=args.timeout_seconds,
        )
        _require_result(result, label=f"{lane} inventory generation")

    result, _ = _invoke_frozen(
        "targetEffectGenerator",
        (
            "--inventory",
            os.fspath(baseline_evidence / "capability-inventory.json"),
            "--output",
            os.fspath(reports / "target-effect-baseline.json"),
        ),
        state=state,
        pin=pin,
        tools=tools,
        env=trusted_env,
        candidate_root=candidate_root,
        reviewed_ref=reviewed_ref,
        trusted_root=trusted_root,
        cwd=trusted_root,
        log_path=logs / "target-effect.log",
        timeout_seconds=args.timeout_seconds,
    )
    _require_result(result, label="target-effect generation")

    result, _ = _invoke_frozen(
        "capabilityComparator",
        (
            "--baseline-inventory",
            os.fspath(baseline_evidence / "capability-inventory.json"),
            "--candidate-inventory",
            os.fspath(candidate_evidence / "capability-inventory.json"),
            "--baseline-ref",
            baseline_ref,
            "--candidate-ref",
            reviewed_ref,
            "--dispositions",
            os.fspath(dispositions),
            "--output",
            os.fspath(reports / "capability-comparison.json"),
        ),
        state=state,
        pin=pin,
        tools=tools,
        env=trusted_env,
        candidate_root=candidate_root,
        reviewed_ref=reviewed_ref,
        trusted_root=trusted_root,
        cwd=trusted_root,
        log_path=logs / "capability-comparison.log",
        timeout_seconds=args.timeout_seconds,
    )
    _require_result(result, label="capability comparison", semantic=True)

    for index, relative in enumerate(FOCUSED_TESTS):
        focused_log = logs / f"focused-{index:02d}.log"
        result = run_repository_lane(
            [os.fspath(tools.python), relative],
            cwd=candidate_root,
            env=build_repository_env(
                tools=tools,
                lane_root=lane_root_base / f"focused-{index:02d}",
                repo_root=candidate_root,
            ),
            log_path=focused_log,
            timeout_seconds=args.timeout_seconds,
            tools=tools,
            trusted_root=trusted_root,
        )
        _require_result(result, label=f"focused suite {relative}")
        _assert_both_worktrees_clean(
            baseline_root=baseline_root,
            baseline_ref=baseline_ref,
            baseline_tree=baseline_tree,
            candidate_root=candidate_root,
            candidate_ref=reviewed_ref,
            tools=tools,
            env=trusted_env,
        )

    baseline_lane_root = lane_root_base / "pytest-baseline"
    candidate_lane_root = lane_root_base / "pytest-candidate"
    baseline_xml = baseline_evidence / "pytest.xml"
    candidate_xml = candidate_evidence / "pytest.xml"
    baseline_xml_identity = prepare_trusted_output(baseline_xml)
    baseline_result = run_repository_lane(
        [
            os.fspath(tools.python),
            "-m",
            "pytest",
            f"--junitxml={baseline_xml}",
        ],
        cwd=baseline_root,
        env=build_repository_env(
            tools=tools, lane_root=baseline_lane_root, repo_root=baseline_root
        ),
        log_path=logs / "pytest-baseline.log",
        timeout_seconds=args.timeout_seconds,
        tools=tools,
        trusted_root=trusted_root,
        mutable_paths=(baseline_xml,),
    )
    _verify_prepared_file(baseline_xml_identity, require_nonempty=True)
    if baseline_result.exit_code == 124:
        raise VerificationError("baseline Pytest timed out")

    candidate_xml_identity = prepare_trusted_output(candidate_xml)
    candidate_result = run_repository_lane(
        [
            os.fspath(tools.python),
            "-m",
            "pytest",
            f"--junitxml={candidate_xml}",
        ],
        cwd=candidate_root,
        env=build_repository_env(
            tools=tools, lane_root=candidate_lane_root, repo_root=candidate_root
        ),
        log_path=logs / "pytest-candidate.log",
        timeout_seconds=args.timeout_seconds,
        tools=tools,
        trusted_root=trusted_root,
        mutable_paths=(candidate_xml,),
    )
    _verify_prepared_file(candidate_xml_identity, require_nonempty=True)
    if candidate_result.exit_code == 124:
        raise VerificationError("candidate Pytest timed out")
    _assert_both_worktrees_clean(
        baseline_root=baseline_root,
        baseline_ref=baseline_ref,
        baseline_tree=baseline_tree,
        candidate_root=candidate_root,
        candidate_ref=reviewed_ref,
        tools=tools,
        env=trusted_env,
    )

    result, _ = _invoke_frozen(
        "pytestComparator",
        (
            "--baseline-junit",
            os.fspath(baseline_xml),
            "--candidate-junit",
            os.fspath(candidate_xml),
            "--baseline-exit",
            str(baseline_result.exit_code),
            "--candidate-exit",
            str(candidate_result.exit_code),
            "--baseline-ref",
            baseline_ref,
            "--candidate-ref",
            reviewed_ref,
            "--baseline-root",
            os.fspath(baseline_root),
            "--candidate-root",
            os.fspath(candidate_root),
            "--baseline-lane-root",
            os.fspath(baseline_lane_root),
            "--candidate-lane-root",
            os.fspath(candidate_lane_root),
            "--baseline-test-inventory",
            os.fspath(baseline_evidence / "test-inventory.json"),
            "--candidate-test-inventory",
            os.fspath(candidate_evidence / "test-inventory.json"),
            "--volatile-pattern",
            r"agents-mode-installer-regression[/\\][0-9a-f]{32}",
            "--output",
            os.fspath(reports / "pytest-comparison.json"),
        ),
        state=state,
        pin=pin,
        tools=tools,
        env=trusted_env,
        candidate_root=candidate_root,
        reviewed_ref=reviewed_ref,
        trusted_root=trusted_root,
        cwd=trusted_root,
        log_path=logs / "pytest-comparator.log",
        timeout_seconds=args.timeout_seconds,
    )
    _require_result(result, label="Pytest differential", semantic=True)

    for spec in VALIDATORS:
        baseline_log = logs / f"{spec.name}-baseline.log"
        candidate_log = logs / f"{spec.name}-candidate.log"
        baseline_validator = run_repository_lane(
            _validator_command(spec, tools),
            cwd=baseline_root,
            env=build_repository_env(
                tools=tools,
                lane_root=lane_root_base / f"{spec.name}-baseline",
                repo_root=baseline_root,
            ),
            log_path=baseline_log,
            timeout_seconds=args.timeout_seconds,
            tools=tools,
            trusted_root=trusted_root,
        )
        candidate_validator = run_repository_lane(
            _validator_command(spec, tools),
            cwd=candidate_root,
            env=build_repository_env(
                tools=tools,
                lane_root=lane_root_base / f"{spec.name}-candidate",
                repo_root=candidate_root,
            ),
            log_path=candidate_log,
            timeout_seconds=args.timeout_seconds,
            tools=tools,
            trusted_root=trusted_root,
        )
        _assert_both_worktrees_clean(
            baseline_root=baseline_root,
            baseline_ref=baseline_ref,
            baseline_tree=baseline_tree,
            candidate_root=candidate_root,
            candidate_ref=reviewed_ref,
            tools=tools,
            env=trusted_env,
        )
        comparison_args = [
            "--name",
            spec.name,
            "--baseline-exit",
            str(baseline_validator.exit_code),
            "--candidate-exit",
            str(candidate_validator.exit_code),
            "--baseline-log",
            os.fspath(baseline_log),
            "--candidate-log",
            os.fspath(candidate_log),
            "--baseline-root",
            os.fspath(baseline_root),
            "--candidate-root",
            os.fspath(candidate_root),
            "--baseline-ref",
            baseline_ref,
            "--candidate-ref",
            reviewed_ref,
            "--success-pattern",
            spec.success_pattern,
            "--failure-pattern",
            spec.failure_pattern,
            "--semantic-failure-exit",
            "1",
            "--output",
            os.fspath(reports / f"{spec.name}-comparison.json"),
        ]
        for pattern in spec.volatile_patterns:
            comparison_args.extend(("--volatile-pattern", pattern))
        result, _ = _invoke_frozen(
            "commandComparator",
            comparison_args,
            state=state,
            pin=pin,
            tools=tools,
            env=trusted_env,
            candidate_root=candidate_root,
            reviewed_ref=reviewed_ref,
            trusted_root=trusted_root,
            cwd=trusted_root,
            log_path=logs / f"{spec.name}-comparator.log",
            timeout_seconds=args.timeout_seconds,
        )
        _require_result(
            result, label=f"validator differential {spec.name}", semantic=True
        )
        report_path = reports / f"{spec.name}-comparison.json"
        if not report_path.is_file():
            raise VerificationError(
                f"validator comparator did not produce a fresh report: {spec.name}"
            )

    _assert_both_worktrees_clean(
        baseline_root=baseline_root,
        baseline_ref=baseline_ref,
        baseline_tree=baseline_tree,
        candidate_root=candidate_root,
        candidate_ref=reviewed_ref,
        tools=tools,
        env=trusted_env,
    )
    summary = _write_summary(
        trusted_root,
        status="PASS",
        baseline_ref=baseline_ref,
        candidate_ref=reviewed_ref,
        message=(
            "All focused, Pytest, capability, and validator differential gates passed."
        ),
    )
    output = safe_create_output_directory(candidate_root, reviewed_ref)
    _copy_reports(trusted_root, output)
    summary_text = summary.read_text(encoding="utf-8")
    return 0, output, summary_text


def run_verification(args: argparse.Namespace) -> tuple[int, Path, str]:
    with verification_workspace(
        preserve_failed=getattr(args, "preserve_failed_evidence", False)
    ) as workspace:
        return _run_verification(args, workspace)


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-root", type=Path, required=True)
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--reviewed-ref", required=True)
    parser.add_argument("--verifier-python", type=Path, required=True)
    parser.add_argument("--verifier-git", type=Path, required=True)
    parser.add_argument("--verifier-bash", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=900.0)
    parser.add_argument(
        "--preserve-failed-evidence",
        action="store_true",
        help="preserve the external trusted/lane roots only after a failed run",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        return_code, output, summary = run_verification(args)
        print(summary.rstrip())
        print(f"RESULT: PASS Stage 0 evidence copied to {output}")
        return return_code
    except VerificationBlocked as exc:
        print(f"RESULT: BLOCKED Stage 0: {exc}", file=sys.stderr)
        return 1
    except (VerificationError, OSError, ValueError) as exc:
        print(f"RESULT: FAIL Stage 0: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
