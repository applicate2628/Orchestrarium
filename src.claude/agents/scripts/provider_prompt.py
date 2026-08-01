#!/usr/bin/env python3
"""Shared Python owner for Codex and Claude file-based prompt transports."""

from __future__ import annotations

import ctypes
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

EFFORTS = frozenset({"low", "medium", "high", "xhigh", "max"})
ERROR_MARKER = re.compile(
    r"^([0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"(\.[0-9]+)?Z? )?(ERROR|FATAL|API Error)"
    r"(: | [A-Za-z0-9_]+(::[A-Za-z0-9_]+)*: )"
)
INVALID_SLUG = re.compile(r'[\\/:\*\?"<>\|\x00]')


@dataclass
class Control:
    topic: str | None = None
    prompt_file: Path | None = None
    ledger: str | None = None
    ledger_role: str = "architecture-reviewer"
    ledger_lane: str | None = None
    ledger_artifact: str | None = None
    ledger_closes: list[str] = field(default_factory=list)
    provider_flags: list[str] = field(default_factory=list)


def fail(message: str, code: int = 1) -> int:
    print(f"FAIL: {message}", file=sys.stderr)
    return code


def parse_control(argv: list[str]) -> Control:
    result = Control()
    seen_values: dict[str, object] = {}
    value_flags = {
        "-promptfile": "prompt_file",
        "--prompt-file": "prompt_file",
        "-ledger": "ledger",
        "--ledger": "ledger",
        "-ledgerrole": "ledger_role",
        "--ledger-role": "ledger_role",
        "-ledgerlane": "ledger_lane",
        "--ledger-lane": "ledger_lane",
        "-ledgerartifact": "ledger_artifact",
        "--ledger-artifact": "ledger_artifact",
        "-ledgercloses": "ledger_closes",
        "--ledger-closes": "ledger_closes",
    }
    index = 0
    while index < len(argv):
        token = argv[index]
        key = token.lower()
        if token == "--":
            result.provider_flags.extend(argv[index + 1 :])
            break
        if key in value_flags:
            if index + 1 >= len(argv):
                raise ValueError(f"{token} requires a value")
            value = argv[index + 1]
            attr = value_flags[key]
            if attr == "prompt_file":
                parsed_value: object = Path(value)
            elif attr == "ledger_closes":
                result.ledger_closes.append(value)
                index += 2
                continue
            else:
                parsed_value = value
            if attr in seen_values and seen_values[attr] != parsed_value:
                raise ValueError(f"conflicting values for {token}")
            seen_values[attr] = parsed_value
            setattr(result, attr, parsed_value)
            index += 2
            continue
        if result.topic is None:
            result.topic = token
        else:
            result.provider_flags.append(token)
        index += 1
    return result


def validate_topic(topic: str | None) -> str:
    if (
        not topic
        or len(topic) > 64
        or ".." in topic
        or INVALID_SLUG.search(topic)
    ):
        raise ValueError(
            f"invalid TopicSlug {topic!r} - must be 1-64 chars and exclude '..', "
            "path separators, drive/ADS separators, and Windows-invalid filename chars"
        )
    return topic


def resolved_profile(provider: str, flags: list[str]) -> tuple[list[str], str, str]:
    if not flags:
        flags = (
            ["--model", "gpt-5.6-sol", "-c", "model_reasoning_effort=xhigh"]
            if provider == "codex"
            else [
                "-p",
                "--output-format",
                "text",
                "--model",
                "opus",
                "--effort",
                "xhigh",
            ]
        )
    model = ""
    effort = ""
    for index, token in enumerate(flags):
        following = flags[index + 1] if index + 1 < len(flags) else ""
        if token == "--model" and following and not following.startswith("-"):
            model = following
        if provider == "codex" and token == "-c":
            matched = re.fullmatch(
                r'model_reasoning_effort="?(low|medium|high|xhigh|max)"?',
                following,
            )
            if matched:
                effort = matched.group(1)
        elif provider == "claude" and token == "--effort" and following in EFFORTS:
            effort = following
    if not model or not effort:
        example = (
            "--model gpt-5.6-sol -c model_reasoning_effort=xhigh"
            if provider == "codex"
            else "-p --output-format text --model opus --effort xhigh"
        )
        raise ValueError(
            f"A12 violation - resolved {provider} flags carry no explicit model "
            f"and/or effort. Pass the FULL per-profile flag set, e.g.: {example}"
        )
    return flags, model, effort


