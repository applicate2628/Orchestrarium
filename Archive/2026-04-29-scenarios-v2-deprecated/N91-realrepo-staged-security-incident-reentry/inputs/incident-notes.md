# Incident Notes

Observed incident:

- A support-role request could export a resource from another tenant.
- A base64-only token could be edited to point to another tenant, user, or resource.
- A captured token could be replayed because nonce consumption was not enforced.
- A crafted return URL could pass host checks by embedding the allowed host in a longer netloc.
- Audit output stored raw token material.

False leads to reject:

- Do not patch `service.py`; its public orchestration contract is protected.
- Do not remove safe owner/admin export paths.
- Do not replace signed local capability tokens with external network calls.
