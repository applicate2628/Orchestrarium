use rayon::prelude::*;
use serde::Deserialize;
use std::{
    error::Error,
    io::{self, BufRead, Write},
};

type Failure = Box<dyn Error + Send + Sync>;
type Span = Option<(usize, usize)>;
type Hit = (usize, Vec<Span>);

#[derive(Deserialize)]
struct Case {
    text: String,
    binary: bool,
}
#[derive(Deserialize)]
struct Rule {
    regex: String,
    binary: bool,
}

#[derive(Clone)]
struct Engine {
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
    fn new(source: &[Rule]) -> Result<Self, Failure> {
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

fn add_match(
    hits: &mut Vec<Hit>,
    i: usize,
    offset: &mut usize,
    text: &str,
    start: usize,
    end: usize,
    groups: impl FnOnce() -> Vec<Span>,
) -> Result<(), Failure> {
    if end <= start || start < *offset {
        return Err("invalid match range".into());
    }
    hits.push((i, groups()));
    *offset = start
        + text
            .get(start..)
            .and_then(|s| s.chars().next())
            .ok_or("invalid match start")?
            .len_utf8();
    Ok(())
}

fn occurrences(engine: &Engine, case: &Case) -> Result<Vec<Hit>, Failure> {
    let mut hits = Vec::new();
    let text = case.text.as_str();
    for (i, (re, binary)) in engine.rules.iter().enumerate() {
        if case.binary && !binary {
            continue;
        }
        let mut offset = 0;
        let bytes = text.as_bytes();
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
            add_match(
                &mut hits,
                i,
                &mut offset,
                text,
                whole.start(),
                whole.end(),
                || (0..re.captures_len()).map(|n| locs.get(n)).collect(),
            )?;
        }
    }
    Ok(hits)
}

thread_local! {
    static WORKER_ENGINE: std::cell::OnceCell<Engine> = const { std::cell::OnceCell::new() };
}

fn scan_batch(
    engine: &Engine,
    pool: Option<&rayon::ThreadPool>,
    cases: &[Case],
) -> Result<Vec<Vec<Hit>>, Failure> {
    if cases.is_empty() {
        return Ok(Vec::new());
    }
    let Some(pool) = pool else {
        return cases.iter().map(|case| occurrences(engine, case)).collect();
    };
    let chunk_size = cases.len().div_ceil(pool.current_num_threads());
    let chunks: Vec<Result<Vec<Vec<Hit>>, Failure>> = pool.install(|| {
        cases
            .par_chunks(chunk_size)
            .map(|chunk| {
                WORKER_ENGINE.with(|cell| {
                    let engine = cell.get_or_init(|| engine.clone());
                    chunk.iter().map(|case| occurrences(engine, case)).collect()
                })
            })
            .collect()
    });
    let mut ordered = Vec::with_capacity(cases.len());
    for chunk in chunks {
        ordered.extend(chunk?);
    }
    Ok(ordered)
}

const PARALLEL_FROM_ROWS: usize = 4_096;

struct AdaptiveScheduler<'a> {
    engine: &'a Engine,
    pool_attempted: bool,
    capacity: usize,
    pool: Option<rayon::ThreadPool>,
}

impl<'a> AdaptiveScheduler<'a> {
    fn new(engine: &'a Engine, capacity: usize) -> Self {
        Self {
            engine,
            capacity,
            pool: None,
            pool_attempted: false,
        }
    }

    fn scan(&mut self, cases: &[Case]) -> Result<Vec<Vec<Hit>>, Failure> {
        if cases.len() < PARALLEL_FROM_ROWS || self.capacity <= 1 {
            return scan_batch(self.engine, None, cases);
        }
        if !self.pool_attempted {
            self.pool_attempted = true;
            self.pool = rayon::ThreadPoolBuilder::new()
                .num_threads(self.capacity)
                .build()
                .ok();
        }
        scan_batch(self.engine, self.pool.as_ref(), cases)
    }
}

fn main() -> Result<(), Failure> {
    let mut input = io::stdin().lock().lines();
    let header = input.next().ok_or("missing rule header")??;
    let source: Vec<Rule> = serde_json::from_str(&header).map_err(|_| "invalid rules")?;
    let rules = Engine::new(&source)?;
    let workers = if std::env::args().any(|arg| arg == "--serial") {
        1
    } else {
        std::thread::available_parallelism().map_or(1, usize::from)
    };
    let mut scheduler = AdaptiveScheduler::new(&rules, workers);
    let mut out = io::stdout().lock();
    writeln!(out, "orche-match-spans-v1")?;
    out.flush()?;
    for line in input {
        let cases: Vec<Case> = serde_json::from_str(&line?).map_err(|_| "invalid cases")?;
        let reports = scheduler.scan(&cases)?;
        serde_json::to_writer(&mut out, &reports)?;
        writeln!(out)?;
        out.flush()?;
    }
    Ok(())
}

#[cfg(test)]
mod scanner_pattern_tests {
    use super::*;

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
