# Behavior Brief

The preview-share API computes one active session window per user before issuing role-first
preview links. The backend seam owns:

- removing revoked sessions
- removing sessions whose expiry is at or before the cutoff timestamp
- keeping the newest surviving session per user

It does not own deployment policy, warehouse rollups, external request schema changes, or build
tooling.