def _command_from_path(path: str) -> list[str] | None:
    candidate = Path(path).expanduser()
    resolved = str(candidate.resolve()) if candidate.is_file() else shutil.which(path)
    if not resolved:
        return None
    suffix = Path(resolved).suffix.lower()
    if suffix == ".py":
        return [sys.executable, resolved]
    if suffix == ".ps1":
        powershell = (
            shutil.which("pwsh")
            or shutil.which("pwsh.exe")
            or shutil.which("powershell")
            or shutil.which("powershell.exe")
        )
        if not powershell:
            return None
        return [
            powershell,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            resolved,
        ]
    if os.name == "nt" and suffix in {".cmd", ".bat"}:
        command_shell = os.environ.get("COMSPEC") or shutil.which("cmd.exe")
        if not command_shell:
            return None
        return [command_shell, "/d", "/s", "/c", resolved]
    if suffix == ".sh" and os.name == "nt":
        bash = shutil.which("bash")
        return [bash, resolved] if bash else None
    return [resolved]


def resolve_provider_command(provider: str) -> list[str] | None:
    environment_key = "CODEX_BIN" if provider == "codex" else "CLAUDE_BIN"
    requested = os.environ.get(environment_key)
    names = [requested] if requested else [provider, f"{provider}.exe", f"{provider}.cmd"]
    for name in names:
        if name:
            command = _command_from_path(name)
            if command:
                return command
    return None


def _truthy(value: str | None) -> bool:
    return bool(value and value.lower() in {"1", "true", "yes"})


def claude_commercial_auth_present() -> bool:
    if (
        os.environ.get("ANTHROPIC_API_KEY")
        or os.environ.get("ANTHROPIC_AUTH_TOKEN")
        or _truthy(os.environ.get("CLAUDE_CODE_USE_BEDROCK"))
        or _truthy(os.environ.get("CLAUDE_CODE_USE_VERTEX"))
        or os.environ.get("ORCHESTRARIUM_ALLOW_SUBSCRIPTION_CLAUDE") == "1"
    ):
        return True
    settings = [Path.home() / ".claude" / "settings.json", Path.cwd() / ".claude" / "settings.json"]
    for path in settings:
        try:
            if '"apiKeyHelper"' in path.read_text(encoding="utf-8"):
                return True
        except OSError:
            continue
    return False


def secure_output_dir(provider: str) -> Path:
    env_key = "CODEX_PROMPTS_DIR" if provider == "codex" else "CLAUDE_PROMPTS_DIR"
    output = Path(os.environ.get(env_key, f".scratch/{provider}-prompts"))
    existed = output.is_dir()
    output.mkdir(parents=True, exist_ok=True)
    if not existed:
        try:
            output.chmod(0o700)
        except OSError as exc:
            print(f"WARN: could not harden permissions on '{output}': {exc}", file=sys.stderr)
    return output


def reject_link(path: Path) -> None:
    if path.is_symlink() or (
        hasattr(os.path, "isjunction") and os.path.isjunction(path)
    ):
        raise ValueError(
            f"--prompt-file '{path}' is a symlink/junction/mount point; refusing to follow"
        )


def prompt_bytes(control: Control) -> bytes:
    if control.prompt_file is not None:
        if not control.prompt_file.is_file():
            raise ValueError(f"--prompt-file '{control.prompt_file}' does not exist")
        reject_link(control.prompt_file)
        return control.prompt_file.read_bytes()
    if sys.stdin.isatty():
        raise ValueError("no prompt provided (neither --prompt-file nor piped stdin)")
    return sys.stdin.buffer.read()


