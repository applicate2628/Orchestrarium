#!/usr/bin/env python3
"""Shared standard-library runtime for the provider skill-pack validators."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import re
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Sequence


def _load_process_runner_module():
    module_name = "_orchestrarium_process_runner_v1"
    existing = sys.modules.get(module_name)
    if existing is not None:
        return existing
    path = Path(__file__).resolve().parent / "process_supervision" / "process_runner.py"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("process-runner-v1-unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(module_name, None)
        raise
    return module


_PROCESS_RUNNER = _load_process_runner_module()
CapturePolicyV1 = _PROCESS_RUNNER.CapturePolicyV1
EnvironmentRowV1 = _PROCESS_RUNNER.EnvironmentRowV1
ProcessRequestV1 = _PROCESS_RUNNER.ProcessRequestV1
ProcessRunnerV1 = _PROCESS_RUNNER.ProcessRunnerV1
SettlePolicyV1 = _PROCESS_RUNNER.SettlePolicyV1
WindowsArgvAttestationV1 = _PROCESS_RUNNER.WindowsArgvAttestationV1


VALIDATOR_CHILD_TIMEOUT_SECONDS = 120.0
VALIDATOR_SETTLEMENT_TIMEOUT_SECONDS = 5.0
VALIDATOR_ORCHESTRATION_SECONDS = 2.0
VALIDATOR_ENVIRONMENT_ALLOWLIST = (
    "ALLUSERSPROFILE",
    "APPDATA",
    "COMSPEC",
    "HOME",
    "HOMEDRIVE",
    "HOMEPATH",
    "LANG",
    "LC_ALL",
    "LOCALAPPDATA",
    "PATH",
    "PATHEXT",
    "PROGRAMDATA",
    "PROGRAMFILES",
    "PROGRAMW6432",
    "PUBLIC",
    "PYTHONIOENCODING",
    "PYTHONUTF8",
    "SYSTEMDRIVE",
    "SYSTEMROOT",
    "TEMP",
    "TMP",
    "TMPDIR",
    "USERPROFILE",
    "WINDIR",
)


LAW_ID_RE = re.compile(r"\b(A[1-9]|B[1-3]|C[1-6]|D[1-5])\b")
ACTION_SCOPES = frozenset(
    {"all", "dev_repo", "dev_repo_nonstandalone", "installed"}
)
PROJECT_SPECIFIC_UPGRADE_LEDGER_MARKERS = (
    "work-items/roadmaps/orchestrator-upgrades.md",
    "orchestrator upgrades",
    "orchestrarium upgrades",
    "orchestrator upgrade ledger",
    "orchestrarium upgrade ledger",
)


@dataclass(frozen=True)
class Layout:
    root: Path
    provider: str
    dev_repo: bool
    standalone: bool
    pack: Path
    skills: Path
    scripts: Path
    agents_text: str


@dataclass(frozen=True)
class ValidatorCapturePolicyV1:
    """Single owner of the validator's enforceable capture values."""

    policy_id: str = "validator-bounded-v1"
    aggregate_persisted_limit: int = 1024 * 1024
    prefix_limit_per_stream: int = 64 * 1024
    tail_limit_per_stream: int = 128 * 1024
    chunk_size: int = 64 * 1024

    def to_capture_policy(self) -> CapturePolicyV1:
        return CapturePolicyV1(
            policy_id=self.policy_id,
            aggregate_persisted_limit=self.aggregate_persisted_limit,
            prefix_limit_per_stream=self.prefix_limit_per_stream,
            tail_limit_per_stream=self.tail_limit_per_stream,
            chunk_size=self.chunk_size,
        )


@dataclass(frozen=True)
class ValidatorProcessResultV1:
    returncode: int
    stdout: str
    stderr: str
    failure_id: str | None
    timed_out: bool
    stdout_observed_bytes: int
    stdout_persisted_bytes: int
    stdout_truncated: bool
    stderr_observed_bytes: int
    stderr_persisted_bytes: int
    stderr_truncated: bool
    resources_closed: bool
    settlement_state: str
    tree_empty: bool
    direct_reaped: bool
    primary_thread_closed: bool
    job_handle_closed: bool


def required_validator_sequence_budget(child_deadlines: Sequence[float]) -> float:
    deadlines = tuple(child_deadlines)
    if not deadlines:
        return 0.0
    if any(
        not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value <= 0
        for value in deadlines
    ):
        raise ValueError("validator-child-deadline-invalid")
    return (
        sum(float(value) + VALIDATOR_SETTLEMENT_TIMEOUT_SECONDS for value in deadlines)
        + VALIDATOR_ORCHESTRATION_SECONDS
    )


def validator_environment_rows() -> tuple[EnvironmentRowV1, ...]:
    return tuple(
        EnvironmentRowV1(name, os.environ[name])
        for name in VALIDATOR_ENVIRONMENT_ALLOWLIST
        if name in os.environ
    )


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def common_skill_body_sha256(content: bytes) -> str:
    """Hash a common-skill body after canonical newline/frontmatter handling."""
    normalized = content.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    lines = normalized.splitlines(keepends=True)
    body_start = 0
    if lines and lines[0].strip() == b"---":
        for index in range(1, len(lines)):
            if lines[index].strip() == b"---":
                body_start = index + 1
                break
    return hashlib.sha256(b"".join(lines[body_start:])).hexdigest()


def _assembled_codex_agents(root: Path) -> str:
    shared = _read(root / "shared/AGENTS.shared.md").rstrip()
    codex = _read(root / "src.codex/AGENTS.codex.md").rstrip()
    return (
        "<!-- BEGIN ORCHESTRARIUM CODEX PACK -->\n"
        f"{shared}\n\n{codex}\n"
        "<!-- END ORCHESTRARIUM CODEX PACK -->\n"
    )


