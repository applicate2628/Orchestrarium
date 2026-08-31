from __future__ import annotations

import base64
import hashlib
import importlib.util
import io
import json
import shutil
import stat
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
INSTALLER_PATH = ROOT / "scripts" / "production_installer.py"
PRE_H2_GLOBAL_LEAD_TREE_SHA256 = (
    "8088b25e70702f2c77d811bcd0c74e339474a7429a2e997f2df7662c6d75db0f"
)
CURRENT_GLOBAL_LEAD_TREE_SHA256 = (
    "fefe8d5ff71dfa8475fea381cdb756848740b7ea0f4a7573d69bff5b5db113cc"
)
PRE_REBASE_GLOBAL_LEAD_TREE_SHA256 = (
    "d0bec9fd61bf3fde6e48ba38cdbc7c021053a4167bbb694c8aa5c03e06283083"
)
PRE_RANGE_V3_GLOBAL_LEAD_TREE_SHA256 = (
    "1ffea3eb0fcf6589ac874ab49e508807eb0726dff88473d82b8b22b5baa42bf0"
)
PROVIDER_AUTH_BASELINE_GLOBAL_LEAD_TREE_SHA256 = (
    "f03d3b74d68c032ec5c1539ce7936065d5083624b702ec4403fa7e2cc509adc7"
)
PROVIDER_AUTH_BASELINE_GLOBAL_LEAD_REVISION = (
    "d1309ee50598fad1dd1f218d2fab9fd2b1c04a21"
)
PRE_RANGE_V3_GLOBAL_LEAD_REVISION = "8f92dc73d7156888944d50fa37a5b2d921c77fb1"
PRE_KIMI_GLOBAL_LEAD_REVISION = "7872d36d1019d1ac8c2e1615a9f9dbde47395815"
PRE_KIMI_GLOBAL_LEAD_TREE_SHA256 = (
    "565f305b4498f045e7fb40821e5ba30902ca56b0a532d299a96d6c8a1e595d50"
)
PRE_K3_WIRE_FIX_GLOBAL_LEAD_REVISION = "dfd43c4534ba1cc7be89ccbcce2bc4595f052fa0"
PRE_K3_WIRE_FIX_GLOBAL_LEAD_TREE_SHA256 = (
    "dd652b00b68a51273470ad4d3924454255d9ab5260da743fa2aa6bf2a7396627"
)
STOCK_77EC_GLOBAL_LEAD_REVISION = "77ec0c8ec7a2c86450f5dcaca8796fcfab12d1ac"
STOCK_77EC_GLOBAL_LEAD_TREE_SHA256 = (
    "68619d80e3dc7283aec38399961d7cb2267292f01d9975a61f4b9ac59418d12d"
)
STOCK_CONSULTANT_REVISION = "e55b2466281ecc50ad2a940a4de14a5ea90fb98c^"
STOCK_CONSULTANT_TREE_SHA256 = (
    "33998c6a60b442c09957d3edef914daa02d718eafa5f881473ce017fb29a4bd9"
)
E55B_STOCK_CONSULTANT_REVISION = "e55b2466281ecc50ad2a940a4de14a5ea90fb98c"
E55B_STOCK_CONSULTANT_TREE_SHA256 = (
    "f3d56fa8d361acf65d6624242c7cc61007bb8332fe6531dabc7766db940a9c5b"
)
STOCK_CONSULTANT_PRIORS = (
    pytest.param(
        STOCK_CONSULTANT_REVISION,
        STOCK_CONSULTANT_TREE_SHA256,
        id="pre-e55-parent",
    ),
    pytest.param(
        E55B_STOCK_CONSULTANT_REVISION,
        E55B_STOCK_CONSULTANT_TREE_SHA256,
        id="e55b2466",
    ),
)
PARTIAL_KIMI_LUNA_GLOBAL_LEAD_TREE_SHA256 = (
    "006161c105d8fcaaa3e9ae891e8b14e42ca170c026445062f983884a9296a3c6"
)
PRE_DIAGNOSTIC_GLOBAL_LEAD_TREE_SHA256 = (
    "03a7d0587eef6c8997e1f78136510d8ca01c61e9d1d06290fe453e34dafbb435"
)
PRE_PUBLIC_CAPTURE_GLOBAL_LEAD_TREE_SHA256 = (
    "793045007f143b502991ef71a3273f64aa62757115b2eed033a267c4d44bf79f"
)
PRE_CHILD_NONZERO_GLOBAL_LEAD_TREE_SHA256 = (
    "0c8cf87923774de9e345a72e071600d05a19b01e588f5f7acd053a6398e2f81e"
)
PARTIAL_PUSH_GATE_GLOBAL_LEAD_REVISION = (
    "06b1838500fa9c656e13565698f517e5f9ce4eca"
)
PARTIAL_PUSH_GATE_OVERLAY_REVISION = "128aa1572aad11665b836e121d84c04c63e35dfd"
PARTIAL_PUSH_GATE_GLOBAL_LEAD_TREE_SHA256 = (
    "bc0e280d4319f71078daae8476015d6d80a9ce15ffe7a05ffc2c2438875bae88"
)
CURRENT_HYBRID_GLOBAL_LEAD_TREE_SHA256 = (
    "a4afc1fe35ddb5b0417f3ba8c170dceeeef61e95a7eb0b4e617bd28db271a2ff"
)
CURRENT_HYBRID_GLOBAL_LEAD_REVISION = (
    "3dadb8b66e4580df929fecdc5d8d9bf20dcb2c59"
)
PRE_ZOMBIE_CENSUS_GLOBAL_LEAD_REVISION = (
    "448e8c5ac3ba587d6b828ded30db131eece167ac"
)
PRE_ZOMBIE_CENSUS_GLOBAL_LEAD_TREE_SHA256 = (
    "0da7db4510b37eac407ad9577ff171fbaa86985e30a53f341b00f05aeb433975"
)
PRE_COMBINED_HOTFIX_GLOBAL_LEAD_REVISION = (
    "1a56f81fb364b02e0b5e8318343133f077cbb0af"
)
PRE_COMBINED_HOTFIX_GLOBAL_LEAD_TREE_SHA256 = (
    "1e4bdc38283d81f2901a3b089c13fc9a0d10946605b1900ae15006cd42534dc6"
)
PRE_FINAL_REVIEW_GLOBAL_LEAD_REVISION = (
    "7192c9144435e7a6b326446a4c7e678d98a2d875"
)
PRE_FINAL_REVIEW_GLOBAL_LEAD_TREE_SHA256 = (
    "1f870106837564449117d07d4e51734a0a5afc3a79eb9c2e953916c64eb34afd"
)
CURRENT_HYBRID_GLOBAL_LEAD_OVERLAYS = {
    "external-dispatch.md": (
        "e55b2466281ecc50ad2a940a4de14a5ea90fb98c",
        "src.codex/skills/lead/external-dispatch.md",
    ),
    "scripts/check-work-items-state.py": (
        "3cef867b52e59093ec7c445fb5ae3afc560f5233",
        "scripts/check-work-items-state.py",
    ),
    "scripts/mutate-work-item.py": (
        "7872d36d1019d1ac8c2e1615a9f9dbde47395815",
        "scripts/mutate-work-item.py",
    ),
    "scripts/validate-work-item-state.py": (
        "a8abf6330912a4913edb379df1676a18409df678",
        "scripts/validate-work-item-state.py",
    ),
}
PROVIDER_AUTH_BASELINE_STAGED_LEAD_OVERLAYS = {
    "external-dispatch.md": ("8f92dc73", "src.codex/skills/lead/external-dispatch.md"),
    "scripts/provider_prompt.py": ("8f92dc73", "scripts/provider_prompt.py"),
    "shared/provider-prompt-projections.v1.json": (
        "8f92dc73",
        "shared/provider-prompt-projections.v1.json",
    ),
}
PRE_REBASE_FIXTURE_ROOT = (
    ROOT / "tests" / "fixtures" / "global-lead-priors" / "pre-rebase"
)
ADDITIONAL_STOCK_SKILL_FIXTURE_ROOT = (
    ROOT / "tests" / "fixtures" / "canonical-skill-priors"
)
# Exact bytes for the two staged destinations changed after the accepted
# historical trees were observed. Base64 preserves their final-newline state.
PRE_REBASE_STAGED_LEAD_OVERLAYS = {
    "scripts/agents-mode-reminder.py": base64.b64decode(
        b"IyEvdXNyL2Jpbi9lbnYgcHl0aG9uMwoiIiJTZXNzaW9uU3RhcnQgaG9vayB0aGF0IHJlLWluamVjdHMgdGhlIGFj"
        b"dGl2ZSBDb2RleCBkZWxlZ2F0aW9uIHBvc3R1cmUuCgpQeXRob24gaXMgdGhlIHNvbGUgcnVudGltZSBvd25lci4g"
        b"VGhpcyBwYWNrLW9ubHkgaW1wbGVtZW50YXRpb24gd2Fsa3MgdGhlCkNvZGV4IHJlYWQgb3JkZXIgKGBgLi8uYWdl"
        b"bnRzL2BgLCBgYH4vLmNvZGV4L2BgLCB0aGVuIHRoZSBzaGFyZWQgZ2xvYmFsIGZpbGUpCmFuZCBzcGVha3MgdGhl"
        b"IHJvbGUvc2tpbGwtYWN0aXZhdGlvbiBpZGlvbS4gVGhlIENsYXVkZSBpbXBsZW1lbnRhdGlvbiBpcwppbnRlbnRp"
        b"b25hbGx5IHNlcGFyYXRlIGJlY2F1c2UgaXRzIHJlYWQgb3JkZXIgYW5kIEFnZW50LXRvb2wgdm9jYWJ1bGFyeSBk"
        b"aWZmZXIuCmBgZGVsZWdhdGlvbk1vZGVgYCBpcyBub3QgYSBDb2RleCBDTEkgYnVpbHQtaW4sIHNvIHRoaXMgaG9v"
        b"ayBtYWtlcyB0aGUgcmVzb2x2ZWQKYGBmb3JjZWBgIG9yIGBgYXV0b2BgIHBvc3R1cmUgdmlzaWJsZSB0byB0aGUg"
        b"c2Vzc2lvbi4KCkNPTkRJVElPTkFMIEJZIERFU0lHTjogZW1pdHMgYW4gSU1QRVJBVElWRSBkaXJlY3RpdmUgT05M"
        b"WSB3aGVuIHRoZSBlZmZlY3RpdmUKZGVsZWdhdGlvbk1vZGUgaXMgZm9yY2Ugb3IgYXV0bzsgU0lMRU5UIG9uIG1h"
        b"bnVhbCBhbmQgb24gdGhlIG5vLWZpbGUvCnVucmVzb2x2ZWQgc3RhdGUgKGZhaWwtc2FmZSkuIFRoZSBzaWxlbmNl"
        b"IGlzIGxvYWQtYmVhcmluZyAtLSB0aGUgYmxvY2sKYXBwZWFycyBvbmx5IHdoZW4gZGVsZWdhdGlvbiBpcyBvcGVy"
        b"YXRpdmUuCgpTRUxGLUNPTlRBSU5FRCBmaXJzdC1tYXRjaCByZWFkIG9mIHRoZSBkb2N1bWVudGVkIHJlYWQtb3Jk"
        b"ZXIuIFRoZSBpbnN0YWxsZWQKcmVzb2x2ZXIgc2VydmVzIG90aGVyIHBvbGljeSBjb25zdW1lcnM7IHRoaXMgaG9v"
        b"ayBkZWxpYmVyYXRlbHkgZG9lcyBub3QgaW1wb3J0Cml0IHNvIGl0cyBTZXNzaW9uU3RhcnQgcGF0aCBoYXMgbm8g"
        b"cmVzb2x2ZXIgZGVwZW5kZW5jeSBvciBmYWlsdXJlIGNvdXBsaW5nLgpGb3JjZS9hdXRvIGFyZSBhbHdheXMgZmls"
        b"ZS1leHBsaWNpdCwgYW5kIG5vIGZpbGUgYW55d2hlcmUgbWVhbnMgdGhlIHBhY2sgaXMKbm90IGluc3RhbGxlZCBo"
        b"ZXJlIC8gdGhlIGNvbmZpZyB3YXMgcmVtb3ZlZCwgc28gdGhpcyBkb2VzIE5PVCBpbmplY3QgYQpzdGFuZGluZyBk"
        b"aXJlY3RpdmUgaW50byBhbiBhcmJpdHJhcnkgZGlyZWN0b3J5IC0tIHRoZSBkZWZhdWx0cy9ub3JtYWxpemVyCmxh"
        b"eWVycyBzdGF5IG91dCBvZiBzY29wZSBvbiBwdXJwb3NlOgogIC4vLmFnZW50cy8uYWdlbnRzLW1vZGUueWFtbCAt"
        b"PiAuLy5hZ2VudHMvLmFnZW50cy1tb2RlIC0+CiAgfi8uY29kZXgvLmFnZW50cy1tb2RlLnlhbWwgLT4gfi8uY29k"
        b"ZXgvLmFnZW50cy1tb2RlIC0+IH4vLmFnZW50cy1tb2RlLnlhbWwKICBGaXJzdCBmaWxlIERFRklOSU5HIGRlbGVn"
        b"YXRpb25Nb2RlIHdpbnM7IG5vbmUgLT4gdW5yZXNvbHZlZCAtPiBzaWxlbnQuCgpObyBzdGRpbiBkZXBlbmRlbmN5"
        b"OiB0aGlzIGhvb2sgbmV2ZXIgcmVhZHMgaXRzIG93biBTZXNzaW9uU3RhcnQgZW52ZWxvcGUgLS0KY3dkIGNvbWVz"
        b"IGZyb20gdGhlIHByb2Nlc3MncyB3b3JraW5nIGRpcmVjdG9yeSBhbmQgaG9tZSBmcm9tIFVTRVJQUk9GSUxFL0hP"
        b"TUUsCm5vdCBmcm9tIGFuIGVudmVsb3BlIGZpZWxkLgpGYWlsLW9wZW46IGFueSBlcnJvciB5aWVsZHMgInVucmVz"
        b"b2x2ZWQiIChzaWxlbnQpIGFuZCB0aGlzIGFsd2F5cyBleGl0cyAwLgoiIiIKZnJvbSBfX2Z1dHVyZV9fIGltcG9y"
        b"dCBhbm5vdGF0aW9ucwoKaW1wb3J0IG9zCmltcG9ydCByZQppbXBvcnQgc3lzCmZyb20gcGF0aGxpYiBpbXBvcnQg"
        b"UGF0aAoKc3lzLnBhdGguaW5zZXJ0KDAsIG9zLnBhdGguZGlybmFtZShvcy5wYXRoLmFic3BhdGgoX19maWxlX18p"
        b"KSkKZnJvbSBob29rX2NvbW1vbiBpbXBvcnQgZW1pdF9zZXNzaW9uX3N0YXJ0X2NvbnRleHQKCiMgU3RyaXAgdGhl"
        b"IGBkZWxlZ2F0aW9uTW9kZTpgIGtleSBwcmVmaXggY2FzZS1zZW5zaXRpdmVseTsgYERlbGVnYXRpb25Nb2RlOmAK"
        b"IyBtdXN0IG5vdCBtYXRjaC4KX0tFWV9SRSA9IHJlLmNvbXBpbGUociJeZGVsZWdhdGlvbk1vZGU6XHMqIikKIyBB"
        b"IFdISVRFU1BBQ0UtcHJlY2VkZWQgJyAjLi4uJyBjb21tZW50IG9ubHksIHNvIGEgbGl0ZXJhbCB2YWx1ZSBsaWtl"
        b"CiMgJ2ZvcmNlI3gnIHN0YXlzIGludGFjdCAobm8gcHJlY2VkaW5nIHdoaXRlc3BhY2UgLT4gbm90IGEgY29tbWVu"
        b"dCAtPiBzdGF5cwojIGxpdGVyYWwgLT4gdW5yZWNvZ25pemVkIC0+IHNpbGVudCkuCl9DT01NRU5UX1JFID0gcmUu"
        b"Y29tcGlsZShyIlxzKyMuKiQiKQoKRk9SQ0VfQ09OVEVYVCA9ICgKICAgICdbRGVsZWdhdGlvbiBwb3N0dXJlIC0g"
        b"cmUtc2hvd24gYXQgc2Vzc2lvbiBzdGFydCBhbmQgYWZ0ZXIgZXZlcnkgY29tcGFjdGlvbl1cbkVmZmVjdGl2ZSBk"
        b"ZWxlZ2F0aW9uTW9kZTogRk9SQ0UuIFNUQU5ESU5HIElOU1RSVUNUSU9OLCBub3QgYWR2aXNvcnk6IGF0IHRoZSBG"
        b"SVJTVCBkZWNpc2lvbiBwb2ludCBvZiBhbnkgbm9uLXRyaXZpYWwgdGFzayAobXVsdGktc3RlcCBpbXBsZW1lbnRh"
        b"dGlvbiwgZGVzaWduLCByZXNlYXJjaCwgcmV2aWV3LCBidWctZml4KSwgU1RPUCAtIGhvbGQgdGhlICRsZWFkIG9y"
        b"Y2hlc3RyYXRpb24gcm9sZSBpbiBUSElTIHNlc3Npb24sIGNsYXNzaWZ5IHRoZSB0YXNrLCBwaWNrIHRoZSB0ZWFt"
        b"IHRlbXBsYXRlLCBhbmQgYWN0aXZhdGUgdGhlIG1hdGNoaW5nIHNwZWNpYWxpc3Qgcm9sZS9za2lsbCBwZXIgc3Rh"
        b"Z2UgKCRsZWFkIGlzIHRoZSByb2xlIHlvdSBob2xkLCBub3QgYSBzdWJhZ2VudCB5b3Ugc3Bhd24pLiBEb2luZyBz"
        b"dWJzdGFudGlhbCB3b3JrIGlubGluZSB3aGVuIGEgbWF0Y2hpbmcgc3BlY2lhbGlzdCBhbmQgYSB2aWFibGUgdG9v"
        b"bCBwYXRoIGV4aXN0IHZpb2xhdGVzIHRoZSBhY3RpdmUgcG9zdHVyZS4gV2hlbiB5b3UgbGF1bmNoIGFueSBleHRl"
        b"cm5hbCBwcm92aWRlciAoY29uc3VsdGFudCAvIENvZGV4IC8gQ2xhdWRlKSBhcyAkbGVhZCwgdGFrZSB0aGUgbGF1"
        b"bmNoIGZsYWdzIGZyb20gc2tpbGxzL2xlYWQvZXh0ZXJuYWwtZGlzcGF0Y2gubWQgLSBmaWxlLWJhc2VkIHByb21w"
        b"dCwgZXhwbGljaXQgbW9kZWwrZWZmb3J0LCBydW4tY29tcGxldGlvbiBvcmFjbGUsIHN0YWxsIHBvbGljeSAtIG5l"
        b"dmVyIGltcHJvdmlzZSB0aGVtIGZyb20gbWVtb3J5LiBNYWludGFpbiB3b3JrLWl0ZW1zLyByZWNvdmVyeSBzdGF0"
        b"ZSBmb3IgbXVsdGktc3RhZ2UgY2hhaW5zLiBUaGlzIFNUSUxMIEFQUExJRVMgQUZURVIgQ09NUEFDVElPTi4nCikK"
        b"QVVUT19DT05URVhUID0gKAogICAgJ1tEZWxlZ2F0aW9uIHBvc3R1cmUgLSByZS1zaG93biBhdCBzZXNzaW9uIHN0"
        b"YXJ0IGFuZCBhZnRlciBldmVyeSBjb21wYWN0aW9uXVxuRWZmZWN0aXZlIGRlbGVnYXRpb25Nb2RlOiBBVVRPLiBI"
        b"b2xkaW5nIHRoZSAkbGVhZCBvcmNoZXN0cmF0aW9uIHJvbGUgaW4gVEhJUyBzZXNzaW9uIGFuZCBhY3RpdmF0aW5n"
        b"IHRoZSBtYXRjaGluZyBzcGVjaWFsaXN0IHJvbGUvc2tpbGwgcGVyIHN0YWdlIGlzIHRoZSBERUZBVUxUIGZvciBh"
        b"bnkgbm9uLXRyaXZpYWwgdGFzayAobXVsdGktc3RlcCBpbXBsZW1lbnRhdGlvbiwgZGVzaWduLCByZXNlYXJjaCwg"
        b"cmV2aWV3LCBidWctZml4KSAtIGRvIGl0IHVubGVzcyB0aGUgdGFzayBpcyB0cml2aWFsIG9yIHlvdSByZWNvcmQg"
        b"d2h5IGlubGluZSBpcyBiZXR0ZXIuICRsZWFkIGlzIHRoZSByb2xlIHlvdSBob2xkLCBub3QgYSBzdWJhZ2VudCB5"
        b"b3Ugc3Bhd24uIFdoZW4geW91IGxhdW5jaCBhbnkgZXh0ZXJuYWwgcHJvdmlkZXIgKGNvbnN1bHRhbnQgLyBDb2Rl"
        b"eCAvIENsYXVkZSkgYXMgJGxlYWQsIHRha2UgdGhlIGxhdW5jaCBmbGFncyBmcm9tIHNraWxscy9sZWFkL2V4dGVy"
        b"bmFsLWRpc3BhdGNoLm1kIC0gZmlsZS1iYXNlZCBwcm9tcHQsIGV4cGxpY2l0IG1vZGVsK2VmZm9ydCwgcnVuLWNv"
        b"bXBsZXRpb24gb3JhY2xlLCBzdGFsbCBwb2xpY3kgLSBuZXZlciBpbXByb3Zpc2UgdGhlbSBmcm9tIG1lbW9yeS4g"
        b"TWFpbnRhaW4gd29yay1pdGVtcy8gcmVjb3Zlcnkgc3RhdGUgZm9yIG11bHRpLXN0YWdlIGNoYWlucy4gVGhpcyBT"
        b"VElMTCBBUFBMSUVTIEFGVEVSIENPTVBBQ1RJT04uJwopCgoKZGVmIF9nZXRfZGVsZWdhdGlvbl9tb2RlKCkgLT4g"
        b"c3RyOgogICAgIiIiRmlyc3QtbWF0Y2ggcmVhZCBhY3Jvc3MgdGhlIGRvY3VtZW50ZWQgQ29kZXgtbGluZSByZWFk"
        b"LW9yZGVyLiBSZXR1cm5zCiAgICB0aGUgbG93ZXJjYXNlZCwgdHJpbW1lZCB2YWx1ZSBvZiB0aGUgZmlyc3QgZmls"
        b"ZSdzIHRvcC1sZXZlbAogICAgYGRlbGVnYXRpb25Nb2RlOmAgbGluZSwgb3IgInVucmVzb2x2ZWQiIGlmIG5vIGNh"
        b"bmRpZGF0ZSBmaWxlIGRlZmluZXMgb25lLgogICAgUmVhZCBlcnJvcnMgcmVtYWluIGZhaWwtb3BlbiBwZXIgY2Fu"
        b"ZGlkYXRlIGFuZCBjb250aW51ZSB0byB0aGUgbmV4dCBwYXRoLiIiIgogICAgIyBVU0VSUFJPRklMRSBmaXJzdCwg"
        b"dGhlbiBIT01FIGtlZXBzIHRoZSBvd25lciBXaW5kb3dzLWF3YXJlIHdoaWxlIHJlbWFpbmluZwogICAgIyBwb3J0"
        b"YWJsZSB0byBQT1NJWCBlbnZpcm9ubWVudHMuCiAgICBob21lX2RpciA9IG9zLmVudmlyb24uZ2V0KCJVU0VSUFJP"
        b"RklMRSIpIG9yIG9zLmVudmlyb24uZ2V0KCJIT01FIikgb3IgIiIKCiAgICBjYW5kaWRhdGVzID0gWwogICAgICAg"
        b"IFBhdGguY3dkKCkgLyAiLmFnZW50cyIgLyAiLmFnZW50cy1tb2RlLnlhbWwiLAogICAgICAgIFBhdGguY3dkKCkg"
        b"LyAiLmFnZW50cyIgLyAiLmFnZW50cy1tb2RlIiwKICAgIF0KICAgIGlmIGhvbWVfZGlyOgogICAgICAgIGhvbWUg"
        b"PSBQYXRoKGhvbWVfZGlyKQogICAgICAgIGNhbmRpZGF0ZXMuZXh0ZW5kKFsKICAgICAgICAgICAgaG9tZSAvICIu"
        b"Y29kZXgiIC8gIi5hZ2VudHMtbW9kZS55YW1sIiwKICAgICAgICAgICAgaG9tZSAvICIuY29kZXgiIC8gIi5hZ2Vu"
        b"dHMtbW9kZSIsCiAgICAgICAgICAgIGhvbWUgLyAiLmFnZW50cy1tb2RlLnlhbWwiLAogICAgICAgIF0pCgogICAg"
        b"Zm9yIGNhbmRpZGF0ZSBpbiBjYW5kaWRhdGVzOgogICAgICAgIHRyeToKICAgICAgICAgICAgaWYgbm90IGNhbmRp"
        b"ZGF0ZS5pc19maWxlKCk6CiAgICAgICAgICAgICAgICBjb250aW51ZQogICAgICAgICAgICB0ZXh0ID0gY2FuZGlk"
        b"YXRlLnJlYWRfdGV4dChlbmNvZGluZz0idXRmLTgiLCBlcnJvcnM9InJlcGxhY2UiKQogICAgICAgIGV4Y2VwdCBF"
        b"eGNlcHRpb246CiAgICAgICAgICAgIGNvbnRpbnVlCiAgICAgICAgbGluZSA9IE5vbmUKICAgICAgICBmb3IgcmF3"
        b"X2xpbmUgaW4gdGV4dC5zcGxpdGxpbmVzKCk6CiAgICAgICAgICAgIGlmIHJhd19saW5lLnN0YXJ0c3dpdGgoImRl"
        b"bGVnYXRpb25Nb2RlOiIpOgogICAgICAgICAgICAgICAgbGluZSA9IHJhd19saW5lCiAgICAgICAgICAgICAgICBi"
        b"cmVhawogICAgICAgIGlmIGxpbmUgaXMgTm9uZToKICAgICAgICAgICAgY29udGludWUKICAgICAgICB2YWx1ZSA9"
        b"IF9LRVlfUkUuc3ViKCIiLCBsaW5lLCBjb3VudD0xKQogICAgICAgIHZhbHVlID0gX0NPTU1FTlRfUkUuc3ViKCIi"
        b"LCB2YWx1ZSkKICAgICAgICByZXR1cm4gdmFsdWUuc3RyaXAoKS5sb3dlcigpCgogICAgcmV0dXJuICJ1bnJlc29s"
        b"dmVkIgoKCmRlZiBtYWluKCkgLT4gaW50OgogICAgdHJ5OgogICAgICAgIG1vZGUgPSBfZ2V0X2RlbGVnYXRpb25f"
        b"bW9kZSgpCiAgICBleGNlcHQgRXhjZXB0aW9uOgogICAgICAgIG1vZGUgPSAidW5yZXNvbHZlZCIKICAgIGlmIG1v"
        b"ZGUgPT0gImZvcmNlIjoKICAgICAgICBlbWl0X3Nlc3Npb25fc3RhcnRfY29udGV4dChGT1JDRV9DT05URVhUKQog"
        b"ICAgZWxpZiBtb2RlID09ICJhdXRvIjoKICAgICAgICBlbWl0X3Nlc3Npb25fc3RhcnRfY29udGV4dChBVVRPX0NP"
        b"TlRFWFQpCiAgICAjIG1hbnVhbCB2YWx1ZSwgdW5yZXNvbHZlZCwgb3IgZW1wdHkgLT4gc2lsZW50CiAgICByZXR1"
        b"cm4gMAoKCmlmIF9fbmFtZV9fID09ICJfX21haW5fXyI6CiAgICBzeXMuZXhpdChtYWluKCkpCg=="
    ),
    "shared/orchestrarium-role-manifest.json": base64.b64decode(
        b"ewogICJzY2hlbWFWZXJzaW9uIjogMSwKICAicGFja1JldmlzaW9uIjogIjEueC1uYXRpdmUtcm9sZS1wb2xpY3kt"
        b"djEiLAogICJwb2xpY3lTaGEyNTYiOiAiYTc5OGJmNDUzMjQ3MGVkOTgyZmY5OGNiNDUwMGQ0MDM3YmJhNmYxNTFl"
        b"NjBjMjVjMmI1YTU3MmJlZDU1MGM1NiIsCiAgInJvbGVzIjogewogICAgImFsZ29yaXRobS1zY2llbnRpc3QiOiB7"
        b"CiAgICAgICJyZWxhdGl2ZVBhdGgiOiAiYWxnb3JpdGhtLXNjaWVudGlzdC50b21sIiwKICAgICAgInNoYTI1NiI6"
        b"ICIxYmM3YzYwYjMwZjFiYjM2MGE1MDJlZTk1NWU0MTUxM2E4MGQzZTNmOWUyMjJlNWE2NzM4MTdhN2U0MjFjOGJk"
        b"IgogICAgfSwKICAgICJhbmFseXN0IjogewogICAgICAicmVsYXRpdmVQYXRoIjogImFuYWx5c3QudG9tbCIsCiAg"
        b"ICAgICJzaGEyNTYiOiAiNDIyY2QyY2IyY2M1YmQ2ZTIzYTBlOTdjZmFiZjUzNTNkOTlkYjMxZDQ0MTk2Njk2ZDZl"
        b"OGNiNzNhYTdlYjk1YSIKICAgIH0sCiAgICAiYXJjaGl0ZWN0IjogewogICAgICAicmVsYXRpdmVQYXRoIjogImFy"
        b"Y2hpdGVjdC50b21sIiwKICAgICAgInNoYTI1NiI6ICJiY2RkODNhYmNiM2U1ZDk5ZTBkZDA5NjNkNjIyYjQ3NWVh"
        b"MTFkNDUwYmIxNmYxYWYxYmM5Mzg1NTg5MWZmNGZiIgogICAgfSwKICAgICJhcmNoaXRlY3R1cmUtcmV2aWV3ZXIi"
        b"OiB7CiAgICAgICJyZWxhdGl2ZVBhdGgiOiAiYXJjaGl0ZWN0dXJlLXJldmlld2VyLnRvbWwiLAogICAgICAic2hh"
        b"MjU2IjogIjIzOWE5MWVmMzViNTRjYzY0MDM3MjEzMmI1MTY2MmJjYmUwZGE4OGRkZWQ2OGZmNTNkMzM5NjIxNjg5"
        b"ZGY4YzMiCiAgICB9LAogICAgImJhY2tlbmQtZW5naW5lZXIiOiB7CiAgICAgICJyZWxhdGl2ZVBhdGgiOiAiYmFj"
        b"a2VuZC1lbmdpbmVlci50b21sIiwKICAgICAgInNoYTI1NiI6ICI0YzZlMDYzMDBlOGM5MDYxMzBjOTAwYmQ4YTE3"
        b"MzhkMTdjMjExNWNhNjQ3Yjc3YTI1OWI5NDUzMWY1Zjg3NjlhIgogICAgfSwKICAgICJjb21wdXRhdGlvbmFsLXNj"
        b"aWVudGlzdCI6IHsKICAgICAgInJlbGF0aXZlUGF0aCI6ICJjb21wdXRhdGlvbmFsLXNjaWVudGlzdC50b21sIiwK"
        b"ICAgICAgInNoYTI1NiI6ICI3ZGRjZmIzYWZlNmQ5MDMyZDAzZDNkYTY0Njg2NjJhOTYxODE5Y2VhY2Y1MjUyY2Fj"
        b"Y2NjZmM2OTc0NGNjOWQzIgogICAgfSwKICAgICJkZWZhdWx0IjogewogICAgICAicmVsYXRpdmVQYXRoIjogImRl"
        b"ZmF1bHQudG9tbCIsCiAgICAgICJzaGEyNTYiOiAiYjM4YmI3YzRhMDVmOTNiZDU0YTExYzlhMDZkMmJiZGFlOWJl"
        b"ZDM1M2RiNGZkZDJmNDJiNGFiYjlmZDNiYTNlMSIKICAgIH0sCiAgICAiZXhwbG9yZXIiOiB7CiAgICAgICJyZWxh"
        b"dGl2ZVBhdGgiOiAiZXhwbG9yZXIudG9tbCIsCiAgICAgICJzaGEyNTYiOiAiMjgyZjY4ZTBlNTA5ZmEyZDllYjJi"
        b"Zjc3ZTg0MWY2OTgwOWY2N2ZjMTlkM2NiNzRlZWUzZTkzMjQ3NjczZTVkYiIKICAgIH0sCiAgICAia25vd2xlZGdl"
        b"LWFyY2hpdmlzdCI6IHsKICAgICAgInJlbGF0aXZlUGF0aCI6ICJrbm93bGVkZ2UtYXJjaGl2aXN0LnRvbWwiLAog"
        b"ICAgICAic2hhMjU2IjogIjA2NzJiOTk0ZjQxZDNhNWQ2OWJhMmY4ZDcxOWQxOWNiOTBlOWQ3ZmU2ZWQ3MjBjOWRh"
        b"YTA5MDA5ZWM0ZjIzNDkiCiAgICB9LAogICAgIm1lY2hhbmljYWwtc2NvdXQiOiB7CiAgICAgICJyZWxhdGl2ZVBh"
        b"dGgiOiAibWVjaGFuaWNhbC1zY291dC50b21sIiwKICAgICAgInNoYTI1NiI6ICIxZDJkNmM0ZmI2NDYzNzEwZjhl"
        b"NmNkMWJkYTE3MzhmODIzMGNkNzQ4M2I5ZjM0MmY3ZjBlNTAwZTVhYzViYjY3IgogICAgfSwKICAgICJtZWNoYW5p"
        b"Y2FsLXdvcmtlciI6IHsKICAgICAgInJlbGF0aXZlUGF0aCI6ICJtZWNoYW5pY2FsLXdvcmtlci50b21sIiwKICAg"
        b"ICAgInNoYTI1NiI6ICJjY2Y3NjMzZjU1Mzg5Y2U4MjZjZDg0ODY5MjI3N2I3NjRhNTU5ZWUwYjdiYzgxNDAyZDU2"
        b"NTdiOTA4MTY1ODY5IgogICAgfSwKICAgICJwbGFubmVyIjogewogICAgICAicmVsYXRpdmVQYXRoIjogInBsYW5u"
        b"ZXIudG9tbCIsCiAgICAgICJzaGEyNTYiOiAiMDUzMTY4N2MwYTEwNmMwZjQ0ZDRjMGJiNWM1ZTRiOThjMjYxOGM5"
        b"OTM4N2JiYmM0NDNlYjEwOGI0ZWVkOTMwZiIKICAgIH0sCiAgICAicGxhdGZvcm0tZW5naW5lZXIiOiB7CiAgICAg"
        b"ICJyZWxhdGl2ZVBhdGgiOiAicGxhdGZvcm0tZW5naW5lZXIudG9tbCIsCiAgICAgICJzaGEyNTYiOiAiY2ViMzBm"
        b"Y2Q1NDZiZWY4MjA0NWY3YjNjM2I0OGUzOWY5OGFlODNlYmJlYTE3YTZjNTIxMGMyYjQ2Y2IyMTQwZCIKICAgIH0s"
        b"CiAgICAicWEtZW5naW5lZXIiOiB7CiAgICAgICJyZWxhdGl2ZVBhdGgiOiAicWEtZW5naW5lZXIudG9tbCIsCiAg"
        b"ICAgICJzaGEyNTYiOiAiNjVhNWRkMDNhNDE5NmE5OWQwMGM3MmM4MWFhOThlMTQ3MGVlYWMwYzZkOWI0NTNhMzE0"
        b"N2M4MzZjMTQ2Y2E5YiIKICAgIH0sCiAgICAic2VjdXJpdHktZW5naW5lZXIiOiB7CiAgICAgICJyZWxhdGl2ZVBh"
        b"dGgiOiAic2VjdXJpdHktZW5naW5lZXIudG9tbCIsCiAgICAgICJzaGEyNTYiOiAiNTQxMTdkZWNkZmNmOWJmZjU3"
        b"NmUyM2QzMWExZGM2YWEyZDJmNGZkMGQ0OTg4MjBmOWMxMjQ0YjY3NDJmNzhmOSIKICAgIH0sCiAgICAic2VjdXJp"
        b"dHktcmV2aWV3ZXIiOiB7CiAgICAgICJyZWxhdGl2ZVBhdGgiOiAic2VjdXJpdHktcmV2aWV3ZXIudG9tbCIsCiAg"
        b"ICAgICJzaGEyNTYiOiAiMGY5Yjc1NzEzMTI4ODg1YjhkYjg2YjMyYTllY2IzZTc1NmIwMDIyYWRkMTY5YTg5ZmMx"
        b"MGQ2MTU3NDU0NDVmMSIKICAgIH0sCiAgICAid29ya2VyIjogewogICAgICAicmVsYXRpdmVQYXRoIjogIndvcmtl"
        b"ci50b21sIiwKICAgICAgInNoYTI1NiI6ICI5NjBmMGM2MTdiNGI1ODU2NTg1ZmEzZjNhZmFjN2UwZWY5ZmI5OWJm"
        b"YzE5NzdiNzRmZTZkZDk5NjI2YjJhNTdkIgogICAgfQogIH0KfQo="
    ),
}
STOCK_8521_CANONICAL_SKILL_TREE_SHA256 = {
    "consultant": "57da94b645283cc695ff8f82a108a6f490f0036a564be76c22f663ba6afa3a38",
    "design-panel": "ac107c9d6c4a3833d0af90756c8b560f7ca4c4dfcc3d14d6a14faae1530f859f",
    "external-brigade": "7a931c84bc3b72a85afcee813e9bb4705923301b6644892dcd291ffacb837113",
    "external-reviewer": "9bd5a9811b6573a6d6697f627caee4ebe975460de0118e22bd9e8cd7bb76e0c5",
    "external-worker": "170628e06c5866ddc9d9e4d5aaabbb1422f57ab067ce0085bd99960f34d53c3c",
    "init-project": "4f0a5fdb8af605dc10cb2044f33db3339b410feaf23764cc395f9c3feaaf6353",
    "lead": "b7d78ee5082cce97e0cb2fcb59ee2e5712617b43212a1c6c3199370797f9aa21",
    "review-loop": "2d78f499bf7b4bb2e6dafdf0ef875f2d9d39448c28df6f3835bc8153fba02ce0",
    "second-opinion": "f9a2114c8baead9ec8a259288ff74e157af60864c9f3d70ba0bcc52154b2b4b6",
}
STOCK_7872_CANONICAL_SKILL_TREE_SHA256 = {
    "consultant": "f1a23b5ceaa93c29cf0c5f9c9eec8c5997a7b4339fcd90abd13798df77e60793",
    "design-panel": "685b75f5726dd16dbcf2b5fb3238652b8564242e5b66f0daf2b582267905f67b",
    "init-project": "cd5bc7386f286393ee8dab782ed603fff7ad61e8c828f34cca102a3a5e2aba9f",
    "manual-repo-transfer": "03c0c2fd12a8273f8325fb145dc2b8e9e97502e497649fc2d474988a9f95070b",
    "review-loop": "d956cf70db42a7c936d21984fe6aeb83748de02c544eec56ca54971629f85f7e",
    "second-opinion": "b82628910567799a6f03962f3ec0289cb47b4607093c074466b1a2656b53f432",
}
ADDITIONAL_STOCK_SKILL_PRIORS = {
    "architect": (
        "4e193102e852b25437b3244a4896b31a5e8fc6c5",
        "51612976f7fde46e3046222d607435b2fba5ef27ede636a06a80cb86c6fc7f5e",
    ),
    "architecture-reviewer": (
        "4e193102e852b25437b3244a4896b31a5e8fc6c5",
        "19b179fe14a2bb6135e46dd7435265e7483d0bf6d5ec97b55520e39f3cbb1b4d",
    ),
    "graphics-engineer": (
        "65efb6b679d2808c5cdd3f95774a82942c65ad35",
        "e4b1294c4f2de8e31f0083500c7a7335a2abece08f801bb4e60e715eed3e081d",
    ),
    "github-pr-review-bot": (
        "2dbf91b3e96e9dbf2bf785d16bf6964faf766d46",
        "d1a5bff367e42891951371faa2d66274cb34f0eb7b9c86c214376e75833f6841",
    ),
    "init-project": (
        "9831fe66b157020f90f888ec8c878887135aa776",
        "c079a182db6139257be2b7b138c6a4b28aa730747c1988d54132f8b07504dd1c",
    ),
    "manual-repo-transfer": (
        "6dbf861a4c119f59c52813a02758f14ea9050aa7",
        "45fc1efc9f0558664afb1f386c5fc7ac2692a607fb8c7be6265b2cfc4d10029b",
    ),
    "second-opinion": (
        "0274b69a25e1b36f83da4c21f630d222d627c4ee",
        "fe989a918e11ff8066a0c8af54f73ba7bbf763719ea3b604ed147b79bec684d6",
    ),
    "toolchain-engineer": (
        "4e193102e852b25437b3244a4896b31a5e8fc6c5",
        "51cf24ae0699a6bb379ee6bbf7b51e2a982cba12aaeab2dc76e57d4b4ccf2a74",
    ),
    "review-loop": (
        "01a7eb0ded829233c21c588f1234f62b31308f35",
        "3e7be1c11624a0fb7beae1c286dd09a3abb4c6b1fb70d138c9bfdc77c1d8df8a",
    ),
    "visualization-engineer": (
        "65efb6b679d2808c5cdd3f95774a82942c65ad35",
        "56218f313e0ee24fc973eae8792bac0cddfd17ccab390fffb028d787cd0286f0",
    ),
}