def write_private(path: Path, data: bytes) -> None:
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(data)


def _posix_start_marker(pid: int) -> str | None:
    try:
        raw = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
    except OSError:
        return None
    close = raw.rfind(") ")
    fields = raw[close + 2 :].split() if close >= 0 else []
    return fields[19] if len(fields) >= 20 else None


def process_start_marker(pid: int) -> str | None:
    if os.name != "nt":
        return _posix_start_marker(pid)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    handle = kernel32.OpenProcess(0x1000, False, pid)
    if not handle:
        return None
    try:
        creation = ctypes.c_ulonglong()
        exit_time = ctypes.c_ulonglong()
        kernel = ctypes.c_ulonglong()
        user = ctypes.c_ulonglong()
        if not kernel32.GetProcessTimes(
            handle,
            ctypes.byref(creation),
            ctypes.byref(exit_time),
            ctypes.byref(kernel),
            ctypes.byref(user),
        ):
            return None
        return str(creation.value)
    finally:
        kernel32.CloseHandle(handle)


def ledger_helper() -> Path | None:
    script_dir = Path(__file__).resolve().parent
    candidates = (
        script_dir / "agent-run-ledger.py",
        Path("scripts/agent-run-ledger.py"),
        script_dir.parents[2] / "scripts" / "agent-run-ledger.py",
    )
    return next((path for path in candidates if path.is_file()), None)


def run_ledger(args: list[str]) -> bool:
    helper = ledger_helper()
    if helper is None:
        return False
    return (
        subprocess.run(
            [sys.executable, str(helper), *args],
            capture_output=True,
            check=False,
        ).returncode
        == 0
    )


def codex_hook_health_helper(codex_home: Path) -> Path | None:
    installed_helper = codex_home / "skills" / "lead" / "scripts" / "check-hook-health.py"
    if installed_helper.is_file():
        return installed_helper

    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parents[2]
    source_helper = repo_root / "scripts" / "check-hook-health.py"
    if (repo_root / "shared" / "AGENTS.shared.md").is_file() and source_helper.is_file():
        return source_helper
    return None


def _trust_probe_env(codex_home: Path) -> dict[str, str]:
    allowed = {
        "COMSPEC",
        "LANG",
        "LC_ALL",
        "PATH",
        "PATHEXT",
        "SYSTEMROOT",
        "TEMP",
        "TMP",
        "TMPDIR",
        "WINDIR",
    }
    child = {key: value for key, value in os.environ.items() if key.upper() in allowed}
    child["CODEX_HOME"] = str(codex_home)
    return child


