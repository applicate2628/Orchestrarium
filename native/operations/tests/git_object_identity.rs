use std::io::Cursor;

use orche_native_operations::{
    BatchRequestError, BatchSession, FrameError, Limits, ObjectFormat, ObjectKind,
    VerifiedReadError, read_verified_object,
};

fn response(id: &str, kind: &str, raw: &[u8]) -> Cursor<Vec<u8>> {
    let mut data = format!("{} {} {}\n", id, kind, raw.len()).into_bytes();
    data.extend_from_slice(raw);
    data.push(b'\n');
    Cursor::new(data)
}

#[test]
fn receives_only_full_objects_of_the_requested_format_and_type() {
    // Known Git object hashes from independent SHA-1/SHA-256 fixtures. Commit
    // and tag bodies exercise raw identity; semantic parsing is not this owner.
    let cases: &[(ObjectFormat, ObjectKind, &str, &[u8], &str)] = &[
        (
            ObjectFormat::Sha1,
            ObjectKind::Blob,
            "blob",
            b"hello\n",
            "ce013625030ba8dba906f756967f9e9ca394464a",
        ),
        (
            ObjectFormat::Sha256,
            ObjectKind::Blob,
            "blob",
            b"hello\n",
            "2cf8d83d9ee29543b34a87727421fdecb7e3f3a183d337639025de576db9ebb4",
        ),
        (
            ObjectFormat::Sha1,
            ObjectKind::Tree,
            "tree",
            b"",
            "4b825dc642cb6eb9a060e54bf8d69288fbee4904",
        ),
        (
            ObjectFormat::Sha256,
            ObjectKind::Tree,
            "tree",
            b"",
            "6ef19b41225c5369f1c104d45d8d85efa9b057b53b14b4b9b939dd74decc5321",
        ),
        (
            ObjectFormat::Sha1,
            ObjectKind::Commit,
            "commit",
            b"fixed commit fixture\n",
            "7dbec05b093df6129e475559116bfdba7857c7a5",
        ),
        (
            ObjectFormat::Sha256,
            ObjectKind::Commit,
            "commit",
            b"fixed commit fixture\n",
            "c6589123624d12f92528005f5105a24ea56132ee4071c3ecbb1363a09e781e99",
        ),
        (
            ObjectFormat::Sha1,
            ObjectKind::Tag,
            "tag",
            b"fixed tag fixture\n",
            "52e2bfbef97c95c8ccc283d4bdc4fb70b6f901be",
        ),
        (
            ObjectFormat::Sha256,
            ObjectKind::Tag,
            "tag",
            b"fixed tag fixture\n",
            "8007e71af821286e8cbad0dcab04f74e30de56bdf192cb0f2da83f027b5c0095",
        ),
    ];
    for &(format, expected, kind, raw, id) in cases {
        let limits = Limits::default();
        let result = read_verified_object(
            &mut response(id, kind, raw),
            format,
            id.as_bytes(),
            Some(expected),
            &limits,
        )
        .unwrap();
        assert_eq!(result.kind(), expected);
        assert_eq!(result.bytes(), raw);
        let mut corrupt = raw.to_vec();
        if let Some(first) = corrupt.first_mut() {
            *first ^= 1;
        } else {
            corrupt.push(0);
        }
        assert_eq!(
            read_verified_object(
                &mut response(id, kind, &corrupt),
                format,
                id.as_bytes(),
                Some(expected),
                &limits,
            ),
            Err(VerifiedReadError::IdentityMismatch)
        );
        let other_kind = if expected == ObjectKind::Tree {
            "blob"
        } else {
            "tree"
        };
        assert_eq!(
            read_verified_object(
                &mut response(id, other_kind, raw),
                format,
                id.as_bytes(),
                None,
                &limits,
            ),
            Err(VerifiedReadError::IdentityMismatch)
        );
        assert_eq!(
            read_verified_object(
                &mut response(id, other_kind, raw),
                format,
                id.as_bytes(),
                Some(expected),
                &limits,
            ),
            Err(VerifiedReadError::Framing(FrameError::Identity))
        );
        let wrong_format = match format {
            ObjectFormat::Sha1 => ObjectFormat::Sha256,
            ObjectFormat::Sha256 => ObjectFormat::Sha1,
        };
        let mut unread = response(id, kind, raw);
        assert_eq!(
            read_verified_object(&mut unread, wrong_format, id.as_bytes(), None, &limits,),
            Err(VerifiedReadError::InvalidRequestId)
        );
        assert_eq!(unread.position(), 0);
        let upper = id.to_ascii_uppercase();
        assert_eq!(
            read_verified_object(&mut unread, format, upper.as_bytes(), None, &limits,),
            Err(VerifiedReadError::InvalidRequestId)
        );
        assert_eq!(unread.position(), 0);
    }
}

