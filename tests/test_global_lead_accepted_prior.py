from __future__ import annotations

import base64
import hashlib
import importlib.util
import io
import json
import shutil
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
PRE_KIMI_GLOBAL_LEAD_REVISION = "7872d36d1019d1ac8c2e1615a9f9dbde47395815"
PRE_KIMI_GLOBAL_LEAD_TREE_SHA256 = (
    "565f305b4498f045e7fb40821e5ba30902ca56b0a532d299a96d6c8a1e595d50"
)
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
    "init-project": "4f0a5fdb8af605dc10cb2044f33db3339b410feaf23764cc395f9c3feaaf6353",
    "lead": "b7d78ee5082cce97e0cb2fcb59ee2e5712617b43212a1c6c3199370797f9aa21",
    "review-loop": "2d78f499bf7b4bb2e6dafdf0ef875f2d9d39448c28df6f3835bc8153fba02ce0",
    "second-opinion": "f9a2114c8baead9ec8a259288ff74e157af60864c9f3d70ba0bcc52154b2b4b6",
}
STOCK_7872_CANONICAL_SKILL_TREE_SHA256 = {
    "consultant": "f1a23b5ceaa93c29cf0c5f9c9eec8c5997a7b4339fcd90abd13798df77e60793",
    "design-panel": "685b75f5726dd16dbcf2b5fb3238652b8564242e5b66f0daf2b582267905f67b",
    "init-project": "cd5bc7386f286393ee8dab782ed603fff7ad61e8c828f34cca102a3a5e2aba9f",
    "review-loop": "d956cf70db42a7c936d21984fe6aeb83748de02c544eec56ca54971629f85f7e",
    "second-opinion": "b82628910567799a6f03962f3ec0289cb47b4607093c074466b1a2656b53f432",
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


def _historical_blob(revision: str, source: str) -> bytes:
    return subprocess.run(
        ["git", "show", f"{revision}:{source}"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout


def _pre_rebase_fixture_payloads() -> dict[str, bytes]:
    manifest_path = PRE_REBASE_FIXTURE_ROOT / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert set(manifest) == {"schemaVersion", "baseline", "files"}
    assert manifest["schemaVersion"] == 1
    assert manifest["baseline"] == "7872d36d"
    files = manifest["files"]
    assert isinstance(files, dict) and files
    fixture_files = {
        path.relative_to(PRE_REBASE_FIXTURE_ROOT).as_posix()
        for path in PRE_REBASE_FIXTURE_ROOT.rglob("*")
        if path.is_file() and path != manifest_path
    }
    assert fixture_files == set(files)

    payloads: dict[str, bytes] = {}
    for relative, expected_sha256 in files.items():
        fixture_relative = Path(relative)
        assert not fixture_relative.is_absolute()
        assert ".." not in fixture_relative.parts
        payload = (PRE_REBASE_FIXTURE_ROOT / fixture_relative).read_bytes()
        assert hashlib.sha256(payload).hexdigest() == expected_sha256
        payloads[relative] = payload
    return payloads


def _remove_historical_members(lead: Path, relatives: tuple[str, ...]) -> None:
    for relative in relatives:
        target = lead / relative
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


def _seed_pre_range_v3_staged_lead(installer, destination: Path) -> Path:
    lead = _copy_current_staged_lead(installer, destination)
    for relative, source in PRE_RANGE_V3_STAGED_LEAD_OVERLAYS.items():
        (lead / relative).write_bytes(_historical_blob(*source))
    return lead


def _seed_provider_auth_baseline_staged_lead(installer, destination: Path) -> Path:
    lead = _copy_current_staged_lead(installer, destination)
    for relative, source in PROVIDER_AUTH_BASELINE_STAGED_LEAD_OVERLAYS.items():
        (lead / relative).write_bytes(_historical_blob(*source))
    return lead


def test_exact_provider_auth_baseline_lead_is_accepted_and_drift_refused(
    tmp_path: Path,
) -> None:
    installer = _load_installer()
    skills_root = tmp_path / ".agents" / "skills"
    historical = _seed_provider_auth_baseline_staged_lead(
        installer, skills_root / "lead"
    )
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

    _seed_provider_auth_baseline_staged_lead(installer, skills_root / "lead")
    with (skills_root / "lead" / "SKILL.md").open("ab") as stream:
        stream.write(b"customized\n")
    with pytest.raises(ValueError, match="E_ACCEPTED_PRIOR_COLLISION: lead"):
        installer._preflight_canonical_skills(
            ROOT / "src.codex" / "skills", skills_root, root=ROOT
        )


def test_exact_pre_kimi_global_lead_is_accepted_and_one_byte_drift_refused(
    tmp_path: Path,
) -> None:
    installer = _load_installer()
    historical = _seed_revision_staged_lead(
        PRE_KIMI_GLOBAL_LEAD_REVISION, tmp_path / "historical" / "lead"
    )
    assert installer._tree_sha256(
        historical, ignore_runtime_cache=True
    ) == PRE_KIMI_GLOBAL_LEAD_TREE_SHA256

    skills_root = tmp_path / "exact" / ".agents" / "skills"
    shutil.copytree(historical, skills_root / "lead")
    plan = installer._preflight_canonical_skills(
        ROOT / "src.codex" / "skills", skills_root, root=ROOT
    )
    try:
        lead = next(skill for skill in plan.skills if skill.name == "lead")
        assert lead.accepted_prior == PRE_KIMI_GLOBAL_LEAD_TREE_SHA256
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
    historical = _seed_pre_range_v3_staged_lead(installer, skills_root / "lead")
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

    _seed_pre_range_v3_staged_lead(installer, skills_root / "lead")
    with (skills_root / "lead" / "SKILL.md").open("ab") as stream:
        stream.write(b"customized\n")
    with pytest.raises(ValueError, match="E_ACCEPTED_PRIOR_COLLISION: lead"):
        installer._preflight_canonical_skills(
            ROOT / "src.codex" / "skills", skills_root, root=ROOT
        )


def _seed_pre_rebase_staged_lead(installer, destination: Path) -> Path:
    lead = _copy_current_staged_lead(installer, destination)
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
    historical = _seed_pre_rebase_staged_lead(
        installer, tmp_path / "historical"
    )
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
    historical = _seed_pre_rebase_staged_lead(
        installer, tmp_path / "historical"
    )
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


def test_h2_global_lead_rebaseline_diff_is_only_mutate_work_item() -> None:
    assert set(PRE_H2_ONLY_HISTORICAL_FILES) - set(
        OBSERVED_GLOBAL_LEAD_HISTORICAL_FILES
    ) == {"scripts/mutate-work-item.py"}
    assert hashlib.sha256(
        _historical_blob(*PRE_H2_ONLY_HISTORICAL_FILES["scripts/mutate-work-item.py"])
    ).hexdigest() == "f56ba552c8e7bdc8b814d29d5583d0bce38b5fc2d0581fc4097612e9dbf73da5"
    assert hashlib.sha256(
        (ROOT / "scripts" / "mutate-work-item.py").read_bytes()
    ).hexdigest() == "a34e6cdd61f0fb6248177628e78304769a547c6a09941c661d4b332dc3a1d1a9"


def _seed_exact_observed_global_lead(
    installer,
    skills_root: Path,
    expected_digest: str,
    historical_files: dict[str, bytes | tuple[str, str]],
) -> Path:
    lead = skills_root / "lead"
    _copy_current_staged_lead(installer, lead)
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
