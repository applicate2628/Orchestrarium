// A test driver; this is not a scanner transport or release executable.
#[path = "../src/publication/tree_record.rs"]
mod tree_record;
#[path = "../src/publication/tree_walk.rs"]
mod tree_walk;
use orche_native_operations::{FrameError, Limits, ObjectKind, read_frame};
use orche_native_operations::{ObjectFormat, VerifiedReadError, read_verified_object};
use std::{
    cell::{Cell, RefCell},
    collections::{HashMap, HashSet},
    io::{self, BufRead, Write},
};
use tree_record::{ObjectWidth, TreeRecordError, VerifiedTreePayload};
use tree_walk::{Entry, Event, Kind, Selection, WalkError, walk};

fn unhex(input: &str) -> Vec<u8> {
    let (pairs, remainder) = input.as_bytes().as_chunks::<2>();
    assert!(remainder.is_empty());
    pairs
        .iter()
        .map(|pair| u8::from_str_radix(std::str::from_utf8(pair).unwrap(), 16).unwrap())
        .collect()
}

fn hex(input: &[u8]) -> String {
    const DIGITS: &[u8] = b"0123456789abcdef";
    let mut out = String::with_capacity(input.len() * 2);
    for b in input {
        out.push(DIGITS[(b >> 4) as usize] as char);
        out.push(DIGITS[(b & 15) as usize] as char);
    }
    out
}

fn object_width(width: usize) -> ObjectWidth {
    match width {
        20 => ObjectWidth::Sha1,
        32 => ObjectWidth::Sha256,
        _ => panic!("unsupported fixture width"),
    }
}

fn record_reason(err: TreeRecordError) -> &'static str {
    match err {
        TreeRecordError::Tree => "tree",
        TreeRecordError::TreePath => "tree-path",
        TreeRecordError::TreeMode => "tree-mode",
    }
}

fn run_records() {
    let stdout = io::stdout();
    let mut out = io::BufWriter::new(stdout.lock());
    for line in io::stdin().lock().lines() {
        let line = line.unwrap();
        let (width, body) = line.split_once(' ').unwrap();
        let width = object_width(width.parse().unwrap());
        let raw = if body == "-" { Vec::new() } else { unhex(body) };
        match VerifiedTreePayload::from_verified_bytes(&raw, width).parse() {
            Ok(entries) => {
                for entry in entries {
                    let payload = raw.as_ptr_range();
                    for bytes in [entry.name, entry.oid, entry.mode] {
                        let field = bytes.as_ptr_range();
                        assert!(payload.start <= field.start && field.end <= payload.end);
                    }
                    let kind = match entry.kind {
                        Kind::Blob => "blob",
                        Kind::Tree => "tree",
                        Kind::Gitlink => "gitlink",
                    };
                    writeln!(
                        out,
                        "E {} {} {} {}",
                        kind,
                        std::str::from_utf8(entry.mode).unwrap(),
                        hex(entry.name),
                        hex(entry.oid)
                    )
                    .unwrap();
                }
                writeln!(out, "R ok").unwrap();
            }
            Err(err) => {
                let reason = record_reason(err);
                writeln!(out, "R PS-MSG-FRAME {reason}").unwrap();
            }
        }
    }
    out.flush().unwrap();
}

fn kind_name(kind: ObjectKind) -> &'static str {
    match kind {
        ObjectKind::Commit => "commit",
        ObjectKind::Tree => "tree",
        ObjectKind::Blob => "blob",
        ObjectKind::Tag => "tag",
    }
}

fn frame_error(err: FrameError) -> String {
    let (code, reason) = match err {
        FrameError::Missing => ("READ", "missing"),
        FrameError::Header => ("FRAME", "header"),
        FrameError::Identity => ("FRAME", "identity"),
        FrameError::Type => ("FRAME", "type"),
        FrameError::Length => ("FRAME", "length"),
        FrameError::HeaderDelimiter => ("FRAME", "header-delimiter"),
        FrameError::RecordDelimiter => ("FRAME", "record-delimiter"),
        FrameError::ShortRead => ("READ", "short-read"),
        FrameError::Pipe => ("READ", "pipe"),
        FrameError::TooLarge(kind) => {
            return format!("PS-MSG-LIMIT {}-bytes", kind_name(kind));
        }
    };
    format!("PS-MSG-{code} {reason}")
}

