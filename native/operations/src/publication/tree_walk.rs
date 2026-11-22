//! Ordered expansion of already admitted Git tree records for the native-plan lane.
//! This module does not open a repository, classify findings, or make a coverage decision.

use std::collections::HashSet;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Kind {
    Tree,
    Blob,
    Gitlink,
}

pub struct Entry<'graph> {
    pub kind: Kind,
    pub name: &'graph [u8],
    pub oid: &'graph [u8],
    pub mode: &'graph [u8],
}

#[derive(Debug, Eq, PartialEq)]
pub enum Event<'event> {
    ReachedTree(&'event [u8]),
    Metadata {
        tree: &'event [u8],
        path: &'event [u8],
    },
    Subject {
        path: &'event [u8],
        blob: &'event [u8],
        mode: &'event [u8],
    },
}

#[derive(Debug, Eq, PartialEq)]
pub enum WalkError<E> {
    TreeCycle,
    PathBytes,
    Owner(E),
}

enum Pending<'graph> {
    Enter(&'graph [u8], Vec<u8>),
    Leave(&'graph [u8]),
}

/// Expand one root in scanner order. The caller supplies only verified parsed
/// graph entries and owns the root's identity, budget, metadata admission,
/// index/proof, and all findings. Events borrow the current path for the call.
pub fn walk<'graph, E>(
    root: &'graph [u8],
    max_path_bytes: usize,
    unpublished_trees: &HashSet<&[u8]>,
    unpublished_blobs: &HashSet<&[u8]>,
    mut load: impl FnMut(&'graph [u8]) -> Result<&'graph [Entry<'graph>], E>,
    mut guard: impl FnMut(usize) -> Result<(), E>,
    mut emit: impl FnMut(Event<'_>) -> Result<(), E>,
) -> Result<(), WalkError<E>> {
    guard(0).map_err(WalkError::Owner)?;
    let mut stack = vec![Pending::Enter(root, Vec::new())];
    let mut frontier = 1;
    let mut active = HashSet::new();
    while let Some(next) = stack.pop() {
        let (oid, mut path) = match next {
            Pending::Leave(oid) => {
                active.remove(oid);
                continue;
            }
            Pending::Enter(oid, path) => (oid, path),
        };
        guard(frontier).map_err(WalkError::Owner)?;
        frontier -= 1;
        if !active.insert(oid) {
            return Err(WalkError::TreeCycle);
        }
        let entries = load(oid).map_err(WalkError::Owner)?;
        stack.push(Pending::Leave(oid));
        let unpublished = unpublished_trees.contains(oid);
        if unpublished {
            emit(Event::ReachedTree(oid)).map_err(WalkError::Owner)?;
        }
        let prefix_len = path.len();
        for entry in entries.iter().rev() {
            guard(frontier).map_err(WalkError::Owner)?;
            let separator = usize::from(prefix_len != 0);
            if prefix_len
                .checked_add(separator)
                .and_then(|size| size.checked_add(entry.name.len()))
                .is_none_or(|size| size > max_path_bytes)
            {
                return Err(WalkError::PathBytes);
            }
            path.truncate(prefix_len);
            if separator != 0 {
                path.push(b'/');
            }
            path.extend_from_slice(entry.name);
            if unpublished {
                emit(Event::Metadata {
                    tree: oid,
                    path: &path,
                })
                .map_err(WalkError::Owner)?;
            }
            match entry.kind {
                Kind::Tree => {
                    guard(frontier + 1).map_err(WalkError::Owner)?;
                    stack.push(Pending::Enter(entry.oid, path.clone()));
                    frontier += 1;
                }
                Kind::Blob if unpublished_blobs.contains(entry.oid) => {
                    emit(Event::Subject {
                        path: &path,
                        blob: entry.oid,
                        mode: entry.mode,
                    })
                    .map_err(WalkError::Owner)?;
                }
                Kind::Blob | Kind::Gitlink => {}
            }
        }
    }
    Ok(())
}
