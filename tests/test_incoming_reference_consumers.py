"""Incoming acquisition: mandatory records, opaque attachments, ordinary text, unknown."""

import hashlib
import io
import struct
import zipfile
import zlib
from pathlib import Path

import pytest

from test_mutate_work_item import load_module


REFERENCE = "bug:owned-record"
STRICT_CONFIGURATIONS = (
    ("fixed-bug", {}),
    ("supersession", {"mutable_consumers_only": True}),
    ("v0-migration", {}),
    ("successor-import", {}),
)
TOLERANT_CONFIGURATIONS = (
    ("legacy-retirement", {"mutable_consumers_only": True, "scan_markdown_links": False,
                           "literal_path_references": ("work-items/bugs/owned-record.md",)}),
    ("legacy-transition", {}),
    ("build-inventory", {}),
    ("v1-terminalization", {}),
    ("terminalized-inventory", {}),
    ("inventory-preflight", {}),
    ("verify-inventory", {}),
)
ALL_CONFIGURATIONS = tuple(
    (name, {"strict_consumer_reads": True, **options})
    for name, options in STRICT_CONFIGURATIONS
) + TOLERANT_CONFIGURATIONS


@pytest.fixture(scope="module")
def module():
    return load_module()


def chunk(kind, payload):
    return (struct.pack(">I", len(payload)) + kind + payload
            + struct.pack(">I", zlib.crc32(kind + payload)))


def png(width=3, height=2, metadata=b""):
    """Encode synthetic fixtures; no production native-validity oracle is implied."""
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    pixels = zlib.compress((b"\0" + b"\xff\x80\x12" * width) * height)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header)
            + (chunk(b"tEXt", b"note\0" + metadata) if metadata else b"")
            + chunk(b"IDAT", pixels) + chunk(b"IEND", b""))


