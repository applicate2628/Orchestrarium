"""Canonical, closed policy data contracts for reviewed publication findings.

This module owns policy encoding and record validity.  It deliberately does
not inspect scanner output, authenticate report labels, or run Git commands.
Repository metadata is supplied by the admitted scan owner.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import ntpath
import os
import re
import stat
import sys
import tempfile
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any


POLICY_MODULE_CONTRACT_ID = "orchestrarium.publication-review-policy.module.v1"
POLICY_MODULE_KEY = "_orchestrarium_publication_review_policy_v1"
POLICY_INJECTION_KEY = "__injected_review_policy_module__"
LINKED_RUNTIME_SUBROOTS_MODULE_KEY = "_orchestrarium_linked_runtime_subroots_v1"
POLICY_SCHEMA_VERSION = 1

DOMAIN_RECORD = "orchestrarium.publication-review.record.v1"
DOMAIN_REPOSITORY = "orchestrarium.publication-review.repository.v1"
DOMAIN_DETECTOR_LEAF = "orchestrarium.publication-review.detector-leaf.v1"
DOMAIN_DETECTOR = "orchestrarium.publication-review.detector.v1"
DOMAIN_OCCURRENCE = "orchestrarium.publication-review.occurrence.v1"
DOMAIN_BINDING = "orchestrarium.publication-review.binding.v1"
DOMAIN_SNAPSHOT = "orchestrarium.publication-review.snapshot.v1"
DOMAIN_APPLIED = "orchestrarium.publication-review.applied.v1"
DOMAIN_APPLIED_SET = "orchestrarium.publication-review.applied-set.v1"

_HASH_DOMAINS = frozenset(
    {
        DOMAIN_RECORD,
        DOMAIN_REPOSITORY,
        DOMAIN_DETECTOR_LEAF,
        DOMAIN_DETECTOR,
        DOMAIN_OCCURRENCE,
        DOMAIN_BINDING,
        DOMAIN_SNAPSHOT,
        DOMAIN_APPLIED,
    }
)
_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z", re.ASCII)
_SHA_RE = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
_OID_RE = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z", re.ASCII)
_DECIMAL_RE = re.compile(r"(?:0|[1-9][0-9]*)\Z", re.ASCII)
_SIGNED_DECIMAL_RE = re.compile(r"(?:0|-?[1-9][0-9]*)\Z", re.ASCII)
_BASE64_RE = re.compile(r"(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?\Z", re.ASCII)


class PolicyInputError(ValueError):
    """A value does not satisfy the closed reviewed-policy contract."""


class PolicyError(RuntimeError):
    """Typed policy-owner failure with a nonauthorizing optional observation."""

    def __init__(self, detail: Mapping[str, str], outcome: Mapping[str, Any] | None = None):
        self.detail = MappingProxyType(dict(detail))
        self.outcome = MappingProxyType(_thaw(outcome)) if outcome is not None else None
        super().__init__(detail["code"] + ":" + detail["phase"])


class _ResourceUnsettledError(OSError):
    pass


@dataclass(frozen=True, slots=True)
class _IntegerToken:
    spelling: str


@dataclass(frozen=True, slots=True)
class _FloatToken:
    spelling: str


class _JSONObject:
    __slots__ = ("pairs",)

    def __init__(self, pairs: list[tuple[str, Any]]) -> None:
        self.pairs = tuple(pairs)

    def unique_mapping(self) -> dict[str, Any] | None:
        result: dict[str, Any] = {}
        for key, value in self.pairs:
            if key in result:
                return None
            result[key] = value
        return result

    def unique_value(self, name: str) -> tuple[bool, Any]:
        matches = [value for key, value in self.pairs if key == name]
        if len(matches) != 1:
            return False, None
        return True, matches[0]


def _is_unicode_scalar_text(value: str) -> bool:
    return type(value) is str and not any(0xD800 <= ord(ch) <= 0xDFFF for ch in value)


def _int_to_decimal(value: int) -> str:
    """Render arbitrary-size integers without Python's decimal digit ceiling."""
    if type(value) is not int:
        raise PolicyInputError("canonical-integer")
    if value == 0:
        return "0"
    negative = value < 0
    remaining = -value if negative else value
    chunks: list[int] = []
    base = 1_000_000_000
    while remaining:
        remaining, chunk = divmod(remaining, base)
        chunks.append(chunk)
    rendered = str(chunks.pop()) + "".join(f"{chunk:09d}" for chunk in reversed(chunks))
    return "-" + rendered if negative else rendered


def _decimal_to_int(spelling: str) -> int:
    """Parse JSON's integer grammar without imposing a convenience length cap."""
    negative = spelling.startswith("-")
    digits = spelling[1:] if negative else spelling
    if not digits or (len(digits) > 1 and digits[0] == "0"):
        raise PolicyInputError("json-integer")
    value = 0
    first = len(digits) % 9 or 9
    value = int(digits[:first])
    for start in range(first, len(digits), 9):
        value = value * 1_000_000_000 + int(digits[start : start + 9])
    return -value if negative else value


def _canonical_text(value: Any) -> str:
    if value is None:
        return "null"
    if type(value) is bool:
        return "true" if value else "false"
    if type(value) is int:
        return _int_to_decimal(value)
    if type(value) is str:
        if not _is_unicode_scalar_text(value):
            raise PolicyInputError("unicode-scalar")
        return json.dumps(value, ensure_ascii=True, separators=(",", ":"))
    if type(value) is dict:
        if any(type(key) is not str or not _is_unicode_scalar_text(key) for key in value):
            raise PolicyInputError("json-object-key")
        keys = sorted(value)
        return "{" + ",".join(
            _canonical_text(key) + ":" + _canonical_text(value[key]) for key in keys
        ) + "}"
    if type(value) is list:
        return "[" + ",".join(_canonical_text(item) for item in value) + "]"
    raise PolicyInputError("canonical-json-type")


def C(value: Any) -> bytes:
    """Return the frozen canonical ASCII JSON encoding C(x)."""
    return _canonical_text(value).encode("ascii")


def H(domain: str, value: Any) -> str:
    """Return the frozen domain-separated digest H(domain, x)."""
    if type(domain) is not str or domain not in _HASH_DOMAINS:
        raise PolicyInputError("hash-domain")
    payload = C(value)
    framed = (
        domain.encode("ascii")
        + b"\0"
        + _int_to_decimal(len(payload)).encode("ascii")
        + b":"
        + payload
    )
    return hashlib.sha256(framed).hexdigest()


def applied_set_digest(rows: Iterable[Mapping[str, Any]]) -> str:
    """Hash ordered applied rows using the protocol's streaming frame/count."""
    digest = hashlib.sha256()
    digest.update(DOMAIN_APPLIED_SET.encode("ascii"))
    digest.update(b"\0")
    count = 0
    for row in rows:
        encoded = C(row)
        digest.update(_int_to_decimal(len(encoded)).encode("ascii"))
        digest.update(b":")
        digest.update(encoded)
        count += 1
    digest.update(b"!")
    digest.update(_int_to_decimal(count).encode("ascii"))
    return digest.hexdigest()


def record_digest(record_without_sha: Mapping[str, Any]) -> str:
    if "recordSha256" in record_without_sha:
        raise PolicyInputError("record-digest-input")
    return H(DOMAIN_RECORD, record_without_sha)


def seal_record(record_without_sha: Mapping[str, Any]) -> dict[str, Any]:
    """Copy a complete record body and add its canonical record digest."""
    body = _thaw(record_without_sha)
    digest = record_digest(body)
    sealed = dict(body)
    sealed["recordSha256"] = digest
    _validate_record(sealed)
    return sealed


def _exact_object(value: Any, keys: tuple[str, ...], where: str) -> dict[str, Any]:
    if type(value) is not dict or set(value) != set(keys):
        raise PolicyInputError(where + "-fields")
    return value


def _require_id(value: Any, where: str = "id") -> str:
    if type(value) is not str or _ID_RE.fullmatch(value) is None:
        raise PolicyInputError(where)
    return value


def _require_sha(value: Any, where: str = "sha256") -> str:
    if type(value) is not str or _SHA_RE.fullmatch(value) is None:
        raise PolicyInputError(where)
    return value


def _require_uint(value: Any, where: str = "uint") -> int:
    if type(value) is not int or value < 0:
        raise PolicyInputError(where)
    return value


def _require_positive(value: Any, where: str = "positive") -> int:
    if type(value) is not int or value <= 0:
        raise PolicyInputError(where)
    return value


def _require_text(value: Any, where: str = "text") -> str:
    if not _is_unicode_scalar_text(value) or value == "":
        raise PolicyInputError(where)
    return value


def _decode_base64(value: Any, where: str) -> bytes:
    if type(value) is not str or _BASE64_RE.fullmatch(value) is None:
        raise PolicyInputError(where)
    try:
        decoded = base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise PolicyInputError(where) from exc
    if base64.b64encode(decoded).decode("ascii") != value:
        raise PolicyInputError(where)
    return decoded


def _validate_native_locator(encoding: Any, encoded: Any, where: str) -> bytes:
    if encoding == "windows-utf16le":
        raw = _decode_base64(encoded, where + "-base64")
        if not raw or len(raw) % 2:
            raise PolicyInputError(where + "-path")
        try:
            spelling = raw.decode("utf-16-le", errors="surrogatepass")
        except UnicodeDecodeError as exc:
            raise PolicyInputError(where + "-path") from exc
        drive, _tail = ntpath.splitdrive(spelling)
        if not drive or not ntpath.isabs(spelling) or "\x00" in spelling:
            raise PolicyInputError(where + "-absolute")
        return raw
    if encoding == "posix-bytes":
        raw = _decode_base64(encoded, where + "-base64")
        if not raw.startswith(b"/") or b"\0" in raw:
            raise PolicyInputError(where + "-absolute")
        return raw
    raise PolicyInputError(where + "-encoding")


def _validate_native_directory(value: Any, where: str) -> dict[str, Any]:
    obj = _exact_object(
        value,
        ("pathEncoding", "pathBase64", "device", "inode"),
        where,
    )
    _validate_native_locator(obj["pathEncoding"], obj["pathBase64"], where)
    if type(obj["device"]) is not str or _DECIMAL_RE.fullmatch(obj["device"]) is None:
        raise PolicyInputError(where + "-device")
    if type(obj["inode"]) is not str or _DECIMAL_RE.fullmatch(obj["inode"]) is None:
        raise PolicyInputError(where + "-inode")
    return obj


def _validate_repository(value: Any) -> dict[str, Any]:
    obj = _exact_object(
        value,
        ("kind", "objectFormat", "commonGit", "worktreeGit", "worktreeRoot"),
        "repository",
    )
    if obj["kind"] != "native-worktree-v1":
        raise PolicyInputError("repository-kind")
    if obj["objectFormat"] not in ("sha1", "sha256"):
        raise PolicyInputError("repository-object-format")
    for name in ("commonGit", "worktreeGit", "worktreeRoot"):
        _validate_native_directory(obj[name], "repository-" + name)
    return obj


def repository_digest(repository: Mapping[str, Any]) -> str:
    _validate_repository(_thaw(repository))
    return H(DOMAIN_REPOSITORY, _thaw(repository))


def _require_oid(value: Any, object_format: str, where: str) -> str:
    size = 40 if object_format == "sha1" else 64
    if type(value) is not str or len(value) != size or _OID_RE.fullmatch(value) is None:
        raise PolicyInputError(where)
    return value


def _validate_region(value: Any, blob_size: int, where: str) -> dict[str, Any]:
    obj = _exact_object(value, ("startByte", "endByteExclusive", "sha256"), where)
    start = _require_uint(obj["startByte"], where + "-start")
    end = _require_uint(obj["endByteExclusive"], where + "-end")
    _require_sha(obj["sha256"], where + "-sha")
    if start >= end or end > blob_size:
        raise PolicyInputError(where + "-bounds")
    return obj


def _region_key(region: Mapping[str, Any]) -> tuple[int, int, str]:
    return (region["startByte"], region["endByteExclusive"], region["sha256"])


def _inside(inner: Mapping[str, Any], outer: Mapping[str, Any]) -> bool:
    return outer["startByte"] <= inner["startByte"] < inner["endByteExclusive"] <= outer["endByteExclusive"]