#[test]
fn truncated_or_unterminated_input_never_produces_a_verified_object() {
    let id = "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391";
    let mut missing_delimiter = response(id, "blob", b"").into_inner();
    assert_eq!(missing_delimiter.pop(), Some(b'\n'));
    assert_eq!(
        read_verified_object(
            &mut Cursor::new(missing_delimiter),
            ObjectFormat::Sha1,
            id.as_bytes(),
            Some(ObjectKind::Blob),
            &Limits::default(),
        ),
        Err(VerifiedReadError::Framing(FrameError::ShortRead)),
    );
}

#[test]
fn a_batch_session_reuses_one_pair_of_pipes_only_after_a_verified_response() {
    let id = "ce013625030ba8dba906f756967f9e9ca394464a";
    let good = response(id, "blob", b"hello\n").into_inner();
    let bad = response(id, "blob", b"wrong\n").into_inner();
    let mut request = Vec::new();
    let mut input = Cursor::new([good.as_slice(), &bad, &good].concat());
    {
        let mut session = BatchSession::new(
            &mut input,
            &mut request,
            ObjectFormat::Sha1,
            Limits::default(),
        );
        assert_eq!(
            session
                .fetch(id.as_bytes(), Some(ObjectKind::Blob))
                .unwrap()
                .bytes(),
            b"hello\n"
        );
        assert_eq!(
            session.fetch(id.as_bytes(), None),
            Err(BatchRequestError::Response(
                VerifiedReadError::IdentityMismatch
            ))
        );
        assert_eq!(
            session.fetch(id.as_bytes(), None),
            Err(BatchRequestError::Poisoned)
        );
    }
    assert_eq!(request, format!("{id}\n{id}\n").as_bytes());
    assert_eq!(input.position(), (good.len() + bad.len()) as u64);
}

#[test]
fn invalid_ids_never_reach_the_child_and_io_failure_cannot_retry() {
    let mut requests = Vec::new();
    let mut responses = Cursor::new(Vec::<u8>::new());
    {
        let mut session = BatchSession::new(
            &mut responses,
            &mut requests,
            ObjectFormat::Sha256,
            Limits::default(),
        );
        assert_eq!(
            session.fetch(b"HEAD\n", None),
            Err(BatchRequestError::Response(
                VerifiedReadError::InvalidRequestId
            ))
        );
        assert_eq!(
            session.fetch(&[b'0'; 64], None),
            Err(BatchRequestError::Poisoned)
        );
    }
    assert!(requests.is_empty());
    assert_eq!(responses.position(), 0);

    struct FailedFlush(Vec<u8>);
    impl std::io::Write for FailedFlush {
        fn write(&mut self, buf: &[u8]) -> std::io::Result<usize> {
            self.0.extend_from_slice(buf);
            Ok(buf.len())
        }
        fn flush(&mut self) -> std::io::Result<()> {
            Err(std::io::ErrorKind::BrokenPipe.into())
        }
    }
    let mut sent = FailedFlush(Vec::new());
    {
        let mut session = BatchSession::new(
            &mut responses,
            &mut sent,
            ObjectFormat::Sha256,
            Limits::default(),
        );
        assert_eq!(
            session.fetch(&[b'0'; 64], None),
            Err(BatchRequestError::Write)
        );
        assert_eq!(
            session.fetch(&[b'0'; 64], None),
            Err(BatchRequestError::Poisoned)
        );
    }
    assert_eq!(sent.0.len(), 65);
    assert_eq!(responses.position(), 0);
}

