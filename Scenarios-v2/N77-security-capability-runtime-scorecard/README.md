# N77 Security Capability Runtime Scorecard

This bundle tests a security implementation patch, not a review memo.

The worker must repair a small export authorization surface with capability-token
signing, tenant/user/resource binding, replay and expiry protection, safe redirect
handling, audit redaction, and a focused regression test.

The verifier uses hidden exploit attempts and exact changed-path accounting. A
pretty security explanation without a working patch is a scoreable failure.