def _validate_candidate(value: Any, blob_size: int, review_region: Mapping[str, Any]) -> dict[str, Any]:
    obj = _exact_object(
        value,
        (
            "normalFormId",
            "startByte",
            "endByteExclusive",
            "sha256",
            "assignment",
            "contributors",
            "occurrenceSha256",
        ),
        "candidate",
    )
    normal_form = _require_id(obj["normalFormId"], "candidate-normal-form")
    if normal_form not in ("nf-simple-match-v1", "nf-value-assignment-v1"):
        raise PolicyInputError("candidate-normal-form")
    span = {
        "startByte": obj["startByte"],
        "endByteExclusive": obj["endByteExclusive"],
        "sha256": obj["sha256"],
    }
    _validate_region(span, blob_size, "candidate-span")
    if not _inside(span, review_region):
        raise PolicyInputError("candidate-review-region")
    assignment_value = obj["assignment"]
    if normal_form == "nf-simple-match-v1":
        if assignment_value is not None:
            raise PolicyInputError("candidate-simple-assignment")
    else:
        assignment = _exact_object(
            assignment_value,
            ("identifier", "delimiter", "rhs"),
            "candidate-assignment",
        )
        for name in ("identifier", "delimiter", "rhs"):
            _validate_region(assignment[name], blob_size, "candidate-" + name)
        if not (
            assignment["identifier"]["endByteExclusive"] <= assignment["delimiter"]["startByte"]
            and assignment["delimiter"]["endByteExclusive"] <= assignment["rhs"]["startByte"]
        ):
            raise PolicyInputError("candidate-assignment-order")
        if _region_key(span) != _region_key(assignment["rhs"]):
            raise PolicyInputError("candidate-rhs-span")

    contributors = obj["contributors"]
    if type(contributors) is not list or not contributors:
        raise PolicyInputError("candidate-contributors")
    contributor_keys: list[tuple[str, int, int, str]] = []
    for contributor in contributors:
        item = _exact_object(contributor, ("leafId", "fullMatch"), "candidate-contributor")
        leaf = _require_id(item["leafId"], "candidate-leaf")
        _validate_region(item["fullMatch"], blob_size, "candidate-full-match")
        if not _inside(item["fullMatch"], review_region):
            raise PolicyInputError("candidate-contributor-review-region")
        if not (
            item["fullMatch"]["startByte"]
            <= span["startByte"]
            < span["endByteExclusive"]
            <= item["fullMatch"]["endByteExclusive"]
        ):
            raise PolicyInputError("candidate-contributor-candidate-span")
        contributor_keys.append((leaf, *_region_key(item["fullMatch"])))
    if contributor_keys != sorted(set(contributor_keys)):
        raise PolicyInputError("candidate-contributor-order")
    if normal_form == "nf-simple-match-v1":
        if len(contributors) != 1 or _region_key(span) != _region_key(contributors[0]["fullMatch"]):
            raise PolicyInputError("candidate-simple-witness")

    _require_sha(obj["occurrenceSha256"], "candidate-occurrence-sha")
    return obj


def _validate_occurrence(value: Any, repository: Mapping[str, Any]) -> dict[str, Any]:
    obj = _exact_object(
        value,
        (
            "id",
            "rawPathBase64",
            "blobOid",
            "blobSha256",
            "blobByteCount",
            "gitMode",
            "detector",
            "reviewRegion",
            "candidate",
            "contexts",
        ),
        "occurrence",
    )
    _require_id(obj["id"], "occurrence-id")
    raw_path = _decode_base64(obj["rawPathBase64"], "occurrence-path")
    if not raw_path or b"\0" in raw_path:
        raise PolicyInputError("occurrence-path")
    object_format = repository["objectFormat"]
    _require_oid(obj["blobOid"], object_format, "occurrence-blob-oid")
    _require_sha(obj["blobSha256"], "occurrence-blob-sha")
    blob_size = _require_uint(obj["blobByteCount"], "occurrence-blob-size")
    if obj["gitMode"] not in ("100644", "100755"):
        raise PolicyInputError("occurrence-git-mode")
    detector = _exact_object(obj["detector"], ("ruleId", "meaningSha256"), "detector")
    _require_id(detector["ruleId"], "detector-rule-id")
    _require_sha(detector["meaningSha256"], "detector-meaning")
    review_region = _validate_region(obj["reviewRegion"], blob_size, "review-region")
    candidate = _validate_candidate(obj["candidate"], blob_size, review_region)
    candidate_body = {
        "detector": detector,
        "normalFormId": candidate["normalFormId"],
        "startByte": candidate["startByte"],
        "endByteExclusive": candidate["endByteExclusive"],
        "sha256": candidate["sha256"],
        "assignment": candidate["assignment"],
        "contributors": candidate["contributors"],
    }
    expected_occurrence_sha = H(DOMAIN_OCCURRENCE, candidate_body)
    if candidate["occurrenceSha256"] != expected_occurrence_sha:
        raise PolicyInputError("candidate-occurrence-digest")

    contexts = obj["contexts"]
    if type(contexts) is not list or not contexts:
        raise PolicyInputError("occurrence-contexts")
    context_ids: list[str] = []
    for context in contexts:
        item = _exact_object(context, ("id", "region"), "context")
        context_ids.append(_require_id(item["id"], "context-id"))
        _validate_region(item["region"], blob_size, "context-region")
    if context_ids != sorted(set(context_ids)):
        raise PolicyInputError("context-order")
    return obj


def _validate_artifact(value: Any, where: str) -> dict[str, Any]:
    obj = _exact_object(value, ("reference", "sha256"), where)
    _require_text(obj["reference"], where + "-reference")
    _require_sha(obj["sha256"], where + "-sha")
    return obj


def _validate_record(value: Any) -> dict[str, Any]:
    obj = _exact_object(
        value,
        (
            "id",
            "revision",
            "previousRecordSha256",
            "state",
            "repository",
            "modes",
            "rangeScope",
            "occurrences",
            "reason",
            "removalCondition",
            "authorization",
            "revocation",
            "recordSha256",
        ),
        "record",
    )
    _require_id(obj["id"], "record-id")
    _require_positive(obj["revision"], "record-revision")
    previous = obj["previousRecordSha256"]
    if previous is not None:
        _require_sha(previous, "record-previous-sha")
    if obj["state"] not in ("active", "revoked"):
        raise PolicyInputError("record-state")
    repository = _validate_repository(obj["repository"])

    modes = obj["modes"]
    if type(modes) is not list or not modes or any(
        type(mode) is not str or mode not in ("staged-blob-text", "range-blob-text")
        for mode in modes
    ):
        raise PolicyInputError("record-modes")
    if modes != sorted(set(modes)):
        raise PolicyInputError("record-mode-order")

    range_scope = obj["rangeScope"]
    if "range-blob-text" not in modes:
        if range_scope is not None:
            raise PolicyInputError("record-range-scope")
    else:
        if type(range_scope) is not dict:
            raise PolicyInputError("record-range-scope")
        if range_scope.get("kind") == "object-content":
            _exact_object(range_scope, ("kind",), "range-object-content")
        elif range_scope.get("kind") == "exact-commits":
            _exact_object(range_scope, ("kind", "commits"), "range-exact-commits")
            commits = range_scope["commits"]
            if type(commits) is not list or not commits:
                raise PolicyInputError("range-commits")
            for commit in commits:
                _require_oid(commit, repository["objectFormat"], "range-commit")
            if commits != sorted(set(commits)):
                raise PolicyInputError("range-commit-order")
        else:
            raise PolicyInputError("record-range-kind")

    occurrences = obj["occurrences"]
    if type(occurrences) is not list or not occurrences:
        raise PolicyInputError("record-occurrences")
    occurrence_ids: list[str] = []
    for occurrence in occurrences:
        checked = _validate_occurrence(occurrence, repository)
        occurrence_ids.append(checked["id"])
    if occurrence_ids != sorted(set(occurrence_ids)):
        raise PolicyInputError("record-occurrence-order")

    _require_text(obj["reason"], "record-reason")
    _require_text(obj["removalCondition"], "record-removal-condition")
    authorization = _exact_object(
        obj["authorization"],
        ("reviewArtifact", "rootReceivingReference", "supportingArtifacts"),
        "authorization",
    )
    _validate_artifact(authorization["reviewArtifact"], "authorization-review")
    _require_text(authorization["rootReceivingReference"], "authorization-root-reference")
    supporting = authorization["supportingArtifacts"]
    if type(supporting) is not list:
        raise PolicyInputError("authorization-supporting")
    support_keys: list[tuple[str, str]] = []
    for item in supporting:
        checked = _validate_artifact(item, "authorization-supporting-artifact")
        support_keys.append((checked["reference"], checked["sha256"]))
    if support_keys != sorted(set(support_keys)):
        raise PolicyInputError("authorization-supporting-order")

    revocation = obj["revocation"]
    if obj["state"] == "active":
        if revocation is not None:
            raise PolicyInputError("active-revocation")
    else:
        revocation_obj = _exact_object(
            revocation,
            ("reason", "rootReceivingReference"),
            "revocation",
        )
        _require_text(revocation_obj["reason"], "revocation-reason")
        _require_text(revocation_obj["rootReceivingReference"], "revocation-root-reference")

    observed = _require_sha(obj["recordSha256"], "record-sha")
    body = {key: item for key, item in obj.items() if key != "recordSha256"}
    if H(DOMAIN_RECORD, body) != observed:
        raise PolicyInputError("record-digest")
    return obj


def _freeze(value: Any) -> Any:
    if type(value) is dict:
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if type(value) is list:
        return tuple(_freeze(item) for item in value)
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if type(value) is tuple:
        return [_thaw(item) for item in value]
    return value


@dataclass(frozen=True, slots=True)
class DecodedDocument:
    """Read-time independent records plus mutation-safety state."""

    outer_valid: bool
    revision: int | None
    records: tuple[Mapping[str, Any], ...]
    invalid_record_count: int
    invalid_record_ids: tuple[str | None, ...]
    duplicate_ids: tuple[str, ...]
    raw_sha256: str

    @property
    def mutation_safe(self) -> bool:
        return self.outer_valid and self.invalid_record_count == 0 and not self.duplicate_ids

    def usable_records(self) -> tuple[dict[str, Any], ...]:
        """Return independent plain closed dictionaries for policy consumers."""
        return tuple(_thaw(record) for record in self.records)


def _native_path(value: Path | str, *, allow_relative: bool = False) -> dict[str, str]:
    spelling = os.fspath(value)
    if type(spelling) is not str or "\x00" in spelling:
        raise PolicyInputError("native-path")
    if not allow_relative and not Path(spelling).is_absolute():
        raise PolicyInputError("native-path-absolute")
    if os.name == "nt":
        encoding = "windows-utf16le"
        raw = spelling.encode("utf-16-le", errors="surrogatepass")
    else:
        encoding = "posix-bytes"
        raw = os.fsencode(spelling)
    if not allow_relative and not _validate_native_locator(encoding, base64.b64encode(raw).decode("ascii"), "native-path"):
        raise PolicyInputError("native-path-absolute")
    return {"pathEncoding": encoding, "pathBase64": base64.b64encode(raw).decode("ascii")}


def _identity4(metadata: os.stat_result) -> tuple[str, str, str, str]:
    return (
        _int_to_decimal(int(metadata.st_dev)),
        _int_to_decimal(int(metadata.st_ino)),
        _int_to_decimal(int(metadata.st_mode)),
        _int_to_decimal(int(getattr(metadata, "st_file_attributes", 0))),
    )


def _is_reparse(metadata: os.stat_result) -> bool:
    return bool(
        int(getattr(metadata, "st_file_attributes", 0))
        & int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
    )


def _directory_object(path: Path, metadata: os.stat_result) -> dict[str, str]:
    if _is_reparse(metadata) or not stat.S_ISDIR(metadata.st_mode):
        raise PolicyInputError("origin-directory-kind")
    native = _native_path(path)
    return {
        "pathEncoding": native["pathEncoding"],
        "pathBase64": native["pathBase64"],
        "device": _int_to_decimal(int(metadata.st_dev)),
        "inode": _int_to_decimal(int(metadata.st_ino)),
    }


def _native_identity(metadata: os.stat_result) -> tuple[str, ...]:
    return _identity4(metadata)


def _link_witnesses(link_chain: Any) -> tuple[tuple[Any, ...], ...]:
    result: list[tuple[Any, ...]] = []
    seen: set[bytes] = set()
    for raw_path, identity, raw_target, kind in link_chain:
        if kind not in ("symlink", "junction"):
            raise PolicyInputError("origin-link-kind")
        link_path = _native_path(Path(raw_path))
        target_spelling = os.fspath(raw_target)
        if type(target_spelling) is not str or "\x00" in target_spelling:
            raise PolicyInputError("origin-link-target")
        if os.name == "nt":
            target_bytes = target_spelling.encode("utf-16-le", errors="surrogatepass")
            target_encoding = "windows-utf16le"
        else:
            target_bytes = os.fsencode(target_spelling)
            target_encoding = "posix-bytes"
        witness = (
            link_path,
            tuple(_int_to_decimal(int(value)) for value in identity),
            kind,
            {"pathEncoding": target_encoding, "pathBase64": base64.b64encode(target_bytes).decode("ascii")},
        )
        marker = C([witness[0], list(witness[1]), witness[2], witness[3]])
        if marker in seen:
            continue
        seen.add(marker)
        result.append(witness)
    return tuple(result)


@dataclass(frozen=True, slots=True)
class OriginSelection:
    """Nonserialized selection of the one fixed host policy location."""

    contractId: str
    status: str
    diagnostic: str
    logicalRoot: Mapping[str, str] | None
    logicalLeaf: Mapping[str, str] | None
    logicalIdentity: tuple[str, ...] | None
    physicalRoot: Mapping[str, str] | None
    physicalIdentity: tuple[str, ...] | None
    links: tuple[tuple[Any, ...], ...]
    logicalRootPath: Path | None
    physicalRootPath: Path | None
    policyLeafPath: Path | None
    linkedAuthority: Any | None