def bitmap(width=12, height=2, depth=24, *, pixel_text=b""):
    stride = ((width * depth + 31) // 32) * 4
    pixels = pixel_text.ljust(stride * abs(height), b"\0")
    assert len(pixels) == stride * abs(height)
    header = struct.pack("<2sIHHI", b"BM", 54 + len(pixels), 0, 0, 54)
    dib = struct.pack("<IiiHHIIiiII", 40, width, height, 1, depth, 0, len(pixels), 0, 0, 0, 0)
    return header + dib + pixels


def package(*, word=True):
    stream = io.BytesIO()
    members = {
        "[Content_Types].xml": b"<Types/>",
        "_rels/.rels": b"<Relationships/>",
        ("word/document.xml" if word else "notes.txt"): REFERENCE.encode() + b"\xff",
        "docProps/core.xml": b"metadata " + REFERENCE.encode(),
        "word/_rels/document.xml.rels": b"navigation " + REFERENCE.encode(),
    }
    with zipfile.ZipFile(stream, "w") as archive:
        for name, data in members.items():
            info = zipfile.ZipInfo(name, (2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)
    return stream.getvalue()


PDF = b"%PDF-1.7\n% native navigation " + REFERENCE.encode() + b"\n%%EOF\n"
ATTACHMENTS = (
    ("png", png(metadata=REFERENCE.encode())),
    ("bitmap", bitmap(pixel_text=REFERENCE.encode())),
    ("pdf", PDF),
    ("word", package()),
)


def seed(root, relative, payload):
    source = root / "work-items" / "bugs" / "owned-record.md"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"id: owned-record\n")
    consumer = root / "work-items" / relative
    consumer.parent.mkdir(parents=True, exist_ok=True)
    consumer.write_bytes(payload)
    return source, consumer


def test_opaque_markdown_body_keeps_real_incoming_navigation(module, tmp_path):
    payload = b"\xef\xbb\xbfmultibyte \xc3\xa9 opaque \x97\r\n[\xff](../bugs/owned-record.md?rev=1#proof)\r\n\x81"
    source, consumer = seed(tmp_path, "notes/consumer.md", payload)
    for strict in (False, True):
        result = module._incoming_link_result(tmp_path, {source}, REFERENCE, strict_consumer_reads=strict)
        assert result == {"result": "unmapped", "references": [{
            "consumer": "notes/consumer.md", "kind": "physical",
            "value": "../bugs/owned-record.md?rev=1#proof",
        }]}
    assert consumer.read_bytes() == payload


@pytest.mark.parametrize("strict", (False, True))
@pytest.mark.parametrize("payload,expected", (
    (b"opaque\xff\0 prose\n" + REFERENCE.encode(), "logical-only"),
    (b"opaque\xff\0 prose only", "clear"),
    (b"[x](../bugs/\xff.md)", "semantic"),
    (b"[x](../bugs/owned-record.md#\xff)", "semantic"),
    (b"[x](../bugs/unrelated.md#\xff)", "clear"),
    (b"[x](https://example.invalid/\xff)", "clear"),
    (b"[x](../bugs/owned-record.md\0)", "semantic"),
    (REFERENCE.encode("utf-16"), "representation"),
    (REFERENCE.encode("utf-32"), "representation"),
))
def test_navigation_semantics_hold_only_the_dependent_case(module, tmp_path, strict, payload, expected):
    source, consumer = seed(tmp_path, "notes/navigation.md", payload)
    if expected in {"semantic", "representation"}:
        with pytest.raises(module.LifecycleError) as refused:
            module._incoming_link_result(tmp_path, {source}, REFERENCE, strict_consumer_reads=strict)
        assert refused.value.failure_id == "WI-CATEGORY-MIGRATION-INVENTORY"
        assert "notes/navigation.md" in str(refused.value)
        assert ("unrepresentable incoming" if expected == "semantic" else "unsupported marked") in str(refused.value)
        if expected == "semantic":
            assert "character offset" in str(refused.value)
        assert not any(0xD800 <= ord(c) <= 0xDFFF for c in str(refused.value))
    else:
        assert module._incoming_link_result(tmp_path, {source}, REFERENCE, strict_consumer_reads=strict)["result"] == expected
    assert consumer.read_bytes() == payload


@pytest.mark.parametrize("prefix,malformed", ((b"", False), (b"PREFX", False), (b"", True)))
@pytest.mark.parametrize("strict", (False, True))
def test_renamed_zip_identity_is_not_ordinary_markdown(module, tmp_path, prefix, malformed, strict):
    stream = io.BytesIO()
    content = b"\x97 [x](../bugs/owned-record.md)".ljust(49, b" ")
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr(zipfile.ZipInfo("notes.txt", (2020, 1, 1, 0, 0, 0)), content)
    raw = stream.getvalue()
    assert len(raw) == 165
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        assert archive.testzip() is None
    corrupted = raw.replace(b"../bugs/owned-record.md", b"../bugs/renamed-owned-record.md")
    with zipfile.ZipFile(io.BytesIO(corrupted)) as archive:
        assert archive.testzip() == "notes.txt"
    payload = prefix + (raw[:60] if malformed else raw)
    source, consumer = seed(tmp_path, "notes/renamed.md", payload)
    observed = module._incoming_attachment_kind(payload)
    assert observed.identity == "zip" and observed.admitted is None
    assert (observed.cause is not None) == malformed
    with pytest.raises(module.LifecycleError, match="malformed zip" if malformed else "unsupported zip"):
        module._incoming_link_result(tmp_path, {source}, REFERENCE, strict_consumer_reads=strict)
    assert consumer.read_bytes() == payload


def test_image_spans_inverse_and_conflicts(module):
    raw = b"\xef\xbb\xbf\xc3\xa9\x97\r\n[a](old) [b](long-old) [c](old)\r\n\x81"
    image = module._IncomingConsumerImage(raw)
    links = list(module._markdown_local_links(image.view))
    edits = [(link.href_start, link.href_end, new) for link, new in zip(links, ("much-longer", "x", "middle"))]
    after = image.edit([*edits, edits[0]])
    assert after == raw.replace(b"(old)", b"(much-longer)", 1).replace(b"(long-old)", b"(x)").replace(b"(old)", b"(middle)")
    inverse_image = module._IncomingConsumerImage(after)
    inverse_links = list(module._markdown_local_links(inverse_image.view))
    assert inverse_image.edit([(link.href_start, link.href_end, old.href)
                               for link, old in zip(inverse_links, links)]) == raw
    with pytest.raises(module.LifecycleError, match="conflicting"):
        image.edit([edits[0], (edits[0][0], edits[0][1], "conflict")])


@pytest.mark.parametrize("rollback", (False, True))
def test_active_document_bytes_follow_public_close_and_rollback(module, tmp_path, monkeypatch, rollback):
    from test_mutate_work_item import seed_active, write_empty_bug_dispositions, closure, tree_file_bytes
    root = tmp_path / "repo"
    instant = "2026-10-08T11:14:59Z"
    seed_active(module, root, "closing")
    seed_active(module, root, "side")
    (root / "work-items/active/side/status.md").write_bytes(b"status: active\r\n")
    target = root / "work-items/active/closing/evidence.md"
    target.write_bytes(b"Useful result\n")
    consumer = root / "work-items/active/side/design.md"
    href = b"../closing/evidence.md?rev=1#proof"
    before = b"\xef\xbb\xbf\xc3\xa9\x97\r\n[one](" + href + b") [two](" + href + b")\r\n\x81"
    consumer.write_bytes(before)
    write_empty_bug_dispositions(root, "closing", instant)
    module.refresh_readme(root)
    canonical = tree_file_bytes(root / "work-items")
    if rollback:
        def fail_after_uri_write(_root, **_kwargs):
            assert consumer.read_bytes() != before
            raise module.LifecycleError("WI-README-STALE", "synthetic failure after owned URI write")
        monkeypatch.setattr(module, "refresh_readme", fail_after_uri_write)
        with pytest.raises(module.LifecycleError, match="synthetic failure"):
            module.close_item(root, "closing", closure(instant).encode(), instant)
        assert tree_file_bytes(root / "work-items") == canonical
    else:
        archive = module.close_item(root, "closing", closure(instant).encode(), instant)
        expected = before.replace(href, b"../../archive/2026-10/closing/evidence.md?rev=1#proof")
        assert consumer.read_bytes() == expected
        assert module.resolve_category(root, "work-item:closing") == archive
        assert module.close_item(root, "closing", closure(instant).encode(), instant) == archive
        assert len(module._close_link_uri_changes(before, expected)) == 2
        with pytest.raises(module.LifecycleError, match="non-URI"):
            module._close_link_uri_changes(before, expected.replace(b"\x97", b"\x96"))


@pytest.mark.parametrize(
    "foreign_status",
    (
        b"status: active\r\n",
        b"status: blocked\r\n",
        b"status: active\r\ntemplate: staged\r\ntask: partial only\r\n",
    ),
)
def test_public_close_uses_foreign_owner_current_membership_only(
    module, tmp_path, foreign_status
):
    from test_mutate_work_item import seed_active, write_empty_bug_dispositions, closure

    root = tmp_path / "repo"
    instant = "2026-10-08T11:14:59Z"
    selected_slug, owner_slug = "closing", "other-owner"
    seed_active(module, root, selected_slug)
    seed_active(module, root, owner_slug)
    owner_status = root / "work-items/active" / owner_slug / "status.md"
    owner_status.write_bytes(foreign_status)
    evidence = root / "work-items/active" / selected_slug / "evidence.md"
    evidence.write_bytes(b"Useful result\n")
    consumer = root / "work-items/active" / owner_slug / "notes.md"
    href = b"../closing/evidence.md?rev=1#proof"
    before = b"\xef\xbb\xbf\xc3\xa9\x97\r\n[one](" + href + b") [two](" + href + b")\r\n\x81"
    consumer.write_bytes(before)
    write_empty_bug_dispositions(root, selected_slug, instant)
    module.refresh_readme(root)

    archive = module.close_item(root, selected_slug, closure(instant).encode(), instant)

    expected = before.replace(
        href, b"../../archive/2026-10/closing/evidence.md?rev=1#proof"
    )
    assert consumer.read_bytes() == expected
    assert owner_status.read_bytes() == foreign_status
    assert module.resolve_category(root, f"work-item:{selected_slug}") == archive
    assert len(module._close_link_uri_changes(before, expected)) == 2


def test_public_close_can_rewrite_the_active_owner_status_consumer(module, tmp_path):
    from test_mutate_work_item import seed_active, write_empty_bug_dispositions, closure

    root = tmp_path / "repo"
    instant = "2026-10-08T11:14:59Z"
    selected_slug, owner_slug = "closing", "different-owner"
    seed_active(module, root, selected_slug)
    seed_active(module, root, owner_slug)
    status = root / "work-items/active" / owner_slug / "status.md"
    href = b"../closing/evidence.md?rev=1#proof"
    before = b"status: blocked\r\n[reference](" + href + b")\r\n"
    status.write_bytes(before)
    (root / "work-items/active" / selected_slug / "evidence.md").write_bytes(b"Useful result\n")
    write_empty_bug_dispositions(root, selected_slug, instant)
    module.refresh_readme(root)

    module.close_item(root, selected_slug, closure(instant).encode(), instant)

    expected = before.replace(
        href, b"../../archive/2026-10/closing/evidence.md?rev=1#proof"
    )
    assert status.read_bytes() == expected
    assert b"status: blocked\r\n" in status.read_bytes()


@pytest.mark.parametrize(
    "status_bytes, expected_failure",
    (
        (None, "WI-CATEGORY-STATUS-INVALID"),
        (b"", "WI-CATEGORY-STATUS-INVALID"),
        (b"status: paused\n", "WI-CATEGORY-STATUS-INVALID"),
        (b"status: candidate\n", "WI-CATEGORY-STATUS-INVALID"),
        (b"status: completed\n", "WI-CATEGORY-TERMINAL-IN-CURRENT"),
        (b"\xff", "WI-CATEGORY-STATUS-INVALID"),
    ),
)
def test_active_owner_link_evidence_refuses_unreadable_or_noncurrent_status(
    module, tmp_path, status_bytes, expected_failure
):
    from test_mutate_work_item import seed_active

    root = tmp_path / "repo"
    owner_slug = "consumer-owner"
    seed_active(module, root, owner_slug)
    status = root / "work-items/active" / owner_slug / "status.md"
    if status_bytes is None:
        status.unlink()
    else:
        status.write_bytes(status_bytes)
    consumer = root / "work-items/active" / owner_slug / "notes.md"
    before = b"[reference](../other/evidence.md)\n"

    with pytest.raises(module.LifecycleError) as refused:
        module._close_link_active_owner_evidence(
            root, consumer, before, f"active/{owner_slug}"
        )

    assert refused.value.failure_id == expected_failure



def test_public_close_reports_owner_membership_failure_with_both_relative_paths(
    module, tmp_path
):
    from test_mutate_work_item import (
        seed_active, write_empty_bug_dispositions, closure, tree_file_bytes,
    )

    root=tmp_path/"repo"
    instant="2026-10-08T11:14:59Z"
    selected_slug, owner_slug="closing", "2026-10-19-diagnostic-owner"
    seed_active(module,root,selected_slug)
    seed_active(module,root,owner_slug)
    owner=root/"work-items/active"/owner_slug
    consumer=owner/"AUDIT.md"
    consumer.write_bytes(b"Audit evidence\n[reference](../closing/evidence.md)\n")
    (root/"work-items/active"/selected_slug/"evidence.md").write_bytes(b"Verified target\n")
    write_empty_bug_dispositions(root,selected_slug,instant)
    module.refresh_readme(root)
    status=owner/"status.md"
    status.write_bytes(b"status: paused\n")
    before=tree_file_bytes(root/"work-items")

    with pytest.raises(module.LifecycleError) as refused:
        module.close_item(root,selected_slug,closure(instant).encode(),instant)

    message=str(refused.value)
    assert refused.value.failure_id=="WI-CATEGORY-STATUS-INVALID"
    assert f"work-items/active/{owner_slug}/AUDIT.md" in message
    assert f"work-items/active/{owner_slug}/status.md" in message
    assert "rejected status 'paused'" in message
    assert "active work-item has invalid status 'paused'" in message
    assert f"work-items/active/{owner_slug}" in message
    assert str(root) not in message
    assert refused.value.args==(message,)
    assert refused.value.__cause__ is None
    assert tree_file_bytes(root/"work-items")==before


def test_active_owner_link_evidence_reports_non_utf8_with_both_relative_paths(
    module, tmp_path
):
    from test_mutate_work_item import seed_active, tree_file_bytes

    root=tmp_path/"repo"
    owner_slug="2026-10-19-diagnostic-owner"
    seed_active(module,root,owner_slug)
    owner=root/"work-items/active"/owner_slug
    status=owner/"status.md"
    consumer=owner/"AUDIT.md"
    before=b"[reference](../other/evidence.md)\n"
    consumer.write_bytes(before)
    status.write_bytes(b"\xff")
    tree_before=tree_file_bytes(root/"work-items")

    with pytest.raises(module.LifecycleError) as refused:
        module._close_link_active_owner_evidence(
            root,consumer,before,f"active/{owner_slug}"
        )

    message=str(refused.value)
    assert refused.value.failure_id=="WI-CATEGORY-STATUS-INVALID"
    assert f"work-items/active/{owner_slug}/AUDIT.md" in message
    assert f"work-items/active/{owner_slug}/status.md" in message
    assert "status must be UTF-8" in message
    assert "invalid start byte" in message
    assert str(root) not in message
    assert isinstance(refused.value.__cause__,UnicodeDecodeError)
    assert refused.value.__cause__.reason=="invalid start byte"
    assert tree_file_bytes(root/"work-items")==tree_before


def test_current_foreign_membership_does_not_admit_invalid_selected_lifecycle(
    module, tmp_path
):
    from test_mutate_work_item import (
        seed_active, write_empty_bug_dispositions, closure, tree_file_bytes,
    )

    root = tmp_path / "repo"
    instant = "2026-10-08T11:14:59Z"
    seed_active(module, root, "closing")
    seed_active(module, root, "foreign")
    selected_status = root / "work-items/active/closing/status.md"
    selected_status.write_bytes(b"status: active\n")
    foreign_status = root / "work-items/active/foreign/status.md"
    foreign_status.write_bytes(b"status: blocked\n")
    (root / "work-items/active/closing/evidence.md").write_bytes(b"Useful result\n")
    consumer = root / "work-items/active/foreign/notes.md"
    consumer.write_bytes(b"[reference](../closing/evidence.md)\n")
    write_empty_bug_dispositions(root, "closing", instant)
    module.refresh_readme(root)
    before = tree_file_bytes(root / "work-items")

    with pytest.raises(module.LifecycleError):
        module.close_item(root, "closing", closure(instant).encode(), instant)

    assert tree_file_bytes(root / "work-items") == before
    assert foreign_status.read_bytes() == b"status: blocked\n"


@pytest.mark.parametrize("payload", (
    pytest.param(b"\x00\xffordinary binary input\x00", id="binary"),
    pytest.param(
        b"work-item:a-close-target\n[target](../status.md#source)\n"
        b"work-items/active/a-close-target/status.md\n",
        id="utf8-incidental-references",
    ),
    pytest.param(b"", id="empty"),
))
def test_owned_input_data_has_no_incoming_reference_authority(module, tmp_path, payload):
    item = tmp_path / "work-items" / "active" / "a-close-target"
    source = item / "status.md"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"status: active\n")
    consumer = item / "inputs" / "source.dat"
    consumer.parent.mkdir()
    consumer.write_bytes(payload)
    before = consumer.read_bytes()

    assert module._incoming_link_result(
        tmp_path,
        {source},
        "work-item:a-close-target",
        literal_path_references=("work-items/active/a-close-target/status.md",),
        strict_consumer_reads=True,
    ) == {"result": "clear", "references": []}
    assert consumer.read_bytes() == before


