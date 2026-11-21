use serde_json::{Value, json};
use std::{
    io::Write,
    process::{Command, Output, Stdio},
};

fn request(batches: &[Value], malformed_tail: bool) -> Output {
    let mut child = Command::new(env!("CARGO_BIN_EXE_orche-publication-match"))
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .unwrap();
    let mut input = child.stdin.take().unwrap();
    writeln!(input, "{}", json!([{"regex":"(aba)(x)?","binary":true}])).unwrap();
    for batch in batches {
        writeln!(input, "{batch}").unwrap();
    }
    if malformed_tail {
        writeln!(input, "{{").unwrap();
    }
    drop(input);
    child.wait_with_output().unwrap()
}

#[test]
fn ordered_byte_spans_are_stable_across_batch_threshold() {
    let row = json!({"text":"\u{e9}ababa","binary":false});
    let expected = json!([[0, [[2, 5], [2, 5], null]], [0, [[4, 7], [4, 7], null]]]);
    for n in [0, 4095, 4096, 4097] {
        let out = request(&[json!(vec![row.clone(); n])], false);
        assert!(out.status.success());
        let data = std::str::from_utf8(&out.stdout).unwrap();
        let mut lines = data.lines();
        assert_eq!(lines.next(), Some("orche-match-spans-v1"));
        let got: Vec<Value> = serde_json::from_str(lines.next().unwrap()).unwrap();
        assert_eq!(got, vec![expected.clone(); n]);
        assert_eq!(lines.next(), None);
    }
}

#[test]
fn malformed_batch_has_no_result() {
    let out = request(&[], true);
    assert!(!out.status.success());
    assert_eq!(
        std::str::from_utf8(&out.stdout)
            .unwrap()
            .lines()
            .collect::<Vec<_>>(),
        ["orche-match-spans-v1"]
    );
}