@dataclass(frozen=True, slots=True)
class PolicySnapshot:
    """Immutable capture using the exact schema-1 snapshot wire fields."""

    schemaVersion: int
    status: str
    origin: Mapping[str, Any] | None
    rawBase64: str | None
    rawSha256: str | None
    diagnostic: str

    def object(self) -> dict[str, Any]:
        return {
            "schemaVersion": self.schemaVersion,
            "status": self.status,
            "origin": _thaw(self.origin) if self.origin is not None else None,
            "rawBase64": self.rawBase64,
            "rawSha256": self.rawSha256,
            "diagnostic": self.diagnostic,
        }


@dataclass(frozen=True, slots=True)
class PolicyCapture:
    snapshot: PolicySnapshot
    decoded: DecodedDocument | None
    resourcesSettled: bool

    @property
    def snapshotId(self) -> str:
        return snapshot_id(self.snapshot)


@dataclass(frozen=True, slots=True)
class PolicyReadV1:
    snapshot: dict[str, Any]
    snapshot_id: str
    usable_records: tuple[dict[str, Any], ...]
    issues: tuple[dict[str, Any], ...]


@dataclass(frozen=True, slots=True)
class RepositoryQueryV1:
    key: str
    git_args: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RepositoryQueryPlanV1:
    root: Path
    root_before: dict[str, str]
    queries: tuple[RepositoryQueryV1, ...]


@dataclass(frozen=True, slots=True)
class RepositoryQueryResultV1:
    query_key: str
    git_args: tuple[str, ...]
    returncode: int | None
    stdout: bytes | None
    stderr: bytes | None
    complete: bool
    resources_settled: bool | None
    failure_kind: str | None


def _declared_linked_helper_path(module_file: str) -> Path | None:
    if module_file.startswith("<closure>/") or module_file.startswith("<closure>\\"):
        return None
    path = Path(module_file)
    parts = path.parts
    layouts: tuple[tuple[tuple[str, ...], int, bool], ...] = (
        (("scripts", "universal-hooks", "scripts", "publication_review_policy.py"), 3, False),
        (("src.codex", "skills", "lead", "scripts", "publication_review_policy.py"), 4, False),
        (("src.claude", "agents", "scripts", "publication_review_policy.py"), 3, False),
        (("scripts", "publication_review_policy.py"), 0, True),
    )
    matches = [
        (len(suffix), parent_index, is_component, suffix)
        for suffix, parent_index, is_component in layouts
        if len(parts) >= len(suffix) and parts[-len(suffix) :] == suffix
    ]
    if not matches:
        return None
    matches.sort(key=lambda row: row[0], reverse=True)
    if len(matches) > 1 and matches[0][0] == matches[1][0]:
        return None
    _length, parent_index, is_component, _suffix = matches[0]
    base = path.parents[parent_index]
    return base / "linked_runtime_subroots.py" if is_component else base / "scripts" / "linked_runtime_subroots.py"


def _linked_runtime_module() -> Any | None:
    linked_module = sys.modules.get(LINKED_RUNTIME_SUBROOTS_MODULE_KEY)
    if linked_module is not None:
        return linked_module
    module_file = globals().get("__file__")
    if type(module_file) is not str:
        return None
    # Captured child execution must consume the exact injected module.  It may
    # never reach back to a live source or installed filesystem copy.
    if module_file.startswith("<closure>/") or module_file.startswith("<closure>\\"):
        return None
    helper_path = _declared_linked_helper_path(module_file)
    if helper_path is None:
        return None
    try:
        metadata = helper_path.lstat()
        if _is_reparse(metadata) or not stat.S_ISREG(metadata.st_mode):
            return None
        import importlib.util

        spec = importlib.util.spec_from_file_location(LINKED_RUNTIME_SUBROOTS_MODULE_KEY, helper_path)
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        sys.modules[LINKED_RUNTIME_SUBROOTS_MODULE_KEY] = module
        try:
            spec.loader.exec_module(module)
        except BaseException:
            if sys.modules.get(LINKED_RUNTIME_SUBROOTS_MODULE_KEY) is module:
                del sys.modules[LINKED_RUNTIME_SUBROOTS_MODULE_KEY]
            raise
        return module
    except (OSError, ImportError, RuntimeError, TypeError, ValueError):
        return None


def _unavailable_origin(diagnostic: str = "invalid-origin") -> OriginSelection:
    return OriginSelection(
        contractId="orchestrarium.publication-review-origin.v1",
        status="unavailable",
        diagnostic=diagnostic,
        logicalRoot=None,
        logicalLeaf=None,
        logicalIdentity=None,
        physicalRoot=None,
        physicalIdentity=None,
        links=(),
        logicalRootPath=None,
        physicalRootPath=None,
        policyLeafPath=None,
        linkedAuthority=None,
    )


def _absent_origin(logical_root: Path) -> OriginSelection:
    logical_leaf = logical_root / "reviewed-exceptions.json"
    try:
        logical_root_value = MappingProxyType(_native_path(logical_root))
        logical_leaf_value = MappingProxyType(_native_path(logical_leaf))
    except (OSError, RuntimeError, TypeError, ValueError):
        return _unavailable_origin()
    return OriginSelection(
        contractId="orchestrarium.publication-review-origin.v1",
        status="absent",
        diagnostic="absent",
        logicalRoot=logical_root_value,
        logicalLeaf=logical_leaf_value,
        logicalIdentity=None,
        physicalRoot=None,
        physicalIdentity=None,
        links=(),
        logicalRootPath=logical_root,
        physicalRootPath=None,
        policyLeafPath=None,
        linkedAuthority=None,
    )


def resolve_trusted_origin() -> OriginSelection:
    """Select only Path.home()/.agents/publication/reviewed-exceptions.json.

    Linked ancestors are resolved only by the installed shared L module under
    its exact captured module key. Ordinary roots retain their actual native
    identity; no report, repository, cwd, environment override, or caller path
    can select another policy location.
    """
    linked_module = _linked_runtime_module()
    authority_type = getattr(linked_module, "LinkedRuntimeSubrootAuthority", None)
    bind = getattr(authority_type, "bind", None)
    if not callable(bind):
        return _unavailable_origin()
    try:
        home = Path.home()
        logical_root = home / ".agents" / "publication"
        if not home.is_absolute() or not logical_root.is_absolute():
            return _unavailable_origin()
        try:
            logical_root.lstat()
        except FileNotFoundError:
            return _absent_origin(logical_root)
        authority = bind(
            logical_root,
            scope="global",
            trusted_global_roots=(logical_root,),
            allow_linked_ancestors=True,
        )
        if authority is None:
            root_metadata = logical_root.lstat()
            if _is_reparse(root_metadata) or not stat.S_ISDIR(root_metadata.st_mode):
                return _unavailable_origin()
            physical_root = logical_root
            logical_identity = _identity4(root_metadata)
            physical_identity = logical_identity
            links: tuple[tuple[Any, ...], ...] = ()
        else:
            physical_root = Path(authority.resolved_root)
            logical_identity = tuple(_int_to_decimal(int(value)) for value in authority.logical_identity)
            physical_identity = tuple(_int_to_decimal(int(value)) for value in authority.resolved_identity)
            links = _link_witnesses(authority.link_chain)
            authority.assert_current()
        logical_leaf = logical_root / "reviewed-exceptions.json"
        return OriginSelection(
            contractId="orchestrarium.publication-review-origin.v1",
            status="selected",
            diagnostic="none",
            logicalRoot=MappingProxyType(_native_path(logical_root)),
            logicalLeaf=MappingProxyType(_native_path(logical_leaf)),
            logicalIdentity=tuple(logical_identity),
            physicalRoot=MappingProxyType(_directory_object(physical_root, physical_root.lstat())),
            physicalIdentity=tuple(physical_identity),
            links=links,
            logicalRootPath=logical_root,
            physicalRootPath=physical_root,
            policyLeafPath=physical_root / "reviewed-exceptions.json",
            linkedAuthority=authority,
        )
    except (OSError, RuntimeError, TypeError, ValueError, AttributeError):
        return _unavailable_origin()


def _selection_core(selection: OriginSelection) -> tuple[Any, ...]:
    return (
        dict(selection.logicalRoot) if selection.logicalRoot is not None else None,
        selection.logicalIdentity,
        dict(selection.physicalRoot) if selection.physicalRoot is not None else None,
        selection.physicalIdentity,
        selection.links,
        dict(selection.logicalLeaf) if selection.logicalLeaf is not None else None,
        selection.status,
        selection.diagnostic,
    )


def _origin_object(selection: OriginSelection, file_generation: Mapping[str, Any]) -> dict[str, Any]:
    if (
        selection.status != "selected"
        or selection.logicalRoot is None
        or selection.logicalIdentity is None
        or selection.physicalRoot is None
        or selection.links is None
        or selection.logicalLeaf is None
    ):
        raise PolicyInputError("origin-selection")
    return {
        "logicalRoot": dict(selection.logicalRoot),
        "logicalIdentity": list(selection.logicalIdentity),
        "physicalRoot": dict(selection.physicalRoot),
        "links": [
            [link_path, list(identity), kind, raw_target]
            for link_path, identity, kind, raw_target in selection.links
        ],
        "leafPath": dict(selection.logicalLeaf),
        "fileGeneration": dict(file_generation),
    }


def _file_generation(metadata: os.stat_result) -> dict[str, Any]:
    mtime_ns = getattr(metadata, "st_mtime_ns", int(metadata.st_mtime * 1_000_000_000))
    return {
        "device": _int_to_decimal(int(metadata.st_dev)),
        "inode": _int_to_decimal(int(metadata.st_ino)),
        "mode": _int_to_decimal(int(metadata.st_mode)),
        "links": _int_to_decimal(int(metadata.st_nlink)),
        "size": int(metadata.st_size),
        "mtimeNs": _int_to_decimal(int(mtime_ns)),
    }


def _decode_native_path_object(value: Any, where: str, *, allow_relative: bool = False) -> tuple[str, bytes, str]:
    obj = _exact_object(value, ("pathEncoding", "pathBase64"), where)
    encoding = obj["pathEncoding"]
    raw = _decode_base64(obj["pathBase64"], where + "-base64")
    if not raw:
        raise PolicyInputError(where + "-path")
    if encoding == "windows-utf16le":
        if len(raw) % 2:
            raise PolicyInputError(where + "-path")
        try:
            spelling = raw.decode("utf-16-le", errors="surrogatepass")
        except UnicodeDecodeError as exc:
            raise PolicyInputError(where + "-path") from exc
        if "\x00" in spelling:
            raise PolicyInputError(where + "-path")
        if not allow_relative:
            drive, _tail = ntpath.splitdrive(spelling)
            if not drive or not ntpath.isabs(spelling):
                raise PolicyInputError(where + "-absolute")
        return encoding, raw, spelling
    if encoding == "posix-bytes":
        if b"\0" in raw:
            raise PolicyInputError(where + "-path")
        if not allow_relative and not raw.startswith(b"/"):
            raise PolicyInputError(where + "-absolute")
        return encoding, raw, os.fsdecode(raw)
    raise PolicyInputError(where + "-encoding")


def _validate_identity4(value: Any, where: str) -> tuple[str, ...]:
    if type(value) not in (list, tuple) or len(value) != 4:
        raise PolicyInputError(where)
    result: list[str] = []
    for part in value:
        if type(part) is not str or _DECIMAL_RE.fullmatch(part) is None:
            raise PolicyInputError(where)
        result.append(part)
    return tuple(result)


def _validate_origin_object(value: Any) -> dict[str, Any]:
    origin = _exact_object(
        value,
        ("logicalRoot", "logicalIdentity", "physicalRoot", "links", "leafPath", "fileGeneration"),
        "origin",
    )
    logical_encoding, logical_raw, logical_text = _decode_native_path_object(
        origin["logicalRoot"], "origin-logical-root"
    )
    leaf_encoding, leaf_raw, leaf_text = _decode_native_path_object(origin["leafPath"], "origin-leaf")
    if logical_encoding != leaf_encoding:
        raise PolicyInputError("origin-path-encoding")
    if logical_encoding == "windows-utf16le":
        if ntpath.dirname(leaf_text) != logical_text or ntpath.basename(leaf_text) != "reviewed-exceptions.json":
            raise PolicyInputError("origin-leaf-scope")
    else:
        if os.path.dirname(leaf_raw) != logical_raw or os.path.basename(leaf_raw) != b"reviewed-exceptions.json":
            raise PolicyInputError("origin-leaf-scope")
    _validate_identity4(origin["logicalIdentity"], "origin-logical-identity")
    _validate_native_directory(origin["physicalRoot"], "origin-physical-root")

    links = origin["links"]
    if type(links) not in (list, tuple):
        raise PolicyInputError("origin-links")
    markers: list[bytes] = []
    for link in links:
        if type(link) not in (list, tuple) or len(link) != 4:
            raise PolicyInputError("origin-link")
        link_path, identity, kind, raw_target = link
        link_encoding, _link_raw, _link_text = _decode_native_path_object(link_path, "origin-link-path")
        _validate_identity4(identity, "origin-link-identity")
        if kind not in ("symlink", "junction"):
            raise PolicyInputError("origin-link-kind")
        target_encoding, _target_raw, _target_text = _decode_native_path_object(
            raw_target, "origin-link-target", allow_relative=True
        )
        if target_encoding != link_encoding:
            raise PolicyInputError("origin-link-encoding")
        markers.append(C([link_path, list(identity), kind, raw_target]))
    if len(markers) != len(set(markers)):
        raise PolicyInputError("origin-link-duplicate")

    generation = _exact_object(
        origin["fileGeneration"],
        ("device", "inode", "mode", "links", "size", "mtimeNs"),
        "origin-file-generation",
    )
    for name in ("device", "inode", "mode", "links"):
        if type(generation[name]) is not str or _DECIMAL_RE.fullmatch(generation[name]) is None:
            raise PolicyInputError("origin-file-generation-" + name)
    _require_uint(generation["size"], "origin-file-generation-size")
    if type(generation["mtimeNs"]) is not str or _SIGNED_DECIMAL_RE.fullmatch(generation["mtimeNs"]) is None:
        raise PolicyInputError("origin-file-generation-mtime")
    return origin


