# Native operations receiving components

The Rust plan owns these source-only receiving components. There is no
dispatcher, new Cargo package, installation, or activation in this slice.
The pre-SDK publication matcher remains separate and unchanged.

## Publication tree walk

The walker expands one already selected root. The caller supplies verified
parsed entries, current tree and blob membership, and the budget callback.
It keeps exact path bytes and blob modes, emits ordered tree/metadata/subject
observations, and rejects cycles and overlong paths. The maximum path length
bounds depth for admitted nonempty path components; the frontier check counts
pending trees and does not double as a graph-size limit. Events do not get
retained by the walker. No new detector, Git transport, tag selection,
identity proof, admission, report, or publication decision is added.

On an approved local toolchain, build the std-only test driver and compare it
against the actual Python walk loop in the chosen receiving checkout:

~~~text
rustc --edition=2024 -D warnings native/operations/tests/tree_walk_driver.rs -o <test-driver>
python -B native/operations/tests/tree_walk_parity.py --driver <test-driver> --source <receiving-check-publication-safety.py>
~~~

The driver format is only a fixture. It is not a supported runtime protocol.
The comparison checks ordered bytes, guard calls, and refusal distinctions on
synthetic graphs at both Git object-ID widths. Python callback substitutes
record graph events but do not run policy or classify findings. This does not
qualify Git acquisition, a full scanner verdict, hardware throughput, or
runtime cutover. Future integration still needs exact receiving-source parity
and full gate measurements without bypassing the existing owner.

## Publication tree record parser

The existing Git acquisition owner must validate the complete object's type,
framing, byte length and identity before constructing a verified payload view.
The parser performs structural decoding only: it accepts either object-ID
width and returns ordered borrowed mode, name and object-ID byte ranges.
A malformed payload does not expose entries already decoded from that payload.
Keep the verified payload alive while its entry views are in use.

Run the additional differential test with the same compiled test driver:

~~~text
python -B native/operations/tests/tree_record_parity.py --driver <test-driver> --source <receiving-check-publication-safety.py>
~~~

The receiving Python parser supplies the byte-exact order and refusal oracle.
The test also feeds borrowed records into the walker without copying their
fields. Git acquisition, ownership and publication authority remain outside
this component.

## Git batch frame decoder

The decoder consumes one response from a buffered byte stream. The acquisition
owner supplies the checked request ID and optional expected type. Compare the
header, decode the declared length, enforce the receiving transport's bounds,
and require the exact payload and final LF before returning any bytes.
Malformed or incomplete frames cannot yield a partial record. The owner
must poison the session on failures; the decoder does not resynchronize it,
spawn Git, schedule deadlines, or perform cryptographic identity verification.

Defaults mirror the current receiving reader (64 KiB header, 1 MiB structured
object, and 64 MiB blob). The receiving Python runtime also bounds decimal
conversion; the compatible setting is configurable and supplied by the parity
test. These are decoder compatibility parameters, not a new publication policy.

The same test-only driver also accepts
incrementally buffered batch frames.

~~~text
python -B native/operations/tests/git_batch_parity.py --driver <test-driver> --source <receiving-check-publication-safety.py>
~~~

The test executes the actual receiving byte-reader method against a local
in-memory stream. It does not qualify a real subprocess, cancellation,
deadline enforcement, content identity, or publication.


## Publication receiving composition

The same test driver can feed locally hash-verified Git tree fixtures through
the batch decoder, borrowed record parser, and walker in one process.
Errors are delivered at the corresponding tree lookup, so the test observes
the exact prefix of valid coverage events followed by the refusal. A correct
frame with a malformed authenticated tree still fails structural decoding.

~~~text
python -B native/operations/tests/publication_composition_parity.py --driver <test-driver> --source <receiving-check-publication-safety.py>
~~~

Pass --git-scratch with an existing disposable workspace directory to also
compare unmodified git cat-file --batch output from file-only bare Git
repositories in both SHA-1 and SHA-256 formats. This checks empty and nested
trees and the refusal for a missing child with actual Git output. No remote,
hook, or publication operation is involved. Use the receiving Python source
being qualified, not an incidental checkout of an older scanner.

Fixture preparation verifies both Git object-ID algorithms with Python; neither
the Rust framing decoder nor this test adapter provides hash authority. This
is a test-only arena, not a production cache, dispatcher, or acquisition
owner. It does not qualify the subject index, receipt, or publication path.