def require_codex_hook_trust(
    command: list[str],
    codex_home: Path,
    query_cwd: Path,
) -> int:
    helper = codex_hook_health_helper(codex_home)
    if helper is None:
        return fail("Codex hook trust helper was not found")
    host_os = "windows" if os.name == "nt" else "posix"
    target = (codex_home / "hooks.json").resolve(strict=False)
    inventory = helper.with_name("codex-hook-inventory.json")
    inventory_args = ["--inventory", str(inventory)] if inventory.is_file() else []
    try:
        completed = subprocess.run(
            [
                sys.executable,
                str(helper),
                "--target",
                str(target),
                "--platform",
                "codex",
                "--host-os",
                host_os,
                "--codex-trust-mode",
                "require",
                *inventory_args,
                "--codex-command-json",
                json.dumps(command),
                "--codex-home",
                str(codex_home),
                "--query-cwd",
                str(query_cwd),
            ],
            capture_output=True,
            text=True,
            check=False,
            cwd=query_cwd,
            env=_trust_probe_env(codex_home),
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return fail("Codex hook trust inventory query failed")
    if completed.returncode:
        detail = " ".join((completed.stderr or completed.stdout).split())[:512]
        return fail(detail or "Codex hook trust requirement failed")
    return 0


def ledger_common(
    control: Control,
    provider: str,
    model: str,
    effort: str,
    slug: str,
) -> list[str]:
    values = [
        "--role",
        control.ledger_role,
        "--execution-role",
        "external-reviewer",
        "--provider",
        provider,
        "--scope",
        f"external run: {slug}",
        "--model",
        model,
        "--effort",
        effort,
    ]
    if control.ledger_lane:
        values += ["--lane", control.ledger_lane]
    if control.ledger_artifact:
        values += ["--artifact", control.ledger_artifact]
    return values


def has_error_markers(path: Path) -> int:
    try:
        return sum(
            1
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
            if ERROR_MARKER.match(line)
        )
    except OSError:
        return 0


def final_nonblank_line(path: Path) -> str:
    try:
        lines = [
            line.rstrip("\r")
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
            if line.strip()
        ]
        return lines[-1] if lines else ""
    except OSError:
        return ""


def record_terminal(
    control: Control,
    provider: str,
    model: str,
    effort: str,
    slug: str,
    launch_run_id: str,
    exit_code: int,
    out_path: Path,
    err_path: Path,
    lastmsg_path: Path | None,
) -> None:
    verdict_path = (
        lastmsg_path
        if lastmsg_path is not None and lastmsg_path.is_file() and lastmsg_path.stat().st_size
        else out_path
    )
    final_line = final_nonblank_line(verdict_path)
    marker_count = has_error_markers(err_path)
    status, gate = "blocked", "none"
    if exit_code != 0:
        note = f"oracle: nonzero exit ({exit_code})"
    elif not verdict_path.is_file() or verdict_path.stat().st_size == 0:
        note = "oracle: empty .out"
    elif marker_count:
        note = f"oracle: err markers present ({marker_count})"
    elif final_line == "GATE: PASS":
        status, gate, note = "completed", "PASS", "oracle: final-line GATE: PASS"
    elif final_line == "GATE: REVISE":
        status, gate, note = "revise", "REVISE", "oracle: final-line GATE: REVISE"
    else:
        note = "oracle: final line is not an anchored GATE verdict"

    args = [
        "--work-item",
        control.ledger or "",
        "append",
        "--status",
        status,
        "--gate",
        gate,
        "--event-kind",
        "terminal",
        "--launch-run-id",
        launch_run_id,
        "--evidence",
        f"review:{verdict_path}",
        "--notes",
        note,
        *ledger_common(control, provider, model, effort, slug),
    ]
    if gate == "PASS":
        for closed in control.ledger_closes:
            args += ["--closes", closed]
    if not run_ledger(args):
        print(
            f"FAIL: the verdict in {verdict_path} is NOT in the ledger; "
            f"launch {launch_run_id} stays unsettled.",
            file=sys.stderr,
        )


def launch(provider: str, argv: list[str]) -> int:
    try:
        control = parse_control(argv)
        topic = validate_topic(control.topic)
        flags, model, effort = resolved_profile(provider, control.provider_flags)
    except ValueError as exc:
        return fail(str(exc))

    command = resolve_provider_command(provider)
    if command is None:
        key = "CODEX_BIN" if provider == "codex" else "CLAUDE_BIN"
        return fail(
            f"{provider} binary '{os.environ.get(key) or provider}' not found on PATH. "
            f"Set {key} if installed elsewhere."
        )
    if provider == "claude" and not claude_commercial_auth_present():
        print(
            "WARNING: Refusing automated Claude launch.\n"
            "Automated `claude -p` under a subscription is not permitted.\n"
            "Anthropic policy: https://code.claude.com/docs/en/legal-and-compliance\n\n"
            "Use commercial authentication (ANTHROPIC_API_KEY, "
            "ANTHROPIC_AUTH_TOKEN, apiKeyHelper, Amazon Bedrock, or Google "
            "Vertex AI), or explicitly set ORCHESTRARIUM_ALLOW_SUBSCRIPTION_CLAUDE=1.",
            file=sys.stderr,
        )
        return 3

    if provider == "codex":
        if not Path(command[0]).is_absolute() or not Path(command[0]).is_file():
            return fail("resolved Codex executable is not an absolute regular file")
        codex_home = Path(
            os.environ.get("CODEX_HOME") or Path.home() / ".codex"
        ).expanduser().resolve(strict=False)
        query_cwd = Path.cwd().resolve()
        trust_result = require_codex_hook_trust(command, codex_home, query_cwd)
        if trust_result:
            return trust_result

    try:
        body = prompt_bytes(control)
        output_dir = secure_output_dir(provider)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        slug = f"{topic}-{timestamp}-{secrets.token_hex(4)}"
        prompt_path = output_dir / f"{slug}.md"
        out_path = output_dir / f"{slug}.out"
        err_path = output_dir / f"{slug}.err"
        pid_path = output_dir / f"{slug}.pid"
        lastmsg_path = output_dir / f"{slug}.lastmsg" if provider == "codex" else None
        write_private(prompt_path, body)
    except (OSError, ValueError) as exc:
        return fail(str(exc))

    launch_run_id = ""
    if control.ledger:
        if ledger_helper() is None:
            return fail("-Ledger given but agent-run-ledger.py was not found")
        launch_run_id = (
            datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            + f"-launch-{slug}"
        )
        launch_args = [
            "--work-item",
            control.ledger,
            "append",
            "--run-id",
            launch_run_id,
            "--status",
            "running",
            "--gate",
            "none",
            "--event-kind",
            "launch",
            "--prompt-file",
            str(prompt_path),
            "--notes",
            "wrapper-dispatched; terminal event follows the completion oracle",
            *ledger_common(control, provider, model, effort, slug),
        ]
        if not run_ledger(launch_args):
            return fail(f"could not record launch event in {control.ledger}")

    provider_args = (
        [
            "exec",
            "--skip-git-repo-check",
            "--output-last-message",
            str(lastmsg_path),
            *flags,
        ]
        if provider == "codex"
        else flags
    )
    child_environment = os.environ.copy()
    if provider == "claude":
        child_environment["ORCHESTRARIUM_DISPATCHED_REVIEW"] = "1"
    else:
        child_environment["CODEX_HOME"] = str(codex_home)

    exit_code = 1
    launch_error: str | None = None
    try:
        out_path.touch(mode=0o600, exist_ok=False)
        err_path.touch(mode=0o600, exist_ok=False)
        with out_path.open("wb") as stdout_stream, err_path.open("wb") as stderr_stream:
            process = subprocess.Popen(
                command + provider_args,
                stdin=subprocess.PIPE,
                stdout=stdout_stream,
                stderr=stderr_stream,
                env=child_environment,
                cwd=query_cwd if provider == "codex" else None,
            )
            marker = process_start_marker(process.pid)
            pid_text = f"pid={process.pid}\n"
            if marker:
                pid_text += f"start={marker}\n"
            write_private(pid_path, pid_text.encode("utf-8"))

            paths = [prompt_path, out_path, err_path]
            if lastmsg_path is not None:
                paths.append(lastmsg_path)
            paths.append(pid_path)
            for path in paths:
                print(path)
            print("# actively await this dispatch (do NOT passively wait for a notification):")
            watcher = Path(__file__).resolve().with_name("await-codex-dispatch.py")
            watch_parts = [
                sys.executable,
                str(watcher),
                "--out",
                str(out_path),
                "--err",
                str(err_path),
            ]
            if lastmsg_path is not None:
                watch_parts += ["--lastmsg", str(lastmsg_path)]
            watch_parts += ["--pid-file", str(pid_path), "--stall-secs", "2700"]
            print(subprocess.list2cmdline(watch_parts))
            sys.stdout.flush()
            try:
                process.communicate(body)
            except KeyboardInterrupt:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                exit_code = 130
            else:
                exit_code = process.returncode if process.returncode is not None else 1
    except OSError as exc:
        launch_error = f"{provider} launch failed: {exc}"
        exit_code = 1

    if control.ledger:
        record_terminal(
            control,
            provider,
            model,
            effort,
            slug,
            launch_run_id,
            exit_code,
            out_path,
            err_path,
            lastmsg_path,
        )
    if launch_error is not None:
        return fail(launch_error)
    return exit_code