fn run_frames() {
    let stdout = io::stdout();
    let mut out = io::BufWriter::new(stdout.lock());
    for line in io::stdin().lock().lines() {
        let line = line.unwrap();
        let fields: Vec<_> = line.split_ascii_whitespace().collect();
        let kind = match fields[1] {
            "-" => None,
            "blob" => Some(ObjectKind::Blob),
            "tree" => Some(ObjectKind::Tree),
            _ => panic!("invalid fixture type"),
        };
        let wire = if fields[5] == "-" {
            Vec::new()
        } else {
            unhex(fields[5])
        };
        let mut input = io::BufReader::with_capacity(fields[2].parse().unwrap(), wire.as_slice());
        let limits = Limits {
            decimal_digits: fields[4].parse().unwrap(),
            ..Limits::default()
        };
        for _ in 0..fields[3].parse::<usize>().unwrap() {
            match read_frame(&mut input, fields[0].as_bytes(), kind, &limits) {
                Ok(frame) => {
                    let payload = if frame.payload.is_empty() {
                        "-".into()
                    } else {
                        hex(&frame.payload)
                    };
                    writeln!(out, "F {} {}", kind_name(frame.kind), payload).unwrap();
                }
                Err(err) => {
                    writeln!(out, "R {}", frame_error(err)).unwrap();
                    break;
                }
            }
        }
    }
    out.flush().unwrap();
}

