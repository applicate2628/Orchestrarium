//! Candidate native operation seams. No process, publication, or install authority.

#[path = "publication/git_batch.rs"]
mod git_batch;
#[path = "publication/git_identity.rs"]
mod git_identity;

pub use git_batch::{FrameError, Limits, ObjectKind, read_frame};
pub use git_identity::{
    BatchRequestError, BatchSession, ObjectFormat, VerifiedObject, VerifiedReadError,
    VerifiedStagedObject, read_verified_object,
};