# These entries are pinned historical source blobs, not a version-range
# approximation. The target omits the current transport set below.
PRE_RANGE_V3_STAGED_LEAD_OVERLAYS = {
    **PROVIDER_AUTH_BASELINE_STAGED_LEAD_OVERLAYS,
    "scripts/check-publication-safety.py": (
        "6850a129321288fc23538b89582cf2cfd413e48c",
        "src.codex/skills/lead/scripts/check-publication-safety.py",
    ),
    "scripts/check-git-push-gate.py": (
        "6850a129321288fc23538b89582cf2cfd413e48c",
        "src.codex/skills/lead/scripts/check-git-push-gate.py",
    ),
}
H2_STAGED_RUNTIME_OVERLAYS = {
    "scripts/check-publication-safety.py": (
        "7872d36d1019d1ac8c2e1615a9f9dbde47395815",
        "src.codex/skills/lead/scripts/check-publication-safety.py",
    ),
    "scripts/check-git-push-gate.py": (
        "7872d36d1019d1ac8c2e1615a9f9dbde47395815",
        "src.codex/skills/lead/scripts/check-git-push-gate.py",
    ),
    "scripts/resolve-agents-mode.py": (
        "ab6cd8a30557b8040b3820be3bddccdf5e4c7755",
        "scripts/resolve-agents-mode.py",
    ),
}
OBSERVED_GLOBAL_LEAD_HISTORICAL_FILES = {
    **PRE_REBASE_STAGED_LEAD_OVERLAYS,
    **H2_STAGED_RUNTIME_OVERLAYS,
    "external-dispatch.md": (
        "1641fd1c10d501d83891f1bbd27ab93a92eb03b7",
        "src.codex/skills/lead/external-dispatch.md",
    ),
    "operating-model.md": (
        "5587048312ba83ad44da8b7151ae83473932c7bc",
        "src.codex/skills/lead/operating-model.md",
    ),
    "subagent-contracts.md": (
        "1641fd1c10d501d83891f1bbd27ab93a92eb03b7",
        "src.codex/skills/lead/subagent-contracts.md",
    ),
    "scripts/agent-run-ledger.py": (
        "4faedfa13126346b1bac9fc0af49bc0ef5164a45",
        "scripts/agent-run-ledger.py",
    ),
    "scripts/validate-skill-pack.py": (
        "e7a691dea4f1d3cb154d338c63b274ebcd74ee4c",
        "src.codex/skills/lead/scripts/validate-skill-pack.py",
    ),
    "scripts/validate-work-item-state.py": (
        "4faedfa13126346b1bac9fc0af49bc0ef5164a45",
        "scripts/validate-work-item-state.py",
    ),
    "shared/schemas/agent-runs.schema.json": (
        "4faedfa13126346b1bac9fc0af49bc0ef5164a45",
        "shared/schemas/agent-runs.schema.json",
    ),
}
PRE_H2_ONLY_HISTORICAL_FILES = {
    **OBSERVED_GLOBAL_LEAD_HISTORICAL_FILES,
    "scripts/mutate-work-item.py": (
        "e7a691dea4f1d3cb154d338c63b274ebcd74ee4c",
        "scripts/mutate-work-item.py",
    ),
}
POST_7872_GLOBAL_LEAD_RUNTIME_FILES = (
    "scripts/solution_attempt/reducer.py",
    "scripts/external-role-taxonomy.v1.json",
)
OBSERVED_GLOBAL_LEAD_ABSENT_TRANSPORT_FILES = (
    "scripts/external-prompt-governance.md",
    *POST_7872_GLOBAL_LEAD_RUNTIME_FILES,
    "scripts/invoke-claude-prompt.py",
    "scripts/invoke-codex-prompt.py",
    "scripts/invoke-grok-prompt.py",
    "scripts/invoke-kimi-prompt.py",
    "scripts/provider_prompt.py",
    "scripts/validate-provider-prompt-projections.py",
    "shared/provider-prompt-projections.v1.json",
)

