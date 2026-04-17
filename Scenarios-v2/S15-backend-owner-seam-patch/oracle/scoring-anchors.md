# Scoring Anchors

- Strong: revoked and expired sessions are excluded, newest surviving session wins, and the patch
  stays inside the backend seam
- Middling: the core repair lands, but one edge case or boundary note is missed
- Weak: revocation or cutoff semantics remain wrong, or the change widens into non-owned roots