@pytest.mark.parametrize("name,options", ALL_CONFIGURATIONS)
@pytest.mark.parametrize("kind,payload", ATTACHMENTS)
@pytest.mark.parametrize("relative", ("active/other/nested/renamed.asset", "archive/2026-01/old/renamed.bin"))
def test_native_attachment_channels_are_opaque(module, tmp_path, name, options, kind, payload, relative):
    """Break caught: native metadata/UTF-8 payloads are scanned or rejected as lifecycle text."""
    source, consumer = seed(tmp_path, relative, payload)
    before = hashlib.sha256(consumer.read_bytes()).hexdigest()
    for _ in range(2):
        assert module._incoming_link_result(tmp_path, {source}, REFERENCE, **options) == {
            "result": "clear", "references": [],
        }
    assert hashlib.sha256(consumer.read_bytes()).hexdigest() == before


@pytest.mark.parametrize("name,options", ALL_CONFIGURATIONS)
@pytest.mark.parametrize("suffix", (".bin", ".png", ".bmp", ".pdf", ".docx"))
def test_attachment_looking_names_do_not_hide_utf8_records(module, tmp_path, name, options, suffix):
    """Break caught: filename dispatch drops ordinary text or changes extraction/order."""
    payload = (b"BM ordinary text " + REFERENCE.encode()
               + b"\n[link](../../bugs/owned-record.md?mode=1#proof)\nwork-items/bugs/owned-record.md\n")
    source, consumer = seed(tmp_path, "active/other/notes" + suffix, payload)
    physical = ("work-items/bugs/owned-record.md" if name == "legacy-retirement"
                else "../../bugs/owned-record.md?mode=1#proof")
    assert module._incoming_link_result(tmp_path, {source}, REFERENCE, **options) == {
        "result": "unmapped", "references": [
            {"consumer": "active/other/notes" + suffix, "kind": "logical", "value": REFERENCE},
            {"consumer": "active/other/notes" + suffix, "kind": "physical", "value": physical},
        ],
    }
    assert consumer.read_bytes() == payload