fn main() {
    if std::env::args().nth(1).as_deref() == Some("--frames") {
        run_frames();
        return;
    }
    if std::env::args().nth(1).as_deref() == Some("--records") {
        run_records();
        return;
    }

    let stdin = io::stdin();
    let lines: Vec<Vec<String>> = stdin
        .lock()
        .lines()
        .map(|r| {
            r.unwrap()
                .split_ascii_whitespace()
                .map(str::to_owned)
                .collect()
        })
        .collect();
    let header = &lines[0];
    let root = unhex(&header[0]);
    let max_bytes = header[1].parse().unwrap();
    let max_frontier: usize = header[2].parse().unwrap();
    let expire_step: usize = header[3].parse().unwrap();
    let mut owned = HashMap::new();
    let mut raw_trees = HashMap::new();
    let mut framed_trees = HashMap::new();
    let mut unpublished_trees = HashSet::new();
    let mut unpublished_blobs = HashSet::new();
    let mut receiver_trees = HashSet::new();
    for row in lines.iter().skip(1) {
        let oid = unhex(&row[1]);
        match row[0].as_str() {
            "B" => {
                unpublished_blobs.insert(oid);
            }
            "O" => {
                receiver_trees.insert(oid);
            }
            "T" => {
                if row[2] == "new" {
                    unpublished_trees.insert(oid.clone());
                }
                assert!(owned.insert(oid, Vec::new()).is_none());
            }
            "P" => {
                if row[2] == "new" {
                    unpublished_trees.insert(oid.clone());
                }
                assert!(raw_trees.insert(oid, unhex(&row[3])).is_none());
            }
            "F" => {
                if row[2] == "new" {
                    unpublished_trees.insert(oid.clone());
                }
                let chunks = row[3].parse().unwrap();
                let wire = if row[4] == "-" {
                    Vec::new()
                } else {
                    unhex(&row[4])
                };
                let mut input = io::BufReader::with_capacity(chunks, wire.as_slice());
                let format = match object_width(root.len()) {
                    ObjectWidth::Sha1 => ObjectFormat::Sha1,
                    ObjectWidth::Sha256 => ObjectFormat::Sha256,
                };
                let raw = read_verified_object(
                    &mut input,
                    format,
                    row[1].as_bytes(),
                    Some(ObjectKind::Tree),
                    &Limits::default(),
                )
                .map(|object| object.into_bytes())
                .map_err(|err| match err {
                    VerifiedReadError::Framing(frame) => frame_error(frame),
                    _ => String::from("PS-MSG-FRAME identity"),
                });
                assert!(framed_trees.insert(oid, raw).is_none());
            }
            "E" => {
                let kind = match row[2].as_str() {
                    "tree" => Kind::Tree,
                    "blob" => Kind::Blob,
                    "gitlink" => Kind::Gitlink,
                    _ => panic!("unknown fixture kind"),
                };
                owned.get_mut(&oid).unwrap().push((
                    kind,
                    unhex(&row[3]),
                    unhex(&row[4]),
                    row[5].as_bytes().to_vec(),
                ));
            }
            _ => panic!("unknown fixture row"),
        }
    }
    let mut arena: HashMap<_, Result<Vec<_>, String>> = owned
        .iter()
        .map(|(oid, entries)| {
            (
                oid.as_slice(),
                Ok(entries
                    .iter()
                    .map(|(kind, name, oid, mode)| Entry {
                        kind: *kind,
                        name,
                        oid,
                        mode,
                    })
                    .collect()),
            )
        })
        .collect();
    for (oid, raw) in &raw_trees {
        let records = VerifiedTreePayload::from_verified_bytes(raw, object_width(root.len()))
            .parse()
            .unwrap();
        assert!(arena.insert(oid.as_slice(), Ok(records)).is_none());
    }
    // Replay framing, identity, and parser errors at lookup to preserve
    // the owner's traversal order.
    for (oid, validated) in &framed_trees {
        let records = match validated {
            Ok(raw) => VerifiedTreePayload::from_verified_bytes(raw, object_width(root.len()))
                .parse()
                .map_err(|e| {
                    let reason = record_reason(e);
                    format!("PS-MSG-FRAME {reason}")
                }),
            Err(err) => Err(err.clone()),
        };
        assert!(arena.insert(oid.as_slice(), records).is_none());
    }
    let trees = unpublished_trees.iter().map(Vec::as_slice).collect();
    let blobs = unpublished_blobs.iter().map(Vec::as_slice).collect();
    let receiver_trees = receiver_trees.iter().map(Vec::as_slice).collect();
    let stdout = io::stdout();
    let out = RefCell::new(io::BufWriter::new(stdout.lock()));
    let checks = Cell::new(0usize);
    let result = walk(
        &root,
        max_bytes,
        Selection {
            unpublished_trees: &trees,
            unpublished_blobs: &blobs,
            receiver_trees: &receiver_trees,
        },
        |oid| match arena.get(oid) {
            Some(Ok(rows)) => Ok(rows.as_slice()),
            Some(Err(refusal)) => Err(refusal.as_str()),
            None => Err("missing-tree"),
        },
        |frontier| {
            writeln!(out.borrow_mut(), "G {frontier}").unwrap();
            let index = checks.get() + 1;
            checks.set(index);
            if expire_step != 0 && index >= expire_step {
                Err("deadline")
            } else if frontier > max_frontier {
                Err("tree-frontier")
            } else {
                Ok(())
            }
        },
        |event| {
            let mut dst = out.borrow_mut();
            match event {
                Event::ReachedTree(oid) => writeln!(dst, "T {}", hex(oid)),
                Event::Metadata { tree, path } => writeln!(dst, "M {} {}", hex(tree), hex(path)),
                Event::Subject { path, blob, mode } => {
                    writeln!(dst, "S {} {} {}", hex(path), hex(blob), hex(mode))
                }
            }
            .unwrap();
            Ok(())
        },
    );
    let result = match result {
        Ok(()) => "ok",
        Err(WalkError::TreeCycle) => "tree-cycle",
        Err(WalkError::PathBytes) => "path-bytes",
        Err(WalkError::Owner(code)) => code,
    };
    let mut buffer = out.borrow_mut();
    writeln!(buffer, "R {result}").unwrap();
    buffer.flush().unwrap();
}