def _same_file_generation(left: os.stat_result, right: os.stat_result) -> bool:
    return _file_generation(left) == _file_generation(right)


def _snapshot(
    status: str,
    origin: Mapping[str, Any] | None,
    raw: bytes | None,
    diagnostic: str,
) -> PolicySnapshot:
    if status not in ("captured", "absent", "unavailable"):
        raise PolicyInputError("snapshot-status")
    if diagnostic not in ("none", "absent", "unreadable", "invalid-origin", "invalid-data"):
        raise PolicyInputError("snapshot-diagnostic")
    if status == "captured":
        if origin is None or raw is None or diagnostic != "none":
            raise PolicyInputError("snapshot-captured-shape")
        _validate_origin_object(_thaw(origin))
        raw_b64 = base64.b64encode(raw).decode("ascii")
        raw_sha = hashlib.sha256(raw).hexdigest()
    else:
        if raw is not None or diagnostic == "none":
            raise PolicyInputError("snapshot-unavailable-shape")
        raw_b64 = None
        raw_sha = None
    return PolicySnapshot(
        schemaVersion=1,
        status=status,
        origin=_freeze(_thaw(origin)) if origin is not None else None,
        rawBase64=raw_b64,
        rawSha256=raw_sha,
        diagnostic=diagnostic,
    )


def snapshot_id(snapshot: PolicySnapshot | Mapping[str, Any]) -> str:
    value = snapshot.object() if isinstance(snapshot, PolicySnapshot) else _thaw(snapshot)
    expected = ("schemaVersion", "status", "origin", "rawBase64", "rawSha256", "diagnostic")
    obj = _exact_object(value, expected, "snapshot")
    if obj["schemaVersion"] != 1 or type(obj["schemaVersion"]) is not int:
        raise PolicyInputError("snapshot-schema")
    if obj["status"] not in ("captured", "absent", "unavailable"):
        raise PolicyInputError("snapshot-status")
    if obj["diagnostic"] not in ("none", "absent", "unreadable", "invalid-origin", "invalid-data"):
        raise PolicyInputError("snapshot-diagnostic")
    if obj["status"] == "captured":
        if obj["origin"] is None or obj["diagnostic"] != "none":
            raise PolicyInputError("snapshot-captured-shape")
        _validate_origin_object(obj["origin"])
        raw = _decode_base64(obj["rawBase64"], "snapshot-raw")
        if _require_sha(obj["rawSha256"], "snapshot-raw-sha") != hashlib.sha256(raw).hexdigest():
            raise PolicyInputError("snapshot-raw-digest")
    elif obj["rawBase64"] is not None or obj["rawSha256"] is not None or obj["diagnostic"] == "none":
        raise PolicyInputError("snapshot-unavailable-shape")
    return H(DOMAIN_SNAPSHOT, obj)


def _policy_read_from_snapshot(snapshot: Mapping[str, Any]) -> PolicyReadV1:
    plain_snapshot = _thaw(snapshot)
    snapshot_digest = snapshot_id(plain_snapshot)
    issues: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    status = plain_snapshot["status"]
    if status == "absent":
        issues.append({"decision_id": None, "code": "POLICY-ABSENT"})
    elif status == "unavailable":
        issues.append({"decision_id": None, "code": "POLICY-UNAVAILABLE"})
    else:
        raw = _decode_base64(plain_snapshot["rawBase64"], "snapshot-raw")
        decoded = decode_document(raw)
        if not decoded.outer_valid:
            issues.append({"decision_id": None, "code": "POLICY-DOCUMENT-INVALID"})
        else:
            duplicate_ids = set(decoded.duplicate_ids)
            for record_id in decoded.duplicate_ids:
                issues.append({"decision_id": record_id, "code": "POLICY-DUPLICATE-ID"})
            for record_id in decoded.invalid_record_ids:
                if record_id not in duplicate_ids:
                    issues.append({"decision_id": record_id, "code": "POLICY-RECORD-INVALID"})
            for record in decoded.usable_records():
                if record["id"] in duplicate_ids:
                    continue
                if record["state"] == "revoked":
                    issues.append({"decision_id": record["id"], "code": "POLICY-REVOKED"})
                else:
                    records.append(record)
    records.sort(key=lambda record: record["id"])
    issues.sort(key=lambda issue: (issue["decision_id"] or "", issue["code"]))
    return PolicyReadV1(
        snapshot=plain_snapshot,
        snapshot_id=snapshot_digest,
        usable_records=tuple(records),
        issues=tuple(issues),
    )


def decode_policy_snapshot(snapshot: dict[str, Any]) -> PolicyReadV1:
    """Purely validate and decode captured Snapshot data; it grants no origin trust."""
    if type(snapshot) is not dict:
        raise PolicyInputError("snapshot-type")
    snapshot_id(snapshot)
    return _policy_read_from_snapshot(snapshot)


def _path_contains(parent: Path, child: Path) -> bool | None:
    try:
        parent_text = os.path.normcase(os.path.abspath(os.fspath(parent)))
        child_text = os.path.normcase(os.path.abspath(os.fspath(child)))
        common = os.path.normcase(os.path.commonpath((parent_text, child_text)))
        return common == parent_text
    except ValueError:
        # On Windows, different drives prove disjointness.
        if os.name == "nt":
            return False
        return None
    except (OSError, RuntimeError, TypeError):
        return None


def _paths_overlap(left: Path, right: Path) -> bool | None:
    left_contains = _path_contains(left, right)
    right_contains = _path_contains(right, left)
    if left_contains is None or right_contains is None:
        return None
    return left_contains or right_contains


def _origin_outside_selected_root(selection: OriginSelection, selected_root: Path) -> bool:
    if selection.status == "absent":
        if selection.logicalRootPath is None:
            return False
        overlap = _paths_overlap(selection.logicalRootPath, selected_root)
        return overlap is False
    if (
        selection.status != "selected"
        or selection.logicalRootPath is None
        or selection.physicalRootPath is None
    ):
        return False
    for origin_root in (selection.logicalRootPath, selection.physicalRootPath):
        overlap = _paths_overlap(origin_root, selected_root)
        if overlap is not False:
            return False
    for link_path, _identity, _kind, raw_target in selection.links:
        link_value = _decode_native_path_object(link_path, "origin-link-path")[2]
        link_path_obj = Path(link_value)
        overlap = _paths_overlap(link_path_obj, selected_root)
        if overlap is not False:
            return False
        target_path = _link_target_scope_path(link_path, raw_target)
        if _paths_overlap(target_path, selected_root) is not False:
            return False
    return True


def read_policy_snapshot(trusted_origin: OriginSelection, selected_root: Path) -> PolicyReadV1:
    """Capture the fixed host policy leaf; this operation performs no Git IO."""
    if not isinstance(trusted_origin, OriginSelection) or trusted_origin.contractId != "orchestrarium.publication-review-origin.v1":
        snapshot = _snapshot("unavailable", None, None, "invalid-origin")
        return _policy_read_from_snapshot(snapshot.object())
    if not isinstance(selected_root, Path) or not selected_root.is_absolute():
        snapshot = _snapshot("unavailable", None, None, "invalid-origin")
        return _policy_read_from_snapshot(snapshot.object())

    selection = resolve_trusted_origin()
    if _selection_core(selection) != _selection_core(trusted_origin):
        snapshot = _snapshot("unavailable", None, None, "invalid-origin")
        return _policy_read_from_snapshot(snapshot.object())
    if not _origin_outside_selected_root(selection, selected_root):
        snapshot = _snapshot("unavailable", None, None, "invalid-origin")
        return _policy_read_from_snapshot(snapshot.object())
    captured = _capture_policy_file(selection)
    if not captured.resourcesSettled:
        _raise_policy_error("POLICY-IO", "settlement")
    return _policy_read_from_snapshot(captured.snapshot.object())


_REPOSITORY_QUERY_SUFFIXES = (
    ("topLevel", ("--show-toplevel",)),
    ("commonGit", ("--path-format=absolute", "--git-common-dir")),
    ("worktreeGit", ("--absolute-git-dir",)),
    ("objectFormat", ("--show-object-format",)),
)


def _unavailable_repository(diagnostic: str = "metadata-unavailable") -> dict[str, Any]:
    if diagnostic not in ("metadata-unavailable", "unprovable-native-identity"):
        diagnostic = "metadata-unavailable"
    return {"status": "unavailable", "repository": None, "diagnostic": diagnostic}


def repository_query_plan(selected_root: Path) -> RepositoryQueryPlanV1:
    """Capture one already-qualified root and describe, but never run, Git IO."""
    if not isinstance(selected_root, Path) or not selected_root.is_absolute():
        raise PolicyInputError("repository-root-absolute")
    root = selected_root
    try:
        before = root.lstat()
    except OSError as exc:
        raise PolicyInputError("repository-root-unavailable") from exc
    root_before = _directory_object(root, before)
    prefix = (
        "--no-optional-locks",
        "-C",
        os.fspath(root),
        "rev-parse",
    )
    queries = tuple(
        RepositoryQueryV1(key=key, git_args=prefix + suffix)
        for key, suffix in _REPOSITORY_QUERY_SUFFIXES
    )
    return RepositoryQueryPlanV1(root=root, root_before=root_before, queries=queries)


def _query_plan_is_exact(plan: RepositoryQueryPlanV1) -> bool:
    try:
        expected = repository_query_plan(plan.root)
    except (PolicyInputError, OSError, RuntimeError, TypeError, ValueError):
        return False
    return plan.root_before == expected.root_before and plan.queries == expected.queries


def _query_output_path(raw: bytes) -> tuple[Path, dict[str, str], os.stat_result]:
    if type(raw) is not bytes or not raw.endswith(b"\n"):
        raise PolicyInputError("repository-path-line")
    output = raw[:-1]
    if not output or b"\0" in output:
        raise PolicyInputError("repository-path-empty")
    try:
        spelling = os.fsdecode(output)
        if os.fsencode(spelling) != output:
            raise PolicyInputError("repository-path-roundtrip")
    except (UnicodeError, ValueError) as exc:
        raise PolicyInputError("repository-path-decode") from exc
    if os.name == "nt":
        drive, _tail = ntpath.splitdrive(spelling)
        if not drive or not ntpath.isabs(spelling):
            raise PolicyInputError("repository-path-absolute")
        encoding = "windows-utf16le"
        native_bytes = spelling.encode("utf-16-le", errors="surrogatepass")
    else:
        if not output.startswith(b"/"):
            raise PolicyInputError("repository-path-absolute")
        encoding = "posix-bytes"
        native_bytes = output
    path = Path(spelling)
    metadata = path.lstat()
    if _is_reparse(metadata) or not stat.S_ISDIR(metadata.st_mode):
        raise PolicyInputError("repository-path-kind")
    native = {
        "pathEncoding": encoding,
        "pathBase64": base64.b64encode(native_bytes).decode("ascii"),
    }
    return path, native, metadata


def _native_directory_from_output(native_path: Mapping[str, str], metadata: os.stat_result) -> dict[str, str]:
    if _is_reparse(metadata) or not stat.S_ISDIR(metadata.st_mode):
        raise PolicyInputError("repository-directory-kind")
    return {
        "pathEncoding": native_path["pathEncoding"],
        "pathBase64": native_path["pathBase64"],
        "device": _int_to_decimal(int(metadata.st_dev)),
        "inode": _int_to_decimal(int(metadata.st_ino)),
    }


def _same_comparison_path(left: Path, right: Path) -> bool:
    left_text = os.path.normcase(os.path.normpath(os.fspath(left)))
    right_text = os.path.normcase(os.path.normpath(os.fspath(right)))
    return left_text == right_text


