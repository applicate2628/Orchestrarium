"""Exact selected workspace registration; physical effects use the main installer."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys
import uuid

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
from python_installer_bootstrap import ensure_supported_python
ensure_supported_python(str(Path(__file__).resolve()))
import production_installer as backend

RELATIVE = Path(".github/hooks/orchestrarium.json")
LIMIT = 65536


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("COPILOT-REGISTRATION-DUPLICATE")
        result[key] = value
    return result


def validate(payload: bytes) -> None:
    if not isinstance(payload, bytes) or len(payload) > LIMIT:
        raise ValueError("COPILOT-REGISTRATION-SIZE")
    try:
        doc = json.loads(payload.decode("utf-8"), object_pairs_hook=_unique)
    except RecursionError:
        raise ValueError("COPILOT-REGISTRATION-DEPTH") from None
    if (type(doc) is not dict or set(doc) != {"version", "hooks"}
            or type(doc["version"]) is not int or doc["version"] != 1
            or type(doc["hooks"]) is not dict or set(doc["hooks"]) != {"preToolUse"}):
        raise ValueError("COPILOT-REGISTRATION-SHAPE")
    rows = doc["hooks"]["preToolUse"]
    if type(rows) is not list or len(rows) != 1 or type(rows[0]) is not dict:
        raise ValueError("COPILOT-REGISTRATION-MIXED-HANDLERS")
    row = rows[0]
    keys = set(row) - {"type"}
    if (row.get("type") != "command" or len(keys) != 1
            or not keys <= {"command", "powershell", "bash"}):
        raise ValueError("COPILOT-REGISTRATION-SHAPE")
    command = row[next(iter(keys))]
    if type(command) is not str or not command.strip() or "\0" in command:
        raise ValueError("COPILOT-REGISTRATION-COMMAND")


def read_candidate(path: Path) -> bytes:
    with path.open("rb") as stream:
        data = stream.read(LIMIT + 1)
    validate(data)
    return data


def change(project: Path, desired: bytes | None, *, previous: bytes | None = None,
           apply: bool = False) -> dict:
    """Previous bytes are explicit selection, not inferred ownership or a receipt."""
    if desired is not None:
        validate(desired)
    if previous is not None:
        validate(previous)
    anchor = Path(project).absolute()
    destination = anchor / RELATIVE
    # Existing physical owner rejects linked ancestry before observation.
    inspection = backend._InstallTransaction([destination], enabled=False)
    reader = backend._CreateOnlyMutablePath(anchor, inspection, dry_run=True)
    reader.destination(RELATIVE)
    if destination.exists():
        reader._assert_regular(destination, existing=True)
        current = read_candidate(destination)
    else:
        current = None
    if previous is not None and current != previous:
        raise ValueError("COPILOT-REGISTRATION-STALE-SELECTION")
    if current == desired:
        return {"action": "unchanged", "applied": False, "path": str(destination)}
    if current is not None and previous is None:
        raise ValueError("COPILOT-REGISTRATION-SELECTION-REQUIRED")
    action = "remove" if desired is None else "create" if current is None else "update"
    trash = Path("trash") / ("orchestrarium-hook-" + uuid.uuid4().hex + ".json")
    paths = [destination] + ([anchor / trash] if current is not None else [])
    with backend._InstallTransaction(paths, enabled=apply) as tx:
        writer = backend._CreateOnlyMutablePath(anchor, tx, dry_run=not apply)
        writer.destination(RELATIVE)
        # Recheck selection after snapshot acquisition; writer binds its beforeimage.
        observed = read_candidate(destination) if destination.exists() else None
        if observed != current:
            raise ValueError("COPILOT-REGISTRATION-STALE-SELECTION")
        if current is not None:
            # Keep exact previous bytes recoverable; never silently dispose them.
            writer.write_file(trash, current)
        if desired is None:
            if apply:
                writer.remove_exact_file(RELATIVE, hashlib.sha256(current).hexdigest())
            else:
                writer.destination(RELATIVE)
        else:
            writer.write_file(RELATIVE, desired)
        if apply:
            if desired is None:
                if destination.exists():
                    raise ValueError("COPILOT-REGISTRATION-POSTCONDITION")
            elif destination.read_bytes() != desired:
                raise ValueError("COPILOT-REGISTRATION-POSTCONDITION")
            tx.commit()
    return {"action": action, "applied": apply, "path": str(destination),
            "previous_sha256": hashlib.sha256(current).hexdigest() if current is not None else None,
            "trash": str(anchor / trash) if current is not None and apply else None}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--project", type=Path, required=True)
    operation = parser.add_mutually_exclusive_group(required=True)
    operation.add_argument("--desired", type=Path)
    operation.add_argument("--remove", action="store_true")
    parser.add_argument("--previous", type=Path, help="Explicitly selected exact prior single-handler JSON")
    parser.add_argument("--apply", action="store_true", help="Without this flag, only preview")
    args = parser.parse_args(argv)
    try:
        result = change(args.project, read_candidate(args.desired) if args.desired else None,
                        previous=read_candidate(args.previous) if args.previous else None,
                        apply=args.apply)
        print(json.dumps(result, sort_keys=True))
        return 0
    except (ValueError, OSError, UnicodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
