//! Ordered lexical matching shared by publication transports.

use serde::Deserialize;
use std::error::Error;

pub type Failure = Box<dyn Error + Send + Sync>;
pub type Span = Option<(usize, usize)>;
pub type Hit = (usize, Vec<Span>);

#[derive(Deserialize)]
pub struct Rule {
    pub regex: String,
    pub binary: bool,
}

#[derive(Clone)]
pub struct Engine {
    rules: Vec<(pcre2::bytes::Regex, bool)>,
}

fn scanner_pattern(pattern: &str) -> Result<String, Failure> {
    // Materialize the scanner's whitespace class, independently of PCRE2's
    // interpretation of the shorthand. Keep all non-whitespace escapes intact.
    const SPACE: &str = r"\x{9}-\x{d}\x{1c}-\x{20}\x{85}\x{a0}\x{1680}\x{2000}-\x{200a}\x{2028}\x{2029}\x{202f}\x{205f}\x{3000}";
    let mut result = String::with_capacity(pattern.len());
    let mut chars = pattern.chars();
    let mut in_class = false;
    while let Some(c) = chars.next() {
        match c {
            '\\' => match chars.next().ok_or("incomplete escape")? {
                's' if in_class => result.push_str(SPACE),
                space @ ('s' | 'S') if !in_class => {
                    result.push('[');
                    if space == 'S' {
                        result.push('^');
                    }
                    result.push_str(SPACE);
                    result.push(']');
                }
                'S' => return Err("negated whitespace in a character class is unsupported".into()),
                other => {
                    result.push('\\');
                    result.push(other);
                }
            },
            '[' if !in_class => {
                in_class = true;
                result.push(c);
            }
            ']' if in_class => {
                in_class = false;
                result.push(c);
            }
            _ => result.push(c),
        }
    }
    Ok(result)
}

impl Engine {
    pub fn new(source: &[Rule]) -> Result<Self, Failure> {
        let mut rules = Vec::new();
        for rule in source {
            let matcher = pcre2::bytes::RegexBuilder::new()
                .utf(true)
                .ucp(true)
                .jit(true)
                .build(&scanner_pattern(&rule.regex)?)
                .map_err(|_| "PCRE2 JIT rule compilation failed")?;
            rules.push((matcher, rule.binary));
        }
        Ok(Self { rules })
    }
}

pub fn visit_occurrences(
    engine: &Engine,
    text: &str,
    binary_subject: bool,
    mut emit: impl FnMut(Hit) -> Result<(), Failure>,
) -> Result<(), Failure> {
    let bytes = text.as_bytes();
    for (i, (re, binary)) in engine.rules.iter().enumerate() {
        if binary_subject && !binary {
            continue;
        }
        let mut offset = 0;
        if re
            .find_at(bytes, 0)
            .map_err(|_| "PCRE2 JIT match failed")?
            .is_none()
        {
            continue;
        }
        let mut locs = re.capture_locations();
        while let Some(whole) = re
            .captures_read_at(&mut locs, bytes, offset)
            .map_err(|_| "PCRE2 JIT match failed")?
        {
            let start = whole.start();
            if whole.end() <= start || start < offset {
                return Err("invalid match range".into());
            }
            offset = start
                + text
                    .get(start..)
                    .and_then(|s| s.chars().next())
                    .ok_or("invalid match start")?
                    .len_utf8();
            emit((i, (0..re.captures_len()).map(|n| locs.get(n)).collect()))?;
        }
    }
    Ok(())
}

#[cfg(test)]
mod scanner_pattern_tests {
    use super::*;

    #[test]
    fn borrowed_subject_preserves_order_overlap_and_binary_policy() {
        let engine = Engine::new(&[
            Rule {
                regex: "(\u{e9}.)".into(),
                binary: false,
            },
            Rule {
                regex: "(\u{e9})".into(),
                binary: true,
            },
        ])
        .unwrap();
        let owner = String::from("x\u{e9}\u{e9}!x");
        let subject = &owner[1..owner.len() - 1];
        let all = visit_test_hits(&engine, subject, false);
        assert_eq!(
            all,
            [
                (0, vec![Some((0, 4)), Some((0, 4))]),
                (0, vec![Some((2, 5)), Some((2, 5))]),
                (1, vec![Some((0, 2)), Some((0, 2))]),
                (1, vec![Some((2, 4)), Some((2, 4))]),
            ]
        );
        assert_eq!(visit_test_hits(&engine, subject, true), all[2..]);

        let mut visited = 0;
        let result = visit_occurrences(&engine, subject, false, |_| {
            visited += 1;
            Err("sink refused".into())
        });
        assert_eq!(result.unwrap_err().to_string(), "sink refused");
        assert_eq!(visited, 1);
    }

    fn visit_test_hits(engine: &Engine, text: &str, binary: bool) -> Vec<Hit> {
        let mut hits = Vec::new();
        visit_occurrences(engine, text, binary, |hit| {
            hits.push(hit);
            Ok(())
        })
        .unwrap();
        hits
    }

    #[test]
    fn scanner_whitespace_is_engine_independent() {
        let build = |p| {
            pcre2::bytes::RegexBuilder::new()
                .utf(true)
                .ucp(true)
                .jit(true)
                .build(&scanner_pattern(p).unwrap())
                .unwrap()
        };
        let space = build(r"\A\s\z");
        let not_space = build(r"\A\S\z");
        let class = build(r"\A[\s]\z");
        let mut buf = [0; 4];
        for c in (0..=0x10ffff).filter_map(char::from_u32) {
            let bytes = c.encode_utf8(&mut buf).as_bytes();
            let expected = c.is_whitespace() || ('\u{1c}'..='\u{1f}').contains(&c);
            assert_eq!(
                space.is_match(bytes).unwrap(),
                expected,
                "U+{:04X}",
                u32::from(c)
            );
            assert_eq!(not_space.is_match(bytes).unwrap(), !expected);
            assert_eq!(class.is_match(bytes).unwrap(), expected);
        }
    }

    #[test]
    fn preserves_literal_escape_and_rejects_unsupported_class() {
        assert_eq!(scanner_pattern(r"\\s[\]]").unwrap(), r"\\s[\]]");
        assert!(scanner_pattern(r"[\S]").is_err());
    }
}