@pytest.mark.parametrize("name,options", ALL_CONFIGURATIONS)
def test_exclusions_precede_acquisition_and_archive_filter_remains(module, tmp_path, monkeypatch, name, options):
    """Break caught: owned/derived/history exclusions move after acquisition."""
    source, _ = seed(tmp_path, "active/other/notes.txt", REFERENCE.encode())
    excluded = [source, tmp_path / "work-items" / "README.md", tmp_path / "work-items" / "index.md"]
    historical = tmp_path / "work-items" / "archive" / "2026-01" / "old.bin"
    historical.parent.mkdir(parents=True)
    historical.write_bytes(REFERENCE.encode())
    for path in excluded[1:]:
        path.write_bytes(b"\xff")
    if options.get("mutable_consumers_only"):
        excluded.append(historical)
    read_bytes = Path.read_bytes

    def checked_read(path):
        if path in excluded:
            raise AssertionError("excluded consumer reached acquisition")
        return read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", checked_read)
    references = [{"consumer": "active/other/notes.txt", "kind": "logical", "value": REFERENCE}]
    if not options.get("mutable_consumers_only"):
        references.append({"consumer": "archive/2026-01/old.bin", "kind": "logical", "value": REFERENCE})
    assert module._incoming_link_result(tmp_path, {source}, REFERENCE, **options) == {
        "result": "logical-only", "references": references,
    }


@pytest.mark.parametrize("name,options", ALL_CONFIGURATIONS)
@pytest.mark.parametrize("payload", (REFERENCE.encode("utf-16"), b"\xffunknown", package(word=False)))
def test_unclassified_inputs_keep_strict_and_tolerant_policy(module, tmp_path, name, options, payload):
    """Break caught: unknown encoding/generic ZIP becomes an attachment by name or decode failure."""
    source, consumer = seed(tmp_path, "active/other/unknown.doc", payload)
    if options.get("strict_consumer_reads"):
        with pytest.raises(module.LifecycleError) as refused:
            module._incoming_link_result(tmp_path, {source}, REFERENCE, **options)
        assert refused.value.failure_id == "WI-CATEGORY-MIGRATION-INVENTORY"
        assert isinstance(refused.value.__cause__, UnicodeDecodeError)
    else:
        assert module._incoming_link_result(tmp_path, {source}, REFERENCE, **options) == {
            "result": "clear", "references": [],
        }
    assert consumer.read_bytes() == payload