def _load_installer():
    spec = importlib.util.spec_from_file_location(
        "global_lead_accepted_prior_installer", INSTALLER_PATH
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _seed_revision_staged_lead(revision: str, destination: Path) -> Path:
    source = destination.parent / "historical-source"
    archive = subprocess.run(
        ["git", "archive", "--format=tar", revision],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as package:
        package.extractall(source, filter="data")

    installer_path = source / "scripts" / "production_installer.py"
    module_name = f"global_lead_historical_{revision}"
    spec = importlib.util.spec_from_file_location(module_name, installer_path)
    assert spec and spec.loader
    historical_installer = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = historical_installer
    spec.loader.exec_module(historical_installer)
    stage = historical_installer._stage_canonical_lead_tree(
        source,
        source / "src.codex" / "skills" / "lead",
        destination / "scripts",
    )
    try:
        shutil.copytree(stage.path, destination)
    finally:
        shutil.rmtree(stage.path, ignore_errors=True)
        sys.modules.pop(module_name, None)
    return destination


def _replace_with_revision_staged_lead(revision: str, destination: Path) -> Path:
    if destination.exists():
        shutil.rmtree(destination)
    return _seed_revision_staged_lead(revision, destination)


def _historical_blob(revision: str, source: str) -> bytes:
    return subprocess.run(
        ["git", "show", f"{revision}:{source}"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout


def _fixture_payloads(
    fixture_root: Path, *, expected_baseline: str
) -> dict[str, bytes]:
    manifest_path = fixture_root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert set(manifest) == {"schemaVersion", "baseline", "files"}
    assert manifest["schemaVersion"] == 1
    assert manifest["baseline"] == expected_baseline
    files = manifest["files"]
    assert isinstance(files, dict) and files
    fixture_files = {
        path.relative_to(fixture_root).as_posix()
        for path in fixture_root.rglob("*")
        if path.is_file() and path != manifest_path
    }
    assert fixture_files == set(files)

    payloads: dict[str, bytes] = {}
    for relative, expected_sha256 in files.items():
        fixture_relative = Path(relative)
        assert not fixture_relative.is_absolute()
        assert ".." not in fixture_relative.parts
        payload = (fixture_root / fixture_relative).read_bytes()
        assert hashlib.sha256(payload).hexdigest() == expected_sha256
        payloads[relative] = payload
    return payloads


def _pre_rebase_fixture_payloads() -> dict[str, bytes]:
    return _fixture_payloads(PRE_REBASE_FIXTURE_ROOT, expected_baseline="7872d36d")


def _remove_historical_members(lead: Path, relatives: tuple[str, ...]) -> None:
    for relative in relatives:
        target = lead / relative
        if not target.exists():
            continue
        target.unlink()
        parent = target.parent
        while parent != lead and not any(parent.iterdir()):
            parent.rmdir()
            parent = parent.parent


def _extract_8521_skill(name: str, destination: Path) -> Path:
    if name == "lead":
        archive = subprocess.run(
            ["git", "archive", "--format=tar", "8521b638"],
            cwd=ROOT,
            check=True,
            capture_output=True,
        ).stdout
        with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as package:
            package.extractall(destination, filter="data")
        target = destination / "installed"
        result = subprocess.run(
            [
                sys.executable,
                str(destination / "scripts" / "install-claude.py"),
                "--target",
                str(target),
                "--force",
                "--allow-unsafe-target",
                "--no-hypothesis-hook",
            ],
            cwd=destination,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        return target / ".agents" / "skills" / "lead"
    archive = subprocess.run(
        ["git", "archive", "--format=tar", "8521b638", f"src.codex/skills/{name}"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as package:
        package.extractall(destination, filter="data")
    return destination / "src.codex" / "skills" / name


def _extract_7872_skill(name: str, destination: Path) -> Path:
    archive = subprocess.run(
        [
            "git",
            "archive",
            "--format=tar",
            PRE_KIMI_GLOBAL_LEAD_REVISION,
            f"src.codex/skills/{name}",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as package:
        package.extractall(destination, filter="data")
    return destination / "src.codex" / "skills" / name


def _extract_additional_stock_skill(
    name: str, revision: str, destination: Path
) -> Path:
    fixture_root = ADDITIONAL_STOCK_SKILL_FIXTURE_ROOT / revision
    if fixture_root.is_dir():
        payloads = _fixture_payloads(fixture_root, expected_baseline=revision)
        fixture_names = {Path(relative).parts[0] for relative in payloads}
        expected_names = {
            skill_name
            for skill_name, (skill_revision, _digest) in (
                ADDITIONAL_STOCK_SKILL_PRIORS.items()
            )
            if skill_revision == revision
        }
        assert fixture_names == expected_names
        target = destination / name
        selected = {
            Path(relative).relative_to(name): payload
            for relative, payload in payloads.items()
            if Path(relative).parts[0] == name
        }
        assert selected
        for relative, payload in selected.items():
            path = target / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
        return target

    archive = subprocess.run(
        [
            "git",
            "archive",
            "--format=tar",
            revision,
            f"src.codex/skills/{name}",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as package:
        package.extractall(destination, filter="data")
    return destination / "src.codex" / "skills" / name


def _extract_stock_consultant(destination: Path, revision: str) -> Path:
    archive = subprocess.run(
        [
            "git",
            "archive",
            "--format=tar",
            revision,
            "src.codex/skills/consultant",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as package:
        package.extractall(destination, filter="data")
    return destination / "src.codex" / "skills" / "consultant"


def _tree_bytes(root: Path) -> dict[Path, bytes]:
    return {
        path.relative_to(root): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def _runtime_cache_insensitive_tree_bytes(root: Path) -> dict[Path, bytes]:
    files: dict[Path, bytes] = {}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        metadata = path.lstat()
        if (
            stat.S_ISREG(metadata.st_mode)
            and not path.is_symlink()
            and relative.suffix.casefold() == ".pyc"
            and "__pycache__" in relative.parts[:-1]
        ):
            continue
        files[relative] = path.read_bytes()
    return files


@pytest.mark.parametrize(("revision", "expected_prior"), STOCK_CONSULTANT_PRIORS)
def test_exact_stock_consultant_is_accepted_and_replaced_byte_for_byte(
    tmp_path: Path, revision: str, expected_prior: str
) -> None:
    installer = _load_installer()
    historical = _extract_stock_consultant(tmp_path / "historical", revision)
    assert installer._tree_sha256(historical) == expected_prior

    target = tmp_path / "target"
    skills_root = target / ".agents" / "skills"
    skills_root.mkdir(parents=True)
    installed = skills_root / "consultant"
    shutil.copytree(historical, installed)
    plan = installer._preflight_canonical_skills(
        ROOT / "src.codex" / "skills", skills_root, root=ROOT
    )
    try:
        selected = next(skill for skill in plan.skills if skill.name == "consultant")
        assert selected.accepted_prior == expected_prior
        owner = installer._CreateOnlyMutablePath(
            target, installer._InstallTransaction([], enabled=False), dry_run=False
        )
        installer._apply_canonical_skills_plan(plan, skills_root, owner, root=ROOT)
        assert _tree_bytes(installed) == _tree_bytes(
            ROOT / "src.codex" / "skills" / "consultant"
        )
    finally:
        installer._discard_canonical_skills_plan(plan)


@pytest.mark.parametrize(("revision", "expected_prior"), STOCK_CONSULTANT_PRIORS)
def test_stock_consultant_one_byte_drift_is_rejected(
    tmp_path: Path, revision: str, expected_prior: str
) -> None:
    installer = _load_installer()
    historical = _extract_stock_consultant(tmp_path / "historical", revision)
    assert installer._tree_sha256(historical) == expected_prior
    skills_root = tmp_path / "target" / ".agents" / "skills"
    skills_root.mkdir(parents=True)
    installed = skills_root / "consultant"
    shutil.copytree(historical, installed)
    with (installed / "SKILL.md").open("ab") as stream:
        stream.write(b"x")

    with pytest.raises(ValueError, match="E_ACCEPTED_PRIOR_COLLISION: consultant"):
        installer._preflight_canonical_skills(
            ROOT / "src.codex" / "skills", skills_root, root=ROOT
        )


@pytest.mark.parametrize(("revision", "expected_prior"), STOCK_CONSULTANT_PRIORS)
def test_stock_consultant_prior_is_rejected_for_another_skill(
    tmp_path: Path, revision: str, expected_prior: str
) -> None:
    installer = _load_installer()
    historical = _extract_stock_consultant(tmp_path / "historical", revision)
    assert installer._tree_sha256(historical) == expected_prior
    skills_root = tmp_path / "target" / ".agents" / "skills"
    skills_root.mkdir(parents=True)
    shutil.copytree(historical, skills_root / "design-panel")

    with pytest.raises(ValueError, match="E_ACCEPTED_PRIOR_COLLISION: design-panel"):
        installer._preflight_canonical_skills(
            ROOT / "src.codex" / "skills", skills_root, root=ROOT
        )


@pytest.mark.parametrize(("revision", "expected_prior"), STOCK_CONSULTANT_PRIORS)
def test_stock_consultant_transaction_abort_restores_prior(
    tmp_path: Path, revision: str, expected_prior: str
) -> None:
    installer = _load_installer()
    historical = _extract_stock_consultant(tmp_path / "historical", revision)
    assert installer._tree_sha256(historical) == expected_prior
    target = tmp_path / "target"
    skills_root = target / ".agents" / "skills"
    skills_root.mkdir(parents=True)
    installed = skills_root / "consultant"
    shutil.copytree(historical, installed)
    prior_bytes = _tree_bytes(installed)
    plan = installer._preflight_canonical_skills(
        ROOT / "src.codex" / "skills", skills_root, root=ROOT
    )
    try:
        with pytest.raises(RuntimeError, match="forced consultant rollback"):
            transaction = installer._InstallTransaction([installed], enabled=True)
            with transaction:
                owner = installer._CreateOnlyMutablePath(
                    target, transaction, dry_run=False
                )
                installer._apply_canonical_skills_plan(
                    plan, skills_root, owner, root=ROOT
                )
                raise RuntimeError("forced consultant rollback")
    finally:
        installer._discard_canonical_skills_plan(plan)

    assert _tree_bytes(installed) == prior_bytes
    assert {path.name for path in skills_root.iterdir()} == {"consultant"}


@pytest.mark.parametrize(("revision", "expected_prior"), STOCK_CONSULTANT_PRIORS)
def test_stock_consultant_second_preflight_is_noop(
    tmp_path: Path, revision: str, expected_prior: str
) -> None:
    installer = _load_installer()
    historical = _extract_stock_consultant(tmp_path / "historical", revision)
    assert installer._tree_sha256(historical) == expected_prior
    target = tmp_path / "target"
    skills_root = target / ".agents" / "skills"
    skills_root.mkdir(parents=True)
    shutil.copytree(historical, skills_root / "consultant")
    owner = installer._CreateOnlyMutablePath(
        target, installer._InstallTransaction([], enabled=False), dry_run=False
    )

    first_plan = installer._preflight_canonical_skills(
        ROOT / "src.codex" / "skills", skills_root, root=ROOT
    )
    try:
        installer._apply_canonical_skills_plan(
            first_plan, skills_root, owner, root=ROOT
        )
    finally:
        installer._discard_canonical_skills_plan(first_plan)

    before = _tree_bytes(skills_root)
    second_plan = installer._preflight_canonical_skills(
        ROOT / "src.codex" / "skills", skills_root, root=ROOT
    )
    try:
        selected = next(
            skill for skill in second_plan.skills if skill.name == "consultant"
        )
        assert selected.accepted_prior is None
        installer._apply_canonical_skills_plan(
            second_plan, skills_root, owner, root=ROOT
        )
    finally:
        installer._discard_canonical_skills_plan(second_plan)

    assert _tree_bytes(skills_root) == before


def _assert_exact_stock_skill_is_accepted_and_drift_refused(
    installer,
    tmp_path: Path,
    name: str,
    expected_prior: str,
    historical: Path,
) -> None:
    assert installer._tree_sha256(historical) == expected_prior

    skills_root = tmp_path / "target" / ".agents" / "skills"
    skills_root.mkdir(parents=True)
    shutil.copytree(historical, skills_root / name)
    plan = installer._preflight_canonical_skills(
        ROOT / "src.codex" / "skills", skills_root, root=ROOT
    )
    try:
        selected = next(skill for skill in plan.skills if skill.name == name)
        assert selected.accepted_prior == expected_prior
        owner = installer._CreateOnlyMutablePath(
            tmp_path / "target",
            installer._InstallTransaction([], enabled=False),
            dry_run=False,
        )
        installer._apply_canonical_skills_plan(plan, skills_root, owner, root=ROOT)
        assert (
            installer._tree_sha256(
                skills_root / name, ignore_runtime_cache=selected.ignore_runtime_cache
            )
            == selected.source_digest
        )
    finally:
        installer._discard_canonical_skills_plan(plan)

    before_noop = {
        path.relative_to(skills_root): path.read_bytes()
        for path in skills_root.rglob("*")
        if path.is_file()
    }
    current_plan = installer._preflight_canonical_skills(
        ROOT / "src.codex" / "skills", skills_root, root=ROOT
    )
    try:
        selected = next(skill for skill in current_plan.skills if skill.name == name)
        assert selected.accepted_prior is None
        installer._apply_canonical_skills_plan(current_plan, skills_root, owner, root=ROOT)
        assert {
            path.relative_to(skills_root): path.read_bytes()
            for path in skills_root.rglob("*")
            if path.is_file()
        } == before_noop
    finally:
        installer._discard_canonical_skills_plan(current_plan)

    drift_root = tmp_path / "drift" / ".agents" / "skills"
    drift_root.mkdir(parents=True)
    shutil.copytree(historical, drift_root / name)
    with (drift_root / name / "SKILL.md").open("ab") as stream:
        stream.write(b"one byte of drift\n")
    with pytest.raises(ValueError, match=rf"E_ACCEPTED_PRIOR_COLLISION: {name}"):
        installer._preflight_canonical_skills(
            ROOT / "src.codex" / "skills", drift_root, root=ROOT
        )


def _copy_current_staged_lead(installer, destination: Path) -> Path:
    if destination.exists():
        shutil.rmtree(destination)
    stage = installer._stage_canonical_lead_tree(
        ROOT,
        ROOT / "src.codex" / "skills" / "lead",
        destination / "scripts",
    )
    try:
        shutil.copytree(stage.path, destination)
    finally:
        shutil.rmtree(stage.path, ignore_errors=True)
    return destination


def _seed_partial_push_gate_staged_lead(destination: Path) -> Path:
    lead = _seed_revision_staged_lead(
        PARTIAL_PUSH_GATE_GLOBAL_LEAD_REVISION, destination
    )
    (lead / "scripts" / "check-git-push-gate.py").write_bytes(
        _historical_blob(
            PARTIAL_PUSH_GATE_OVERLAY_REVISION,
            "scripts/universal-hooks/scripts/check-git-push-gate.py",
        )
    )
    return lead


def _seed_current_hybrid_global_lead(installer, destination: Path) -> Path:
    lead = _seed_revision_staged_lead(
        CURRENT_HYBRID_GLOBAL_LEAD_REVISION, destination
    )
    for relative, source in CURRENT_HYBRID_GLOBAL_LEAD_OVERLAYS.items():
        (lead / relative).write_bytes(_historical_blob(*source))
    return lead


def test_exact_current_hybrid_global_lead_migrates_noops_and_rejects_drift(
    tmp_path: Path,
) -> None:
    installer = _load_installer()
    current = _copy_current_staged_lead(installer, tmp_path / "current" / "lead")
    historical = _seed_current_hybrid_global_lead(
        installer, tmp_path / "historical" / "lead"
    )
    historical_files = _tree_bytes(historical)
    for relative, source in CURRENT_HYBRID_GLOBAL_LEAD_OVERLAYS.items():
        assert historical_files[Path(relative)] == _historical_blob(*source)
    assert (
        installer._tree_sha256(historical, ignore_runtime_cache=True)
        == CURRENT_HYBRID_GLOBAL_LEAD_TREE_SHA256
    )

    target = tmp_path / "target"
    skills_root = target / ".agents" / "skills"
    shutil.copytree(historical, skills_root / "lead")
    plan = installer._preflight_canonical_skills(
        ROOT / "src.codex" / "skills", skills_root, root=ROOT
    )
    try:
        lead = next(skill for skill in plan.skills if skill.name == "lead")
        assert lead.accepted_prior == CURRENT_HYBRID_GLOBAL_LEAD_TREE_SHA256
        owner = installer._CreateOnlyMutablePath(
            target, installer._InstallTransaction([], enabled=False), dry_run=False
        )
        installer._apply_canonical_skills_plan(plan, skills_root, owner, root=ROOT)
    finally:
        installer._discard_canonical_skills_plan(plan)
    assert _runtime_cache_insensitive_tree_bytes(
        skills_root / "lead"
    ) == _runtime_cache_insensitive_tree_bytes(current)

    before_noop = _tree_bytes(skills_root)
    current_plan = installer._preflight_canonical_skills(
        ROOT / "src.codex" / "skills", skills_root, root=ROOT
    )
    try:
        lead = next(skill for skill in current_plan.skills if skill.name == "lead")
        assert lead.accepted_prior is None
        installer._apply_canonical_skills_plan(
            current_plan, skills_root, owner, root=ROOT
        )
    finally:
        installer._discard_canonical_skills_plan(current_plan)
    assert _tree_bytes(skills_root) == before_noop

    drift_root = tmp_path / "drift" / ".agents" / "skills"
    drift = _seed_current_hybrid_global_lead(installer, drift_root / "lead")
    with (drift / "SKILL.md").open("ab") as stream:
        stream.write(b"x")
    with pytest.raises(ValueError, match="E_ACCEPTED_PRIOR_COLLISION: lead"):
        installer._preflight_canonical_skills(
            ROOT / "src.codex" / "skills", drift_root, root=ROOT
        )

    extra_root = tmp_path / "extra" / ".agents" / "skills"
    extra = _seed_current_hybrid_global_lead(installer, extra_root / "lead")
    (extra / "unrecognized.txt").write_text("extra\n", encoding="utf-8")
    with pytest.raises(ValueError, match="E_ACCEPTED_PRIOR_COLLISION: lead"):
        installer._preflight_canonical_skills(
            ROOT / "src.codex" / "skills", extra_root, root=ROOT
        )


@pytest.mark.parametrize(
    ("revision", "expected_digest"),
    (
        (
            PRE_ZOMBIE_CENSUS_GLOBAL_LEAD_REVISION,
            PRE_ZOMBIE_CENSUS_GLOBAL_LEAD_TREE_SHA256,
        ),
        (
            PRE_COMBINED_HOTFIX_GLOBAL_LEAD_REVISION,
            PRE_COMBINED_HOTFIX_GLOBAL_LEAD_TREE_SHA256,
        ),
        (
            PRE_FINAL_REVIEW_GLOBAL_LEAD_REVISION,
            PRE_FINAL_REVIEW_GLOBAL_LEAD_TREE_SHA256,
        ),
    ),
)
def test_exact_immediate_stock_lead_migrates_and_rejects_drift(
    tmp_path: Path, revision: str, expected_digest: str,
) -> None:
    installer = _load_installer()
    skills_root = tmp_path / "accepted" / ".agents" / "skills"
    historical = _seed_revision_staged_lead(
        revision, skills_root / "lead"
    )
    assert (
        installer._tree_sha256(historical, ignore_runtime_cache=True)
        == expected_digest
    )

    plan = installer._preflight_canonical_skills(
        ROOT / "src.codex" / "skills", skills_root, root=ROOT
    )
    try:
        lead = next(skill for skill in plan.skills if skill.name == "lead")
        assert lead.accepted_prior == expected_digest
    finally:
        installer._discard_canonical_skills_plan(plan)

    drift_root = tmp_path / "drift" / ".agents" / "skills"
    drift = _seed_revision_staged_lead(
        revision, drift_root / "lead"
    )
    with (drift / "scripts" / "process_supervision" / "process_runner.py").open(
        "ab"
    ) as stream:
        stream.write(b"x")
    with pytest.raises(ValueError, match="E_ACCEPTED_PRIOR_COLLISION: lead"):
        installer._preflight_canonical_skills(
            ROOT / "src.codex" / "skills", drift_root, root=ROOT
        )


def test_exact_partial_push_gate_lead_migrates_rolls_back_and_rejects_drift(
    tmp_path: Path,
) -> None:
    installer = _load_installer()
    baseline = _seed_revision_staged_lead(
        PARTIAL_PUSH_GATE_GLOBAL_LEAD_REVISION,
        tmp_path / "baseline" / "lead",
    )
    historical = _seed_partial_push_gate_staged_lead(
        tmp_path / "historical" / "lead"
    )
    baseline_files = _tree_bytes(baseline)
    historical_files = _tree_bytes(historical)
    overlay = Path("scripts/check-git-push-gate.py")
    assert len(baseline_files) == len(historical_files) == 55
    assert {
        relative
        for relative in baseline_files
        if baseline_files[relative] != historical_files[relative]
    } == {overlay}
    assert historical_files[overlay] == _historical_blob(
        PARTIAL_PUSH_GATE_OVERLAY_REVISION,
        "scripts/universal-hooks/scripts/check-git-push-gate.py",
    )
    assert (
        installer._tree_sha256(historical, ignore_runtime_cache=True)
        == PARTIAL_PUSH_GATE_GLOBAL_LEAD_TREE_SHA256
    )

    target = tmp_path / "target"
    skills_root = target / ".agents" / "skills"
    shutil.copytree(historical, skills_root / "lead")
    plan = installer._preflight_canonical_skills(
        ROOT / "src.codex" / "skills", skills_root, root=ROOT
    )
    try:
        lead = next(skill for skill in plan.skills if skill.name == "lead")
        assert lead.accepted_prior == PARTIAL_PUSH_GATE_GLOBAL_LEAD_TREE_SHA256
        owner = installer._CreateOnlyMutablePath(
            target, installer._InstallTransaction([], enabled=False), dry_run=False
        )
        installer._apply_canonical_skills_plan(plan, skills_root, owner, root=ROOT)
    finally:
        installer._discard_canonical_skills_plan(plan)

    current = _copy_current_staged_lead(installer, tmp_path / "current" / "lead")
    assert _runtime_cache_insensitive_tree_bytes(
        skills_root / "lead"
    ) == _runtime_cache_insensitive_tree_bytes(current)
    before_noop = _tree_bytes(skills_root)
    current_plan = installer._preflight_canonical_skills(
        ROOT / "src.codex" / "skills", skills_root, root=ROOT
    )
    try:
        lead = next(skill for skill in current_plan.skills if skill.name == "lead")
        assert lead.accepted_prior is None
        installer._apply_canonical_skills_plan(
            current_plan, skills_root, owner, root=ROOT
        )
    finally:
        installer._discard_canonical_skills_plan(current_plan)
    assert _tree_bytes(skills_root) == before_noop

    drift_root = tmp_path / "drift" / ".agents" / "skills"
    shutil.copytree(historical, drift_root / "lead")
    with (drift_root / "lead" / "SKILL.md").open("ab") as stream:
        stream.write(b"x")
    with pytest.raises(ValueError, match="E_ACCEPTED_PRIOR_COLLISION: lead"):
        installer._preflight_canonical_skills(
            ROOT / "src.codex" / "skills", drift_root, root=ROOT
        )

    rollback_target = tmp_path / "rollback"
    rollback_skills = rollback_target / ".agents" / "skills"
    rollback_lead = rollback_skills / "lead"
    shutil.copytree(historical, rollback_lead)
    prior_bytes = _tree_bytes(rollback_lead)
    rollback_plan = installer._preflight_canonical_skills(
        ROOT / "src.codex" / "skills", rollback_skills, root=ROOT
    )
    try:
        with pytest.raises(RuntimeError, match="forced Lead rollback"):
            transaction = installer._InstallTransaction(
                [rollback_lead], enabled=True
            )
            with transaction:
                rollback_owner = installer._CreateOnlyMutablePath(
                    rollback_target, transaction, dry_run=False
                )
                installer._apply_canonical_skills_plan(
                    rollback_plan,
                    rollback_skills,
                    rollback_owner,
                    root=ROOT,
                )
                raise RuntimeError("forced Lead rollback")
    finally:
        installer._discard_canonical_skills_plan(rollback_plan)
    assert _tree_bytes(rollback_lead) == prior_bytes
    assert {path.name for path in rollback_skills.iterdir()} == {"lead"}


def test_partial_kimi_luna_global_lead_prior_is_exactly_hash_pinned() -> None:
    installer = _load_installer()

    assert (
        PARTIAL_KIMI_LUNA_GLOBAL_LEAD_TREE_SHA256
        in installer.GLOBAL_LEAD_ACCEPTED_PRIOR_TREE_SHA256
    )
    one_byte_falsifier = "1" + PARTIAL_KIMI_LUNA_GLOBAL_LEAD_TREE_SHA256[1:]
    assert one_byte_falsifier not in installer.GLOBAL_LEAD_ACCEPTED_PRIOR_TREE_SHA256


def test_pre_diagnostic_global_lead_prior_is_exactly_hash_pinned() -> None:
    installer = _load_installer()

    assert (
        PRE_DIAGNOSTIC_GLOBAL_LEAD_TREE_SHA256
        in installer.GLOBAL_LEAD_ACCEPTED_PRIOR_TREE_SHA256
    )
    one_byte_falsifier = "1" + PRE_DIAGNOSTIC_GLOBAL_LEAD_TREE_SHA256[1:]
    assert one_byte_falsifier not in installer.GLOBAL_LEAD_ACCEPTED_PRIOR_TREE_SHA256


def test_pre_public_capture_global_lead_prior_is_exactly_hash_pinned() -> None:
    installer = _load_installer()

    assert (
        PRE_PUBLIC_CAPTURE_GLOBAL_LEAD_TREE_SHA256
        in installer.GLOBAL_LEAD_ACCEPTED_PRIOR_TREE_SHA256
    )
    one_byte_falsifier = "1" + PRE_PUBLIC_CAPTURE_GLOBAL_LEAD_TREE_SHA256[1:]
    assert one_byte_falsifier not in installer.GLOBAL_LEAD_ACCEPTED_PRIOR_TREE_SHA256


def test_pre_child_nonzero_global_lead_prior_is_exactly_hash_pinned() -> None:
    installer = _load_installer()

    assert (
        PRE_CHILD_NONZERO_GLOBAL_LEAD_TREE_SHA256
        in installer.GLOBAL_LEAD_ACCEPTED_PRIOR_TREE_SHA256
    )
    one_byte_falsifier = "1" + PRE_CHILD_NONZERO_GLOBAL_LEAD_TREE_SHA256[1:]
    assert one_byte_falsifier not in installer.GLOBAL_LEAD_ACCEPTED_PRIOR_TREE_SHA256


def _seed_pre_range_v3_staged_lead(destination: Path) -> Path:
    lead = _replace_with_revision_staged_lead(
        PRE_RANGE_V3_GLOBAL_LEAD_REVISION, destination
    )
    for relative, source in PRE_RANGE_V3_STAGED_LEAD_OVERLAYS.items():
        (lead / relative).write_bytes(_historical_blob(*source))
    return lead


def _seed_provider_auth_baseline_staged_lead(destination: Path) -> Path:
    lead = _replace_with_revision_staged_lead(
        PROVIDER_AUTH_BASELINE_GLOBAL_LEAD_REVISION, destination
    )
    for relative, source in PROVIDER_AUTH_BASELINE_STAGED_LEAD_OVERLAYS.items():
        (lead / relative).write_bytes(_historical_blob(*source))
    return lead


def test_exact_provider_auth_baseline_lead_is_accepted_and_drift_refused(
    tmp_path: Path,
) -> None:
    installer = _load_installer()
    skills_root = tmp_path / ".agents" / "skills"
    historical = _seed_provider_auth_baseline_staged_lead(skills_root / "lead")
    assert installer._tree_sha256(
        historical, ignore_runtime_cache=True
    ) == PROVIDER_AUTH_BASELINE_GLOBAL_LEAD_TREE_SHA256

    plan = installer._preflight_canonical_skills(
        ROOT / "src.codex" / "skills", skills_root, root=ROOT
    )
    try:
        lead = next(skill for skill in plan.skills if skill.name == "lead")
        assert lead.accepted_prior == PROVIDER_AUTH_BASELINE_GLOBAL_LEAD_TREE_SHA256
    finally:
        installer._discard_canonical_skills_plan(plan)

    _seed_provider_auth_baseline_staged_lead(skills_root / "lead")
    with (skills_root / "lead" / "SKILL.md").open("ab") as stream:
        stream.write(b"customized\n")
    with pytest.raises(ValueError, match="E_ACCEPTED_PRIOR_COLLISION: lead"):
        installer._preflight_canonical_skills(
            ROOT / "src.codex" / "skills", skills_root, root=ROOT
        )


@pytest.mark.parametrize(
    ("revision", "expected_digest"),
    (
        (PRE_KIMI_GLOBAL_LEAD_REVISION, PRE_KIMI_GLOBAL_LEAD_TREE_SHA256),
        (
            PRE_K3_WIRE_FIX_GLOBAL_LEAD_REVISION,
            PRE_K3_WIRE_FIX_GLOBAL_LEAD_TREE_SHA256,
        ),
        (STOCK_77EC_GLOBAL_LEAD_REVISION, STOCK_77EC_GLOBAL_LEAD_TREE_SHA256),
        (
            "3dadb8b66e4580df929fecdc5d8d9bf20dcb2c59",
            "836f24dafcc409be2d120248a19ec34772af03238b7600389961a708315a15b7",
        ),
        (
            "fa5d42726ef50e7e6551e8eda13c0f0445a14c5b",
            "d73912c5e01c693fa8f6c0c3aa071e51f595f3d88e6a81aa7aa8abfa8995bfda",
        ),
        (
            "9339bcf29f1864789c7a133260a2a2a2abeb3060",
            "c3508f94d6830da703a5519fbe28bf7011f2a8850e67b5ed5a49c47465283295",
        ),
        (
            "6dbf861a4c119f59c52813a02758f14ea9050aa7",
            "9b11e845e746adeb81e56243169ade9e48aaf2adc349b40073beb21b5b596c30",
        ),
        (
            "94715eed9e0563a38d83572f4b6d525d2f9172d9",
            "a90c1989a0c136c55af71b68c62fad6a2cc239162a953d45643dfee903795560",
        ),
        (
            "00dd36a02245d54329b7b2c0fd28931d6ee3e8eb",
            "2600ed4cdcdcf64767ad8486225a8bd4687c8ca3618344f7e4bbb709587f30ef",
        ),
        (
            "5b901299c744153363bc3f261183c5243440e1b9",
            "3ca341a8c4ec35a7cbcd7920d6f5be7c1888b1d143393b544643fb005c97dab4",
        ),
        (
            "4c067f25750fb224c3bdf987789885e5b357264f",
            "3067dcada53a7b090fa9a66594e3b4d3266d98f9ffe322c36c001c077bcfa0c0",
        ),
        (
            "6aa0e234e43f639a70f6f46311ab535e49039ad4",
            "52f2c3d21a5d83bc36fccafe7599ca089006fc4d1b93237ab606dd1e7390422a",
        ),
        (
            "2dbf91b3e96e9dbf2bf785d16bf6964faf766d46",
            "d6cf6e5cd2a1cdb08346d396b60fcd905d36bf2533b96508f942f684b52b0255",
        ),
    ),
    ids=(
        "pre-kimi", "pre-k3-wire-fix", "stock-77ec", "stock-3dad",
        "stock-fa5d", "stock-9339", "stock-6dbf", "stock-947", "stock-00dd",
        "stock-5b", "stock-4c", "stock-6aa", "stock-2db",
    ),
)
def test_exact_shipped_global_lead_is_accepted_and_one_byte_drift_refused(
    tmp_path: Path,
    revision: str,
    expected_digest: str,
) -> None:
    installer = _load_installer()
    historical = _seed_revision_staged_lead(
        revision, tmp_path / "historical" / "lead"
    )
    assert installer._tree_sha256(
        historical, ignore_runtime_cache=True
    ) == expected_digest

    skills_root = tmp_path / "exact" / ".agents" / "skills"
    shutil.copytree(historical, skills_root / "lead")
    plan = installer._preflight_canonical_skills(
        ROOT / "src.codex" / "skills", skills_root, root=ROOT
    )
    try:
        lead = next(skill for skill in plan.skills if skill.name == "lead")
        assert lead.accepted_prior == expected_digest
        owner = installer._CreateOnlyMutablePath(
            tmp_path,
            installer._InstallTransaction([], enabled=False),
            dry_run=False,
        )
        installer._apply_canonical_skills_plan(plan, skills_root, owner, root=ROOT)
        assert installer._tree_sha256(
            skills_root / "lead", ignore_runtime_cache=True
        ) == lead.source_digest
    finally:
        installer._discard_canonical_skills_plan(plan)

    drift_root = tmp_path / "drift" / ".agents" / "skills"
    shutil.copytree(historical, drift_root / "lead")
    with (drift_root / "lead" / "SKILL.md").open("ab") as stream:
        stream.write(b"x")
    with pytest.raises(ValueError, match="E_ACCEPTED_PRIOR_COLLISION: lead"):
        installer._preflight_canonical_skills(
            ROOT / "src.codex" / "skills", drift_root, root=ROOT
        )


def test_exact_pre_range_v3_lead_is_accepted_and_customized_tree_refused(
    tmp_path: Path,
) -> None:
    installer = _load_installer()
    skills_root = tmp_path / ".agents" / "skills"
    historical = _seed_pre_range_v3_staged_lead(skills_root / "lead")
    assert installer._tree_sha256(
        historical, ignore_runtime_cache=True
    ) == PRE_RANGE_V3_GLOBAL_LEAD_TREE_SHA256

    plan = installer._preflight_canonical_skills(
        ROOT / "src.codex" / "skills", skills_root, root=ROOT
    )
    try:
        lead = next(skill for skill in plan.skills if skill.name == "lead")
        assert lead.accepted_prior == PRE_RANGE_V3_GLOBAL_LEAD_TREE_SHA256
    finally:
        installer._discard_canonical_skills_plan(plan)

    _seed_pre_range_v3_staged_lead(skills_root / "lead")
    with (skills_root / "lead" / "SKILL.md").open("ab") as stream:
        stream.write(b"customized\n")
    with pytest.raises(ValueError, match="E_ACCEPTED_PRIOR_COLLISION: lead"):
        installer._preflight_canonical_skills(
            ROOT / "src.codex" / "skills", skills_root, root=ROOT
        )


def _seed_pre_rebase_staged_lead(destination: Path) -> Path:
    lead = _replace_with_revision_staged_lead(
        PRE_KIMI_GLOBAL_LEAD_REVISION, destination
    )
    for relative, payload in PRE_REBASE_STAGED_LEAD_OVERLAYS.items():
        (lead / relative).write_bytes(payload)
    for relative, payload in _pre_rebase_fixture_payloads().items():
        (lead / relative).write_bytes(payload)
    for relative, source in H2_STAGED_RUNTIME_OVERLAYS.items():
        (lead / relative).write_bytes(_historical_blob(*source))
    _remove_historical_members(lead, POST_7872_GLOBAL_LEAD_RUNTIME_FILES)
    return lead


def test_exact_pre_rebase_staged_lead_is_accepted_and_current_is_noop(
    tmp_path: Path,
) -> None:
    """The observed staged Lead tree upgrades exactly once, without a no-op rewrite."""

    installer = _load_installer()
    historical = _seed_pre_rebase_staged_lead(tmp_path / "historical")
    assert (
        installer._tree_sha256(historical, ignore_runtime_cache=True)
        == PRE_REBASE_GLOBAL_LEAD_TREE_SHA256
    )

    skills_root = tmp_path / "target" / ".agents" / "skills"
    skills_root.mkdir(parents=True)
    shutil.copytree(historical, skills_root / "lead")
    plan = installer._preflight_canonical_skills(
        ROOT / "src.codex" / "skills", skills_root, root=ROOT
    )
    try:
        lead = next(skill for skill in plan.skills if skill.name == "lead")
        assert lead.accepted_prior == PRE_REBASE_GLOBAL_LEAD_TREE_SHA256
        owner = installer._CreateOnlyMutablePath(
            tmp_path / "target", installer._InstallTransaction([], enabled=False), dry_run=False
        )
        installer._apply_canonical_skills_plan(plan, skills_root, owner, root=ROOT)
    finally:
        installer._discard_canonical_skills_plan(plan)

    before_noop = {
        path.relative_to(skills_root): path.read_bytes()
        for path in skills_root.rglob("*")
        if path.is_file()
    }
    current_plan = installer._preflight_canonical_skills(
        ROOT / "src.codex" / "skills", skills_root, root=ROOT
    )
    try:
        lead = next(skill for skill in current_plan.skills if skill.name == "lead")
        assert lead.accepted_prior is None
        installer._apply_canonical_skills_plan(current_plan, skills_root, owner, root=ROOT)
    finally:
        installer._discard_canonical_skills_plan(current_plan)
    assert {
        path.relative_to(skills_root): path.read_bytes()
        for path in skills_root.rglob("*")
        if path.is_file()
    } == before_noop


def test_pre_rebase_staged_lead_drift_is_rejected_before_transaction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One-byte Lead drift cannot enter the global rollback transaction."""

    installer = _load_installer()
    historical = _seed_pre_rebase_staged_lead(tmp_path / "historical")
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("HOME", str(home))
    assert installer.install("claude", ["--global", "--no-hypothesis-hook"]) == 0

    skills = home / ".agents" / "skills"
    shutil.rmtree(skills / "lead")
    shutil.copytree(historical, skills / "lead")
    with (skills / "lead" / "SKILL.md").open("ab") as stream:
        stream.write(b"one byte of drift\n")
    before_bytes = {
        path.relative_to(skills): path.read_bytes()
        for path in skills.rglob("*")
        if path.is_file()
    }
    before_identity = installer._CreateOnlyMutablePath._identity(skills)
    entered: list[object] = []
    original_enter = installer._InstallTransaction.__enter__

    def observe_enter(transaction):
        entered.append(transaction)
        return original_enter(transaction)

    monkeypatch.setattr(installer._InstallTransaction, "__enter__", observe_enter)
    assert installer.install("claude", ["--global", "--no-hypothesis-hook"]) == 1
    assert entered == []
    assert {
        path.relative_to(skills): path.read_bytes()
        for path in skills.rglob("*")
        if path.is_file()
    } == before_bytes
    assert installer._CreateOnlyMutablePath._identity(skills) == before_identity


@pytest.mark.parametrize(
    ("name", "expected_prior"),
    tuple(STOCK_8521_CANONICAL_SKILL_TREE_SHA256.items()),
)
def test_exact_8521_stock_skill_is_accepted_and_drift_refused(
    tmp_path: Path, name: str, expected_prior: str
) -> None:
    """Only the verified 8521 stock tree may upgrade to the current skill."""

    installer = _load_installer()
    historical = _extract_8521_skill(name, tmp_path / "historical")
    _assert_exact_stock_skill_is_accepted_and_drift_refused(
        installer, tmp_path, name, expected_prior, historical
    )


@pytest.mark.parametrize(
    ("name", "expected_prior"),
    tuple(STOCK_7872_CANONICAL_SKILL_TREE_SHA256.items()),
)
def test_exact_7872_stock_skill_is_accepted_and_drift_refused(
    tmp_path: Path, name: str, expected_prior: str
) -> None:
    """Only each exact shipped 7872 tree may upgrade to the current skill."""

    installer = _load_installer()
    historical = _extract_7872_skill(name, tmp_path / "historical")
    _assert_exact_stock_skill_is_accepted_and_drift_refused(
        installer, tmp_path, name, expected_prior, historical
    )


@pytest.mark.parametrize(
    ("name", "revision", "expected_prior"),
    tuple(
        (name, revision, digest)
        for name, (revision, digest) in ADDITIONAL_STOCK_SKILL_PRIORS.items()
    ),
)
def test_exact_additional_stock_skill_is_accepted_and_drift_refused(
    tmp_path: Path, name: str, revision: str, expected_prior: str
) -> None:
    """Only each exact named shipped stock tree may upgrade to the current skill."""

    installer = _load_installer()
    historical = _extract_additional_stock_skill(
        name, revision, tmp_path / "historical"
    )
    _assert_exact_stock_skill_is_accepted_and_drift_refused(
        installer, tmp_path, name, expected_prior, historical
    )


@pytest.mark.parametrize(
    ("name", "revision", "expected_prior"),
    tuple(
        (name, revision, digest)
        for name, (revision, digest) in ADDITIONAL_STOCK_SKILL_PRIORS.items()
        if (ADDITIONAL_STOCK_SKILL_FIXTURE_ROOT / revision).is_dir()
    ),
)
def test_additional_stock_skill_fixture_survives_missing_git_history(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    revision: str,
    expected_prior: str,
) -> None:
    """Each bounded stock fixture works in a source archive or shallow clone."""

    def reject_git_history(*_args, **_kwargs):
        raise AssertionError("historical Git objects are unavailable")

    monkeypatch.setattr(subprocess, "run", reject_git_history)
    historical = _extract_additional_stock_skill(
        name, revision, tmp_path / "historical"
    )
    installer = _load_installer()
    assert installer._tree_sha256(historical) == expected_prior


def test_github_pr_review_bot_prior_is_skill_scoped(tmp_path: Path) -> None:
    installer = _load_installer()
    revision, expected_prior = ADDITIONAL_STOCK_SKILL_PRIORS["github-pr-review-bot"]
    historical = _extract_additional_stock_skill(
        "github-pr-review-bot", revision, tmp_path / "historical"
    )
    assert installer._tree_sha256(historical) == expected_prior
    skills_root = tmp_path / "target" / ".agents" / "skills"
    skills_root.mkdir(parents=True)
    shutil.copytree(historical, skills_root / "consultant")

    with pytest.raises(ValueError, match="E_ACCEPTED_PRIOR_COLLISION: consultant"):
        installer._preflight_canonical_skills(
            ROOT / "src.codex" / "skills", skills_root, root=ROOT
        )


def test_github_pr_review_bot_prior_transaction_abort_restores_prior(
    tmp_path: Path,
) -> None:
    installer = _load_installer()
    revision, expected_prior = ADDITIONAL_STOCK_SKILL_PRIORS["github-pr-review-bot"]
    historical = _extract_additional_stock_skill(
        "github-pr-review-bot", revision, tmp_path / "historical"
    )
    assert installer._tree_sha256(historical) == expected_prior
    target = tmp_path / "target"
    skills_root = target / ".agents" / "skills"
    skills_root.mkdir(parents=True)
    installed = skills_root / "github-pr-review-bot"
    shutil.copytree(historical, installed)
    prior_bytes = _tree_bytes(installed)
    plan = installer._preflight_canonical_skills(
        ROOT / "src.codex" / "skills", skills_root, root=ROOT
    )
    try:
        with pytest.raises(RuntimeError, match="forced review skill rollback"):
            transaction = installer._InstallTransaction([installed], enabled=True)
            with transaction:
                owner = installer._CreateOnlyMutablePath(
                    target, transaction, dry_run=False
                )
                installer._apply_canonical_skills_plan(
                    plan, skills_root, owner, root=ROOT
                )
                raise RuntimeError("forced review skill rollback")
    finally:
        installer._discard_canonical_skills_plan(plan)

    assert _tree_bytes(installed) == prior_bytes
    assert {path.name for path in skills_root.iterdir()} == {"github-pr-review-bot"}


def test_exact_947_manual_transfer_is_accepted_and_drift_refused(
    tmp_path: Path,
) -> None:
    installer = _load_installer()
    historical = _extract_additional_stock_skill(
        "manual-repo-transfer",
        "94715eed9e0563a38d83572f4b6d525d2f9172d9",
        tmp_path / "historical",
    )
    _assert_exact_stock_skill_is_accepted_and_drift_refused(
        installer,
        tmp_path,
        "manual-repo-transfer",
        "b73cde79962de55bd2cd52bc35f0b450d26cff78abb21b9a496bf38be686a9f3",
        historical,
    )


def test_exact_2db_manual_transfer_is_accepted_and_drift_refused(
    tmp_path: Path,
) -> None:
    installer = _load_installer()
    historical = _extract_additional_stock_skill(
        "manual-repo-transfer",
        "2dbf91b3e96e9dbf2bf785d16bf6964faf766d46",
        tmp_path / "historical",
    )
    _assert_exact_stock_skill_is_accepted_and_drift_refused(
        installer,
        tmp_path,
        "manual-repo-transfer",
        "e0d160e3f216d79fe2aa221b6ed8d4d4b63dd06882d4ea69feb46cdccab1afcc",
        historical,
    )


def _copy_manual_transfer_with_runtime_cache(source: Path, destination: Path) -> Path:
    shutil.copytree(source, destination)
    cache = destination / "scripts" / "__pycache__"
    cache.mkdir(exist_ok=True)
    (cache / "repo_transfer.cpython-314.pyc").write_bytes(b"synthetic runtime cache")
    return destination


def test_current_canonical_skill_runtime_cache_is_a_noop(tmp_path: Path) -> None:
    installer = _load_installer()
    skills_root = tmp_path / "target" / ".agents" / "skills"
    skills_root.mkdir(parents=True)
    installed = _copy_manual_transfer_with_runtime_cache(
        ROOT / "src.codex" / "skills" / "manual-repo-transfer",
        skills_root / "manual-repo-transfer",
    )
    before = {
        path.relative_to(installed): path.read_bytes()
        for path in installed.rglob("*")
        if path.is_file()
    }

    plan = installer._preflight_canonical_skills(
        ROOT / "src.codex" / "skills", skills_root, root=ROOT
    )
    try:
        selected = next(
            skill for skill in plan.skills if skill.name == "manual-repo-transfer"
        )
        assert selected.installed_digest == selected.source_digest
        assert selected.accepted_prior is None
        owner = installer._CreateOnlyMutablePath(
            tmp_path / "target",
            installer._InstallTransaction([], enabled=False),
            dry_run=False,
        )
        installer._apply_canonical_skills_plan(plan, skills_root, owner, root=ROOT)
        assert {
            path.relative_to(installed): path.read_bytes()
            for path in installed.rglob("*")
            if path.is_file()
        } == before
    finally:
        installer._discard_canonical_skills_plan(plan)


def test_stock_canonical_skill_runtime_cache_migrates(tmp_path: Path) -> None:
    installer = _load_installer()
    name = "manual-repo-transfer"
    expected_prior = STOCK_7872_CANONICAL_SKILL_TREE_SHA256[name]
    historical = _extract_7872_skill(name, tmp_path / "historical")
    skills_root = tmp_path / "target" / ".agents" / "skills"
    skills_root.mkdir(parents=True)
    installed = _copy_manual_transfer_with_runtime_cache(
        historical, skills_root / name
    )

    plan = installer._preflight_canonical_skills(
        ROOT / "src.codex" / "skills", skills_root, root=ROOT
    )
    try:
        selected = next(skill for skill in plan.skills if skill.name == name)
        assert selected.installed_digest == expected_prior
        assert selected.accepted_prior == expected_prior
        owner = installer._CreateOnlyMutablePath(
            tmp_path / "target",
            installer._InstallTransaction([], enabled=False),
            dry_run=False,
        )
        installer._apply_canonical_skills_plan(plan, skills_root, owner, root=ROOT)
        assert not (installed / "scripts" / "__pycache__").exists()
        assert installer._tree_sha256(installed, ignore_runtime_cache=True) == (
            selected.source_digest
        )
    finally:
        installer._discard_canonical_skills_plan(plan)


def test_non_cache_extra_inside_runtime_cache_directory_is_collision(
    tmp_path: Path,
) -> None:
    installer = _load_installer()
    name = "manual-repo-transfer"
    historical = _extract_7872_skill(name, tmp_path / "historical")
    skills_root = tmp_path / "target" / ".agents" / "skills"
    skills_root.mkdir(parents=True)
    installed = skills_root / name
    shutil.copytree(historical, installed)
    cache = installed / "scripts" / "__pycache__"
    cache.mkdir()
    (cache / "operator-note.txt").write_text("not runtime cache", encoding="utf-8")

    with pytest.raises(ValueError, match="E_ACCEPTED_PRIOR_COLLISION: manual-repo-transfer"):
        installer._preflight_canonical_skills(
            ROOT / "src.codex" / "skills", skills_root, root=ROOT
        )


def test_h2_global_lead_rebaseline_diff_is_only_mutate_work_item(
    tmp_path: Path,
) -> None:
    assert set(PRE_H2_ONLY_HISTORICAL_FILES) - set(
        OBSERVED_GLOBAL_LEAD_HISTORICAL_FILES
    ) == {"scripts/mutate-work-item.py"}
    historical = _historical_blob(
        *PRE_H2_ONLY_HISTORICAL_FILES["scripts/mutate-work-item.py"]
    )
    assert hashlib.sha256(historical).hexdigest() == (
        "f56ba552c8e7bdc8b814d29d5583d0bce38b5fc2d0581fc4097612e9dbf73da5"
    )

    current = _copy_current_staged_lead(
        _load_installer(), tmp_path / "current" / "lead"
    )
    current_staged = (current / "scripts" / "mutate-work-item.py").read_bytes()
    assert current_staged == (ROOT / "scripts" / "mutate-work-item.py").read_bytes()
    assert current_staged != historical


def _seed_exact_observed_global_lead(
    installer,
    skills_root: Path,
    expected_digest: str,
    historical_files: dict[str, bytes | tuple[str, str]],
) -> Path:
    lead = skills_root / "lead"
    _replace_with_revision_staged_lead(PRE_KIMI_GLOBAL_LEAD_REVISION, lead)
    for relative, historical_file in historical_files.items():
        payload = (
            historical_file
            if isinstance(historical_file, bytes)
            else _historical_blob(*historical_file)
        )
        (lead / relative).write_bytes(payload)
    _remove_historical_members(lead, OBSERVED_GLOBAL_LEAD_ABSENT_TRANSPORT_FILES)
    assert (
        installer._tree_sha256(lead, ignore_runtime_cache=True)
        == expected_digest
    )
    return lead


@pytest.mark.parametrize(
    ("expected_digest", "historical_files"),
    (
        (PRE_H2_GLOBAL_LEAD_TREE_SHA256, PRE_H2_ONLY_HISTORICAL_FILES),
        (CURRENT_GLOBAL_LEAD_TREE_SHA256, OBSERVED_GLOBAL_LEAD_HISTORICAL_FILES),
    ),
    ids=("pre-h2", "current-h2"),
)
def test_only_exact_observed_global_lead_tree_is_an_accepted_prior(
    tmp_path: Path,
    expected_digest: str,
    historical_files: dict[str, bytes | tuple[str, str]],
) -> None:
    installer = _load_installer()
    skills_root = tmp_path / ".agents" / "skills"
    lead = _seed_exact_observed_global_lead(
        installer, skills_root, expected_digest, historical_files
    )

    plan = installer._preflight_canonical_skills(
        ROOT / "src.codex" / "skills", skills_root, root=ROOT
    )
    try:
        planned_lead = next(skill for skill in plan.skills if skill.name == "lead")
        assert planned_lead.accepted_prior == expected_digest

        owner = installer._CreateOnlyMutablePath(
            tmp_path, installer._InstallTransaction([], enabled=False), dry_run=False
        )
        installer._apply_canonical_skills_plan(plan, skills_root, owner, root=ROOT)
        assert (
            installer._tree_sha256(skills_root / "lead", ignore_runtime_cache=True)
            == planned_lead.source_digest
        )
    finally:
        installer._discard_canonical_skills_plan(plan)

    _seed_exact_observed_global_lead(
        installer, skills_root, expected_digest, historical_files
    )
    with (skills_root / "lead" / "SKILL.md").open("ab") as stream:
        stream.write(b"x")
    with pytest.raises(ValueError, match="E_ACCEPTED_PRIOR_COLLISION: lead"):
        installer._preflight_canonical_skills(
            ROOT / "src.codex" / "skills", skills_root, root=ROOT
        )

    _seed_exact_observed_global_lead(
        installer, skills_root, expected_digest, historical_files
    )
    (skills_root / "lead" / "unrecognized.txt").write_text("extra\n", encoding="utf-8")
    with pytest.raises(ValueError, match="E_ACCEPTED_PRIOR_COLLISION: lead"):
        installer._preflight_canonical_skills(
            ROOT / "src.codex" / "skills", skills_root, root=ROOT
        )