#[test]
#[ignore = "requires an operator-provided disposable fixture root and native Git"]
fn native_git_keeps_one_batch_open_for_both_object_widths() {
    use std::io::BufReader;
    use std::process::{Command, Stdio};

    let root = std::env::var_os("ORCHE_NATIVE_GIT_FIXTURES").unwrap();
    for (format, algorithm, digits, empty_tree) in [
        (
            ObjectFormat::Sha1,
            "sha1",
            40,
            "4b825dc642cb6eb9a060e54bf8d69288fbee4904",
        ),
        (
            ObjectFormat::Sha256,
            "sha256",
            64,
            "6ef19b41225c5369f1c104d45d8d85efa9b057b53b14b4b9b939dd74decc5321",
        ),
    ] {
        let repo = std::path::Path::new(&root).join(algorithm);
        assert!(!repo.exists(), "fixture checkout must be new");
        let init = Command::new("git")
            .args(["init", "--bare", &format!("--object-format={algorithm}")])
            .arg(&repo)
            .output()
            .unwrap();
        assert!(init.status.success(), "{:?}", init.stderr);

        let size = 64 * 1_048_576 + 1;
        let fixture = repo.join("large-blob");
        std::fs::File::create(&fixture)
            .unwrap()
            .set_len(size)
            .unwrap();
        let hash = Command::new("git")
            .args(["hash-object", "-w", "--no-filters"])
            .arg(&fixture)
            .current_dir(&repo)
            .output()
            .unwrap();
        assert!(hash.status.success(), "{:?}", hash.stderr);
        let large_oid = std::str::from_utf8(&hash.stdout).unwrap().trim_end();
        let stage = std::fs::File::create_new(repo.join("large-object-stage")).unwrap();
        let mut git = Command::new("git")
            .args(["--no-replace-objects", "cat-file", "--batch"])
            .current_dir(&repo)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .spawn()
            .unwrap();
        let input = BufReader::new(git.stdout.take().unwrap());
        let output = git.stdin.take().unwrap();
        let mut session = BatchSession::new(input, output, format, Limits::default());
        let a = session.fetch(empty_tree.as_bytes(), Some(ObjectKind::Tree));
        let b = session.fetch(empty_tree.as_bytes(), None);
        let large = session.fetch_staged(large_oid.as_bytes(), Some(ObjectKind::Blob), stage);
        // This unambiguous full ID cannot refer to a real object in the fixture.
        let missing = session.fetch(&vec![b'1'; digits], None);
        let rejected = session.fetch(empty_tree.as_bytes(), None);
        drop(session);
        let status = git.wait().unwrap();
        assert!(status.success());
        assert_eq!(a.unwrap().kind(), ObjectKind::Tree);
        assert!(b.unwrap().bytes().is_empty());

        let object = large.unwrap();
        assert_eq!((object.kind(), object.size()), (ObjectKind::Blob, size));
        assert_eq!(object.into_stage().metadata().unwrap().len(), size);
        assert_eq!(
            missing,
            Err(BatchRequestError::Response(VerifiedReadError::Framing(
                FrameError::Missing
            )))
        );
        assert_eq!(rejected, Err(BatchRequestError::Poisoned));
    }
}

#[test]
fn stage_checks_content_and_frame_even_above_the_buffered_cap() {
    let id = b"ce013625030ba8dba906f756967f9e9ca394464a";
    for (payload, delimiter, error) in [
        (b"hello\n", b'\n', None),
        (b"wrong\n", b'\n', Some(VerifiedReadError::IdentityMismatch)),
        (
            b"hello\n",
            b'?',
            Some(VerifiedReadError::Framing(FrameError::RecordDelimiter)),
        ),
    ] {
        let mut raw = response(std::str::from_utf8(id).unwrap(), "blob", payload).into_inner();
        *raw.last_mut().unwrap() = delimiter;
        let limits = Limits {
            blob: 5,
            ..Limits::default()
        };
        let input = std::io::BufReader::with_capacity(3, Cursor::new(raw));
        let mut session = BatchSession::new(input, std::io::sink(), ObjectFormat::Sha1, limits);
        let result = session.fetch_staged(id, Some(ObjectKind::Blob), Cursor::new(Vec::new()));
        if let Some(error) = error {
            assert_eq!(result.unwrap_err(), BatchRequestError::Response(error));
            assert_eq!(session.fetch(id, None), Err(BatchRequestError::Poisoned));
        } else {
            let object = result.unwrap();
            assert_eq!((object.kind(), object.size()), (ObjectKind::Blob, 6));
            assert_eq!(object.into_stage().into_inner(), b"hello\n");
        }
    }
}

#[test]
fn nonempty_stage_is_rejected_before_touching_the_batch_pipes() {
    let id = "ce013625030ba8dba906f756967f9e9ca394464a";
    let mut request = Vec::new();
    let mut input = response(id, "blob", b"hello\n");
    let mut session = BatchSession::new(
        &mut input,
        &mut request,
        ObjectFormat::Sha1,
        Limits::default(),
    );
    assert_eq!(
        session
            .fetch_staged(id.as_bytes(), None, Cursor::new(vec![0]))
            .unwrap_err(),
        BatchRequestError::StageNotEmpty,
    );
    assert_eq!(
        session.fetch(id.as_bytes(), None).unwrap().bytes(),
        b"hello\n"
    );
    assert_eq!(request, format!("{id}\n").as_bytes());
}
