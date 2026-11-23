use std::io::{self, Read, Write};

/// One whole logical line, excluding its separator. Character offsets count
/// Unicode scalars after UTF-8 replacement; byte offsets address the input.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct LineSpan {
    pub number: u64,
    pub char_start: u64,
    pub byte_start: u64,
    pub byte_end: u64,
}

/// Index verified staged bytes with fixed working memory. Each callback is
/// provisional until the read succeeds and returns whether any byte was NUL.
/// The caller owns binary policy, any span storage, and whole-line matching.
pub fn index_text(
    input: impl Read,
    emit: impl FnMut(LineSpan) -> io::Result<()>,
) -> io::Result<bool> {
    index_decoded(input, None::<io::Sink>, emit)
}

/// Normalize staged text and emit whole-line byte spans into that normalized
/// image in one pass. Bytes and spans belong to the caller's provisional
/// stage and are only usable after the successful return (including flush).
pub fn normalize_and_index(
    input: impl Read,
    normalized: impl Write,
    emit: impl FnMut(LineSpan) -> io::Result<()>,
) -> io::Result<bool> {
    index_decoded(input, Some(normalized), emit)
}

fn index_decoded(
    input: impl Read,
    mut normalized: Option<impl Write>,
    mut emit: impl FnMut(LineSpan) -> io::Result<()>,
) -> io::Result<bool> {
    let mut lines = Lines {
        next: LineSpan {
            number: 1,
            char_start: 0,
            byte_start: 0,
            byte_end: 0,
        },
        char_pos: 0,
        byte_pos: 0,
        after_cr: false,
    };
    let has_nul = visit_decoded(input, |text, raw_replaced_bytes| {
        let replaced_bytes = if let Some(sink) = &mut normalized {
            sink.write_all(text.as_bytes())?;
            None
        } else {
            raw_replaced_bytes
        };
        if let Some(width) = replaced_bytes {
            // The decoder emits one replacement scalar at a time for raw input.
            debug_assert_eq!(text, "\u{fffd}");
            lines.advance(width, 1);
        } else if text.is_ascii() {
            lines.accept_ascii(text.as_bytes(), &mut emit)?;
        } else {
            lines.accept_unicode(text, &mut emit)?;
        }
        Ok(())
    })?;
    if lines.next.byte_start < lines.byte_pos {
        lines.next.byte_end = lines.byte_pos;
        emit(lines.next)?;
    }
    if let Some(mut sink) = normalized {
        sink.flush()?;
    }
    Ok(has_nul)
}

/// Write replacement-decoded UTF-8 into a separate private sink using fixed
/// working memory. Returns whole-input NUL presence only after successful
/// read, write and flush. The sink remains provisional on failure.
pub fn normalize_staged_text(input: impl Read, mut sink: impl Write) -> io::Result<bool> {
    let has_nul = visit_decoded(input, |text, _| sink.write_all(text.as_bytes()))?;
    sink.flush()?;
    Ok(has_nul)
}

// A valid prefix retains its byte widths. The replacement callback instead
// records the width of the original invalid byte sequence.
fn visit_decoded(
    mut input: impl Read,
    mut visit: impl FnMut(&str, Option<usize>) -> io::Result<()>,
) -> io::Result<bool> {
    // At most three bytes of an unfinished UTF-8 scalar carry into a read.
    let mut buffer = [0; 16 * 1024 + 3];
    let mut carry = 0;
    let mut has_nul = false;
    loop {
        let count = match input.read(&mut buffer[carry..]) {
            Err(e) if e.kind() == io::ErrorKind::Interrupted => continue,
            result => result?,
        };
        has_nul |= buffer[carry..carry + count].contains(&0);
        let end = carry + count;
        let mut rest = &buffer[..end];
        while !rest.is_empty() {
            let (prefix, invalid) = match std::str::from_utf8(rest) {
                Ok(text) => (text, Some(0)),
                Err(e) => (
                    std::str::from_utf8(&rest[..e.valid_up_to()]).expect("validated UTF-8 prefix"),
                    e.error_len(),
                ),
            };
            if !prefix.is_empty() {
                visit(prefix, None)?;
            }
            rest = &rest[prefix.len()..];
            match invalid {
                Some(0) => break,
                Some(len) => {
                    visit("\u{fffd}", Some(len))?;
                    rest = &rest[len..];
                }
                None if count == 0 => {
                    visit("\u{fffd}", Some(rest.len()))?;
                    rest = &[];
                }
                None => break,
            }
        }
        if count == 0 {
            break;
        }
        carry = rest.len();
        buffer.copy_within(end - carry..end, 0);
    }

    Ok(has_nul)
}

struct Lines {
    next: LineSpan,
    char_pos: u64,
    byte_pos: u64,
    after_cr: bool,
}

fn is_line_separator(ch: char) -> bool {
    matches!(
        ch,
        '\n' | '\r' | '\x0b' | '\x0c' | '\x1c'..='\x1e' | '\u{85}' | '\u{2028}' | '\u{2029}'
    )
}

impl Lines {
    fn accept_ascii(
        &mut self,
        bytes: &[u8],
        emit: &mut impl FnMut(LineSpan) -> io::Result<()>,
    ) -> io::Result<()> {
        let mut start = 0;
        for (position, &byte) in bytes.iter().enumerate() {
            let ch = char::from(byte);
            if is_line_separator(ch) {
                let count = position - start;
                self.advance(count, count);
                self.accept_separator(ch, 1, emit)?;
                start = position + 1;
            }
        }
        let count = bytes.len() - start;
        self.advance(count, count);
        Ok(())
    }

    fn accept_unicode(
        &mut self,
        text: &str,
        emit: &mut impl FnMut(LineSpan) -> io::Result<()>,
    ) -> io::Result<()> {
        let mut start = 0;
        let mut chars = 0;
        for (position, ch) in text.char_indices() {
            if is_line_separator(ch) {
                self.advance(position - start, chars);
                let width = ch.len_utf8();
                self.accept_separator(ch, width, emit)?;
                start = position + width;
                chars = 0;
            } else {
                chars += 1;
            }
        }
        self.advance(text.len() - start, chars);
        Ok(())
    }

    fn advance(&mut self, bytes: usize, chars: usize) {
        if chars != 0 {
            self.byte_pos += bytes as u64;
            self.char_pos += chars as u64;
            self.after_cr = false;
        }
    }

    fn accept_separator(
        &mut self,
        ch: char,
        bytes: usize,
        emit: &mut impl FnMut(LineSpan) -> io::Result<()>,
    ) -> io::Result<()> {
        let byte_start = self.byte_pos;
        self.byte_pos += bytes as u64;
        self.char_pos += 1;
        let crlf = self.after_cr && ch == '\n';
        self.after_cr = ch == '\r';
        if !crlf {
            self.next.byte_end = byte_start;
            emit(self.next)?;
            self.next.number += 1;
        }
        self.next.byte_start = self.byte_pos;
        self.next.char_start = self.char_pos;
        Ok(())
    }
}