@pytest.mark.parametrize("name,options", ALL_CONFIGURATIONS)
def test_read_errors_preserve_failure_cause_and_tolerant_policy(module, tmp_path, monkeypatch, name, options):
    """Break caught: attachment identity accidentally bypasses a failed acquisition."""
    source, consumer = seed(tmp_path, "active/other/unreadable.pdf", PDF)
    original_read = Path.read_bytes
    error = PermissionError("synthetic denied read")

    def denied_read(path):
        if path == consumer:
            raise error
        return original_read(path)

    monkeypatch.setattr(Path, "read_bytes", denied_read)
    if options.get("strict_consumer_reads"):
        with pytest.raises(module.LifecycleError) as refused:
            module._incoming_link_result(tmp_path, {source}, REFERENCE, **options)
        assert refused.value.failure_id == "WI-CATEGORY-MIGRATION-INVENTORY"
        assert refused.value.__cause__ is error
    else:
        assert module._incoming_link_result(tmp_path, {source}, REFERENCE, **options) == {
            "result": "clear", "references": [],
        }


@pytest.mark.parametrize("suffix", (".md", ".MD", ".json", ".jsonl"))
@pytest.mark.parametrize("payload", (png(metadata=REFERENCE.encode()), package(), b"\xff" + REFERENCE.encode()))
def test_mandatory_record_codec_beats_native_signature(module, tmp_path, suffix, payload):
    """Break caught: native signature suppresses a mandatory record's codec failure."""
    source, consumer = seed(tmp_path, "active/other/record" + suffix, payload)
    if suffix.lower() == ".md" and payload == b"\xff" + REFERENCE.encode():
        assert module._incoming_link_result(tmp_path, {source}, REFERENCE, strict_consumer_reads=True) == {
            "result": "logical-only", "references": [{
                "consumer": "active/other/record" + suffix, "kind": "logical", "value": REFERENCE,
            }],
        }
        return
    with pytest.raises(module.LifecycleError) as refused:
        module._incoming_link_result(tmp_path, {source}, REFERENCE, strict_consumer_reads=True)
    assert refused.value.failure_id == "WI-CATEGORY-MIGRATION-INVENTORY"
    if suffix.lower() == ".md":
        assert "unsupported" in str(refused.value)
    else:
        assert isinstance(refused.value.__cause__, UnicodeDecodeError)
    assert consumer.read_bytes() == payload


@pytest.mark.parametrize("suffix", (".md", ".json", ".jsonl"))
def test_utf8_mandatory_records_scan_even_native_looking_bytes(module, tmp_path, suffix):
    """Break caught: record precedence is applied only after attachment classification."""
    source, _ = seed(tmp_path, "active/other/record" + suffix, PDF)
    assert module._incoming_link_result(tmp_path, {source}, REFERENCE, strict_consumer_reads=True) == {
        "result": "logical-only", "references": [
            {"consumer": "active/other/record" + suffix, "kind": "logical", "value": REFERENCE},
        ],
    }


@pytest.mark.parametrize("payload", (png(), b"{", b"{}"))
def test_disposition_manifest_decode_syntax_schema_stay_strict(module, tmp_path, payload):
    """Break caught: inventory scope changes mandatory disposition validation."""
    item = tmp_path / "work-items" / "active" / "owner"
    item.mkdir(parents=True)
    manifest = item / "bug-dispositions.json"
    manifest.write_bytes(payload)
    with pytest.raises(module.LifecycleError) as refused:
        module._load_bug_disposition_manifest(item, "owner", "2026-01-01T00:00:00Z")
    assert refused.value.failure_id == "WI-BUG-DISPOSITIONS-INVALID"
    assert manifest.read_bytes() == payload


@pytest.mark.parametrize("payload", (
    png(7, 4, REFERENCE.encode()) + b"native metadata " + REFERENCE.encode(),
    bitmap(5, -3, 32),
    b"%PDF-2.0\n" + REFERENCE.encode() + b"\n",
    package(),
))
def test_attachment_variants_do_not_require_native_validity_or_projection(module, tmp_path, monkeypatch, payload):
    """Break caught: geometry/content validation or native XML extraction is reinstated."""
    source, consumer = seed(tmp_path, "active/new/nested/different.data", payload)

    def no_native_open(*args, **kwargs):
        raise AssertionError("native content extraction is outside inventory scope")

    monkeypatch.setattr(zipfile.ZipFile, "open", no_native_open)
    assert module._incoming_link_result(tmp_path, {source}, REFERENCE, strict_consumer_reads=True) == {
        "result": "clear", "references": [],
    }
    assert consumer.read_bytes() == payload


def test_opaque_assets_do_not_authorize_immutable_text_rewrites(module, tmp_path):
    """Break caught: an attachment exception suppresses an immutable TEXT reference."""
    source, image = seed(tmp_path, "active/other/image.bin", png(metadata=REFERENCE.encode()))
    historical = tmp_path / "work-items" / "archive" / "2026-01" / "old" / "notes.md"
    historical.parent.mkdir(parents=True)
    historical.write_bytes(b"[old](../../../bugs/owned-record.md?mode=1#proof)\n")
    before = (source.read_bytes(), historical.read_bytes(), image.read_bytes())
    archive = tmp_path / "work-items" / "bugs" / "archive" / "2026-01" / source.name
    with pytest.raises(module.LifecycleError) as refused:
        module._fixed_bug_link_plans(tmp_path, source, archive, "owned-record")
    assert refused.value.failure_id == "WI-FIXED-BUG-LINK-INVENTORY"
    assert (source.read_bytes(), historical.read_bytes(), image.read_bytes()) == before
    assert not archive.exists()


