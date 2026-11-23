//! Structural decoding of one Git batch frame. Transport and identity proof
//! remain with the existing acquisition owner.
use std::io::{self, BufRead};

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ObjectKind {
    Commit,
    Tree,
    Blob,
    Tag,
}

#[derive(Debug, Eq, PartialEq)]
pub enum FrameError {
    Missing,
    Header,
    Identity,
    Type,
    Length,
    TooLarge(ObjectKind),
    HeaderDelimiter,
    RecordDelimiter,
    ShortRead,
    Pipe,
}

#[derive(Debug, Eq, PartialEq)]
pub struct Frame {
    pub kind: ObjectKind,
    pub payload: Vec<u8>,
}

pub struct Limits {
    pub header: usize,
    pub record: usize,
    pub blob: usize,
    // Preserve the receiving Python integer parser's configured decimal limit.
    // Zero represents Python's unlimited setting; the header remains bounded.
    pub decimal_digits: usize,
}

impl Default for Limits {
    fn default() -> Self {
        Self {
            header: 65_536,
            record: 1_048_576,
            blob: 64 * 1_048_576,
            decimal_digits: 4_300,
        }
    }
}

fn read_header(input: &mut impl BufRead, limit: usize) -> Result<Vec<u8>, FrameError> {
    let mut header = Vec::new();
    loop {
        let available = input.fill_buf().map_err(|_| FrameError::Pipe)?;
        if available.is_empty() {
            return Err(FrameError::HeaderDelimiter);
        }
        let delimiter = available.iter().position(|&b| b == b'\n');
        let len = delimiter.unwrap_or(available.len());
        if len > limit - header.len() {
            return Err(FrameError::Pipe);
        }
        header.extend_from_slice(&available[..len]);
        input.consume(len + usize::from(delimiter.is_some()));
        if delimiter.is_some() {
            return Ok(header);
        }
    }
}

fn length(mut raw: &[u8], cap: u64, max_digits: usize) -> Option<(u64, bool)> {
    fn whitespace(b: u8) -> bool {
        matches!(b, b' ' | b'\t'..=b'\r')
    }
    while raw.first().copied().is_some_and(whitespace) {
        raw = &raw[1..];
    }
    while raw.last().copied().is_some_and(whitespace) {
        raw = &raw[..raw.len() - 1];
    }
    let negative = raw.first() == Some(&b'-');
    if matches!(raw.first(), Some(b'+' | b'-')) {
        raw = &raw[1..];
    }
    let (mut value, mut digits, mut above) = (0u64, 0usize, false);
    let mut needs_digit = true;
    for &b in raw {
        if b.is_ascii_digit() {
            digits += 1;
            needs_digit = false;
            if !above {
                match value
                    .checked_mul(10)
                    .and_then(|v| v.checked_add(u64::from(b - b'0')))
                {
                    Some(n) if n <= cap => value = n,
                    _ => above = true,
                }
            }
        } else if b == b'_' && !needs_digit {
            needs_digit = true;
        } else {
            return None;
        }
    }
    if needs_digit
        || (max_digits != 0 && digits > max_digits)
        || (negative && (above || value != 0))
    {
        return None;
    }
    Some((value, above))
}

pub(crate) fn read_exact(input: &mut impl BufRead, dst: &mut [u8]) -> Result<(), FrameError> {
    input.read_exact(dst).map_err(|err| {
        if err.kind() == io::ErrorKind::UnexpectedEof {
            FrameError::ShortRead
        } else {
            FrameError::Pipe
        }
    })
}

/// Decode one response using the caller's already validated lowercase ASCII
/// object ID (40 or 64 hex bytes). A failure must poison the owner's session:
/// no resynchronization or use of partially decoded data is provided here.
/// A successful structural header match is not cryptographic identity proof.
pub fn read_frame(
    input: &mut impl BufRead,
    expected_oid: &[u8],
    expected_type: Option<ObjectKind>,
    limits: &Limits,
) -> Result<Frame, FrameError> {
    let (kind, size) = read_frame_header(input, expected_oid, expected_type, limits, true)?;
    let mut payload = vec![0; size as usize];
    read_exact(input, &mut payload)?;
    read_record_delimiter(input)?;
    Ok(Frame { kind, payload })
}

pub(crate) fn read_frame_header(
    input: &mut impl BufRead,
    expected_oid: &[u8],
    expected_type: Option<ObjectKind>,
    limits: &Limits,
    buffered: bool,
) -> Result<(ObjectKind, u64), FrameError> {
    let head = read_header(input, limits.header)?;
    if head.strip_suffix(b" missing") == Some(expected_oid) {
        return Err(FrameError::Missing);
    }
    let mut fields = head.split(|&b| b == b' ');
    let (Some(oid), Some(raw_type), Some(raw_length), None) =
        (fields.next(), fields.next(), fields.next(), fields.next())
    else {
        return Err(FrameError::Header);
    };
    if oid != expected_oid {
        return Err(FrameError::Identity);
    }
    let kind = match raw_type {
        b"commit" => ObjectKind::Commit,
        b"tree" => ObjectKind::Tree,
        b"blob" => ObjectKind::Blob,
        b"tag" => ObjectKind::Tag,
        _ => return Err(FrameError::Type),
    };
    if expected_type.is_some_and(|expected| expected != kind) {
        return Err(FrameError::Identity);
    }
    let cap = match (buffered, kind) {
        (false, _) => u64::MAX,
        (true, ObjectKind::Blob) => limits.blob as u64,
        (true, _) => limits.record as u64,
    };
    let (size, above) = length(raw_length, cap, limits.decimal_digits).ok_or(FrameError::Length)?;
    if above {
        return Err(FrameError::TooLarge(kind));
    }
    Ok((kind, size))
}

pub(crate) fn read_record_delimiter(input: &mut impl BufRead) -> Result<(), FrameError> {
    let mut delimiter = [0];
    read_exact(input, &mut delimiter)?;
    if delimiter[0] != b'\n' {
        return Err(FrameError::RecordDelimiter);
    }
    Ok(())
}
