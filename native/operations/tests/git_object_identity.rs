use std::io::Cursor;

use orche_native_operations::{
    FrameError, Limits, ObjectFormat, ObjectKind, VerifiedReadError, read_verified_object,
};

fn response(id: &str, kind: &str, raw: &[u8]) -> Cursor<Vec<u8>> {
    let mut data = format!("{} {} {}\n", id, kind, raw.len()).into_bytes();
    data.extend_from_slice(raw);
    data.push(b'\n');
    Cursor::new(data)
}

#[test]
fn receives_only_full_objects_of_the_requested_format_and_type() {
    // Known Git object hashes from independent SHA-1/SHA-256 fixtures. Commit
    // and tag bodies exercise raw identity; semantic parsing is not this owner.
    let cases: &[(ObjectFormat, ObjectKind, &str, &[u8], &str)] = &[
        (
            ObjectFormat::Sha1,
            ObjectKind::Blob,
            "blob",
            b"hello\n",
            "ce013625030ba8dba906f756967f9e9ca394464a",
        ),
        (
            ObjectFormat::Sha256,
            ObjectKind::Blob,
            "blob",
            b"hello\n",
            "2cf8d83d9ee29543b34a87727421fdecb7e3f3a183d337639025de576db9ebb4",
        ),
        (
            ObjectFormat::Sha1,
            ObjectKind::Tree,
            "tree",
            b"",
            "4b825dc642cb6eb9a060e54bf8d69288fbee4904",
        ),
        (
            ObjectFormat::Sha256,
            ObjectKind::Tree,
            "tree",
            b"",
            "6ef19b41225c5369f1c104d45d8d85efa9b057b53b14b4b9b939dd74decc5321",
        ),
        (
            ObjectFormat::Sha1,
            ObjectKind::Commit,
            "commit",
            b"fixed commit fixture\n",
            "7dbec05b093df6129e475559116bfdba7857c7a5",
        ),
        (
            ObjectFormat::Sha256,
            ObjectKind::Commit,
            "commit",
            b"fixed commit fixture\n",
            "c6589123624d12f92528005f5105a24ea56132ee4071c3ecbb1363a09e781e99",
        ),
        (
            ObjectFormat::Sha1,
            ObjectKind::Tag,
            "tag",
            b"fixed tag fixture\n",
            "52e2bfbef97c95c8ccc283d4bdc4fb70b6f901be",
        ),
        (
            ObjectFormat::Sha256,
            ObjectKind::Tag,
            "tag",
            b"fixed tag fixture\n",
            "8007e71af821286e8cbad0dcab04f74e30de56bdf192cb0f2da83f027b5c0095",
        ),
    ];
    for &(format, expected, kind, raw, id) in cases {
        let limits = Limits::default();
        let result = read_verified_object(
            &mut response(id, kind, raw),
            format,
            id.as_bytes(),
            Some(expected),
            &limits,
        )
        .unwrap();
        assert_eq!(result.kind(), expected);
        assert_eq!(result.bytes(), raw);
        let mut corrupt = raw.to_vec();
        if let Some(first) = corrupt.first_mut() {
            *first ^= 1;
        } else {
            corrupt.push(0);
        }
        assert_eq!(
            read_verified_object(
                &mut response(id, kind, &corrupt),
                format,
                id.as_bytes(),
                Some(expected),
                &limits,
            ),
            Err(VerifiedReadError::IdentityMismatch)
        );
        let other_kind = if expected == ObjectKind::Tree {
            "blob"
        } else {
            "tree"
        };
        assert_eq!(
            read_verified_object(
                &mut response(id, other_kind, raw),
                format,
                id.as_bytes(),
                None,
                &limits,
            ),
            Err(VerifiedReadError::IdentityMismatch)
        );
        assert_eq!(
            read_verified_object(
                &mut response(id, other_kind, raw),
                format,
                id.as_bytes(),
                Some(expected),
                &limits,
            ),
            Err(VerifiedReadError::Framing(FrameError::Identity))
        );
        let wrong_format = match format {
            ObjectFormat::Sha1 => ObjectFormat::Sha256,
            ObjectFormat::Sha256 => ObjectFormat::Sha1,
        };
        let mut unread = response(id, kind, raw);
        assert_eq!(
            read_verified_object(&mut unread, wrong_format, id.as_bytes(), None, &limits,),
            Err(VerifiedReadError::InvalidRequestId)
        );
        assert_eq!(unread.position(), 0);
        let upper = id.to_ascii_uppercase();
        assert_eq!(
            read_verified_object(&mut unread, format, upper.as_bytes(), None, &limits,),
            Err(VerifiedReadError::InvalidRequestId)
        );
        assert_eq!(unread.position(), 0);
    }
}

#[test]
fn truncated_or_unterminated_input_never_produces_a_verified_object() {
    let id = "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391";
    let mut missing_delimiter = response(id, "blob", b"").into_inner();
    assert_eq!(missing_delimiter.pop(), Some(b'\n'));
    assert_eq!(
        read_verified_object(
            &mut Cursor::new(missing_delimiter),
            ObjectFormat::Sha1,
            id.as_bytes(),
            Some(ObjectKind::Blob),
            &Limits::default(),
        ),
        Err(VerifiedReadError::Framing(FrameError::ShortRead)),
    );
}
