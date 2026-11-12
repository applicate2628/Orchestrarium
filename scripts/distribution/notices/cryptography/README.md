# OpenSSL in cryptography

The retained cryptography 50.0.2 wheels for Windows x64 and Linux x64 identify
OpenSSL 4.0.3 in their embedded software bill of materials (SBOM).

Copyright (c) 1998-2026 The OpenSSL Project Authors
Copyright (c) 1995-1998 Eric A. Young, Tim J. Hudson

All rights reserved.

OpenSSL 4.0.3 is declared by its upstream source as Apache-2.0 licensed.
Its exact LICENSE.txt is already included as the complete prefix of
cryptography-50.0.2.dist-info/licenses/LICENSE.APACHE in each Python runtime.
That shipped file additionally contains the standard Apache application appendix.
The inspected upstream source archive has no root NOTICE file.

source.json records the wheel, SBOM, source-archive and license hashes and the
origin of the copyright text. This identifies the component and existing license
copy; it does not require a duplicate license file. Python's separate OpenSSL
3.5.9 attribution is not the evidence for this cryptography component.

This mapping does not authenticate the publisher or establish every native
dependency's attribution obligations. Those remaining release checks still apply.

## Terms and Abbreviations

- SBOM: software bill of materials, upstream metadata describing components.
- Apache-2.0: identifier for the Apache License, Version 2.0.
- x64: the 64-bit x86 architecture.