@pytest.mark.parametrize("name,options", ALL_CONFIGURATIONS)
def test_unsupported_container_identity_keeps_acquisition_policy(module, tmp_path, name, options):
    """Break caught: expected unsupported-container errors escape kind/reader policies."""
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        info = zipfile.ZipInfo("notes.txt", (2020, 1, 1, 0, 0, 0))
        archive.writestr(info, b"unknown carrier\xff")
    data = bytearray(stream.getvalue())
    central = data.index(b"PK\x01\x02")
    data[central + 6:central + 8] = (64).to_bytes(2, "little")
    payload = bytes(data)
    source, consumer = seed(tmp_path, "active/other/unsupported.bin", payload)
    assert module._incoming_attachment_kind(payload).admitted is None
    if options.get("strict_consumer_reads"):
        with pytest.raises(module.LifecycleError) as refused:
            module._incoming_link_result(tmp_path, {source}, REFERENCE, **options)
        assert refused.value.failure_id == "WI-CATEGORY-MIGRATION-INVENTORY"
        assert isinstance(refused.value.__cause__, UnicodeDecodeError)
    else:
        assert module._incoming_link_result(tmp_path, {source}, REFERENCE, **options) == {
            "result": "clear", "references": [],
        }
    assert consumer.read_bytes() == payload


@pytest.mark.parametrize("opaque", (False, True))
def test_archive_composes_selected_literal_inside_href_suffix(module, tmp_path, opaque):
    source = tmp_path / "work-items/backlog/old-item.md"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"original task\n")
    consumer = tmp_path / "work-items/notes/consumer.md"
    consumer.parent.mkdir()
    href = "../backlog/old-item.md#work-items/backlog/old-item.md"
    before = (b"\x97\r\n" if opaque else b"prose\r\n") + f"[link]({href})".encode()
    consumer.write_bytes(before)
    archive = tmp_path / "work-items/archive/2026-10/old-item.md"
    rows = [{"consumer": "notes/consumer.md", "kind": "physical", "value": value}
            for value in (href, "work-items/backlog/old-item.md")]
    plans = module._physical_archive_link_plans(
        tmp_path, source, archive, rows, failure_id="WI-LEGACY-COMPLETION-LINKS")
    assert plans[0]["before"] == before
    assert plans[0]["after"] == before.replace(b"backlog/old-item.md", b"archive/2026-10/old-item.md")
    assert consumer.read_bytes() == before


@pytest.mark.parametrize("include_bare", (False, True))
@pytest.mark.parametrize("suffix", ("", "?rev=4#backlog/old-item.md"))
def test_archive_projects_href_base_before_selected_literal(module, tmp_path, include_bare, suffix):
    work_items = tmp_path / "work-items"
    source = work_items / "backlog/old-item.md"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"original task\n")
    consumer = work_items / "ordinary-consumer.MD"
    consumer.parent.mkdir(parents=True, exist_ok=True)
    literal = source.relative_to(work_items).as_posix()
    href = literal + suffix
    before = b"\xef\xbb\xbfResults\r\n\r\n" + f"[proof]({href})\r\n".encode()
    if include_bare:
        before += f"Independent literal: `{literal}`\r\n".encode()
    consumer.write_bytes(before)

    inventory = module._incoming_link_result(
        tmp_path, {source}, "work-item:old-item", strict_consumer_reads=True,
        literal_path_references=(literal,),
    )
    self_rows = inventory["references"]
    assert inventory["result"] == "unmapped"
    assert self_rows == [
        {"consumer": "ordinary-consumer.MD", "kind": "physical", "value": value}
        for value in sorted({literal, href})
    ]
    archive = work_items / "archive/2026-10/old-item/legacy-source/old-item.md"
    plans = module._physical_archive_link_plans(
        tmp_path, source, archive, self_rows, failure_id="WI-LEGACY-COMPLETION-LINKS",
    )
    retained_target = archive.relative_to(tmp_path).as_posix()
    expected_suffix = suffix.replace(literal, retained_target)
    expected_href = archive.relative_to(work_items).as_posix() + expected_suffix
    expected = before.replace(f"[proof]({href})".encode(), f"[proof]({expected_href})".encode())
    if include_bare:
        expected = expected.replace(
            f"`{literal}`".encode(), f"`{retained_target}`".encode(),
        )
    assert plans[0]["before"] == before
    assert plans[0]["after"] == expected
    assert consumer.read_bytes() == before


def test_projection_obligations_keep_bare_separate_when_href_spelling_matches(module):
    before = b"[proof](old.md)\nIndependent literal: `old.md`\n"
    image = module._IncomingConsumerImage(before, ".md")
    link = next(iter(module._markdown_local_links(image.view)))
    pattern = module._incoming_literal_pattern("old.md")
    projected, hrefs, obligations = module._project_incoming_consumer_image(
        image, ".md", [(link.href_start, link.href_end, "new.md")],
        [(pattern, "new.md")],
    )
    self_check = module._IncomingConsumerImage(projected, ".md")
    assert projected == b"[proof](new.md)\nIndependent literal: `new.md`\n"
    assert hrefs == ("new.md",)
    assert {row[1] for row in obligations} == {"consumed-href-base", "bare"}
    assert all(module._incoming_projection_obligation_present(self_check.view, row)
               for row in obligations)

    missing_bare = module._IncomingConsumerImage(b"[proof](new.md)\n", ".md")
    bare = next(row for row in obligations if row[1] == "bare")
    consumed = next(row for row in obligations if row[1] == "consumed-href-base")
    assert module._incoming_literal_pattern("new.md").search(missing_bare.view)
    assert module._incoming_projection_obligation_present(missing_bare.view, consumed)
    assert not module._incoming_projection_obligation_present(missing_bare.view, bare)


