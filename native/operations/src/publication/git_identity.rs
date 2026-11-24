//! Verify the type-prefixed Git content id before exposing a complete frame.
use std::io::{self, BufRead};

use crate::git_batch::{
    Frame, FrameError, Limits, ObjectKind, read_frame, read_frame_header, read_record_delimiter,
};

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
    StageWrite,
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
    let actual = gix_object::compute_hash(id.kind(), native_kind(frame.kind), &frame.payload)
        .map_err(|_| VerifiedReadError::HashRejected)?;
    if actual != id {
        return Err(VerifiedReadError::IdentityMismatch);
    }
    Ok(VerifiedObject(frame))
}

/// Private, owner-provided staging returned only after a complete verified frame.
/// The stage must start empty and must not be used through another handle.
#[derive(Debug)]
pub struct VerifiedStagedObject<S> {
    kind: ObjectKind,
    size: u64,
    stage: S,
}

impl<S> VerifiedStagedObject<S> {
    pub fn kind(&self) -> ObjectKind {
        self.kind
    }

    pub fn size(&self) -> u64 {
        self.size
    }
}

impl<S: io::Read + io::Seek> VerifiedStagedObject<S> {
    /// Rewind and expose only the verified payload, never writable storage.
    /// A consumer result is usable only after it reads exactly that extent.
    /// The consumer must keep any side effects provisional until this returns.
    pub fn consume<T>(
        self,
        consume: impl FnOnce(&mut dyn io::Read) -> io::Result<T>,
    ) -> io::Result<T> {
        let mut stage = self.stage;
        if stage.seek(io::SeekFrom::Start(0))? != 0 {
            return Err(io::Error::other("verified stage could not be rewound"));
        }
        let mut reader = stage.take(self.size);
        let outcome = consume(&mut reader)?;
        if reader.limit() != 0 {
            return Err(io::Error::new(
                io::ErrorKind::UnexpectedEof,
                "verified stage was not fully consumed",
            ));
        }
        Ok(outcome)
    }
}

fn read_staged<S: io::Write>(
    input: &mut impl BufRead,
    id: gix_hash::ObjectId,
    requested_hex: &[u8],
    expected_type: Option<ObjectKind>,
    limits: &Limits,
    mut stage: S,
) -> Result<VerifiedStagedObject<S>, VerifiedReadError> {
    use VerifiedReadError::Framing;
    let (kind, size) =
        read_frame_header(input, requested_hex, expected_type, limits, false).map_err(Framing)?;
    let mut hasher = gix_hash::hasher(id.kind());
    hasher.update(&gix_object::encode::loose_header(native_kind(kind), size));

    let mut remaining = size;
    while remaining != 0 {
        let available = input.fill_buf().map_err(|_| Framing(FrameError::Pipe))?;
        let count = remaining.min(available.len() as u64) as usize;
        if count == 0 {
            return Err(Framing(FrameError::ShortRead));
        }
        let chunk = &available[..count];
        stage
            .write_all(chunk)
            .map_err(|_| VerifiedReadError::StageWrite)?;
        hasher.update(chunk);
        input.consume(count);
        remaining -= count as u64;
    }
    read_record_delimiter(input).map_err(Framing)?;
    let actual = hasher
        .try_finalize()
        .map_err(|_| VerifiedReadError::HashRejected)?;
    if actual != id {
        return Err(VerifiedReadError::IdentityMismatch);
    }
    stage.flush().map_err(|_| VerifiedReadError::StageWrite)?;
    Ok(VerifiedStagedObject { kind, size, stage })
}

fn native_kind(kind: ObjectKind) -> gix_object::Kind {
    match kind {
        ObjectKind::Blob => gix_object::Kind::Blob,
        ObjectKind::Tree => gix_object::Kind::Tree,
        ObjectKind::Commit => gix_object::Kind::Commit,
        ObjectKind::Tag => gix_object::Kind::Tag,
    }
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
    StageNotEmpty,
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
        let id = self.begin(requested_hex)?;
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

    /// Receive a large object in bounded pipe buffers rather than a payload Vec.
    /// The owner must provide a private scratch sink with failure cleanup (not
    /// a final destination); on failure it is dropped without a verified result.
    pub fn fetch_staged<S: io::Write + io::Seek>(
        &mut self,
        requested_hex: &[u8],
        expected_type: Option<ObjectKind>,
        mut stage: S,
    ) -> Result<VerifiedStagedObject<S>, BatchRequestError> {
        if self.failed {
            return Err(BatchRequestError::Poisoned);
        }
        if stage
            .seek(io::SeekFrom::End(0))
            .map_err(|_| BatchRequestError::Response(VerifiedReadError::StageWrite))?
            != 0
        {
            return Err(BatchRequestError::StageNotEmpty);
        }
        let id = self.begin(requested_hex)?;
        let object = read_staged(
            &mut self.input,
            id,
            requested_hex,
            expected_type,
            &self.limits,
            stage,
        )
        .map_err(BatchRequestError::Response)?;
        self.failed = false;
        Ok(object)
    }

    fn begin(&mut self, requested_hex: &[u8]) -> Result<gix_hash::ObjectId, BatchRequestError> {
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
        Ok(id)
    }
}
