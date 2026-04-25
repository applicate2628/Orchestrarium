# N78 Staged Security Reentry Gauntlet

This bundle tests staged security implementation and re-entry, not a review memo.

The worker must preserve a source/threat ledger across fresh invocations, repair a small export
authorization surface, validate hidden exploit coverage, and close out the staged re-entry packet.

The verifier uses the N77 hidden exploit oracle plus staged artifacts. A correct patch without the
source, validation, and closeout records is a scoreable failure.
