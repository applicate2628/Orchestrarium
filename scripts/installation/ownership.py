"""Pure provider ownership codec/planner; filesystem effects stay in the installer."""
from __future__ import annotations

import json
from pathlib import PurePosixPath
import re

try:
    from installation.clients import get_client
except ModuleNotFoundError as error:
    if error.name not in {"installation", "installation.clients"}:
        raise
    from scripts.installation.clients import get_client

SCHEMA = "orche.provider-install.v1"
LAYOUT = "provider-owned-copies-v1"
RECEIPT_NAME = ".orche-install.v1.json"
MAX_BYTES = 4 * 1024 * 1024
_HASH = re.compile(r"[0-9a-f]{64}")


def validate_path(value: object, provider: str, scope: str) -> str:
    client = get_client(provider)
    if scope not in {"global", "project"}:
        raise ValueError("Unsupported installation identity")
    if type(value) is not str or not value or "\\" in value or ":" in value:
        raise ValueError("Invalid owned path")
    parts = value.split("/")
    if any(not part or part in {".", ".."} or part.rstrip(" .") != part
           or any(ord(c) < 32 for c in part) for part in parts):
        raise ValueError("Invalid owned path")
    if PurePosixPath(value).is_absolute():
        raise ValueError("Absolute owned path")
    roots = client["roots"]
    if "scope_roots" in client:
        scoped = client["scope_roots"]
        if type(scoped) is not dict or scope not in scoped:
            raise ValueError("Invalid installation scope roots")
        roots = scoped[scope]
        if type(roots) not in (tuple, list) or any(type(root) is not str for root in roots):
            raise ValueError("Invalid installation scope roots")
    allowed = len(parts) > 1 and parts[0] in roots
    if "scope_prefixes" in client:
        allowed = value.startswith(client["scope_prefixes"][scope]) or value in client["projection_configs"][scope]
    if value in client["documents"][scope]:
        allowed = True
    if not allowed or parts[-1].casefold() == RECEIPT_NAME:
        raise ValueError("Owned path outside selected provider")
    return value


def validate_record(value: object, provider: str, scope: str) -> dict:
    get_client(provider)
    if scope not in {"global", "project"}:
        raise ValueError("Unsupported installation scope")
    if (type(value) is not dict or not {"schema", "provider", "scope", "files"} <= set(value) or not set(value) <= {"schema", "provider", "scope", "files", "configs", "directories", "layout"}
        or value["schema"] != SCHEMA or value["provider"] != provider
        or value["scope"] != scope or type(value["files"]) is not dict):
        raise ValueError("Invalid provider ownership record")
    if "layout" in value and value["layout"] != LAYOUT:
        raise ValueError("Unsupported provider ownership layout")
    seen = set()
    for path, digest in value["files"].items():
        validate_path(path, provider, scope)
        alias = path.casefold()
        if alias in seen or type(digest) is not str or not _HASH.fullmatch(digest):
            raise ValueError("Invalid or aliased owned file")
        seen.add(alias)
    directories = value.get("directories", [])
    if type(directories) is not list:
        raise ValueError("Invalid owned directory list")
    for path in directories:
        validate_path(path, provider, scope)
        if path.casefold() in seen:
            raise ValueError("Aliased owned directory")
        seen.add(path.casefold())
    configs = value.get("configs", {})
    if type(configs) is not dict:
        raise ValueError("Invalid configuration ownership map")
    for path, spec in configs.items():
        if path.casefold() in seen:
            raise ValueError("Overlapping payload and configuration ownership")
        seen.add(path.casefold())
        validate_config(path, spec, provider, scope)
    return value


def decode_record(payload: bytes, provider: str, scope: str) -> dict:
    if len(payload) > MAX_BYTES:
        raise ValueError("Ownership record exceeds limit")
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate ownership field")
            result[key] = value
        return result
    return validate_record(json.loads(payload.decode("utf-8"), object_pairs_hook=unique), provider, scope)


def encode_record(files: dict[str, str], provider: str, scope: str, *, configs: dict | None = None, directories: list[str] | None = None) -> bytes:
    value = dict(schema=SCHEMA, provider=provider, scope=scope, files=files, layout=LAYOUT)
    if configs is not None:
        value["configs"] = configs
    if directories is not None:
        value["directories"] = directories
    return serialize_record(value, provider, scope)