@pytest.mark.parametrize("opaque", (False, True))
def test_successor_composes_selected_logical_inside_href_suffix(module, tmp_path, monkeypatch, opaque):
    work_items = tmp_path / "work-items"
    source = work_items / "active/old-item"
    source.mkdir(parents=True)
    consumer = work_items / "notes/consumer.md"
    consumer.parent.mkdir()
    href = "../active/old-item/status.md#work-item:old-item"
    before = (b"\x97\r\n" if opaque else b"prose\r\n") + f"[link]({href})".encode()
    consumer.write_bytes(before)
    supplied = [
        {"consumer": "notes/consumer.md", "kind": "physical", "value": href,
         "target": "work-items/active/new-item/status.md"},
        {"consumer": "notes/consumer.md", "kind": "logical", "value": "work-item:old-item",
         "meaning": "current-successor"},
    ]
    observed = [{key: row[key] for key in ("consumer", "kind", "value")} for row in supplied]
    monkeypatch.setattr(module, "_incoming_link_result", lambda *args, **kwargs: {"references": observed})
    plans = module._successor_import_links(tmp_path, work_items, source, "new-item", [], {"references": supplied})
    after = module._unb64(plans[0]["afterBase64"])
    assert after == before.replace(b"old-item", b"new-item")
    assert plans[0]["references"] == sorted(supplied, key=lambda row: (row["kind"], row["value"]))
    assert consumer.read_bytes() == before


def test_bug_successor_keeps_full_href_then_global_literal_policy(module, tmp_path):
    source, consumer = seed(tmp_path, "notes/consumer.md", b"unused")
    before = b"\x97 [x](../bugs/owned-record.md#bug:owned-record) bug:owned-record\r\n"
    assert module._bug_successor_link_after(
        consumer, source, before, REFERENCE, "bug:successor") == b"\x97 [x](bug:successor) bug:successor\r\n"