def repository_from_query_results(
    plan: RepositoryQueryPlanV1,
    results: tuple[RepositoryQueryResultV1, ...],
) -> dict[str, Any]:
    """Interpret the exact four settled raw-byte results from the caller."""
    if type(plan) is not RepositoryQueryPlanV1 or not _query_plan_is_exact(plan):
        return _unavailable_repository()
    if type(results) is not tuple or len(results) != len(plan.queries):
        return _unavailable_repository()
    for expected_query, result in zip(plan.queries, results):
        if type(result) is not RepositoryQueryResultV1:
            return _unavailable_repository()
        if result.query_key != expected_query.key or result.git_args != expected_query.git_args:
            return _unavailable_repository()
        if (
            type(result.complete) is not bool
            or result.complete is not True
            or result.resources_settled is not True
            or type(result.returncode) is not int
            or result.returncode != 0
            or type(result.stdout) is not bytes
            or type(result.stderr) is not bytes
            or result.failure_kind is not None
        ):
            return _unavailable_repository()

    try:
        output: dict[str, RepositoryQueryResultV1] = {
            result.query_key: result for result in results
        }
        if len(output) != len(plan.queries):
            return _unavailable_repository()
        top_path, top_native, top_metadata = _query_output_path(output["topLevel"].stdout)
        common_path, common_native, common_metadata = _query_output_path(output["commonGit"].stdout)
        worktree_path, worktree_native, worktree_metadata = _query_output_path(output["worktreeGit"].stdout)
        object_format_raw = output["objectFormat"].stdout
        if not object_format_raw.endswith(b"\n"):
            raise PolicyInputError("repository-object-format-line")
        object_format_bytes = object_format_raw[:-1]
        if object_format_bytes not in (b"sha1", b"sha256"):
            raise PolicyInputError("repository-object-format")
        object_format = object_format_bytes.decode("ascii")

        before_directory = _validate_native_directory(plan.root_before, "repository-root-before")
        if not _same_comparison_path(top_path, plan.root):
            raise PolicyInputError("repository-top-level-path")
        if (
            int(before_directory["device"]) != int(top_metadata.st_dev)
            or int(before_directory["inode"]) != int(top_metadata.st_ino)
        ):
            raise PolicyInputError("repository-top-level-identity")
        current_root = plan.root.lstat()
        if (
            _is_reparse(current_root)
            or not stat.S_ISDIR(current_root.st_mode)
            or _native_directory_from_output(
                {"pathEncoding": before_directory["pathEncoding"], "pathBase64": before_directory["pathBase64"]},
                current_root,
            )
            != plan.root_before
        ):
            raise PolicyInputError("repository-root-drift")

        repository = {
            "kind": "native-worktree-v1",
            "objectFormat": object_format,
            "commonGit": _native_directory_from_output(common_native, common_metadata),
            "worktreeGit": _native_directory_from_output(worktree_native, worktree_metadata),
            "worktreeRoot": _native_directory_from_output(top_native, top_metadata),
        }
        _validate_repository(repository)
    except (OSError, RuntimeError, TypeError, ValueError, AttributeError):
        return _unavailable_repository("unprovable-native-identity")
    return {"status": "captured", "repository": repository, "diagnostic": "none"}


def _native_path_value(value: Any, where: str, *, allow_relative: bool = False) -> tuple[str, bytes, str]:
    return _decode_native_path_object(value, where, allow_relative=allow_relative)


def _scope_path(encoded_path: Any, where: str) -> Path:
    _encoding, _raw, spelling = _native_path_value(encoded_path, where)
    return Path(spelling)


def _link_target_scope_path(link_path: Any, raw_target: Any) -> Path:
    link_encoding, _link_raw, link_spelling = _native_path_value(link_path, "origin-link-path")
    target_encoding, target_raw, target_spelling = _native_path_value(
        raw_target, "origin-link-target", allow_relative=True
    )
    if target_encoding != link_encoding:
        raise PolicyInputError("origin-link-encoding")
    if link_encoding == "windows-utf16le":
        if ntpath.isabs(target_spelling):
            target = target_spelling
        else:
            target = ntpath.join(ntpath.dirname(link_spelling), target_spelling)
        return Path(ntpath.normpath(target))
    if os.path.isabs(target_raw):
        target = target_raw
    else:
        target = os.path.join(os.path.dirname(_link_raw), target_raw)
    return Path(os.fsdecode(os.path.normpath(target)))


def _identity_pair(identity: tuple[str, ...] | list[str]) -> tuple[int, int] | None:
    device, inode = int(identity[0]), int(identity[1])
    if device == 0 and inode == 0:
        return None
    return device, inode


def origin_is_outside_repository(snapshot: dict[str, Any], repository: dict[str, Any]) -> bool:
    """Purely prove captured origin path/identity exclusion from every repo root."""
    try:
        if type(snapshot) is not dict or type(repository) is not dict:
            return False
        snapshot_id(snapshot)
        if snapshot.get("status") != "captured" or snapshot.get("origin") is None:
            return False
        origin = _validate_origin_object(snapshot["origin"])
        repo = _validate_repository(repository)
        core = {
            name: _thaw(origin[name])
            for name in ("logicalRoot", "logicalIdentity", "physicalRoot", "links", "leafPath")
        }
        return _origin_core_is_outside_repository(core, repo, origin["fileGeneration"])
    except (OSError, RuntimeError, TypeError, ValueError, AttributeError, KeyError):
        return False