def serialize_record(value: dict, provider: str, scope: str) -> bytes:
    """Serialize a validated projection without adding ownership or layout.

    This pure codec grants no storage authority or permission to persist.
    encode_record retains its existing copy-layout construction contract.
    """
    value = validate_record(value, provider, scope)
    payload = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    if len(payload) > MAX_BYTES:
        raise ValueError("Ownership record exceeds limit")
    return payload


def serialize_fresh_payloads(files: dict[str, str], provider: str, scope: str) -> bytes | None:
    """Project already confirmed fresh file outcomes into a minimal receipt.

    The caller owns freshness and persistence authority. This pure serializer
    neither verifies that authority nor reads or merges historical ownership.
    """
    client = get_client(provider)
    value = dict(schema=SCHEMA, provider=provider, scope=scope, files={})
    validate_record(value, provider, scope)
    if type(files) is not dict:
        raise ValueError("Invalid fresh payload map")
    for path, digest in files.items():
        if type(path) is not str or type(digest) is not str:
            raise ValueError("Invalid fresh payload entry")
        if not any(path.startswith(root + "/") for root in client["payload_roots"]):
            continue
        parts = path.split("/")
        if "__pycache__" in parts or parts[-1].casefold() == RECEIPT_NAME:
            continue
        validate_path(path, provider, scope)
        value["files"][path] = digest
    if not value["files"]:
        return None
    return serialize_record(value, provider, scope)


def plan_file_removal(record: dict, observed: dict[str, str | None]) -> dict[str, tuple[str, ...]]:
    """Absent is settled; unreadable/changed files are preserved, never adopted."""
    if type(record) is not dict:
        raise ValueError("Invalid provider ownership record")
    validate_record(record, record.get("provider"), record.get("scope"))
    result = {"remove": [], "preserve": [], "absent": []}
    for path, expected in sorted(record["files"].items()):
        action = "absent" if path not in observed else "remove" if observed[path] == expected else "preserve"
        result[action].append(path)
    return {key: tuple(paths) for key, paths in result.items()}


def fresh_control_paths(provider: str, scope: str) -> frozenset[str]:
    """Known control surfaces; membership is not creation authority."""
    client = get_client(provider)
    paths = set(client["documents"][scope])
    paths.update((client["mode_file"][scope], client["registration"]))
    if client["native_config"] is not None:
        paths.add(client["native_config"])
    return frozenset(paths)


def serialize_fresh_install(files: dict[str, str], controls: dict[str, str],
                            provider: str, scope: str) -> bytes | None:
    """Serialize only caller-proven creations, never infer control ownership.

    Whole-file claims require a creator witness. Existing merged controls must
    not enter this input. A later edit preserves the entire control file.
    """
    payload = serialize_fresh_payloads(files, provider, scope)
    value = (decode_record(payload, provider, scope) if payload is not None else
             dict(schema=SCHEMA, provider=provider, scope=scope, files={}))
    if type(controls) is not dict:
        raise ValueError("Invalid created control map")
    configs = {path: {"kind": "created-file", "sha256": digest}
               for path, digest in controls.items()}
    if configs:
        value["configs"] = configs
    if not value["files"] and not configs:
        return None
    return serialize_record(value, provider, scope)


