// Opt-in timing corpus for the pure line-index stage, not the full scanner.
use orche_native_operations::index_text;
use std::{hint::black_box, time::Instant};
fn main() {
    let options: [(&str, Vec<u8>); 4] = [
        ("long-ascii", vec![b'x'; 64 * 1024 * 1024]),
        (
            "normal-ascii",
            b"the quick brown fox jumps over the lazy dog\n".repeat(1_048_576),
        ),
        ("dense-ascii", b"A\r\nB\x0bC\x0cD\n".repeat(3_000_000)),
        (
            "unicode",
            "one \u{00e9}\r\nnext\u{2028}\u{03bb}\n"
                .as_bytes()
                .repeat(1_000_000),
        ),
    ];
    for (name, bytes) in options {
        let mut elapsed = Vec::with_capacity(11);
        let mut observed = None;
        for idx in 0..11 {
            let begin = Instant::now();
            let mut hash = 0_u64;
            let mut count = 0_u64;
            let nul = index_text(black_box(&bytes[..]), |s| {
                count += 1;
                for field in [s.number, s.char_start, s.byte_start, s.byte_end] {
                    hash = hash.rotate_left(9).wrapping_mul(0x9e3779b185ebca87) ^ field;
                }
                Ok(())
            })
            .unwrap();
            let d = begin.elapsed().as_micros();
            if idx >= 2 {
                elapsed.push(d);
            }
            assert_eq!(
                *observed.get_or_insert((nul, count, hash)),
                (nul, count, hash)
            );
            black_box((nul, count, hash));
        }
        elapsed.sort_unstable();
        let (nul, count, hash) = observed.unwrap();
        println!(
            "{name} bytes={} nul={nul} rows={count} hash={hash:016x} median_us={}",
            bytes.len(),
            elapsed[elapsed.len() / 2]
        );
    }
}