@pytest.mark.parametrize("unselected", (b"plain", b"opaque\x97", b"nul\0"))
def test_v1_exact_tuple_ignores_unselected_label_semantics(module, tmp_path, unselected):
    source = tmp_path / "work-items/bugs/owned-record.md"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"target bytes\n")
    target = tmp_path / "work-items/bugs/archive/2026-10/owned-record.md"
    consumer = tmp_path / "work-items/bugs/archive/2026-01/consumer.md"
    consumer.parent.mkdir(parents=True)
    href = "../../../bugs/owned-record.md"
    before = b"[selected](" + href.encode() + b") [" + unselected + b"](" + href.encode() + b")\r\n"
    consumer.write_bytes(before)
    admission = {"source": "bugs/archive/2026-01/consumer.md", "label": "selected", "href": href,
                 "expectedIdentity": REFERENCE, "sourceSha256": hashlib.sha256(before).hexdigest(),
                 "targetSha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                 "receipt": ".scratch/physical-receipt.json"}
    planned = {"source": source, "target": target, "reference": REFERENCE,
               "targetRelative": target.relative_to(tmp_path / "work-items").as_posix(),
               "beforeSha256": admission["targetSha256"], "afterSha256": admission["targetSha256"], "incomingLinks": {
                   "result": "physical-relocation", "references": [{"consumer": admission["source"],
                       "kind": "physical", "value": href}], "physicalRelocation": admission}}
    instant = "2026-10-19T10:00:00Z"
    receipt = tmp_path / ".scratch/physical-receipt.json"
    pending = module._expected_physical_relocation_receipt(
        tmp_path, REFERENCE, admission, source, target, admission["targetSha256"], instant, settled=False)
    plans, links = module._plan_v1_link_relocations(tmp_path, [planned], instant, receipt)
    new_href = "../2026-10/owned-record.md"
    expected = before.replace(href.encode(), new_href.encode(), 1)
    assert plans[0]["after"] == expected
    assert links[0] == pending
    target.parent.mkdir(parents=True)
    target.write_bytes(source.read_bytes())
    consumer.write_bytes(expected)
    settled = module._expected_physical_relocation_receipt(
        tmp_path, REFERENCE, admission, source, target, admission["targetSha256"], instant, settled=True)
    assert settled["sourceBeforeSha256"] == admission["sourceSha256"]
    assert settled["sourceAfterSha256"] == hashlib.sha256(expected).hexdigest()
    if unselected == b"plain":
        for label, raw, reason in (
            ("missing", before, "missing or duplicated"),
            ("selected", before + b"[selected](" + href.encode() + b")", "missing or duplicated"),
            ("selected\0", before.replace(b"[selected]", b"[selected\0]"), "selected label at character offset"),
        ):
            consumer.write_bytes(raw)
            invalid = {**admission, "label": label, "sourceSha256": hashlib.sha256(raw).hexdigest()}
            incoming = {**planned["incomingLinks"], "physicalRelocation": invalid}
            for invoke in (
                lambda: module._expected_physical_relocation_receipt(
                    tmp_path, REFERENCE, invalid, source, target, admission["targetSha256"], instant, settled=False),
                lambda: module._plan_v1_link_relocations(tmp_path, [{**planned, "incomingLinks": incoming}], instant, receipt),
            ):
                with pytest.raises(module.LifecycleError) as refused:
                    invoke()
                assert refused.value.failure_id == "WI-CATEGORY-TERMINAL-EVIDENCE-MISSING"
                assert reason in str(refused.value)
            assert consumer.read_bytes() == raw


@pytest.mark.parametrize("relative,strict_metadata,marked", (
    ("bugs/unrelated.md", True, False), ("active/side/status.md", True, False),
    ("active/side/design.md", False, False), ("active/side/nested/status.md", False, False),
    ("active/side/design.md", False, True),
))
def test_uri_intent_representation_follows_consumer_role(module, tmp_path, relative, strict_metadata, marked):
    import json
    (tmp_path / "work-items").mkdir()
    source = "active/closing"
    archive = "archive/2026-10/closing"
    consumer = tmp_path / "work-items" / relative
    old = module._relative_link(consumer.parent, tmp_path / "work-items" / source / "evidence.md")
    new = module._relative_link(consumer.parent, tmp_path / "work-items" / archive / "evidence.md")
    before = b"opaque \x97\n[x](" + old.encode() + b")\n"
    after = before.replace(old.encode(), new.encode())
    if marked:
        before, after = (f"[x]({href})\n".encode("utf-16") for href in (old, new))
    hashes = {"beforeSha256": hashlib.sha256(before).hexdigest(), "afterSha256": hashlib.sha256(after).hexdigest()}
    maintenance = {"version": 1, "source": source, "target": archive, "allowProtectedUriUpdates": False,
        "consumers": [{"source": relative, "target": relative, **hashes, "authority": "current-metadata",
                       "uriChanges": [{"from": old, "to": new}]}]}
    intent = {"slug": "closing", "terminalInstant": "2026-10-19T10:00:00Z", "bugs": [],
        "activePath": "work-items/" + source, "archivePath": "work-items/" + archive,
        "statusBefore": module._b64(b"status before"), "statusAfter": module._b64(b"status after"),
        "closureBefore": None, "closureAfter": module._b64(b"closure"),
        "bugReceiptAfter": module._b64(json.dumps({"bugs": [], "linkMaintenance": maintenance}).encode()),
        "uriConsumers": {"version": 1, "allowProtectedUriUpdates": False, "rows": [{
            "source": "work-items/" + relative, "target": "work-items/" + relative,
            "before": module._b64(before), "after": module._b64(after), **hashes}]},
        "uriTargetBindings": {"version": 1, "rows": [{"source": "work-items/" + source + "/evidence.md",
            "target": "work-items/" + archive + "/evidence.md", "kind": "file",
            "beforeSha256": "a" * 64, "afterSha256": "a" * 64}]}}
    if strict_metadata or marked:
        with pytest.raises(module.LifecycleError) as refused:
            module._transition_parent_uri_images(tmp_path, intent)
        assert refused.value.failure_id == "WI-LIFECYCLE-TRANSITION-INTENT-INVALID"
        assert relative in str(refused.value)
        assert ("unsupported marked" if marked else "metadata is not strict UTF-8") in str(refused.value)
    else:
        images = module._transition_parent_uri_images(tmp_path, intent)
        assert images == [{"path": consumer, "target": consumer, "before": before, "after": after}]


def test_successor_scan_error_keeps_owner_and_visible_safe_cause(module, tmp_path, monkeypatch):
    def refuse(*args, **kwargs):
        raise module.LifecycleError("WI-CATEGORY-MIGRATION-INVENTORY",
            "incoming consumer notes/consumer.md: unrepresentable incoming local target at character offset 8")
    monkeypatch.setattr(module, "_incoming_link_result", refuse)
    with pytest.raises(module.LifecycleError) as refused:
        module._successor_import_links(tmp_path, tmp_path / "work-items", tmp_path / "work-items/active/old", "new", [], {})
    assert refused.value.failure_id == "WI-SUCCESSOR-LINK-UNMAPPED"
    assert "notes/consumer.md" in str(refused.value) and "local target at character offset 8" in str(refused.value)
    assert refused.value.__cause__.failure_id == "WI-CATEGORY-MIGRATION-INVENTORY"
    assert module._project_current_bug_supersession_cli_failure(refused.value) == (
        "WI-SUCCESSOR-LINK-UNMAPPED: current bug supersession rejected")


def test_direct_image_failure_owners_keep_safe_representation_cause(module, tmp_path):
    source, consumer = seed(tmp_path, "active/side/design.md", REFERENCE.encode("utf-16"))
    raw = consumer.read_bytes()
    operations = [
        ("WI-CATEGORY-MIGRATION-INVENTORY", lambda: module._bug_successor_link_after(
            consumer, source, raw, REFERENCE, "bug:successor")),
        ("WI-CLOSE-LINK-INVENTORY", lambda: module._physical_archive_link_plans(
            tmp_path, source, tmp_path / "work-items/bugs/archive/2026-10/owned-record.md",
            [{"consumer": "active/side/design.md", "kind": "physical", "value": "../../bugs/owned-record.md"}],
            failure_id="WI-CLOSE-LINK-INVENTORY")),
        ("WI-CLOSE-LINK-AUTHORITY", lambda: module._close_link_authority(tmp_path, consumer, raw, None, False, 1)),
        ("WI-CLOSE-LINK-VERIFY", lambda: module._close_link_uri_changes(raw, raw)),
    ]
    for owner, invoke in operations:
        with pytest.raises(module.LifecycleError) as refused:
            invoke()
        assert refused.value.failure_id == owner
        assert "unsupported marked" in str(refused.value) and "utf16-le BOM" in str(refused.value)
        assert not any(0xD800 <= ord(c) <= 0xDFFF for c in str(refused.value))
        assert refused.value.__cause__ is not None
    assert consumer.read_bytes() == raw


def test_public_fixed_bug_failure_keeps_inventory_id_cause_and_bytes(module, tmp_path, capsys):
    from test_mutate_work_item import seed_fixed_bug_with_active_parent, tree_file_bytes
    root = tmp_path / "repo"
    slug = "diagnostic-owned"
    seed_fixed_bug_with_active_parent(module, root, slug)
    consumer = root / "work-items/active/fixed-bug-parent/design.md"
    consumer.write_bytes(b"[selected](../../bugs/\xff.md)\r\n")
    before = tree_file_bytes(root / "work-items")
    result = module.main(["archive-fixed-bug", "--root", str(root), "--slug", slug,
        "--terminal-instant", "2026-10-19T10:00:00Z", "--resolution", "Accepted synthetic fix.",
        "--evidence", "Synthetic current proof.", "--apply"])
    output = capsys.readouterr()
    assert result == 1
    assert "WI-CATEGORY-MIGRATION-INVENTORY:" in output.out
    assert "active/fixed-bug-parent/design.md" in output.out
    assert "unrepresentable incoming local target at character offset" in output.out
    assert "Traceback" not in output.out + output.err
    assert not any(0xD800 <= ord(c) <= 0xDFFF for c in output.out + output.err)
    assert tree_file_bytes(root / "work-items") == before
