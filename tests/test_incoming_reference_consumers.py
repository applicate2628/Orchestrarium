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
    with pytest.raises(module.LifecycleError) as refused:
        module._incoming_link_result(tmp_path, {source}, REFERENCE, strict_consumer_reads=True)
    assert refused.value.failure_id == "WI-CATEGORY-MIGRATION-INVENTORY"
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
    assert module._incoming_attachment_kind(payload) is None
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