def detect_layout(script: Path, provider: str, requested_root: Path | None = None) -> Layout:
    candidates: list[Path] = []
    if requested_root is not None:
        candidates.append(requested_root.resolve())
    logical_script = script.expanduser().absolute()
    candidates.extend(logical_script.parents)
    candidates.extend(logical_script.resolve().parents)
    candidates.append(Path.cwd().resolve())
    seen: set[Path] = set()
    for root in candidates:
        if root in seen:
            continue
        seen.add(root)
        if provider == "codex":
            dev_scripts = root / "src.codex/skills/lead/scripts"
            if (
                dev_scripts.is_dir()
                and (root / "shared/AGENTS.shared.md").is_file()
                and (root / "src.codex/AGENTS.codex.md").is_file()
            ):
                return Layout(
                    root=root,
                    provider=provider,
                    dev_repo=True,
                    standalone=not (root / "src.claude").is_dir(),
                    pack=root / "src.codex",
                    skills=root / "src.codex/skills",
                    scripts=dev_scripts,
                    agents_text=_assembled_codex_agents(root),
                )
            if (root / ".codex/skills").is_dir() and (root / ".codex/AGENTS.md").is_file():
                return Layout(
                    root=root,
                    provider=provider,
                    dev_repo=False,
                    standalone=True,
                    pack=root / ".codex",
                    skills=root / ".codex/skills",
                    scripts=root / ".codex/skills/lead/scripts",
                    agents_text=_read(root / ".codex/AGENTS.md"),
                )
            if (root / ".agents/skills").is_dir() and (root / "AGENTS.md").is_file():
                return Layout(
                    root=root,
                    provider=provider,
                    dev_repo=False,
                    standalone=True,
                    pack=root / ".agents",
                    skills=root / ".agents/skills",
                    scripts=root / ".agents/skills/lead/scripts",
                    agents_text=_read(root / "AGENTS.md"),
                )
        else:
            if (root / "src.claude/agents").is_dir() and (root / "shared/AGENTS.shared.md").is_file():
                return Layout(
                    root=root,
                    provider=provider,
                    dev_repo=True,
                    standalone=not (root / "src.codex").is_dir(),
                    pack=root / "src.claude",
                    skills=root / "src.claude/skills",
                    scripts=root / "src.claude/agents/scripts",
                    agents_text=_read(root / "shared/AGENTS.shared.md"),
                )
            if (root / ".claude/agents").is_dir():
                agents = root / ".claude/AGENTS.md"
                if not agents.is_file():
                    agents = root / ".claude/AGENTS.shared.md"
                if agents.is_file():
                    return Layout(
                        root=root,
                        provider=provider,
                        dev_repo=False,
                        standalone=True,
                        pack=root / ".claude",
                        skills=root / ".claude/skills",
                        scripts=root / ".claude/agents/scripts",
                        agents_text=_read(agents),
                    )
    expected = "src.codex/.codex/.agents" if provider == "codex" else "src.claude/.claude"
    raise RuntimeError(f"Could not detect Orchestrarium {provider} layout ({expected}).")


