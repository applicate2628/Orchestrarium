# Trust Boundary Notes

- query-string parameters are untrusted inputs
- parent-window messages are untrusted until origin, source, and payload ownership are verified
- authorization should be derived from server-owned identity, not client-selected role or tenant