def _origin_core_from_snapshot(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    origin = _validate_origin_object(snapshot["origin"])
    return {
        name: _thaw(origin[name])
        for name in ("logicalRoot", "logicalIdentity", "physicalRoot", "links", "leafPath")
    }


def _origin_core_from_selection(selection: OriginSelection) -> dict[str, Any]:
    if (
        selection.status != "selected"
        or selection.logicalRoot is None
        or selection.logicalIdentity is None
        or selection.physicalRoot is None
        or selection.logicalLeaf is None
    ):
        raise PolicyInputError("origin-unavailable")
    return {
        "logicalRoot": dict(selection.logicalRoot),
        "logicalIdentity": list(selection.logicalIdentity),
        "physicalRoot": dict(selection.physicalRoot),
        "links": [
            [link_path, list(identity), kind, raw_target]
            for link_path, identity, kind, raw_target in selection.links
        ],
        "leafPath": dict(selection.logicalLeaf),
    }


def _origin_core_is_outside_repository(
    core_value: Mapping[str, Any],
    repository_value: Mapping[str, Any],
    file_generation: Mapping[str, Any] | None = None,
) -> bool:
    """Shared pure path/identity predicate for captured and selected origins."""
    try:
        core = _exact_object(
            _thaw(core_value),
            ("logicalRoot", "logicalIdentity", "physicalRoot", "links", "leafPath"),
            "origin-core",
        )
        repository = _validate_repository(_thaw(repository_value))
        _decode_native_path_object(core["logicalRoot"], "origin-logical-root")
        _decode_native_path_object(core["leafPath"], "origin-leaf")
        logical_identity = _validate_identity4(core["logicalIdentity"], "origin-logical-identity")
        physical_root = _validate_native_directory(core["physicalRoot"], "origin-physical-root")

        repo_paths: list[Path] = []
        repo_ids: set[tuple[int, int]] = set()
        for index, name in enumerate(("commonGit", "worktreeGit", "worktreeRoot")):
            directory = repository[name]
            repo_paths.append(
                _scope_path(
                    {"pathEncoding": directory["pathEncoding"], "pathBase64": directory["pathBase64"]},
                    "repository-root-" + str(index),
                )
            )
            pair = (int(directory["device"]), int(directory["inode"]))
            if pair != (0, 0):
                repo_ids.add(pair)

        origin_paths = [
            _scope_path(core["logicalRoot"], "origin-logical-root"),
            _scope_path(core["leafPath"], "origin-leaf"),
            _scope_path(
                {"pathEncoding": physical_root["pathEncoding"], "pathBase64": physical_root["pathBase64"]},
                "origin-physical-root",
            ),
        ]
        origin_ids: list[tuple[str, ...]] = [
            logical_identity,
            (physical_root["device"], physical_root["inode"], "0", "0"),
        ]
        links = core["links"]
        if type(links) not in (list, tuple):
            return False
        for link in links:
            if type(link) not in (list, tuple) or len(link) != 4:
                return False
            link_path, identity, kind, raw_target = link
            if kind not in ("symlink", "junction"):
                return False
            origin_paths.append(_scope_path(link_path, "origin-link-path"))
            origin_paths.append(_link_target_scope_path(link_path, raw_target))
            origin_ids.append(_validate_identity4(identity, "origin-link-identity"))
        if file_generation is not None:
            generation = _exact_object(
                _thaw(file_generation),
                ("device", "inode", "mode", "links", "size", "mtimeNs"),
                "origin-file-generation",
            )
            origin_ids.append(
                (
                    generation["device"],
                    generation["inode"],
                    generation["mode"],
                    "0",
                )
            )
        for identity in origin_ids:
            pair = _identity_pair(identity)
            if pair is not None and pair in repo_ids:
                return False
        for origin_path in origin_paths:
            for repository_path in repo_paths:
                if _paths_overlap(origin_path, repository_path) is not False:
                    return False
        return True
    except (OSError, RuntimeError, TypeError, ValueError, AttributeError, KeyError):
        return False


def _repository_matches_native_filesystem(repository: Mapping[str, Any]) -> bool:
    try:
        checked = _validate_repository(_thaw(repository))
        expected_encoding = "windows-utf16le" if os.name == "nt" else "posix-bytes"
        for name in ("commonGit", "worktreeGit", "worktreeRoot"):
            directory = checked[name]
            encoding, raw, spelling = _decode_native_path_object(
                {"pathEncoding": directory["pathEncoding"], "pathBase64": directory["pathBase64"]},
                "repository-" + name,
            )
            if encoding != expected_encoding:
                return False
            path = Path(spelling)
            metadata = path.lstat()
            if _is_reparse(metadata) or not stat.S_ISDIR(metadata.st_mode):
                return False
            if (
                _int_to_decimal(int(metadata.st_dev)) != directory["device"]
                or _int_to_decimal(int(metadata.st_ino)) != directory["inode"]
            ):
                return False
        return True
    except (OSError, RuntimeError, TypeError, ValueError, AttributeError, KeyError):
        return False


def _validate_used_list(value: Any) -> list[list[str]]:
    if type(value) is not list:
        raise PolicyInputError("used-list")
    result: list[list[str]] = []
    for pair in value:
        if type(pair) is not list or len(pair) != 2:
            raise PolicyInputError("used-list-row")
        decision_id = _require_id(pair[0], "used-list-id")
        record_sha = _require_sha(pair[1], "used-list-record-sha")
        result.append([decision_id, record_sha])
    decision_ids = [pair[0] for pair in result]
    if decision_ids != sorted(set(decision_ids)):
        raise PolicyInputError("used-list-order")
    return result


def _finalization(
    input_snapshot_id: str,
    used_list: list[list[str]],
    current_snapshot_id: str | None,
    repository_sha256: str,
    status: str,
    reason: str,
    resources_settled: bool,
) -> dict[str, Any]:
    result = {
        "inputSnapshotId": input_snapshot_id,
        "usedList": used_list,
        "currentSnapshotId": current_snapshot_id,
        "repositorySha256": repository_sha256,
        "status": status,
        "reason": reason,
        "resourcesSettled": resources_settled,
    }
    _validate_finalization(result)
    return result


def _validate_finalization(value: Any) -> dict[str, Any]:
    obj = _exact_object(
        value,
        (
            "inputSnapshotId",
            "usedList",
            "currentSnapshotId",
            "repositorySha256",
            "status",
            "reason",
            "resourcesSettled",
        ),
        "finalization",
    )
    _require_sha(obj["inputSnapshotId"], "finalization-input-snapshot")
    _validate_used_list(obj["usedList"])
    if obj["currentSnapshotId"] is not None:
        _require_sha(obj["currentSnapshotId"], "finalization-current-snapshot")
    _require_sha(obj["repositorySha256"], "finalization-repository")
    if obj["status"] not in ("valid", "invalid", "unavailable"):
        raise PolicyInputError("finalization-status")
    if obj["reason"] not in (
        "none",
        "repository-drift",
        "origin-drift",
        "used-record-missing",
        "used-record-invalid",
        "used-record-revoked",
        "used-record-changed",
        "origin-unavailable",
        "policy-unavailable",
        "resource-unsettled",
    ):
        raise PolicyInputError("finalization-reason")
    if type(obj["resourcesSettled"]) is not bool:
        raise PolicyInputError("finalization-settlement")
    if obj["status"] == "valid" and (
        not obj["usedList"]
        or obj["currentSnapshotId"] is None
        or obj["reason"] != "none"
        or obj["resourcesSettled"] is not True
    ):
        raise PolicyInputError("finalization-valid-shape")
    return obj


def verify_used(
    initial_snapshot: dict[str, Any],
    selected_repository: dict[str, Any],
    used_list: list[list[str]],
) -> dict[str, Any]:
    """Reacquire fixed policy/origin and validate only the exact used records."""
    if type(initial_snapshot) is not dict:
        raise PolicyInputError("initial-snapshot-type")
    input_snapshot_id = snapshot_id(initial_snapshot)
    used = _validate_used_list(used_list)
    if type(selected_repository) is not dict:
        raise PolicyInputError("selected-repository-type")
    repository = _validate_repository(selected_repository)
    repository_sha = H(DOMAIN_REPOSITORY, repository)
    if not used:
        return _finalization(
            input_snapshot_id,
            used,
            None,
            repository_sha,
            "invalid",
            "used-record-missing",
            True,
        )

    if not _repository_matches_native_filesystem(repository):
        return _finalization(
            input_snapshot_id, used, None, repository_sha, "invalid", "repository-drift", True
        )
    if initial_snapshot["status"] != "captured" or initial_snapshot["origin"] is None:
        return _finalization(
            input_snapshot_id,
            used,
            None,
            repository_sha,
            "invalid",
            "used-record-missing",
            True,
        )
    if not origin_is_outside_repository(initial_snapshot, repository):
        return _finalization(
            input_snapshot_id,
            used,
            None,
            repository_sha,
            "invalid",
            "origin-drift",
            True,
        )

    selection = resolve_trusted_origin()
    if selection.status != "selected":
        return _finalization(
            input_snapshot_id,
            used,
            None,
            repository_sha,
            "unavailable",
            "origin-unavailable",
            True,
        )
    try:
        initial_core = _origin_core_from_snapshot(initial_snapshot)
        current_core = _origin_core_from_selection(selection)
    except PolicyInputError:
        return _finalization(
            input_snapshot_id,
            used,
            None,
            repository_sha,
            "invalid",
            "origin-drift",
            True,
        )
    if initial_core != current_core:
        return _finalization(
            input_snapshot_id,
            used,
            None,
            repository_sha,
            "invalid",
            "origin-drift",
            True,
        )

    captured = _capture_policy_file(selection)
    if not captured.resourcesSettled:
        return _finalization(
            input_snapshot_id,
            used,
            None,
            repository_sha,
            "invalid",
            "resource-unsettled",
            False,
        )
    current_snapshot = captured.snapshot.object()
    current_snapshot_id = snapshot_id(current_snapshot)
    if current_snapshot["status"] == "captured" and not origin_is_outside_repository(
        current_snapshot, repository
    ):
        return _finalization(
            input_snapshot_id,
            used,
            current_snapshot_id,
            repository_sha,
            "invalid",
            "origin-drift",
            captured.resourcesSettled,
        )
    if current_snapshot["status"] == "unavailable":
        reason = "origin-unavailable" if current_snapshot["diagnostic"] == "invalid-origin" else "policy-unavailable"
        return _finalization(
            input_snapshot_id,
            used,
            None,
            repository_sha,
            "unavailable",
            reason,
            captured.resourcesSettled,
        )
    if current_snapshot["status"] == "absent":
        return _finalization(
            input_snapshot_id,
            used,
            current_snapshot_id,
            repository_sha,
            "invalid",
            "used-record-missing",
            captured.resourcesSettled,
        )

    decoded = decode_document(_decode_base64(current_snapshot["rawBase64"], "snapshot-raw"))
    if not decoded.outer_valid:
        return _finalization(
            input_snapshot_id,
            used,
            current_snapshot_id,
            repository_sha,
            "invalid",
            "used-record-invalid",
            captured.resourcesSettled,
        )

    valid_records = {record["id"]: record for record in decoded.usable_records()}
    invalid_ids = set(decoded.invalid_record_ids)
    duplicate_ids = set(decoded.duplicate_ids)
    for decision_id, record_sha in used:
        if decision_id in duplicate_ids or decision_id in invalid_ids:
            return _finalization(
                input_snapshot_id,
                used,
                current_snapshot_id,
                repository_sha,
                "invalid",
                "used-record-invalid",
                captured.resourcesSettled,
            )
        record = valid_records.get(decision_id)
        if record is None:
            return _finalization(
                input_snapshot_id,
                used,
                current_snapshot_id,
                repository_sha,
                "invalid",
                "used-record-missing",
                captured.resourcesSettled,
            )
        if record["state"] == "revoked":
            return _finalization(
                input_snapshot_id,
                used,
                current_snapshot_id,
                repository_sha,
                "invalid",
                "used-record-revoked",
                captured.resourcesSettled,
            )
        if record["recordSha256"] != record_sha:
            return _finalization(
                input_snapshot_id,
                used,
                current_snapshot_id,
                repository_sha,
                "invalid",
                "used-record-changed",
                captured.resourcesSettled,
            )
    return _finalization(
        input_snapshot_id,
        used,
        current_snapshot_id,
        repository_sha,
        "valid",
        "none",
        captured.resourcesSettled,
    )


def _digests(document_sha: str | None, record_sha: str | None) -> dict[str, str | None]:
    if document_sha is not None:
        _require_sha(document_sha, "promotion-document-digest")
    if record_sha is not None:
        _require_sha(record_sha, "promotion-record-digest")
    return {"documentSha256": document_sha, "recordSha256": record_sha}


def _failure_detail(code: str, phase: str) -> dict[str, str]:
    if code not in ("POLICY-INPUT", "POLICY-ORIGIN", "POLICY-PREIMAGE", "POLICY-STATE", "POLICY-IO"):
        raise PolicyInputError("policy-error-code")
    if phase not in ("validate", "capture", "prepare", "replace", "durability", "readback", "settlement"):
        raise PolicyInputError("policy-error-phase")
    return {"code": code, "phase": phase}


def _promotion_result(
    *,
    kind: str,
    decision_id: str,
    before: Mapping[str, Any],
    proposed: Mapping[str, Any],
    observed: Mapping[str, Any] | None,
    effect: str,
    origin: Mapping[str, Any] | None,
    resources_settled: bool,
    diagnostic: Mapping[str, str] | None,
) -> dict[str, Any]:
    result = {
        "schemaVersion": 1,
        "kind": kind,
        "decisionId": decision_id,
        "before": dict(before),
        "proposed": dict(proposed),
        "observed": dict(observed) if observed is not None else None,
        "effect": effect,
        "origin": _thaw(origin) if origin is not None else None,
        "resourcesSettled": resources_settled,
        "diagnostic": dict(diagnostic) if diagnostic is not None else None,
    }
    return _validate_promotion_result(result)


def _validate_promotion_result(value: Any) -> dict[str, Any]:
    obj = _exact_object(
        value,
        (
            "schemaVersion",
            "kind",
            "decisionId",
            "before",
            "proposed",
            "observed",
            "effect",
            "origin",
            "resourcesSettled",
            "diagnostic",
        ),
        "promotion-result",
    )
    if obj["schemaVersion"] != 1 or type(obj["schemaVersion"]) is not int:
        raise PolicyInputError("promotion-result-version")
    if obj["kind"] not in ("preview", "committed", "idempotent", "recovery-required"):
        raise PolicyInputError("promotion-result-kind")
    _require_id(obj["decisionId"], "promotion-result-id")
    for name in ("before", "proposed"):
        digests = _exact_object(obj[name], ("documentSha256", "recordSha256"), "promotion-" + name)
        for digest in digests.values():
            if digest is not None:
                _require_sha(digest, "promotion-result-digest")
    if obj["observed"] is not None:
        observed = _exact_object(obj["observed"], ("documentSha256", "recordSha256"), "promotion-observed")
        for digest in observed.values():
            if digest is not None:
                _require_sha(digest, "promotion-observed-digest")
    if obj["effect"] not in ("not-applied", "applied", "unknown"):
        raise PolicyInputError("promotion-result-effect")
    if obj["origin"] is not None:
        _validate_origin_object(obj["origin"])
    if type(obj["resourcesSettled"]) is not bool:
        raise PolicyInputError("promotion-result-settlement")
    if obj["diagnostic"] is not None:
        detail = _exact_object(obj["diagnostic"], ("code", "phase"), "promotion-diagnostic")
        _failure_detail(detail["code"], detail["phase"])
    if obj["kind"] == "preview" and (
        obj["effect"] != "not-applied"
        or obj["observed"] is None
        or obj["diagnostic"] is not None
        or not obj["resourcesSettled"]
    ):
        raise PolicyInputError("promotion-preview-shape")
    if obj["kind"] == "idempotent" and (
        obj["effect"] != "not-applied"
        or obj["observed"] is None
        or obj["diagnostic"] is not None
        or not obj["resourcesSettled"]
    ):
        raise PolicyInputError("promotion-idempotent-shape")
    if obj["kind"] == "committed" and (
        obj["effect"] != "applied"
        or obj["observed"] != obj["proposed"]
        or obj["diagnostic"] is not None
        or not obj["resourcesSettled"]
    ):
        raise PolicyInputError("promotion-committed-shape")
    if obj["kind"] == "recovery-required" and (
        obj["diagnostic"] is None or obj["effect"] == "not-applied"
    ):
        raise PolicyInputError("promotion-recovery-shape")
    return obj


def _raise_policy_error(
    code: str,
    phase: str,
    outcome: Mapping[str, Any] | None = None,
    cause: BaseException | None = None,
) -> None:
    error = PolicyError(_failure_detail(code, phase), outcome)
    if cause is not None:
        raise error from cause
    raise error


def _repository_root_path(repository: Mapping[str, Any]) -> Path:
    checked = _validate_repository(_thaw(repository))
    _encoding, _raw, spelling = _decode_native_path_object(
        {
            "pathEncoding": checked["worktreeRoot"]["pathEncoding"],
            "pathBase64": checked["worktreeRoot"]["pathBase64"],
        },
        "repository-worktree-root",
    )
    return Path(spelling)


def _origin_selection_outside_repository(selection: OriginSelection, repository: Mapping[str, Any]) -> bool:
    try:
        if selection.status != "selected":
            return False
        return _origin_core_is_outside_repository(_origin_core_from_selection(selection), repository)
    except (PolicyInputError, OSError, RuntimeError, TypeError, ValueError, AttributeError, KeyError):
        return False


def _load_policy_change_state(
    trusted_origin: OriginSelection,
    selected_repository: Mapping[str, Any],
) -> tuple[dict[str, Any], DecodedDocument | None, OriginSelection]:
    if not isinstance(trusted_origin, OriginSelection) or trusted_origin.contractId != "orchestrarium.publication-review-origin.v1":
        _raise_policy_error("POLICY-ORIGIN", "validate")
    repository = _validate_repository(_thaw(selected_repository))
    if not _repository_matches_native_filesystem(repository):
        _raise_policy_error("POLICY-PREIMAGE", "capture")
    root = _repository_root_path(repository)
    policy_read = read_policy_snapshot(trusted_origin, root)
    snapshot = policy_read.snapshot
    if snapshot["status"] == "unavailable":
        code = "POLICY-ORIGIN" if snapshot["diagnostic"] == "invalid-origin" else "POLICY-IO"
        _raise_policy_error(code, "capture")
    current_origin = resolve_trusted_origin()
    if current_origin.status != "selected" or _selection_core(current_origin) != _selection_core(trusted_origin):
        _raise_policy_error("POLICY-ORIGIN", "capture")
    if snapshot["status"] == "captured":
        if not origin_is_outside_repository(snapshot, repository):
            _raise_policy_error("POLICY-ORIGIN", "validate")
        raw = _decode_base64(snapshot["rawBase64"], "snapshot-raw")
        decoded = decode_document(raw)
        if not decoded.outer_valid:
            _raise_policy_error("POLICY-STATE", "validate")
    else:
        if not _origin_selection_outside_repository(current_origin, repository):
            _raise_policy_error("POLICY-ORIGIN", "validate")
        decoded = None
    return snapshot, decoded, current_origin


def _current_record(document: DecodedDocument | None, decision_id: str) -> dict[str, Any] | None:
    if document is None:
        return None
    for record in document.usable_records():
        if record["id"] == decision_id:
            return record
    return None


def _actual_document_sha(snapshot: Mapping[str, Any]) -> str | None:
    if snapshot["status"] == "captured":
        return _require_sha(snapshot["rawSha256"], "snapshot-raw-sha")
    return None


def _idempotent_result(
    decision_id: str,
    snapshot: Mapping[str, Any],
    record: Mapping[str, Any],
) -> dict[str, Any]:
    document_sha = _actual_document_sha(snapshot)
    record_sha = _require_sha(record["recordSha256"], "record-sha")
    digests = _digests(document_sha, record_sha)
    origin = snapshot["origin"]
    return _promotion_result(
        kind="idempotent",
        decision_id=decision_id,
        before=digests,
        proposed=digests,
        observed=digests,
        effect="not-applied",
        origin=origin,
        resources_settled=True,
        diagnostic=None,
    )


def _prepare_change(
    trusted_origin: OriginSelection,
    selected_repository: Mapping[str, Any],
    decision_id: str,
    replacement: Mapping[str, Any],
    expected_document_sha256: str | None,
    expected_record_sha256: str | None,
    apply: bool,
    *,
    required_state: str = "active",
) -> tuple[dict[str, Any], dict[str, Any] | None, OriginSelection, bytes, dict[str, Any], str]:
    if type(apply) is not bool:
        _raise_policy_error("POLICY-INPUT", "validate")
    if expected_document_sha256 is not None:
        _require_sha(expected_document_sha256, "expected-document-sha")
    if expected_record_sha256 is not None:
        _require_sha(expected_record_sha256, "expected-record-sha")
    decision_id = _require_id(decision_id, "decision-id")
    replacement_plain = _thaw(replacement)
    _validate_record(replacement_plain)
    if replacement_plain["id"] != decision_id or replacement_plain["state"] != required_state:
        _raise_policy_error("POLICY-STATE", "validate")

    repository = _validate_repository(_thaw(selected_repository))
    if replacement_plain["repository"] != repository:
        _raise_policy_error("POLICY-STATE", "validate")

    snapshot, decoded, selection = _load_policy_change_state(trusted_origin, repository)
    current = _current_record(decoded, decision_id)
    if current is not None and current == replacement_plain:
        result = _idempotent_result(decision_id, snapshot, current)
        return snapshot, decoded, selection, b"", result, "idempotent"

    if decoded is not None and not decoded.mutation_safe:
        _raise_policy_error("POLICY-STATE", "validate")

    before_document = _actual_document_sha(snapshot)
    before_record = current["recordSha256"] if current is not None else None
    if before_document != expected_document_sha256 or before_record != expected_record_sha256:
        _raise_policy_error("POLICY-PREIMAGE", "validate")
    try:
        transition = validate_record_transition(current, replacement_plain)
    except PolicyInputError as exc:
        _raise_policy_error("POLICY-STATE", "validate", cause=exc)
    if transition == "idempotent":
        result = _idempotent_result(decision_id, snapshot, current or replacement_plain)
        return snapshot, decoded, selection, b"", result, "idempotent"

    records = list(decoded.usable_records()) if decoded is not None else []
    if current is None:
        records.append(replacement_plain)
    else:
        records = [replacement_plain if record["id"] == decision_id else record for record in records]
    document_revision = (decoded.revision if decoded is not None else 0) + 1
    try:
        proposed_bytes = canonical_document(document_revision, records)
    except (PolicyInputError, KeyError, TypeError, ValueError) as exc:
        _raise_policy_error("POLICY-STATE", "prepare", cause=exc)
    proposed_sha = hashlib.sha256(proposed_bytes).hexdigest()
    proposed = _digests(proposed_sha, replacement_plain["recordSha256"])
    before = _digests(before_document, before_record)
    observed = dict(before)
    origin = snapshot["origin"]
    if not apply:
        preview = _promotion_result(
            kind="preview",
            decision_id=decision_id,
            before=before,
            proposed=proposed,
            observed=observed,
            effect="not-applied",
            origin=origin,
            resources_settled=True,
            diagnostic=None,
        )
        return snapshot, decoded, selection, proposed_bytes, preview, "preview"
    return snapshot, decoded, selection, proposed_bytes, {
        "schemaVersion": 1,
        "kind": "pending",
        "decisionId": decision_id,
        "before": before,
        "proposed": proposed,
        "observed": observed,
        "effect": "not-applied",
        "origin": _thaw(origin) if origin is not None else None,
        "resourcesSettled": True,
        "diagnostic": None,
    }, "apply"


def _observed_digests(snapshot: Mapping[str, Any], decision_id: str) -> dict[str, str | None]:
    document_sha = _actual_document_sha(snapshot)
    record_sha: str | None = None
    if snapshot["status"] == "captured":
        try:
            decoded = decode_document(_decode_base64(snapshot["rawBase64"], "snapshot-raw"))
            if decoded.outer_valid and decision_id not in set(decoded.duplicate_ids):
                for record in decoded.usable_records():
                    if record["id"] == decision_id:
                        record_sha = record["recordSha256"]
                        break
        except (PolicyInputError, TypeError, ValueError):
            record_sha = None
    return _digests(document_sha, record_sha)


def _cleanup_owned_temp(
    path: Path | None,
    identity: tuple[int, int] | None,
    *,
    expected_links: int = 1,
) -> bool:
    if path is None:
        return True
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return True
    except OSError:
        return False
    if (
        identity is None
        or _is_reparse(metadata)
        or not stat.S_ISREG(metadata.st_mode)
        or metadata.st_nlink != expected_links
        or (int(metadata.st_dev), int(metadata.st_ino)) != identity
    ):
        return False
    try:
        path.unlink()
        try:
            path.lstat()
            return False
        except FileNotFoundError:
            return True
    except OSError:
        return False


def _sync_policy_directory(selection: OriginSelection) -> None:
    if os.name == "nt":
        # The supported Python file flush above is the available durability
        # operation on this path; Windows directory handles are not opened via
        # the portable os.open directory contract.
        return
    directory_flag = getattr(os, "O_DIRECTORY", None)
    nofollow = getattr(os, "O_NOFOLLOW", None)
    if directory_flag is None or nofollow is None or selection.physicalRootPath is None:
        raise OSError("policy directory durability is unavailable")
    fd = os.open(selection.physicalRootPath, os.O_RDONLY | directory_flag | nofollow)
    try:
        opened = os.fstat(fd)
        expected = selection.physicalRoot
        if (
            expected is None
            or not stat.S_ISDIR(opened.st_mode)
            or _is_reparse(opened)
            or _int_to_decimal(int(opened.st_dev)) != expected["device"]
            or _int_to_decimal(int(opened.st_ino)) != expected["inode"]
        ):
            raise OSError("policy directory identity changed")
        os.fsync(fd)
    finally:
        try:
            os.close(fd)
        except OSError as exc:
            raise _ResourceUnsettledError("policy directory handle did not settle") from exc


def _commit_policy_change(
    trusted_origin: OriginSelection,
    selected_repository: Mapping[str, Any],
    pending: Mapping[str, Any],
    proposed_bytes: bytes,
) -> dict[str, Any]:
    decision_id = pending["decisionId"]
    proposed = dict(pending["proposed"])
    before = dict(pending["before"])
    original_origin = pending["origin"]
    selection = trusted_origin
    if selection.status != "selected" or selection.policyLeafPath is None or selection.physicalRootPath is None:
        _raise_policy_error("POLICY-ORIGIN", "prepare")

    current_before, current_decoded_before, current_selection_before = _load_policy_change_state(
        trusted_origin, selected_repository
    )
    current_record_before = _current_record(current_decoded_before, decision_id)
    if (
        _actual_document_sha(current_before) != before["documentSha256"]
        or (current_record_before["recordSha256"] if current_record_before is not None else None)
        != before["recordSha256"]
        or _selection_core(current_selection_before) != _selection_core(selection)
    ):
        _raise_policy_error("POLICY-PREIMAGE", "capture")

    temp_path: Path | None = None
    temp_identity: tuple[int, int] | None = None
    temp_fd: int | None = None
    replace_attempted = False
    replaced = False
    resources_settled = True
    failure_phase = "prepare"
    try:
        fd, temp_name = tempfile.mkstemp(
            prefix=".reviewed-exceptions-",
            suffix=".tmp",
            dir=selection.physicalRootPath,
        )
        temp_fd = fd
        temp_path = Path(temp_name)
        opened = os.fstat(fd)
        if _is_reparse(opened) or not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1:
            raise OSError("temporary policy file identity is invalid")
        temp_identity = (int(opened.st_dev), int(opened.st_ino))
        view = memoryview(proposed_bytes)
        while view:
            written = os.write(fd, view)
            if written <= 0:
                raise OSError("temporary policy write made no progress")
            view = view[written:]
        os.fsync(fd)
        written_stat = os.fstat(fd)
        if (
            (int(written_stat.st_dev), int(written_stat.st_ino)) != temp_identity
            or int(written_stat.st_size) != len(proposed_bytes)
        ):
            raise OSError("temporary policy write identity changed")
        os.close(fd)
        temp_fd = None

        failure_phase = "capture"
        latest_snapshot, latest_decoded, latest_selection = _load_policy_change_state(
            trusted_origin, selected_repository
        )
        latest_doc_sha = _actual_document_sha(latest_snapshot)
        latest_record = _current_record(latest_decoded, decision_id)
        latest_record_sha = latest_record["recordSha256"] if latest_record is not None else None
        if latest_doc_sha != before["documentSha256"] or latest_record_sha != before["recordSha256"]:
            _raise_policy_error("POLICY-PREIMAGE", "capture")
        if _selection_core(latest_selection) != _selection_core(selection):
            _raise_policy_error("POLICY-ORIGIN", "capture")
        temp_stat = temp_path.lstat()
        if (
            _is_reparse(temp_stat)
            or not stat.S_ISREG(temp_stat.st_mode)
            or temp_stat.st_nlink != 1
            or (int(temp_stat.st_dev), int(temp_stat.st_ino)) != temp_identity
            or int(temp_stat.st_size) != len(proposed_bytes)
        ):
            _raise_policy_error("POLICY-IO", "prepare")

        failure_phase = "replace"
        replace_attempted = True
        if before["documentSha256"] is None:
            # Creation is an atomic no-overwrite link.  Remove only the
            # creator-owned temporary name after the destination exists.
            os.link(temp_path, selection.policyLeafPath)
            replaced = True
            if not _cleanup_owned_temp(temp_path, temp_identity, expected_links=2):
                resources_settled = False
                failure_phase = "settlement"
                raise _ResourceUnsettledError("temporary policy link did not settle")
            temp_path = None
            temp_identity = None
        else:
            os.replace(temp_path, selection.policyLeafPath)
            replaced = True
            temp_path = None
            temp_identity = None
        failure_phase = "durability"
        _sync_policy_directory(selection)

        failure_phase = "readback"
        readback = _capture_policy_file(selection)
        if not readback.resourcesSettled:
            resources_settled = False
            raise OSError("policy readback resources did not settle")
        readback_snapshot = readback.snapshot.object()
        observed = _observed_digests(readback_snapshot, decision_id)
        if (
            readback_snapshot["status"] != "captured"
            or readback_snapshot["rawSha256"] != proposed["documentSha256"]
            or observed["recordSha256"] != proposed["recordSha256"]
        ):
            raise OSError("policy readback did not match the proposed bytes")
        return _promotion_result(
            kind="committed",
            decision_id=decision_id,
            before=before,
            proposed=proposed,
            observed=observed,
            effect="applied",
            origin=readback_snapshot["origin"],
            resources_settled=True,
            diagnostic=None,
        )
    except BaseException as exc:
        if temp_fd is not None:
            try:
                os.close(temp_fd)
                temp_fd = None
            except OSError:
                resources_settled = False
        if not replace_attempted:
            if not _cleanup_owned_temp(temp_path, temp_identity):
                resources_settled = False
                detail = _failure_detail("POLICY-IO", "settlement")
                raise PolicyError(detail, None) from exc
            if not resources_settled:
                detail = _failure_detail("POLICY-IO", "settlement")
                raise PolicyError(detail, None) from exc
            if isinstance(exc, PolicyError):
                raise
            if isinstance(exc, (KeyboardInterrupt, SystemExit, GeneratorExit)):
                raise
            code = "POLICY-IO" if failure_phase in ("prepare", "replace") else "POLICY-PREIMAGE"
            _raise_policy_error(code, failure_phase, cause=exc)

        if isinstance(exc, _ResourceUnsettledError):
            resources_settled = False
            failure_phase = "settlement"
        if not replaced and not _cleanup_owned_temp(temp_path, temp_identity):
            resources_settled = False
        if replaced and temp_path is not None and failure_phase != "settlement":
            if not _cleanup_owned_temp(temp_path, temp_identity):
                resources_settled = False
            else:
                temp_path = None

        # The replace boundary has been crossed.  Keep the actual current file
        # and report its observed state; never restore an older active policy.
        observed_value: dict[str, str | None] | None = None
        actual_origin: Mapping[str, Any] | None = original_origin
        try:
            latest = _capture_policy_file(resolve_trusted_origin())
            if latest.resourcesSettled:
                latest_object = latest.snapshot.object()
                observed_value = _observed_digests(latest_object, decision_id)
                if latest_object["origin"] is not None:
                    actual_origin = latest_object["origin"]
            else:
                resources_settled = False
        except BaseException:
            resources_settled = False
        effect = "applied" if observed_value == proposed else "unknown"
        diagnostic_phase = failure_phase if failure_phase in (
            "durability",
            "readback",
            "settlement",
            "replace",
        ) else "readback"
        diagnostic = _failure_detail("POLICY-IO", diagnostic_phase)
        outcome = _promotion_result(
            kind="recovery-required",
            decision_id=decision_id,
            before=before,
            proposed=proposed,
            observed=observed_value,
            effect=effect,
            origin=actual_origin,
            resources_settled=resources_settled,
            diagnostic=diagnostic,
        )
        raise PolicyError(diagnostic, outcome) from exc


def promote_decision(
    trusted_origin: OriginSelection,
    selected_repository: dict[str, Any],
    replacement_record: dict[str, Any],
    *,
    expected_document_sha256: str | None,
    expected_record_sha256: str | None,
    apply: bool = False,
) -> dict[str, Any]:
    """Preview or apply a Root-received active decision using current preimages.

    The caller is the authority boundary and has already received the actual
    reviewer decision. This function validates its closed record data; it does
    not authenticate role names or report labels. Root serializes all writers
    across capture, replace, and independent readback.
    """
    try:
        _snapshot_before, _decoded, _selection, proposed_bytes, result, state = _prepare_change(
            trusted_origin,
            selected_repository,
            _require_id(replacement_record.get("id") if isinstance(replacement_record, Mapping) else None),
            replacement_record,
            expected_document_sha256,
            expected_record_sha256,
            apply,
        )
    except PolicyInputError as exc:
        _raise_policy_error("POLICY-INPUT", "validate", cause=exc)
    if state in ("preview", "idempotent"):
        return result
    return _commit_policy_change(trusted_origin, selected_repository, result, proposed_bytes)


def revoke_decision(
    trusted_origin: OriginSelection,
    selected_repository: dict[str, Any],
    decision_id: str,
    reason: str,
    root_receiving_reference: str,
    *,
    expected_document_sha256: str | None,
    expected_record_sha256: str | None,
    apply: bool = False,
) -> dict[str, Any]:
    """Preview or apply a forward-only revocation through the same write owner."""
    try:
        decision_id = _require_id(decision_id, "decision-id")
        _require_text(reason, "revocation-reason")
        _require_text(root_receiving_reference, "revocation-root-reference")
        if type(apply) is not bool:
            raise PolicyInputError("apply-bool")
        if expected_document_sha256 is not None:
            _require_sha(expected_document_sha256, "expected-document-sha")
        if expected_record_sha256 is not None:
            _require_sha(expected_record_sha256, "expected-record-sha")
        snapshot, decoded, _selection = _load_policy_change_state(trusted_origin, selected_repository)
    except PolicyError:
        raise
    except PolicyInputError as exc:
        _raise_policy_error("POLICY-INPUT", "validate", cause=exc)

    current = _current_record(decoded, decision_id)
    if current is None:
        _raise_policy_error("POLICY-STATE", "validate")
    repository = _validate_repository(_thaw(selected_repository))
    if current["repository"] != repository:
        _raise_policy_error("POLICY-STATE", "validate")
    requested_revocation = {
        "reason": reason,
        "rootReceivingReference": root_receiving_reference,
    }
    if current["state"] == "revoked" and current["revocation"] == requested_revocation:
        return _idempotent_result(decision_id, snapshot, current)
    if decoded is not None and not decoded.mutation_safe:
        _raise_policy_error("POLICY-STATE", "validate")

    body = _thaw(current)
    body["revision"] = current["revision"] + 1
    body["previousRecordSha256"] = current["recordSha256"]
    body["state"] = "revoked"
    body["revocation"] = requested_revocation
    body.pop("recordSha256")
    try:
        replacement = seal_record(body)
    except PolicyInputError as exc:
        _raise_policy_error("POLICY-STATE", "prepare", cause=exc)
    try:
        _snapshot_before, _decoded_before, _selection_before, proposed_bytes, result, state = _prepare_change(
            trusted_origin,
            repository,
            decision_id,
            replacement,
            expected_document_sha256,
            expected_record_sha256,
            apply,
            required_state="revoked",
        )
    except PolicyInputError as exc:
        _raise_policy_error("POLICY-INPUT", "validate", cause=exc)
    if state in ("preview", "idempotent"):
        return result
    return _commit_policy_change(trusted_origin, repository, result, proposed_bytes)


def _capture_policy_file(selection: OriginSelection | None) -> PolicyCapture:
    if selection is None or selection.status == "unavailable":
        diagnostic = selection.diagnostic if selection is not None else "invalid-origin"
        snapshot = _snapshot("unavailable", None, None, diagnostic)
        return PolicyCapture(snapshot, None, True)
    if selection.status == "absent":
        snapshot = _snapshot("absent", None, None, "absent")
        return PolicyCapture(snapshot, None, True)
    try:
        if selection.policyLeafPath is None:
            raise PolicyInputError("policy-leaf-missing")
        if selection.linkedAuthority is not None:
            selection.linkedAuthority.assert_current()
        path = selection.policyLeafPath
        before_path = path.lstat()
    except FileNotFoundError:
        current = resolve_trusted_origin()
        if current.status != "selected" or _selection_core(current) != _selection_core(selection):
            snapshot = _snapshot("unavailable", None, None, "invalid-origin")
        else:
            snapshot = _snapshot("absent", None, None, "absent")
        return PolicyCapture(snapshot, None, True)
    except (OSError, RuntimeError, TypeError, ValueError, AttributeError):
        snapshot = _snapshot("unavailable", None, None, "invalid-origin")
        return PolicyCapture(snapshot, None, True)

    if _is_reparse(before_path) or not stat.S_ISREG(before_path.st_mode) or before_path.st_nlink != 1:
        snapshot = _snapshot("unavailable", None, None, "invalid-origin")
        return PolicyCapture(snapshot, None, True)
    if selection.linkedAuthority is not None:
        try:
            selection.linkedAuthority.ordinary_file(Path("reviewed-exceptions.json"))
        except (OSError, RuntimeError, TypeError, ValueError, AttributeError):
            snapshot = _snapshot("unavailable", None, None, "invalid-origin")
            return PolicyCapture(snapshot, None, True)

    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_CLOEXEC", 0)
    if os.name != "nt":
        nofollow = getattr(os, "O_NOFOLLOW", None)
        if nofollow is None:
            snapshot = _snapshot("unavailable", None, None, "invalid-origin")
            return PolicyCapture(snapshot, None, True)
        flags |= nofollow
    fd: int | None = None
    settled = True
    raw: bytes | None = None
    try:
        fd = os.open(path, flags)
        opened = os.fstat(fd)
        if (
            _is_reparse(opened)
            or not stat.S_ISREG(opened.st_mode)
            or opened.st_nlink != 1
            or not _same_file_generation(before_path, opened)
        ):
            raise PolicyInputError("policy-file-identity")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(fd, 65_536)
            if not chunk:
                break
            chunks.append(chunk)
        raw = b"".join(chunks)
        after_fd = os.fstat(fd)
        after_path = path.lstat()
        if (
            not _same_file_generation(opened, after_fd)
            or not _same_file_generation(opened, after_path)
            or len(raw) != opened.st_size
        ):
            raise PolicyInputError("policy-file-drift")
    except (OSError, RuntimeError, TypeError, ValueError, AttributeError):
        raw = None
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                settled = False
    if raw is None or not settled:
        snapshot = _snapshot("unavailable", None, None, "unreadable")
        return PolicyCapture(snapshot, None, settled)

    current = resolve_trusted_origin()
    if current.status != "selected" or _selection_core(current) != _selection_core(selection):
        snapshot = _snapshot("unavailable", None, None, "invalid-origin")
        return PolicyCapture(snapshot, None, settled)
    generation = _file_generation(opened)
    origin = _origin_object(selection, generation)
    snapshot = _snapshot("captured", origin, raw, "none")
    decoded = decode_document(raw)
    return PolicyCapture(snapshot, decoded, settled)


def _materialize(value: Any) -> Any:
    if isinstance(value, _IntegerToken):
        return _decimal_to_int(value.spelling)
    if isinstance(value, _FloatToken):
        raise PolicyInputError("json-float")
    if isinstance(value, _JSONObject):
        unique = value.unique_mapping()
        if unique is None:
            raise PolicyInputError("duplicate-json-key")
        return {key: _materialize(item) for key, item in unique.items()}
    if type(value) is list:
        return [_materialize(item) for item in value]
    if type(value) is str:
        if not _is_unicode_scalar_text(value):
            raise PolicyInputError("unicode-scalar")
        return value
    return value


def _recoverable_record_id(value: Any) -> str | None:
    if not isinstance(value, _JSONObject):
        return None
    present, raw = value.unique_value("id")
    if not present or type(raw) is not str or _ID_RE.fullmatch(raw) is None:
        return None
    return raw


def _invalid_document(raw: bytes, invalid_count: int = 0) -> DecodedDocument:
    return DecodedDocument(
        outer_valid=False,
        revision=None,
        records=(),
        invalid_record_count=invalid_count,
        invalid_record_ids=(),
        duplicate_ids=(),
        raw_sha256=hashlib.sha256(raw).hexdigest(),
    )


def decode_document(raw: bytes) -> DecodedDocument:
    """Decode one raw policy file; malformed records do not veto neighbors."""
    if type(raw) is not bytes or raw.startswith(b"\xef\xbb\xbf"):
        return _invalid_document(raw if type(raw) is bytes else b"")
    try:
        text = raw.decode("utf-8", errors="strict")
        parsed = json.loads(
            text,
            object_pairs_hook=_JSONObject,
            parse_int=_IntegerToken,
            parse_float=_FloatToken,
            parse_constant=_FloatToken,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, ValueError):
        return _invalid_document(raw)
    if not isinstance(parsed, _JSONObject):
        return _invalid_document(raw)
    outer = parsed.unique_mapping()
    if outer is None or set(outer) != {"schemaVersion", "revision", "decisions"}:
        return _invalid_document(raw)
    try:
        schema_version = _materialize(outer["schemaVersion"])
        revision = _materialize(outer["revision"])
    except PolicyInputError:
        return _invalid_document(raw)
    decisions = outer["decisions"]
    if schema_version != POLICY_SCHEMA_VERSION or type(schema_version) is not int:
        return _invalid_document(raw)
    if type(revision) is not int or revision < 0 or type(decisions) is not list:
        return _invalid_document(raw)
    if revision == 0 and decisions:
        return _invalid_document(raw, len(decisions))

    recoverable_ids = [_recoverable_record_id(row) for row in decisions]
    counts: dict[str, int] = {}
    for record_id in recoverable_ids:
        if record_id is not None:
            counts[record_id] = counts.get(record_id, 0) + 1
    duplicate_ids = tuple(sorted(record_id for record_id, count in counts.items() if count > 1))

    valid_records: list[dict[str, Any]] = []
    invalid_count = 0
    invalid_record_ids: list[str | None] = []
    for raw_record, record_id in zip(decisions, recoverable_ids):
        try:
            record = _materialize(raw_record)
            checked = _validate_record(record)
            if record_id is None or record_id in duplicate_ids:
                raise PolicyInputError("record-identity")
            valid_records.append(checked)
        except PolicyInputError:
            invalid_count += 1
            invalid_record_ids.append(record_id)
    valid_records.sort(key=lambda record: record["id"])
    return DecodedDocument(
        outer_valid=True,
        revision=revision,
        records=tuple(_freeze(record) for record in valid_records),
        invalid_record_count=invalid_count,
        invalid_record_ids=tuple(invalid_record_ids),
        duplicate_ids=duplicate_ids,
        raw_sha256=hashlib.sha256(raw).hexdigest(),
    )


def canonical_document(revision: int, records: Iterable[Mapping[str, Any]]) -> bytes:
    """Serialize a validated policy document as C(Document) plus one LF."""
    _require_uint(revision, "document-revision")
    rows = [_thaw(record) for record in records]
    for record in rows:
        _validate_record(record)
    ordered = sorted(rows, key=lambda row: row["id"])
    if revision == 0 and ordered:
        raise PolicyInputError("document-zero-revision")
    ids: list[str] = []
    for record in ordered:
        ids.append(record["id"])
    if ids != sorted(set(ids)):
        raise PolicyInputError("document-record-ids")
    return C({"schemaVersion": POLICY_SCHEMA_VERSION, "revision": revision, "decisions": ordered}) + b"\n"


def _record_scope(record: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        record["repository"],
        record["modes"],
        record["rangeScope"],
        record["occurrences"],
    )


def validate_record_transition(
    current: Mapping[str, Any] | None,
    replacement: Mapping[str, Any],
) -> str:
    """Check a forward-only record revision; return create/update/revoke/reactivate."""
    new = _thaw(replacement)
    _validate_record(new)
    if current is None:
        if new["revision"] != 1 or new["previousRecordSha256"] is not None or new["state"] != "active":
            raise PolicyInputError("record-create-transition")
        return "create"

    old = _thaw(current)
    _validate_record(old)
    if new["id"] != old["id"]:
        raise PolicyInputError("record-transition-id")
    if new == old:
        return "idempotent"
    if new["revision"] != old["revision"] + 1 or new["previousRecordSha256"] != old["recordSha256"]:
        raise PolicyInputError("record-transition-preimage")

    if old["state"] == "active" and new["state"] == "revoked":
        preserved = {key: value for key, value in old.items() if key not in {"revision", "previousRecordSha256", "state", "revocation", "recordSha256"}}
        changed = {key: value for key, value in new.items() if key not in {"revision", "previousRecordSha256", "state", "revocation", "recordSha256"}}
        if preserved != changed:
            raise PolicyInputError("record-revoke-mutates-grant")
        return "revoke"

    if old["state"] == "active" and new["state"] == "active":
        if _record_scope(old) == _record_scope(new) or old["authorization"] == new["authorization"]:
            raise PolicyInputError("record-update-requires-new-scope-and-receiving")
        return "update"

    if old["state"] == "revoked" and new["state"] == "active":
        old_auth = old["authorization"]
        new_auth = new["authorization"]
        if (
            old_auth["reviewArtifact"] == new_auth["reviewArtifact"]
            or old_auth["rootReceivingReference"] == new_auth["rootReceivingReference"]
        ):
            raise PolicyInputError("record-reactivation-requires-fresh-review")
        return "reactivate"

    if old["state"] == "revoked" and new["state"] == "revoked":
        preserved = {
            key: value
            for key, value in old.items()
            if key not in {"revision", "previousRecordSha256", "revocation", "recordSha256"}
        }
        changed = {
            key: value
            for key, value in new.items()
            if key not in {"revision", "previousRecordSha256", "revocation", "recordSha256"}
        }
        if preserved != changed:
            raise PolicyInputError("record-revocation-mutates-grant")
        return "revocation-update"
    raise PolicyInputError("record-transition")