def validate_config(path: str, spec: object, provider: str, scope: str) -> None:
    validate_path(path, provider, scope)
    if type(spec) is not dict:
        raise ValueError("Invalid owned configuration")
    client = get_client(provider)
    kind = spec.get("kind")
    if kind == "json-projection":
        if (path not in client.get("projection_configs", {}).get(scope, ())
                or set(spec) != {"kind", "members", "entries"}
                or type(spec["members"]) is not dict or type(spec["entries"]) is not list):
            raise ValueError("Invalid owned JSON projection")
        if path.endswith("/hooks.json"):
            keys = set(spec["members"])
            if not keys or not keys <= {"orchestrarium-session-start", "orchestrarium-machine-local-path", "orchestrarium-stray-artifact"} or spec["entries"]:
                raise ValueError("Invalid owned named hook")
            for name, block in spec["members"].items():
                event = "SessionStart" if name == "orchestrarium-session-start" else "PreToolUse"
                if type(block) is not dict or set(block) != {event} or type(block[event]) is not list or len(block[event]) != 1:
                    raise ValueError("Invalid owned hook event")
                handler = block[event][0]
                if event == "PreToolUse":
                    if (type(handler) is not dict or set(handler) != {"matcher", "hooks"}
                            or handler["matcher"] != ("^run_command$" if name == "orchestrarium-stray-artifact" else "^(write_to_file|replace_file_content)$")
                            or type(handler["hooks"]) is not list or len(handler["hooks"]) != 1):
                        raise ValueError("Invalid owned tool matcher")
                    handler = handler["hooks"][0]
                if type(handler) is not dict or set(handler) != {"type", "command"} or handler["type"] != "command" or type(handler["command"]) is not str or not handler["command"]:
                    raise ValueError("Invalid owned hook handler")
        elif spec["members"] or len(spec["entries"]) != 1:
            raise ValueError("Invalid owned discovery entry")
        for entry in spec["entries"]:
            if type(entry) is not dict or set(entry) != {"path"} or type(entry["path"]) is not str:
                raise ValueError("Invalid discovery path")
            base = client["scope_prefixes"][scope].rstrip("/")
            if scope == "global":
                base = PurePosixPath(base).name
            expected = base + ("/skills" if path.endswith("/skills.json") else "/rules")
            if entry["path"] != expected:
                raise ValueError("Discovery entry outside selected managed projection")
    elif kind == "created-file":
        if (path not in fresh_control_paths(provider, scope)
            or set(spec) != {"kind", "sha256"}
            or type(spec["sha256"]) is not str or not _HASH.fullmatch(spec["sha256"])):
            raise ValueError("Invalid created control file")
    elif kind == "block":
        allowed = client["documents"][scope]
        if (set(spec) != {"kind", "blockKind", "sha256"} or allowed.get(path) != spec["blockKind"]
            or type(spec["sha256"]) is not str or not _HASH.fullmatch(spec["sha256"])):
            raise ValueError("Invalid owned document block")
    elif kind == "file":
        allowed = client["mode_file"][scope]
        if (path != allowed or set(spec) != {"kind", "sha256"}
            or type(spec["sha256"]) is not str or not _HASH.fullmatch(spec["sha256"])):
            raise ValueError("Invalid owned mode file")
    elif kind == "native-roles":
        if client["native_config"] is None or path != client["native_config"] or set(spec) not in ({"kind", "roles"}, {"kind", "roles", "features"}) or type(spec["roles"]) is not dict:
            raise ValueError("Invalid owned native roles")
        features = spec.get("features", {})
        if type(features) is not dict or any(key not in client["feature_defaults"] or type(value) is not bool or value is not client["feature_defaults"][key] for key, value in features.items()):
            raise ValueError("Invalid owned native feature")
        for name, fields in spec["roles"].items():
            if (not re.fullmatch(r"[a-z0-9_-]+", name) or type(fields) is not dict
                or set(fields) != {"description", "config_file"} or type(fields["description"]) is not str
                or type(fields["config_file"]) is not str
                or not re.fullmatch(r"agents/[a-z0-9_-]+\.toml", fields["config_file"])):
                raise ValueError("Invalid native role record")
    elif kind == "hooks":
        expected = client["registration"]
        if (path != expected or set(spec) != {"kind", "handlers", "agentAdded"}
            or type(spec["handlers"]) is not list or type(spec["agentAdded"]) is not bool
            or client["default_agent_key"] is None and spec["agentAdded"]):
            raise ValueError("Invalid owned hook record")
        for hook in spec["handlers"]:
            if (type(hook) is not dict or set(hook) != {"event", "marker", "context", "handler"}
                or type(hook["event"]) is not str or type(hook["marker"]) is not str
                or type(hook["context"]) is not dict or "hooks" in hook["context"]
                or type(hook["handler"]) is not dict or hook["handler"].get("type") != "command"
                or type(hook["handler"].get("command")) is not str):
                raise ValueError("Invalid hook definition record")
    else:
        raise ValueError("Unsupported owned configuration kind")