def _argv_sha256(argv: Sequence[str]) -> str:
    return hashlib.sha256(
        json.dumps(list(argv), ensure_ascii=False, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()


def _python_argv_attestation(
    executable: Path,
    argv: tuple[str, ...],
) -> WindowsArgvAttestationV1 | None:
    if os.name != "nt":
        return None
    digest = _argv_sha256(argv)
    return WindowsArgvAttestationV1(
        schema_version=1,
        codec="msvcrt-v1",
        parser_family="msvcrt-compatible-v1",
        resolved_executable_identity=(
            _PROCESS_RUNNER.resolve_executable_identity(executable)
        ),
        resolved_executable_version=(
            _PROCESS_RUNNER.resolve_executable_version(executable)
        ),
        covered_argv_shapes=("python-script", "generic"),
        probe_requested_argv_sha256=digest,
        probe_observed_argv_sha256=digest,
        probe_status="pass",
    )


def _diagnostic_text(
    content: bytes,
    policy: ValidatorCapturePolicyV1,
) -> str:
    retained = policy.prefix_limit_per_stream + policy.tail_limit_per_stream
    if len(content) > retained:
        content = (
            content[: policy.prefix_limit_per_stream]
            + content[-policy.tail_limit_per_stream :]
        )
    return content.decode("utf-8", errors="replace")


class Validator:
    def __init__(
        self,
        layout: Layout,
        *,
        process_runner=None,
        child_timeout_seconds: float = VALIDATOR_CHILD_TIMEOUT_SECONDS,
    ) -> None:
        if (
            not isinstance(child_timeout_seconds, (int, float))
            or not math.isfinite(child_timeout_seconds)
            or child_timeout_seconds <= 0
        ):
            raise ValueError("validator-child-deadline-invalid")
        self.layout = layout
        self.passed = 0
        self.warnings = 0
        self.errors = 0
        self.process_failure_id: str | None = None
        self._process_runner = (
            process_runner if process_runner is not None else ProcessRunnerV1()
        )
        self._child_timeout_seconds = child_timeout_seconds
        self._runner_closed = False

    @property
    def checks(self) -> int:
        return self.passed + self.warnings + self.errors

    def logical_path(self, value: str) -> str:
        replacements = (
            ("@PACK", str(self.layout.pack)),
            ("@SKILLS", str(self.layout.skills)),
            ("@SCRIPTS", str(self.layout.scripts)),
            ("@ROOT", str(self.layout.root)),
        )
        if value == "shared/AGENTS.shared.md" and self.layout.provider == "claude":
            return "@AGENTS"
        if (
            value == "@ROOT/src.codex/AGENTS.codex.md"
            and self.layout.provider == "codex"
        ):
            return "@AGENTS"
        if value == "@ROOT/scripts/skill_pack_validator_runtime.py":
            if self.layout.dev_repo:
                return str(self.layout.root / "scripts" / "skill_pack_validator_runtime.py")
            return str(self.layout.scripts / "skill_pack_validator_runtime.py")
        provider_prefixes = (
            ("@ROOT/src.codex/", "codex"),
            ("src.codex/", "codex"),
            ("@ROOT/src.claude/", "claude"),
            ("src.claude/", "claude"),
        )
        for prefix, provider in provider_prefixes:
            if self.layout.provider == provider and value.startswith(prefix):
                return str(self.layout.pack / value.removeprefix(prefix))
        for token, target in replacements:
            if value.startswith(token):
                return target + value.removeprefix(token)
        return value

    def display(self, value: str) -> str:
        if value == "@AGENTS":
            return "AGENTS.md"
        projected = self.logical_path(value)
        return projected.replace("@AGENTS", "AGENTS.md")

    def path(self, value: str) -> Path:
        projected = self.logical_path(value)
        if projected == "@AGENTS":
            raise ValueError("@AGENTS is a virtual assembled document")
        path = Path(projected)
        return path if path.is_absolute() else self.layout.root / path

    def text(self, value: str) -> str:
        if self.logical_path(value) == "@AGENTS":
            return self.layout.agents_text
        return _read(self.path(value))

    def is_file(self, value: str) -> bool:
        return self.logical_path(value) == "@AGENTS" or self.path(value).is_file()

    def ok(self, label: str) -> None:
        self.passed += 1
        print(f"  PASS  {self.display(label)}")

    def fail(self, label: str) -> None:
        self.errors += 1
        print(f"  FAIL  {self.display(label)}")

    def warn(self, label: str) -> None:
        self.warnings += 1
        print(f"  WARN  {self.display(label)}")

    def _read_or_fail(self, file: str, label: str) -> str | None:
        if not self.is_file(file):
            self.fail(f"{label} (file missing: {file})")
            return None
        return self.text(file)

    def check_pointer(self, file: str, target: str) -> None:
        if not self.is_file(file):
            self.fail(f"{file} missing")
        elif target in self.text(file):
            self.ok(f"{file} points to {target}")
        else:
            self.fail(f"{file} missing canonical shared link {target}")

    def check_contains(self, file: str, pattern: str, label: str) -> None:
        text = self._read_or_fail(file, label)
        if text is not None:
            (self.ok if pattern in text else self.fail)(label)

    def check_absent(self, file: str, pattern: str, label: str) -> None:
        text = self._read_or_fail(file, label)
        if text is not None:
            (self.fail if pattern in text else self.ok)(label)

    def check_reusable_instruction_boundaries(self) -> None:
        roots = [self.layout.skills]
        if self.layout.provider == "claude":
            roots.append(self.layout.pack / "agents")
        hits: list[str] = []
        for root in roots:
            if not root.is_dir():
                continue
            for path in sorted(root.rglob("*.md")):
                text = _read(path).casefold()
                normalized = re.sub(r"[-_]+", " ", text)
                matched = tuple(
                    marker
                    for marker in PROJECT_SPECIFIC_UPGRADE_LEDGER_MARKERS
                    if marker in text or marker in normalized
                )
                if matched:
                    try:
                        display = path.relative_to(self.layout.pack).as_posix()
                    except ValueError:
                        display = str(path)
                    hits.append(f"{display} ({', '.join(matched)})")
        label = (
            "installable skill/agent instructions contain no project-specific "
            "Orchestrarium upgrade-ledger obligation"
        )
        if hits:
            self.fail(f"{label}: {'; '.join(hits)}")
        else:
            self.ok(label)

    def check_file(self, file: str, label: str) -> None:
        (self.ok if self.is_file(file) else self.fail)(label)

    def check_not_exists(self, path: str, label: str) -> None:
        (self.ok if not self.path(path).exists() else self.fail)(label)

    def check_max_lines(self, file: str, maximum: str, label: str) -> None:
        text = self._read_or_fail(file, label)
        if text is None:
            return
        actual = text.count("\n")
        limit = int(maximum)
        suffix = f" ({actual} <= {limit})" if actual <= limit else f" ({actual} > {limit})"
        (self.ok if actual <= limit else self.fail)(label + suffix)

    @staticmethod
    def _h2(text: str, heading: str) -> str:
        lines = text.splitlines()
        try:
            start = lines.index(heading)
        except ValueError:
            return ""
        end = len(lines)
        for index in range(start + 1, len(lines)):
            if lines[index].startswith("## "):
                end = index
                break
        return "\n".join(lines[start:end])

    def check_h2_section_contains(
        self, file: str, heading: str, pattern: str, label: str
    ) -> None:
        text = self._read_or_fail(file, label)
        if text is None:
            return
        section = self._h2(text, heading)
        if not section:
            self.fail(f"{label} (missing section: {heading})")
        else:
            (self.ok if pattern in section else self.fail)(label)

    def check_h2_section_absent(
        self, file: str, heading: str, pattern: str, label: str
    ) -> None:
        text = self._read_or_fail(file, label)
        if text is None:
            return
        section = self._h2(text, heading)
        if not section:
            self.fail(f"{label} (missing section: {heading})")
        else:
            (self.fail if pattern in section else self.ok)(label)

    def check_exact_h2_inventory(self, file: str, label: str, *expected: str) -> None:
        text = self._read_or_fail(file, label)
        if text is None:
            return
        actual = tuple(line for line in text.splitlines() if line.startswith("## "))
        (self.ok if actual == tuple(expected) else self.fail)(label)

    def check_normalized_sha256(self, file: str, expected: str, label: str) -> None:
        if not self.is_file(file):
            self.fail(f"{label} (file missing: {file})")
            return
        data = self.path(file).read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        (self.ok if hashlib.sha256(data).hexdigest() == expected else self.fail)(label)

    def check_common_skill_body_pin(self, name: str, expected: str, file: str) -> None:
        if not self.is_file(file):
            self.fail(f"common-skill {name} body-parity pin (file missing: {file})")
            return
        actual = common_skill_body_sha256(self.path(file).read_bytes())
        if actual == expected:
            self.ok(f"common-skill {name} body matches its provider-local body pin")
        else:
            self.fail(
                f"common-skill {name} body drifted from its provider-local body pin "
                f"(expected {expected}, actual {actual})"
            )

    def _run_python(
        self,
        script: Path,
        *args: str,
        timeout_seconds: float | None = None,
    ) -> ValidatorProcessResultV1:
        deadline_seconds = (
            self._child_timeout_seconds
            if timeout_seconds is None
            else timeout_seconds
        )
        if (
            not isinstance(deadline_seconds, (int, float))
            or not math.isfinite(deadline_seconds)
            or deadline_seconds <= 0
        ):
            raise ValueError("validator-child-deadline-invalid")
        executable = Path(sys.executable).resolve()
        argv = (str(executable), str(script), *args)
        capture_policy = ValidatorCapturePolicyV1()
        sink = self._process_runner.mint_memory_capture_sink()
        request = ProcessRequestV1(
            schema_version=1,
            argv=argv,
            resolved_executable=executable,
            cwd=str(self.layout.root),
            environment=validator_environment_rows(),
            stdin_bytes=None,
            deadline_monotonic=time.monotonic() + float(deadline_seconds),
            capture_policy=capture_policy.to_capture_policy(),
            capture_sink_binding=sink,
            settle_policy=SettlePolicyV1(
                timeout_seconds=VALIDATOR_SETTLEMENT_TIMEOUT_SECONDS
            ),
            windows_argv_codec="msvcrt-v1" if os.name == "nt" else None,
            windows_argv_attestation=_python_argv_attestation(executable, argv),
        )
        result = self._process_runner.run(request)
        stdout = sink.bytes_for("stdout")
        stderr = sink.bytes_for("stderr")
        returncode = (
            result.target_exit_code
            if result.outcome in {"success", "child-failure"}
            and result.target_exit_code is not None
            else 1
        )
        return ValidatorProcessResultV1(
            returncode=returncode,
            stdout=_diagnostic_text(stdout, capture_policy),
            stderr=_diagnostic_text(stderr, capture_policy),
            failure_id=result.failure_id,
            timed_out=result.timed_out,
            stdout_observed_bytes=result.stdout.observed_bytes,
            stdout_persisted_bytes=result.stdout.persisted_bytes,
            stdout_truncated=result.stdout.truncated,
            stderr_observed_bytes=result.stderr.observed_bytes,
            stderr_persisted_bytes=result.stderr.persisted_bytes,
            stderr_truncated=result.stderr.truncated,
            resources_closed=result.resources_closed,
            settlement_state=result.tree.settlement_state,
            tree_empty=result.tree.tree_empty,
            direct_reaped=result.tree.direct_reaped,
            primary_thread_closed=result.tree.primary_thread_closed,
            job_handle_closed=result.tree.job_handle_closed,
        )

    def close(self) -> None:
        if self._runner_closed:
            return
        self._runner_closed = True
        result = self._process_runner.close()
        if result.outcome != "closed":
            self.process_failure_id = result.failure_id
            self.fail(
                "validator process runner failed to settle "
                f"({result.failure_id or 'PSV1-RUNNER-CLOSE-INCOMPLETE'})"
            )

    def check_agent_run_ledger_contract(self, label: str) -> None:
        if not self.layout.dev_repo:
            self.warn(f"{label} (dev repo validator unavailable in installed layout)")
            return
        result = self._run_python(
            self.layout.root / "scripts/check-agent-run-ledger-contract.py",
            "--root",
            str(self.layout.root),
        )
        if result.returncode == 0:
            self.ok(label)
        else:
            if result.stdout:
                print(result.stdout.rstrip())
            if result.stderr:
                print(result.stderr.rstrip())
            self.fail(label)

    def check_arch_layering_slices(self, label: str) -> None:
        if not self.layout.dev_repo:
            self.warn(f"{label} (dev repo validator unavailable in installed layout)")
            return
        result = self._run_python(
            self.layout.root / "scripts/validate-arch-layering-slices.py",
            str(self.layout.root),
        )
        if result.returncode == 0:
            self.ok(label)
        else:
            if result.stdout:
                print(result.stdout.rstrip())
            if result.stderr:
                print(result.stderr.rstrip())
            self.fail(label)

    def check_normalizer_strips_example_auto_providers(self, label: str) -> None:
        if not self.layout.dev_repo:
            self.warn(f"{label} (dev repo normalizer unavailable in installed layout)")
            return
        normalizer = self.layout.root / "scripts/normalize-agents-mode.py"
        template = self.layout.root / "shared/agents-mode.defaults.yaml"
        cases = (
            (
                """externalProvider: auto
externalClaudeApiMode: force
externalPriorityProfile: custom-demo
reserveResolver: wrapper:tools/reserve-review.ps1
externalPriorityProfiles:
  custom-demo:
    advisory.repo-understanding: [claude, codex, reserve, gemini, qwen]
    advisory.design-adr: [claude-secret, codex, claude]
    advisory.legacy-secret-only: [claude-secret]
    review.security: [reserve, claude, codex]
    review.ui-visual-correctness: [claude, codex, reserve, gemini]
    design.ui-ux-structure: [reserve, codex, gemini, claude, qwen]
    worker.default-implementation: [reserve, claude, gemini, qwen, codex]
    worker.ui-structural-modernization: [codex, claude]
    review.visual: [claude, codex, reserve]
    worker.secret-only: [reserve, gemini, qwen]
externalOpinionCounts:
  review.visual: 2
""",
                (
                    "  custom-demo:",
                    "    advisory.repo-understanding: [claude, codex, reserve]",
                    "    advisory.design-adr: [codex, claude, reserve]",
                    "    advisory.legacy-secret-only: [reserve]",
                    "    review.security: [claude, codex, reserve]",
                    "    review.ui-visual-correctness: [codex, claude, reserve]",
                    "    design.ui-ux-structure: [codex, claude]",
                    "    worker.default-implementation: [claude, codex]",
                    "reserveResolver: wrapper:tools/reserve-review.ps1",
                ),
                (
                    "externalClaudeApiMode",
                    "worker.secret-only",
                    "worker.ui-structural-modernization",
                    "review.visual",
                ),
            ),
            (
                "externalProvider: auto\nreserveResolver: disabled\n",
                (
                    "reserveResolver: disabled",
                    "    advisory.repo-understanding: [claude, codex]",
                    "    review.ui-visual-correctness: [codex, claude]",
                ),
                (),
            ),
            (
                "externalProvider: auto\nexternalClaudeApiMode: disabled\n",
                (
                    "reserveResolver: disabled",
                    "    advisory.repo-understanding: [claude, codex]",
                    "    review.ui-visual-correctness: [codex, claude]",
                ),
                ("externalClaudeApiMode",),
            ),
        )
        with tempfile.TemporaryDirectory() as temp:
            for index, (source, required, forbidden) in enumerate(cases):
                target = Path(temp) / f"case-{index}.yaml"
                target.write_text(source, encoding="utf-8")
                result = self._run_python(
                    normalizer,
                    "--template",
                    str(template),
                    "--target",
                    str(target),
                    "--provider",
                    "shared",
                )
                output = target.read_text(encoding="utf-8", errors="replace")
                forbidden_profile_provider = re.search(
                    r"^    .+: \[[^\]]*(?:gemini|qwen)",
                    output,
                    re.MULTILINE,
                )
                forbidden_design_worker_reserve = re.search(
                    r"^    (?:design|worker)\..+: \[[^\]]*reserve",
                    output,
                    re.MULTILINE,
                )
                forbidden_disabled_reserve = index > 0 and re.search(
                    r"^    .+: \[[^\]]*reserve",
                    output,
                    re.MULTILINE,
                )
                if (
                    result.returncode != 0
                    or any(item not in output for item in required)
                    or any(item in output for item in forbidden)
                    or (index == 0 and forbidden_profile_provider)
                    or (index == 0 and forbidden_design_worker_reserve)
                    or forbidden_disabled_reserve
                ):
                    self.fail(label)
                    return
        self.ok(label)

    def check_shared_defaults_reserve_policy(self, label: str) -> None:
        if not self.layout.dev_repo:
            self.warn(f"{label} (dev repo defaults unavailable in installed layout)")
            return
        path = self.layout.root / "shared/agents-mode.defaults.yaml"
        if not path.is_file():
            self.fail(f"{label} (shared defaults missing)")
            return
        text = _read(path)
        expected = (
            "    advisory.repo-understanding: [claude, codex, reserve]",
            "    advisory.design-adr: [claude, codex, reserve]",
            "    review.pre-pr: [claude, codex, reserve]",
            "    review.security: [claude, codex, reserve]",
            "    review.performance-architecture: [codex, claude, reserve]",
            "    review.ui-visual-correctness: [codex, claude, reserve]",
        )
        forbidden_lane = re.search(
            r"^    (?:design|worker)\.[^:]+: \[[^\]]*(?:reserve|gemini|qwen)",
            text,
            re.MULTILINE,
        )
        example_provider = re.search(
            r"^    (?:advisory|design|review|worker)\.[^:]+: \[[^\]]*(?:gemini|qwen)",
            text,
            re.MULTILINE,
        )
        if (
            "externalClaudeApiMode" in text
            or "reserveResolver: claude-sonnet" not in text
            or any(item not in text for item in expected)
            or forbidden_lane
            or example_provider
        ):
            self.fail(label)
        else:
            self.ok(label)

    def check_skill_frontmatter_yaml(self, *roles: str) -> None:
        bad = []
        for role in roles:
            path = self.layout.skills / role / "SKILL.md"
            if not path.is_file():
                continue
            text = _read(path)
            if not text.startswith("---"):
                bad.append(str(path))
                continue
            parts = text.split("---", 2)
            if len(parts) < 3:
                bad.append(str(path))
                continue
            try:
                import yaml  # type: ignore[import-not-found]

                data = yaml.safe_load(parts[1])
                if not isinstance(data, dict):
                    bad.append(str(path))
            except ImportError:
                for line in parts[1].splitlines():
                    if line.strip() and not line.lstrip().startswith("#") and ":" not in line:
                        bad.append(str(path))
                        break
            except Exception:
                bad.append(str(path))
        (self.ok if not bad else self.fail)("Codex skill frontmatter is valid YAML")

    def check_openai_yaml_interface(self, file: str, label: str) -> None:
        text = self._read_or_fail(file, label)
        if text is None:
            return
        valid = False
        try:
            import yaml  # type: ignore[import-not-found]

            data = yaml.safe_load(text)
            interface = data.get("interface") if isinstance(data, dict) else None
            required = ("display_name", "short_description", "default_prompt")
            valid = isinstance(interface, dict) and all(
                isinstance(interface.get(key), str) and interface[key].strip()
                for key in required
            )
            if valid:
                valid = len(interface["default_prompt"]) <= 1024
        except ImportError:
            valid = bool(re.search(r"^interface:\s*$", text, re.MULTILINE))
            for key in ("display_name", "short_description", "default_prompt"):
                valid = valid and bool(re.search(rf"^\s+{key}:\s*\S", text, re.MULTILINE))
        except Exception:
            valid = False
        (self.ok if valid else self.fail)(label)

    def check_skill_description_budget(
        self, max_per_description: str, max_total_description: str, *roles: str
    ) -> None:
        per_limit = int(max_per_description)
        total_limit = int(max_total_description)
        missing: list[str] = []
        multiline: list[str] = []
        oversized: list[str] = []
        total = 0
        for role in roles:
            path = self.layout.skills / role / "SKILL.md"
            if not path.is_file():
                continue
            line = next(
                (item for item in _read(path).splitlines() if item.startswith("description:")),
                "",
            )
            value = line.partition(":")[2].strip()
            if not value:
                missing.append(role)
                continue
            if value.startswith((">", "|")):
                multiline.append(role)
                continue
            value = value.strip("\"'")
            total += len(value)
            if len(value) > per_limit:
                oversized.append(role)
        self.ok("Codex skill descriptions are single-line metadata") if not multiline else self.fail(
            "Codex skill descriptions are single-line metadata"
        )
        self.ok(f"Codex skill descriptions stay <= {per_limit} chars") if not (
            missing or oversized
        ) else self.fail(f"Codex skill descriptions stay <= {per_limit} chars")
        self.ok(
            f"Codex skill description total stays <= {total_limit} chars ({total})"
        ) if total <= total_limit else self.fail(
            f"Codex skill description total exceeded ({total} > {total_limit})"
        )

    def dispatch(self, operation: str, args: Sequence[str]) -> None:
        method = getattr(self, operation, None)
        if method is None or not callable(method):
            raise RuntimeError(f"unsupported validation operation: {operation}")
        method(*args)


def extract_roles(agents_text: str, heading: str) -> tuple[str, ...]:
    section = Validator._h2(agents_text, heading)
    return tuple(sorted(set(re.findall(r"\$([a-z][a-z-]{2,})", section))))


def codex_owned_skill_names(
    agents_text: str,
    utility_skills: frozenset[str],
) -> frozenset[str]:
    return utility_skills | frozenset(
        extract_roles(agents_text, "## Role index")
    )


def layering_ids_resolve(path: Path) -> tuple[bool, tuple[str, ...]]:
    text = _read(path)
    unresolved = []
    for law_id in sorted(set(LAW_ID_RE.findall(text))):
        if not re.search(rf"\*\*[^*]*\({law_id}(?:\)| )[^*]*\*\*", text):
            unresolved.append(law_id)
    return not unresolved, tuple(unresolved)


def skill_frontmatter_valid(path: Path, expected_name: str) -> bool:
    text = _read(path)
    if not text.startswith("---"):
        return False
    parts = text.split("---", 2)
    if len(parts) < 3:
        return False
    name = ""
    description = ""
    for line in parts[1].splitlines():
        if line.startswith("name:"):
            name = line.partition(":")[2].strip().strip("\"'")
        elif line.startswith("description:"):
            description = line.partition(":")[2].strip().strip("\"'")
    return name == expected_name and bool(description)


def installer_default_is_production_pair(root: Path) -> bool:
    path = root / "install.py"
    if not path.is_file():
        return False
    text = _read(path)
    match = re.search(r"^    actions = \{\n(?P<body>.*?)^    \}", text, re.MULTILINE | re.DOTALL)
    if not match:
        return False
    body = match.group("body")
    line = next((item for item in body.splitlines() if item.lstrip().startswith('"3":')), "")
    return (
        '"3": (("production", "codex"), ("production", "claude"))' in line
        and "gemini" not in line
        and "qwen" not in line
    )


def run_agents_mode_contract(validator: Validator) -> bool:
    root = validator.layout.root
    result = validator._run_python(
        root / "scripts/validate-agents-mode-contract.py",
        "--root",
        str(root),
    )
    return result.returncode == 0


def validate_ru_mirror_policy(
    reference_dirs: Iterable[Path],
    shared_reference_dir: Path,
    maintainer_only_names: frozenset[str],
) -> list[tuple[bool, str]]:
    results: list[tuple[bool, str]] = []
    for reference_dir in reference_dirs:
        for source in sorted(reference_dir.glob("*.md")):
            if source.name == "README.md":
                continue
            if (
                reference_dir.resolve() == shared_reference_dir.resolve()
                and source.name in maintainer_only_names
            ):
                results.append(
                    (True, f"{source} is maintainer-only; Russian mirror not required")
                )
                continue
            mirror = reference_dir / "ru" / source.name
            results.append(
                (
                    mirror.is_file(),
                    f"{mirror} mirrors {source.name}"
                    if mirror.is_file()
                    else f"{mirror} missing for {source.name}",
                )
            )
    return results


def json_has_key(path: Path, key: str) -> bool:
    try:
        data = json.loads(_read(path))
    except (OSError, json.JSONDecodeError):
        return False
    return key in data


def _verdict(
    validator: Validator,
    condition: bool,
    success: str,
    failure: str | None = None,
) -> None:
    if condition:
        validator.ok(success)
    else:
        validator.fail(failure or success)


def _direct(
    validator: Validator,
    kind: str,
    label: str,
    *,
    maintainer_only_shared_reference_names: frozenset[str],
    utility_skills: frozenset[str],
    curated_role_skills: frozenset[str],
    common_skill_pin_names: frozenset[str],
) -> None:
    layout = validator.layout
    if kind == "file":
        _verdict(validator, validator.is_file(label), label, f"{label} missing")
        return
    if kind == "codex_native_override":
        path = layout.root / ".codex" / "agents" / label
        if path.is_file():
            validator.warn(
                f"agents/{label} present (runtime/operator-owned; "
                "not validated as pack payload)"
            )
        else:
            validator.ok(f"agents/{label} not installed by Orchestrarium")
        return
    if kind == "exists":
        path = label.removesuffix(" exists")
        _verdict(validator, validator.is_file(path), label)
        return
    if kind == "ru_policy":
        shared = layout.root / "shared/references"
        dirs = [shared, layout.root / "references-codex"]
        if not layout.standalone:
            dirs.extend(
                layout.root / name
                for name in (
                    "references-claude",
                    "references-gemini",
                    "references-qwen",
                )
            )
        for passed, message in validate_ru_mirror_policy(
            dirs,
            shared,
            maintainer_only_shared_reference_names,
        ):
            (validator.ok if passed else validator.fail)(str(message))
        return
    if kind == "role_index_codex":
        roles = extract_roles(layout.agents_text, "## Role index")
        for role in roles:
            skill = layout.skills / role
            _verdict(
                validator,
                (skill / "SKILL.md").is_file(),
                str(skill / "SKILL.md"),
                f"{skill / 'SKILL.md'} missing",
            )
            _verdict(
                validator,
                (skill / "agents/openai.yaml").is_file(),
                str(skill / "agents/openai.yaml"),
                f"{skill / 'agents/openai.yaml'} missing",
            )
        return
    if kind == "utility_design_panel":
        _verdict(
            validator,
            "design-panel" in utility_skills,
            "design-panel is registered in UTILITY_SKILLS",
            "design-panel is missing from UTILITY_SKILLS",
        )
        return
    if kind == "orphan_codex":
        owned = codex_owned_skill_names(layout.agents_text, utility_skills)
        common = set(extract_roles(layout.agents_text, "## Common skills"))
        for directory in sorted(
            path for path in layout.skills.iterdir() if path.is_dir()
        ):
            name = directory.name
            if name in owned:
                continue
            if name in common:
                validator.ok(
                    f"Directory {directory}{Path('/') if False else ''}/ "
                    "is registered as a common skill"
                )
            else:
                validator.warn(
                    f"Directory {directory}/ exists but ${name} is not in AGENTS.md "
                    "role index or common-skill index"
                )
        return
    if kind == "common_pin_completeness":
        live_names = frozenset(extract_roles(layout.agents_text, "## Common skills"))
        for name in sorted(live_names):
            _verdict(
                validator,
                name in common_skill_pin_names,
                f"common-skill {name} has an applicable provider-local body pin",
                f"common-skill body pins missing: {name}",
            )
        for name in sorted(common_skill_pin_names - live_names):
            validator.fail(f"common-skill body pins extra: {name}")
        return
    if kind == "layering_codex":
        owned = codex_owned_skill_names(layout.agents_text, utility_skills)
        common = set(extract_roles(layout.agents_text, "## Common skills"))
        for path in sorted(layout.skills.glob("*/SKILL.md")):
            if path.parent.name in common or path.parent.name not in owned:
                continue
            passed, unresolved = layering_ids_resolve(path)
            _verdict(
                validator,
                passed,
                f"{path.parent.name}/SKILL.md: all layering-law IDs resolve in-file",
                f"{path.parent.name}/SKILL.md: law ID(s) {' '.join(unresolved)} "
                "used but no same-file labeled definition (**... (ID):** bullet)",
            )
        return
    if kind == "scripts_codex":
        for path in sorted(layout.scripts.glob("*.sh")):
            has_shebang = path.read_text(
                encoding="utf-8", errors="replace"
            ).startswith("#!")
            if has_shebang:
                validator.ok(f"{path} has shebang")
            else:
                validator.warn(f"{path} missing shebang line")
        return
    if kind == "role_index_claude":
        roles = set(extract_roles(layout.agents_text, "## Role index"))
        common = set(extract_roles(layout.agents_text, "## Common skills"))
        for role in sorted(roles):
            path = layout.pack / "agents" / f"{role}.md"
            _verdict(
                validator,
                path.is_file(),
                f"{role} has agent file",
                f"{role} in role index but {path} missing",
            )
        for name in sorted(common):
            path = layout.pack / "skills" / name / "SKILL.md"
            _verdict(
                validator,
                path.is_file(),
                f"{name} common skill has skill file",
                f"{name} in Common skills but {path} missing",
            )
        for path in sorted((layout.pack / "agents").glob("*.md")):
            name = path.stem
            if name in {"external-worker", "external-reviewer"}:
                validator.ok(f"{name} is an expected external adapter file")
            elif name in common:
                validator.ok(f"{name} is a delegate-style common-skill wrapper")
            elif name not in roles:
                validator.warn(
                    f"{name} has agent file but not in AGENTS.md role index"
                )
        return
    if kind == "curated_registry":
        roles = extract_roles(layout.agents_text, "## Role index")
        for role in roles:
            skill = layout.pack / "skills" / role / "SKILL.md"
            if not skill.is_file():
                continue
            _verdict(
                validator,
                role in curated_role_skills,
                f"{role} skill surface is in the curated role-skill registry",
                f"{role} has skills/{role}/SKILL.md but is not in the curated "
                f"role-skill registry ({' '.join(sorted(curated_role_skills))}) "
                "— roles-as-skills allowlist violation",
            )
        return
    if kind == "layering_claude":
        paths = sorted((layout.pack / "agents").glob("*.md"))
        paths.extend(
            layout.pack / "skills" / role / "SKILL.md"
            for role in (
                "lead",
                "product-manager",
                "analyst",
                "architect",
                "planner",
            )
            if (layout.pack / "skills" / role / "SKILL.md").is_file()
        )
        for path in paths:
            passed, unresolved = layering_ids_resolve(path)
            _verdict(
                validator,
                passed,
                f"{path.name}: all layering-law IDs resolve in-file",
                f"{path.name}: law ID(s) {' '.join(unresolved)} used but no "
                "same-file labeled definition (**... (ID):** bullet)",
            )
        return
    if kind == "team_templates":
        for path in sorted(
            (layout.pack / "agents/team-templates").glob("*.json")
        ):
            _verdict(
                validator,
                json_has_key(path, "requiresLead"),
                f"{path.name} has requiresLead",
                f"{path.name} missing requiresLead field",
            )
            _verdict(
                validator,
                json_has_key(path, "chain"),
                f"{path.name} has chain",
                f"{path.name} missing chain field",
            )
        return
    if kind == "command_prefixes":
        for path in sorted((layout.pack / "commands").glob("*.md")):
            name = path.stem
            _verdict(
                validator,
                name.startswith("agents-"),
                f"/{name} has the agents- prefix",
                f"/{name} command lacks the agents- prefix (key invariant)",
            )
        return
    if kind == "skill_frontmatter":
        for directory in sorted(
            path
            for path in (layout.pack / "skills").iterdir()
            if path.is_dir()
        ):
            path = directory / "SKILL.md"
            if not path.is_file():
                continue
            _verdict(
                validator,
                skill_frontmatter_valid(path, directory.name),
                f"skills/{directory.name} frontmatter valid "
                "(fence + name + description)",
                f"skills/{directory.name}/SKILL.md frontmatter invalid",
            )
        return
    if kind == "policy_catalog":
        path = layout.pack / "agents/contracts/policies-catalog.md"
        _verdict(
            validator,
            path.is_file(),
            "policy catalog exists",
            "policy catalog missing (commands reference it)",
        )
        return
    if kind == "scripts_claude":
        for path in sorted((layout.pack / "agents/scripts").glob("*.sh")):
            has_shebang = path.read_text(
                encoding="utf-8", errors="replace"
            ).startswith("#!")
            if has_shebang:
                validator.ok(f"{path.name} has shebang")
            else:
                validator.warn(f"{path.name} missing shebang line")
        return
    if kind == "installer_default":
        _verdict(
            validator,
            installer_default_is_production_pair(layout.root),
            "root Python installer default dispatch is Codex plus Claude only",
            "root Python installer default dispatch must be Codex plus Claude only",
        )
        return
    if kind == "agents_contract":
        _verdict(
            validator,
            run_agents_mode_contract(validator),
            "agents-mode machine-readable contract matches docs and init preset surfaces",
        )
        return
    if kind == "codex_line_budget":
        text = layout.agents_text
        begin = "<!-- BEGIN ORCHESTRARIUM CODEX PACK -->"
        end = "<!-- END ORCHESTRARIUM CODEX PACK -->"
        if begin in text and end in text:
            text = text[text.index(begin) : text.index(end) + len(end)]
        count = text.count("\n") + (0 if text.endswith("\n") else 1)
        _verdict(
            validator,
            count <= 420,
            f"Codex AGENTS.md pack section line budget <= 420 ({count})",
            f"Codex AGENTS.md pack section line budget exceeded ({count} > 420)",
        )
        return
    if kind == "agents_heading":
        heading = re.search(
            r"## (.+?)(?:'|) (?:present|missing) in AGENTS\.md",
            label,
        )
        name = heading.group(1) if heading else ""
        _verdict(
            validator,
            f"## {name}" in layout.agents_text,
            label,
            label.replace("present", "missing"),
        )
        return
    if kind == "claude_heading":
        text = (layout.pack / "CLAUDE.md").read_text(
            encoding="utf-8", errors="replace"
        )
        _verdict(
            validator,
            "## Delegation rule" in text,
            "## Delegation rule present in CLAUDE.md",
            "## Delegation rule missing from CLAUDE.md",
        )
        return
    raise RuntimeError(f"unsupported direct validation kind: {kind}")


def _scope_applies(scope: str, layout: Layout) -> bool:
    if scope == "all":
        return True
    if scope == "dev_repo":
        return layout.dev_repo
    if scope == "dev_repo_nonstandalone":
        return layout.dev_repo and not layout.standalone
    if scope == "installed":
        return not layout.dev_repo
    raise RuntimeError(f"unsupported validation scope: {scope}")


def _applicable_actions(
    actions: Sequence[tuple[str, ...] | tuple[str, Sequence[tuple[str, ...]]]],
    layout: Layout,
) -> Iterator[tuple[str, ...]]:
    for entry in actions:
        if (
            len(entry) == 2
            and entry[0] in ACTION_SCOPES
            and isinstance(entry[1], (tuple, list))
        ):
            scope = entry[0]
            grouped_actions = entry[1]
            if _scope_applies(scope, layout):
                yield from grouped_actions
            continue
        yield entry


def _planned_validator_child_deadlines(
    actions: Sequence[tuple[str, ...]],
    layout: Layout,
    child_timeout_seconds: float,
) -> tuple[float, ...]:
    if not layout.dev_repo:
        return ()
    count = 0
    for action in actions:
        operation = action[0]
        if operation in {
            "check_agent_run_ledger_contract",
            "check_arch_layering_slices",
        }:
            count += 1
        elif operation == "check_normalizer_strips_example_auto_providers":
            count += 3
        elif operation == "direct" and len(action) >= 2 and action[1] == "agents_contract":
            count += 1
    return (child_timeout_seconds,) * count


def validate_pack(
    *,
    script: Path,
    provider: str,
    actions: Sequence[tuple[str, ...]],
    maintainer_only_shared_reference_names: frozenset[str],
    utility_skills: frozenset[str],
    curated_role_skills: frozenset[str],
    root: Path | None = None,
    enforce_reusable_instruction_boundaries: bool = False,
    process_runner=None,
    child_timeout_seconds: float = VALIDATOR_CHILD_TIMEOUT_SECONDS,
    outer_budget_seconds: float | None = None,
) -> Validator:
    layout = detect_layout(script, provider, root)
    validator = Validator(
        layout,
        process_runner=process_runner,
        child_timeout_seconds=child_timeout_seconds,
    )
    try:
        if enforce_reusable_instruction_boundaries:
            validator.check_reusable_instruction_boundaries()
        applicable_actions = tuple(_applicable_actions(actions, layout))
        child_deadlines = _planned_validator_child_deadlines(
            applicable_actions,
            layout,
            child_timeout_seconds,
        )
        required_budget = required_validator_sequence_budget(child_deadlines)
        admitted_budget = (
            required_budget if outer_budget_seconds is None else outer_budget_seconds
        )
        if (
            not isinstance(admitted_budget, (int, float))
            or not math.isfinite(admitted_budget)
            or admitted_budget < required_budget
        ):
            validator.process_failure_id = "PSV1-DEADLINE-COMPOSITION"
            validator.fail(
                "validator process sequence budget is insufficient "
                "(PSV1-DEADLINE-COMPOSITION)"
            )
            return validator
        common_skill_pin_names = frozenset(
            action[1]
            for action in applicable_actions
            if len(action) >= 2 and action[0] == "check_common_skill_body_pin"
        )
        for action in applicable_actions:
            operation, *args = action
            if operation == "direct":
                _direct(
                    validator,
                    *args,
                    maintainer_only_shared_reference_names=(
                        maintainer_only_shared_reference_names
                    ),
                    utility_skills=utility_skills,
                    curated_role_skills=curated_role_skills,
                    common_skill_pin_names=common_skill_pin_names,
                )
            else:
                validator.dispatch(operation, args)
        return validator
    finally:
        validator.close()


def run_validator_cli(
    *,
    script: Path,
    provider: str,
    actions: Sequence[tuple[str, ...]],
    maintainer_only_shared_reference_names: frozenset[str],
    utility_skills: frozenset[str],
    curated_role_skills: frozenset[str],
    enforce_reusable_instruction_boundaries: bool = False,
    argv: list[str] | None = None,
    description: str | None = None,
) -> int:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--root",
        type=Path,
        help="validate this repository/install root",
    )
    args = parser.parse_args(argv)
    if provider == "claude":
        print("=== Claude Code pack validation ===")
    else:
        print("=== Codex skill pack validation ===")
    try:
        result = validate_pack(
            script=script,
            provider=provider,
            actions=actions,
            maintainer_only_shared_reference_names=(
                maintainer_only_shared_reference_names
            ),
            utility_skills=utility_skills,
            curated_role_skills=curated_role_skills,
            root=args.root,
            enforce_reusable_instruction_boundaries=(
                enforce_reusable_instruction_boundaries
            ),
        )
    except Exception as exc:
        print(f"  FAIL  validator runtime error: {exc}")
        return 1
    print("")
    print("=== Summary ===")
    if provider == "claude":
        print(
            f"  Checks: {result.checks}  |  Passed: {result.passed}  |  "
            f"Warnings: {result.warnings}  |  Errors: {result.errors}"
        )
        print(
            "  RESULT:",
            "FAIL"
            if result.errors
            else "PASS with warnings"
            if result.warnings
            else "PASS",
        )
    else:
        print(
            f"  PASS: {result.passed}  WARN: {result.warnings}  "
            f"FAIL: {result.errors}"
        )
        print(
            "VALIDATION FAILED"
            if result.errors
            else "VALIDATION PASSED (with warnings)"
            if result.warnings
            else "VALIDATION PASSED"
        )
    return 1 if result.errors else 0
