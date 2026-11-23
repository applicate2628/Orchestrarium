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
