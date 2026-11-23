use orche_native_operations::{LineSpan, index_text, normalize_staged_text};
use std::io::{self, Read};

struct Chunk<'a>(&'a [u8], usize);
impl Read for Chunk<'_> {
    fn read(&mut self, out: &mut [u8]) -> io::Result<usize> {
        let n = self.1.min(out.len()).min(self.0.len());
        out[..n].copy_from_slice(&self.0[..n]);
        self.0 = &self.0[n..];
        Ok(n)
    }
}

fn rows(input: &[u8], width: usize) -> (bool, Vec<(u64, u64, String)>) {
    let mut result = Vec::new();
    let nul = index_text(Chunk(input, width), |s: LineSpan| {
        result.push((
            s.number,
            s.char_start,
            String::from_utf8_lossy(&input[s.byte_start as usize..s.byte_end as usize])
                .into_owned(),
        ));
        Ok(())
    })
    .unwrap();
    (nul, result)
}

#[test]
fn preserves_whole_logical_lines_across_read_boundaries() {
    let input =
        b"\r\nA\xc3\xa9\x0b\x1c\x1d\x1e\x0c\xc2\x85\xe2\x80\xa8\xe2\x80\xa9\xf0\x9f\x92\nZ\0\r";
    let expected: Vec<_> = [
        (1, 0, ""),
        (2, 2, "Aé"),
        (3, 5, ""),
        (4, 6, ""),
        (5, 7, ""),
        (6, 8, ""),
        (7, 9, ""),
        (8, 10, ""),
        (9, 11, ""),
        (10, 12, "�"),
        (11, 14, "Z\0"),
    ]
    .into_iter()
    .map(|(n, o, s)| (n, o, s.to_owned()))
    .collect();
    for width in 1..=input.len() {
        assert_eq!(
            rows(input, width),
            (true, expected.clone()),
            "width={width}"
        );
    }
    assert_eq!(rows(b"", 1), (false, vec![]));
    assert_eq!(rows(b"x", 1), (false, vec![(1, 0, "x".to_owned())]));
    assert_eq!(
        rows(b"\r\r", 1),
        (false, vec![(1, 0, "".to_owned()), (2, 1, "".to_owned())])
    );
    assert_eq!(rows(b"\xf0\x9f", 1), (false, vec![(1, 0, "�".to_owned())]));
}

#[test]
fn identifies_late_nul_without_materializing_the_line() {
    let n = 16 * 1024 * 1024;
    let mut count = 0;
    let input = io::repeat(b'x').take(n).chain(&b"\0"[..]);
    assert!(
        index_text(input, |s| {
            count += 1;
            assert_eq!(
                (s.number, s.char_start, s.byte_start, s.byte_end),
                (1, 0, 0, n + 1)
            );
            Ok(())
        })
        .unwrap()
    );
    assert_eq!(count, 1);
}

#[test]
fn ascii_runs_keep_positions_at_and_between_chunk_boundaries() {
    let mut source = vec![b'x'; 16 * 1024 - 1];
    source.extend(b"\r\nA\0B\rC\x0bD\x0cE\x1cF\x1dG\x1eH\nI");
    let expected = [
        (1, 0, 0, 16383),
        (2, 16385, 16385, 16388),
        (3, 16389, 16389, 16390),
        (4, 16391, 16391, 16392),
        (5, 16393, 16393, 16394),
        (6, 16395, 16395, 16396),
        (7, 16397, 16397, 16398),
        (8, 16399, 16399, 16400),
        (9, 16401, 16401, 16402),
    ];
    for width in [1, 31, 16 * 1024 - 1, 16 * 1024, 16 * 1024 + 1] {
        let mut spans = Vec::new();
        assert!(
            index_text(Chunk(&source, width), |s| {
                spans.push((s.number, s.char_start, s.byte_start, s.byte_end));
                Ok(())
            })
            .unwrap()
        );
        assert_eq!(spans, expected, "width={width}");
    }
}

#[test]
fn unfinished_read_is_not_a_verified_result() {
    let input = (&b"a\n"[..]).chain(Fails);
    let error = index_text(input, |_| Ok(())).unwrap_err();
    assert_eq!(error.kind(), io::ErrorKind::Other);
}
struct Fails;
impl Read for Fails {
    fn read(&mut self, _: &mut [u8]) -> io::Result<usize> {
        Err(io::Error::other("fixture read failure"))
    }
}

#[test]
fn normalizes_staged_utf8_independent_of_read_boundaries() {
    let input = b"alpha\0\r\n\xc2\x85\xf0\x9f\x92\n\x80\xe2\x82";
    let expected = String::from_utf8_lossy(input);
    for width in 1..=input.len() {
        let mut output = Vec::new();
        assert!(normalize_staged_text(Chunk(input, width), &mut output).unwrap());
        assert_eq!(output, expected.as_bytes(), "width={width}");
    }
}

