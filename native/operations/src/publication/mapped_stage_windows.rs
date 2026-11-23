use crate::{LineSpan, normalize_and_index};
use std::{
    fs::{File, OpenOptions},
    io::{self, Read},
    os::windows::{
        fs::OpenOptionsExt,
        io::{AsRawHandle, FromRawHandle, OwnedHandle},
    },
    path::Path,
    ptr,
};
use windows_sys::Win32::{
    Storage::FileSystem::{FILE_FLAG_DELETE_ON_CLOSE, FILE_FLAG_OPEN_REPARSE_POINT},
    System::Memory::{
        CreateFileMappingW, FILE_MAP_READ, MEMORY_MAPPED_VIEW_ADDRESS, MapViewOfFile,
        PAGE_READONLY, UnmapViewOfFile,
    },
};

/// One immutable UTF-8 image in a fresh, exclusively opened Windows file.
/// The caller selects an unused leaf in its own ordinary local scratch root.
pub struct MappedStagedText {
    view: Option<ReadView>,
    _file: File,
    has_nul: bool,
}

impl MappedStagedText {
    /// Stream a verified input to private storage and index the whole lines.
    /// Emitted spans remain provisional until this operation succeeds.
    ///
    /// A mapped page fault can terminate the process rather than return an
    /// I/O error. Deploy only behind an operation owner that treats that
    /// termination as an incomplete scan.
    ///
    /// # Safety
    ///
    /// The caller owns the ordinary local scratch parent, its ancestry, and
    /// the selected unused child for the lifetime of the mapping. The backing
    /// filesystem must enforce Windows exclusive sharing; do not provide an
    /// arbitrary repository or remote path.
    pub unsafe fn stage(
        path: &Path,
        input: impl Read,
        emit: impl FnMut(LineSpan) -> io::Result<()>,
    ) -> io::Result<Self> {
        let mut file = OpenOptions::new()
            .read(true)
            .write(true)
            .create_new(true)
            .share_mode(0)
            .custom_flags(FILE_FLAG_DELETE_ON_CLOSE | FILE_FLAG_OPEN_REPARSE_POINT)
            .open(path)?;
        let has_nul = normalize_and_index(input, &mut file, emit)?;
        file.sync_all()?;
        let len = usize::try_from(file.metadata()?.len())
            .ok()
            .filter(|n| *n <= isize::MAX as usize)
            .ok_or_else(|| io::Error::other("normalized stage exceeds address space"))?;
        let view = if len == 0 {
            None
        } else {
            Some(ReadView::map(&file, len)?)
        };
        // No mutable file handle or pathname is exposed through this value.
        // The view field is dropped before the exclusive file handle.
        Ok(Self {
            view,
            _file: file,
            has_nul,
        })
    }

    pub fn has_nul(&self) -> bool {
        self.has_nul
    }

    pub fn line(&self, span: LineSpan) -> io::Result<&str> {
        let start = usize::try_from(span.byte_start).map_err(io::Error::other)?;
        let end = usize::try_from(span.byte_end).map_err(io::Error::other)?;
        let bytes = self.view.as_ref().map_or(&[][..], ReadView::bytes);
        let selected = bytes
            .get(start..end)
            .ok_or_else(|| io::Error::new(io::ErrorKind::InvalidData, "invalid normalized span"))?;
        std::str::from_utf8(selected).map_err(|e| io::Error::new(io::ErrorKind::InvalidData, e))
    }
}

struct ReadView {
    address: MEMORY_MAPPED_VIEW_ADDRESS,
    len: usize,
}

impl ReadView {
    fn map(file: &File, len: usize) -> io::Result<Self> {
        // SAFETY: the valid exclusive file handle remains owned by our caller;
        // use its settled length, default security, and an unnamed mapping.
        let mapping = unsafe {
            CreateFileMappingW(
                file.as_raw_handle(),
                ptr::null(),
                PAGE_READONLY,
                0,
                0,
                ptr::null(),
            )
        };
        if mapping.is_null() {
            return Err(io::Error::last_os_error());
        }
        // SAFETY: a non-null CreateFileMappingW result is an owned handle.
        let mapping = unsafe { OwnedHandle::from_raw_handle(mapping) };
        // SAFETY: map exactly the settled file length with read-only access.
        // The view independently owns its reference after mapping is closed.
        let address = unsafe { MapViewOfFile(mapping.as_raw_handle(), FILE_MAP_READ, 0, 0, len) };
        if address.Value.is_null() {
            return Err(io::Error::last_os_error());
        }
        Ok(Self { address, len })
    }

    fn bytes(&self) -> &[u8] {
        // SAFETY: the live view covers len initialized bytes, is read-only, and
        // its owner never writes or exposes the exclusive backing file again.
        unsafe { std::slice::from_raw_parts(self.address.Value.cast::<u8>(), self.len) }
    }
}

impl Drop for ReadView {
    fn drop(&mut self) {
        // SAFETY: this private owner unmaps the system view exactly once.
        unsafe { UnmapViewOfFile(self.address) };
    }
}
