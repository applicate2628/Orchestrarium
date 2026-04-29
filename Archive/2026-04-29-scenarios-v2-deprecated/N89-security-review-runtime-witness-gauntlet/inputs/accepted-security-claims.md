# Accepted Security Claims

- tenant scope must come from server-owned authenticated context, not request bodies or query strings
- privileged actions must use server-owned roles, not caller-supplied role fields
- export and audit surfaces must not disclose bearer secrets, service tokens, session cookies, or PII
- reset tokens must be unguessable and single-purpose
- session cookies must be secure, HttpOnly, and same-site constrained for privileged admin surfaces
- webhook verification must be mandatory and replay-resistant before applying credit or balance changes
