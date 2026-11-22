// A std-only test driver; this is not a scanner transport or release executable.
#[path = "../src/publication/tree_record.rs"]
mod tree_record;
#[path = "../src/publication/tree_walk.rs"]
mod tree_walk;
use std::{
    cell::{Cell, RefCell},
    collections::{HashMap, HashSet},
    io::{self, BufRead, Write},
};
use tree_record::{ObjectWidth, TreeRecordError, VerifiedTreePayload};
use tree_walk::{Entry, Event, Kind, WalkError, walk};

fn unhex(input: &str) -> Vec<u8> {
    assert!(input.len() % 2 == 0);
    (0..input.len())
        .step_by(2)
        .map(|i| u8::from_str_radix(&input[i..i + 2], 16).unwrap())
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
                let reason = match err {
                    TreeRecordError::Tree => "tree",
                    TreeRecordError::TreePath => "tree-path",
                    TreeRecordError::TreeMode => "tree-mode",
                };
                writeln!(out, "R PS-MSG-FRAME {reason}").unwrap();
            }
        }
    }
    out.flush().unwrap();
}

fn main() {
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
    let mut unpublished_trees = HashSet::new();
    let mut unpublished_blobs = HashSet::new();
    for row in lines.iter().skip(1) {
        let oid = unhex(&row[1]);
        match row[0].as_str() {
            "B" => {
                unpublished_blobs.insert(oid);
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
    let mut arena: HashMap<_, Vec<_>> = owned
        .iter()
        .map(|(oid, entries)| {
            (
                oid.as_slice(),
                entries
                    .iter()
                    .map(|(kind, name, oid, mode)| Entry {
                        kind: *kind,
                        name,
                        oid,
                        mode,
                    })
                    .collect(),
            )
        })
        .collect();
    for (oid, raw) in &raw_trees {
        let records = VerifiedTreePayload::from_verified_bytes(raw, object_width(root.len()))
            .parse()
            .unwrap();
        assert!(arena.insert(oid.as_slice(), records).is_none());
    }
    let trees = unpublished_trees.iter().map(Vec::as_slice).collect();
    let blobs = unpublished_blobs.iter().map(Vec::as_slice).collect();
    let stdout = io::stdout();
    let out = RefCell::new(io::BufWriter::new(stdout.lock()));
    let checks = Cell::new(0usize);
    let result = walk(
        &root,
        max_bytes,
        &trees,
        &blobs,
        |oid| arena.get(oid).map(Vec::as_slice).ok_or("missing-tree"),
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
