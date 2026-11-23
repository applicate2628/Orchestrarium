use std::io::{self, Read};

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
    mut input: impl Read,
    mut emit: impl FnMut(LineSpan) -> io::Result<()>,
) -> io::Result<bool> {
    // At most three bytes of an unfinished UTF-8 scalar carry into a read.
    let mut buffer = [0; 16 * 1024 + 3];
    let mut carry = 0;
    let mut has_nul = false;
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
            for ch in prefix.chars() {
                lines.accept(ch, ch.len_utf8(), &mut emit)?;
            }
            rest = &rest[prefix.len()..];
            match invalid {
                Some(0) => break,
                Some(len) => {
                    lines.accept('\u{fffd}', len, &mut emit)?;
                    rest = &rest[len..];
                }
                None if count == 0 => {
                    lines.accept('\u{fffd}', rest.len(), &mut emit)?;
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

    if lines.next.byte_start < lines.byte_pos {
        lines.next.byte_end = lines.byte_pos;
        emit(lines.next)?;
    }
    Ok(has_nul)
}

struct Lines {
    next: LineSpan,
    char_pos: u64,
    byte_pos: u64,
    after_cr: bool,
}

impl Lines {
    fn accept(
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
        if !crlf
            && matches!(
                ch,
                '\n' | '\r' | '\x0b' | '\x0c' | '\x1c'
                    ..='\x1e' | '\u{85}' | '\u{2028}' | '\u{2029}'
            )
        {
            self.next.byte_end = byte_start;
            emit(self.next)?;
            self.next.number += 1;
        } else if !crlf {
            return Ok(());
        }
        self.next.byte_start = self.byte_pos;
        self.next.char_start = self.char_pos;
        Ok(())
    }
}
