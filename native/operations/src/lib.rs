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

#[path = "publication/line_index.rs"]
mod line_index;
pub use line_index::{LineSpan, index_text, normalize_and_index, normalize_staged_text};

#[cfg(windows)]
#[path = "publication/mapped_stage_windows.rs"]
mod mapped_stage_windows;
#[cfg(windows)]
pub use mapped_stage_windows::{MappedStageDirectory, MappedStagedText};
