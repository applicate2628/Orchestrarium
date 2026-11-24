//! Decode a complete tree payload already verified by the Git acquisition owner.

use super::tree_walk::{Entry, Kind};

pub(crate) enum ObjectWidth {
    Sha1,
    Sha256,
}

impl ObjectWidth {
    const fn bytes(self) -> usize {
        match self {
            Self::Sha1 => 20,
            Self::Sha256 => 32,
        }
    }
}

/// A borrow supplied only after checking Git framing and object identity.
/// This type does not perform those checks and must not confer coverage.
pub(crate) struct VerifiedTreePayload<'a> {
    raw: &'a [u8],
    width: ObjectWidth,
}

#[derive(Debug, PartialEq, Eq)]
pub(crate) enum TreeRecordError {
    Tree,
    TreePath,
    TreeMode,
}

impl<'a> VerifiedTreePayload<'a> {
    pub(crate) fn from_verified_bytes(raw: &'a [u8], width: ObjectWidth) -> Self {
        Self { raw, width }
    }

    /// Invalid input exposes no partially admitted entries.
    pub(crate) fn parse(self) -> Result<Vec<Entry<'a>>, TreeRecordError> {
        let mut entries = Vec::new();
        let mut rest = self.raw;
        let width = self.width.bytes();
        while !rest.is_empty() {
            let Some(space) = rest.iter().position(|&byte| byte == b' ') else {
                return Err(TreeRecordError::Tree);
            };
            let (mode, after_space) = rest.split_at(space);
            let after_space = &after_space[1..];
            let Some(nul) = after_space.iter().position(|&byte| byte == 0) else {
                return Err(TreeRecordError::Tree);
            };
            let (name, after_name) = after_space.split_at(nul);
            let after_name = &after_name[1..];
            if mode.is_empty() || name.is_empty() || after_name.len() < width {
                return Err(TreeRecordError::Tree);
            }
            if name.contains(&b'/') {
                return Err(TreeRecordError::TreePath);
            }
            let kind = match mode {
                b"100644" | b"100755" | b"120000" => Kind::Blob,
                b"40000" | b"040000" => Kind::Tree,
                b"160000" => Kind::Gitlink,
                _ => return Err(TreeRecordError::TreeMode),
            };
            let (oid, next) = after_name.split_at(width);
            entries.push(Entry {
                kind,
                name,
                oid,
                mode,
            });
            rest = next;
        }
        Ok(entries)
    }
}
