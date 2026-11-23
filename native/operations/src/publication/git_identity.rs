//! Verify the type-prefixed Git content id before exposing a complete frame.
use std::io::BufRead;

use crate::git_batch::{Frame, FrameError, Limits, ObjectKind, read_frame};

#[derive(Clone, Copy, Debug)]
pub enum ObjectFormat {
    Sha1,
    Sha256,
}

impl From<ObjectFormat> for gix_hash::Kind {
    fn from(format: ObjectFormat) -> Self {
        match format {
            ObjectFormat::Sha1 => Self::Sha1,
            ObjectFormat::Sha256 => Self::Sha256,
        }
    }
}

#[derive(Debug, Eq, PartialEq)]
pub enum VerifiedReadError {
    InvalidRequestId,
    Framing(FrameError),
    HashRejected,
    IdentityMismatch,
}

/// A complete batch response whose payload hash matched the requested object.
#[derive(Debug, Eq, PartialEq)]
pub struct VerifiedObject(Frame);

impl VerifiedObject {
    pub fn kind(&self) -> ObjectKind {
        self.0.kind
    }

    pub fn bytes(&self) -> &[u8] {
        &self.0.payload
    }

    pub fn into_bytes(self) -> Vec<u8> {
        self.0.payload
    }
}

/// The caller binds the format to the repository and owns the underlying session.
/// An error must not be recovered by reusing this stream as a new session.
pub fn read_verified_object(
    input: &mut impl BufRead,
    format: ObjectFormat,
    requested_hex: &[u8],
    expected_type: Option<ObjectKind>,
    limits: &Limits,
) -> Result<VerifiedObject, VerifiedReadError> {
    let hash_kind = format.into();
    let id = gix_hash::ObjectId::from_hex(requested_hex)
        .ok()
        .filter(|id| id.kind() == hash_kind && !requested_hex.iter().any(u8::is_ascii_uppercase))
        .ok_or(VerifiedReadError::InvalidRequestId)?;
    let frame = read_frame(input, requested_hex, expected_type, limits)
        .map_err(VerifiedReadError::Framing)?;
    let object_kind = match frame.kind {
        ObjectKind::Blob => gix_object::Kind::Blob,
        ObjectKind::Tree => gix_object::Kind::Tree,
        ObjectKind::Commit => gix_object::Kind::Commit,
        ObjectKind::Tag => gix_object::Kind::Tag,
    };
    let actual = gix_object::compute_hash(hash_kind, object_kind, &frame.payload)
        .map_err(|_| VerifiedReadError::HashRejected)?;
    if actual != id {
        return Err(VerifiedReadError::IdentityMismatch);
    }
    Ok(VerifiedObject(frame))
}