#[test]
fn normalization_propagates_source_and_sink_failures() {
    assert!(normalize_staged_text((&b"prefix"[..]).chain(Fails), io::sink()).is_err());
    assert!(normalize_staged_text(&b"prefix"[..], RejectWrites).is_err());
}

struct RejectWrites;
impl io::Write for RejectWrites {
    fn write(&mut self, _: &[u8]) -> io::Result<usize> {
        Err(io::Error::other("fixture sink failure"))
    }
    fn flush(&mut self) -> io::Result<()> {
        Ok(())
    }
}

#[test]
fn indexes_replacement_decoded_bytes_in_the_same_pass() {
    use orche_native_operations::normalize_and_index;
    let input = b"\r\none\x80\xff\r\n\xc2\x85two\xf0\x9f\x92\x0b\0tail\xe2\x82";
    let expected = String::from_utf8_lossy(input);
    let mut expected_spans = Vec::new();
    index_text(expected.as_bytes(), |span| {
        expected_spans.push(span);
        Ok(())
    })
    .unwrap();
    for width in 1..=input.len() {
        let mut bytes = Vec::new();
        let mut spans = Vec::new();
        let has_nul = normalize_and_index(Chunk(input, width), &mut bytes, |span| {
            spans.push(span);
            Ok(())
        })
        .unwrap();
        assert!(has_nul);
        assert_eq!(bytes, expected.as_bytes());
        assert_eq!(spans, expected_spans);
    }
    assert!(normalize_and_index(input.as_slice(), RejectWrites, |_| Ok(())).is_err());
    assert!(
        normalize_and_index(input.as_slice(), io::sink(), |_| Err(io::Error::other(
            "index"
        )))
        .is_err()
    );
}

#[cfg(windows)]
#[test]
#[ignore = "requires an operator-provided disposable directory on local Windows storage"]
fn mapped_normalized_stage_exclusively_owns_its_lines_and_cleanup() {
    use orche_native_operations::MappedStagedText;
    use std::{fs, path::PathBuf};
    let root = PathBuf::from(std::env::var_os("ORCHE_NATIVE_GIT_FIXTURES").unwrap());
    let path = root.join("normalized-private-stage");
    let n = 16 * 1024 * 1024;
    let mut spans = Vec::new();
    let input = io::repeat(b'x').take(n).chain(&b"\xff\r\nZ\0"[..]);
    // SAFETY: the caller supplies our disposable local Windows fixture root
    // and this test alone owns the stage leaf under it.
    let text = unsafe {
        MappedStagedText::stage(&path, input, |span| {
            spans.push(span);
            Ok(())
        })
    }
    .unwrap();
    assert!(text.has_nul());
    assert_eq!(spans.len(), 2);
    assert_eq!(text.line(spans[0]).unwrap().len(), n as usize + 3);
    assert!(text.line(spans[0]).unwrap().ends_with('\u{fffd}'));
    assert_eq!(text.line(spans[1]).unwrap(), "Z\0");
    assert!(fs::OpenOptions::new().write(true).open(&path).is_err());
    let mut invalid = spans[0];
    invalid.byte_end -= 1;
    assert!(text.line(invalid).is_err());
    invalid.byte_start = invalid.byte_end + 1;
    assert!(text.line(invalid).is_err());
    invalid.byte_end = u64::MAX;
    assert!(text.line(invalid).is_err());
    drop(text);
    assert!(!path.exists());

    fs::write(&path, b"incumbent").unwrap();
    // SAFETY: our fixture owns the parent; the existing leaf must cause the
    // create-new admission to refuse before accessing incumbent bytes.
    let collision = unsafe { MappedStagedText::stage(&path, &b"new"[..], |_| Ok(())) };
    assert!(collision.is_err());
    assert_eq!(fs::read(&path).unwrap(), b"incumbent");
    fs::remove_file(&path).unwrap();

    // SAFETY: same exclusive disposable leaf after settlement of the collision
    // fixture; the callback deliberately refuses without changing the backing.
    let failed = unsafe {
        MappedStagedText::stage(&path, &b"line\n"[..], |_| {
            Err(io::Error::other("span sink"))
        })
    };
    assert!(failed.is_err());
    assert!(!path.exists());

    // SAFETY: the test still has the unused leaf under its exclusively owned root.
    let empty =
        unsafe { MappedStagedText::stage(&path, &b""[..], |_| panic!("empty index row")) }.unwrap();
    assert!(!empty.has_nul());
    drop(empty);
    assert!(!path.exists());
}
