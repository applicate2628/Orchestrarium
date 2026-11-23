use crate::{LineSpan, normalize_and_index};
use std::{
    ffi::OsString,
    fs::{File, OpenOptions},
    io::{self, Read},
    os::windows::{
        ffi::OsStringExt,
        fs::{MetadataExt, OpenOptionsExt},
        io::{AsRawHandle, FromRawHandle, OwnedHandle},
    },
    path::{Component, Path, PathBuf, Prefix},
    ptr,
};
use windows_sys::Win32::{
    Storage::FileSystem::{
        FILE_ATTRIBUTE_REPARSE_POINT, FILE_FLAG_BACKUP_SEMANTICS, FILE_FLAG_DELETE_ON_CLOSE,
        FILE_FLAG_OPEN_REPARSE_POINT, FILE_LIST_DIRECTORY, FILE_READ_ATTRIBUTES, FILE_SHARE_READ,
        FILE_SHARE_WRITE, GetFinalPathNameByHandleW, VOLUME_NAME_GUID,
    },
    System::Memory::{
        CreateFileMappingW, FILE_MAP_READ, MEMORY_MAPPED_VIEW_ADDRESS, MapViewOfFile,
        PAGE_READONLY, UnmapViewOfFile,
    },
};

/// A bound local directory for scratch files, held against removal along its
/// checked path. This does not assign ownership or change directory permissions.
pub struct MappedStageDirectory {
    path: PathBuf,
    _ancestry: Vec<File>,
}

impl MappedStageDirectory {
    /// Bind a private local directory supplied by the trusted worker owner.
    ///
    /// # Safety
    ///
    /// The caller must establish private access to the directory, keep that
    /// policy in place, and ensure the ancestry cannot be changed into reparse
    /// points or otherwise redirected while the binding is live. The filesystem
    /// must support Windows exclusive sharing. Held handles rule out ordinary
    /// rename/deletion, not all metadata changes. Do not pass repository paths.
    pub unsafe fn bind(path: &Path) -> io::Result<Self> {
        let mut parts = path.components();
        let Some(Component::Prefix(prefix)) = parts.next() else {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "missing volume",
            ));
        };
        if !matches!(prefix.kind(), Prefix::Disk(_) | Prefix::VerbatimDisk(_))
            || parts.next() != Some(Component::RootDir)
        {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "expected an absolute local drive path",
            ));
        }

        let mut drive = PathBuf::from(prefix.as_os_str());
        drive.push(r"\");
        let handle = open_directory(&drive)?;
        let mut resolved = volume_root(&handle)?;
        let mut ancestry = vec![handle];

        for part in parts {
            let Component::Normal(name) = part else {
                return Err(io::Error::new(
                    io::ErrorKind::InvalidInput,
                    "expected an ordinary scratch path component",
                ));
            };
            resolved.push(name);
            ancestry.push(open_directory(&resolved)?);
        }
        if ancestry.len() == 1 {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "a volume root is not private scratch",
            ));
        }
        Ok(Self {
            path: resolved,
            _ancestry: ancestry,
        })
    }
}

fn open_directory(path: &Path) -> io::Result<File> {
    let file = OpenOptions::new()
        // An attributes-only handle does not enforce file sharing.
        .access_mode(FILE_LIST_DIRECTORY | FILE_READ_ATTRIBUTES)
        .share_mode(FILE_SHARE_READ | FILE_SHARE_WRITE)
        .custom_flags(FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT)
        .open(path)?;
    let info = file.metadata()?;
    if !info.is_dir() || info.file_attributes() & FILE_ATTRIBUTE_REPARSE_POINT != 0 {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "scratch ancestry must contain only ordinary directories",
        ));
    }
    Ok(file)
}

fn volume_root(file: &File) -> io::Result<PathBuf> {
    // SAFETY: query the size for this live directory handle, without a buffer.
    let needed = unsafe {
        GetFinalPathNameByHandleW(file.as_raw_handle(), ptr::null_mut(), 0, VOLUME_NAME_GUID)
    };
    if needed == 0 {
        return Err(io::Error::last_os_error());
    }
    let mut name = vec![0u16; needed as usize];
    // SAFETY: the output buffer has exactly the declared number of UTF-16 units.
    let written = unsafe {
        GetFinalPathNameByHandleW(
            file.as_raw_handle(),
            name.as_mut_ptr(),
            needed,
            VOLUME_NAME_GUID,
        )
    };
    if written == 0 {
        return Err(io::Error::last_os_error());
    }
    if written >= needed {
        return Err(io::Error::other(
            "volume path changed while binding scratch",
        ));
    }
    let root = PathBuf::from(OsString::from_wide(&name[..written as usize]));
    let mut parts = root.components();
    let volume = match parts.next() {
        Some(Component::Prefix(prefix)) => match prefix.kind() {
            Prefix::Verbatim(name) => name.to_str(),
            _ => None,
        },
        _ => None,
    };
    if !volume.is_some_and(|name| name.starts_with("Volume{") && name.ends_with('}'))
        || parts.next() != Some(Component::RootDir)
        || parts.next().is_some()
    {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "the drive does not resolve to a local volume root",
        ));
    }
    Ok(root)
}

/// One immutable UTF-8 image in a fresh, exclusively opened Windows file.
pub struct MappedStagedText<'a> {
    view: Option<ReadView>,
    _file: File,
    has_nul: bool,
    _directory: &'a MappedStageDirectory,
}

impl<'a> MappedStagedText<'a> {
    /// Stream a verified input to private storage and index the whole lines.
    /// Emitted spans remain provisional until this operation succeeds.
    ///
    /// A mapped page fault can terminate the process rather than return an
    /// I/O error. Deploy only behind an operation owner that treats that
    /// termination as an incomplete scan.
    ///
    /// Only a single fresh worker-owned leaf can be created in the bound root.
    pub fn stage(
        directory: &'a MappedStageDirectory,
        leaf: &str,
        input: impl Read,
        emit: impl FnMut(LineSpan) -> io::Result<()>,
    ) -> io::Result<Self> {
        if !leaf.strip_prefix("stage-").is_some_and(|name| {
            !name.is_empty() && name.bytes().all(|c| c.is_ascii_alphanumeric() || c == b'-')
        }) {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "invalid stage leaf",
            ));
        }
        let mut file = OpenOptions::new()
            .read(true)
            .write(true)
            .create_new(true)
            .share_mode(0)
            .custom_flags(FILE_FLAG_DELETE_ON_CLOSE | FILE_FLAG_OPEN_REPARSE_POINT)
            .open(directory.path.join(leaf))?;
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
            _directory: directory,
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
