//! Verify the type-prefixed Git content id before exposing a complete frame.
use std::io::{self, BufRead};

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
    let id = request_id(format, requested_hex)?;
    read_bound_object(input, id, requested_hex, expected_type, limits)
}

fn request_id(
    format: ObjectFormat,
    requested_hex: &[u8],
) -> Result<gix_hash::ObjectId, VerifiedReadError> {
    gix_hash::ObjectId::from_hex(requested_hex)
        .ok()
        .filter(|id| {
            id.kind() == format.into() && !requested_hex.iter().any(u8::is_ascii_uppercase)
        })
        .ok_or(VerifiedReadError::InvalidRequestId)
}

fn read_bound_object(
    input: &mut impl BufRead,
    id: gix_hash::ObjectId,
    requested_hex: &[u8],
    expected_type: Option<ObjectKind>,
    limits: &Limits,
) -> Result<VerifiedObject, VerifiedReadError> {
    let frame = read_frame(input, requested_hex, expected_type, limits)
        .map_err(VerifiedReadError::Framing)?;
    let object_kind = match frame.kind {
        ObjectKind::Blob => gix_object::Kind::Blob,
        ObjectKind::Tree => gix_object::Kind::Tree,
        ObjectKind::Commit => gix_object::Kind::Commit,
        ObjectKind::Tag => gix_object::Kind::Tag,
    };
    let actual = gix_object::compute_hash(id.kind(), object_kind, &frame.payload)
        .map_err(|_| VerifiedReadError::HashRejected)?;
    if actual != id {
        return Err(VerifiedReadError::IdentityMismatch);
    }
    Ok(VerifiedObject(frame))
}

/// Serial request framing over two pipes already held by a process supervisor.
/// This object must remain bound to that one child; do not recreate it on the
/// same pipes after an error. Cancellation, I/O deadlines and reaping remain
/// the supervisor's responsibility.
pub struct BatchSession<R, W> {
    input: R,
    output: W,
    format: ObjectFormat,
    limits: Limits,
    failed: bool,
}

#[derive(Debug, Eq, PartialEq)]
pub enum BatchRequestError {
    Poisoned,
    Write,
    Response(VerifiedReadError),
}

impl<R: BufRead, W: io::Write> BatchSession<R, W> {
    pub fn new(input: R, output: W, format: ObjectFormat, limits: Limits) -> Self {
        Self {
            input,
            output,
            format,
            limits,
            failed: false,
        }
    }

    pub fn fetch(
        &mut self,
        requested_hex: &[u8],
        expected_type: Option<ObjectKind>,
    ) -> Result<VerifiedObject, BatchRequestError> {
        if self.failed {
            return Err(BatchRequestError::Poisoned);
        }
        // A request that did not settle may have already moved either pipe.
        // Restore admission only after the complete authenticated response.
        self.failed = true;
        let id = request_id(self.format, requested_hex).map_err(BatchRequestError::Response)?;
        let mut wire = [b'\n'; 65];
        let len = requested_hex.len();
        wire[..len].copy_from_slice(requested_hex);
        self.output
            .write_all(&wire[..=len])
            .and_then(|()| self.output.flush())
            .map_err(|_| BatchRequestError::Write)?;
        let object = read_bound_object(
            &mut self.input,
            id,
            requested_hex,
            expected_type,
            &self.limits,
        )
        .map_err(BatchRequestError::Response)?;
        self.failed = false;
        Ok(object)
    }
}
