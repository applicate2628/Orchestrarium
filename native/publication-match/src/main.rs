use orche_publication_match::{Engine, Failure, Hit, Rule, visit_occurrences};
use rayon::prelude::*;
use serde::Deserialize;
use std::io::{self, BufRead, Write};

#[derive(Deserialize)]
struct Case {
    text: String,
    binary: bool,
}
fn occurrences(engine: &Engine, case: &Case) -> Result<Vec<Hit>, Failure> {
    let mut hits = Vec::new();
    visit_occurrences(engine, &case.text, case.binary, |hit| {
        hits.push(hit);
        Ok(())
    })?;
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
