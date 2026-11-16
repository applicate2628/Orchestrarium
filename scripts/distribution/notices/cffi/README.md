# CFFI Windows vendored libffi attribution

CFFI 2.1.1's published source setup.py selects src/c/libffi_x86_x64 for
Windows builds with the Microsoft compiler. The x64 branch compiles ffi.c,
prep_cif.c and types.c and links the retained win64.obj instead of win32.c.
The accompanying notice file preserves the exact introductory notices from
those C files and their vendored headers.

The retained Windows wheel contains a diagnostic naming this vendored ffi.c.
Its wheel hash matches the official release metadata. This supports the
source-to-component attribution, but does not reproduce or authenticate the
wheel build. The prebuilt object's correspondence to win64.asm remains
unqualified. No separate object-license conclusion is made.

These source notices include authors and a disclaimer not present in the
existing supplemental Python libffi notice. The CFFI package's MIT-0 license
expressly excludes separately licensed portions. Do not replace either
existing license with this supplemental attribution.

This supplement is limited to the Windows vendored component. It does not
identify the libffi version statically present in the Linux wheel and does not
clear that wheel, all native dependencies, or legal obligations for release.

## Terms and Abbreviations
- CFFI: C Foreign Function Interface, the Python package inspected here.
- libffi: the foreign-function-interface implementation used by CFFI.
- x64: the 64-bit x86 architecture.
- MIT-0: MIT No Attribution license identifier.
