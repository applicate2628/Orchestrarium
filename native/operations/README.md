# Native operations receiving components

The Rust plan owns these source-only receiving components. There is no
dispatcher, new Cargo package, installation, or activation in this slice.
The pre-SDK publication matcher remains separate and unchanged.

## Publication tree walk

The walker expands one already selected root. The caller supplies verified
parsed entries, unpublished tree and blob membership, receiver-overlap tree
membership, and the budget callback. A tree removed from the unpublished
selection by receiver reachability still emits metadata for each traversed
path. Reached-tree observations count unpublished trees. The walker keeps
exact path bytes and blob modes, emits ordered observations, and rejects
cycles and overlong paths. The maximum path length bounds depth for
admitted nonempty path components; the frontier check counts
pending trees and does not double as a graph-size limit. Events do not get
retained by the walker. No new detector, Git transport, tag selection,
identity proof, admission, report, or publication decision is added.

On an approved local toolchain, build the locked test driver and compare it
against the actual Python walk loop in the chosen receiving checkout:

~~~text
cargo build --manifest-path native/operations/Cargo.toml --example tree_walk_driver --locked --offline
python -B native/operations/tests/tree_walk_parity.py --driver <test-driver> --source <receiving-check-publication-safety.py>
~~~

The driver format is only a fixture. It is not a supported runtime protocol.
The comparison checks ordered bytes, guard calls, and refusal distinctions on
synthetic graphs at both Git object-ID widths. Use a receiving source with
receiver-overlap support to compare metadata under reused paths. Python
callback substitutes record graph events but do not run policy or classify
findings. This does not qualify Git acquisition, a full scanner verdict,
hardware throughput, or runtime cutover. Future integration still needs
exact receiving-source parity and full gate measurements without bypassing
the existing owner.

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

## Git object identity receiver

After framing, the candidate receiver validates the requested ID against the
repository format and hashes the complete object with its Git type and length.
It exposes an owned payload only when the content ID matches. Gitoxide provides
the Git object encoding and both hash implementations; the locked SHA-1
implementation includes collision detection. The receiver does not acquire
transport, recover a failed stream, authorize a push, or replace scanning
policy. The caller must abandon a stream after a failed read.

Run the native identity tests with the locked dependencies:

~~~text
cargo test --manifest-path native/operations/Cargo.toml --locked --offline
~~~

The fixtures cover both ID formats, all four Git object types, changed content
under the original header, wrong type, wrong format, and invalid request ID.
The framing size limits are still the existing compatibility bounds. The
real transport, large-object processing, cancellation, and standalone release
remain unqualified.

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

The same test driver can feed Git tree fixtures through the batch decoder,
native identity receiver, borrowed record parser, and walker in one process.
The driver binary is under the Cargo target directory's debug/examples folder.
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
being qualified, not an incidental checkout of an older scanner. The fixture
adapter executes either the legacy receiving loop or the V3 receiving loop
with the ordinary in-memory frontier; it does not qualify the compact receipt
frontier or verified progress reporting.

The Python fixture verifies both ID algorithms independently. A complete
frame with mutated content and the original header is rejected before its
tree is parsed. This is a test-only arena, not the production cache,
dispatcher, or acquisition owner. It does not qualify the subject index,
receipt, or publication path.


### Serial requests over an owned Git child

A batch session binds one input/output pair and one repository hash format.
It submits only complete validated object IDs, flushes each request, and
restores admission only after receiving the full authenticated response.
A partial pipe write or failed response makes the session unusable; the
supervisor must dispose of the corresponding child. The batch session
neither spawns children nor replaces the platform supervisor. Its inputs
must provide the existing cancellation and deadline guarantees before
production use. This does not change object size or publication policy.

To also exercise the batch session with a real Git binary, set
ORCHE_NATIVE_GIT_FIXTURES to an existing empty disposable directory, restrict
Git to the local file protocol, and run the explicit fixture:

~~~text
cargo test --manifest-path native/operations/Cargo.toml --locked --offline --test git_object_identity -- --include-ignored
~~~

The test initializes two bare repositories. Each process answers two small
reads and one blob larger than 64 MiB, followed by a missing object and a
refused retry. The fixture then closes and waits for the child. This does
not qualify process-tree cancellation or release behavior.

### Bounded-memory object staging

The buffered reader retains its compatibility ceilings. For larger input,
the receiving owner can supply a new private scratch file to the staged
reader. It streams the declared object bytes from the input buffer into
that file, using Gitoxide's type-prefixed hash. It returns the stage only
after exact framing, the final delimiter, matching object identity, and
a successful flush. An existing nonempty stage is rejected before sending
a request. Failed staging yields no verified object; the owner must ensure
exclusive access and dispose of scratch material when discarded.

A downstream consumer can take the verified stage through the read-only
handoff. The stage is rewound and exposure is bounded to the verified object
size; both an early-success callback and a premature end of input fail. Data
written by a callback remains provisional until the complete read succeeds.
The real Git fixture passes a blob larger than 64 MiB for each hash format
directly from the fixture-owned staged file through the whole-line index.
On Windows it also checks the mapped line and removal of the temporary mapping
file before reporting fixture success.

The staged reader removes the buffered payload ceiling from this receiving
path only. It does not qualify the matching stage, disk-pressure handling,
threshold warnings, production cancellation, or complete scanner coverage.

### Whole-line coordinates from staged bytes

The text consumer can index a verified stage into byte ranges for complete
lines, with the original decoded character coordinates. It uses fixed
working memory even for a single long line. A successful traversal reports
whether a NUL occurred anywhere in the input. Callers must not publish
provisional rows on an incomplete read or decide binary policy on a prefix.

The index does not run matching or apply source exemptions. The matching
owner must still evaluate each whole selected line, including an oversized
one, without unbounded heap growth or a coverage shortcut.

### Line-index timing

Use the opt-in release build to time in-memory decoding and indexing separately
from Git, disk staging, match evaluation, and the publication verdict:

~~~text
cargo run --manifest-path native/operations/Cargo.toml --locked --release --example line_index_bench
~~~

The synthetic corpus covers a long ASCII line, ordinary ASCII text, dense line
separators, and Unicode text. Compare byte and line counts and result checksums
before comparing medians on the same machine and CPU placement. This is not a
repository-scale scan or runtime performance guarantee.

On one logical core on ASUS, paired runs against 6b016b0e returned identical
row counts and all four-field span checksums. The median elapsed time averaged
across the two orders was 48.1 to 28.4 ms (long ASCII), 43.3 to 28.8 ms (ordinary
ASCII), 53.8 to 49.1 ms (dense separators), and 26.4 to 24.0 ms (Unicode).
These are observations for this corpus, not bounds.

### Windows scratch path binding

Bind a caller-verified private local directory before staging. The binding uses
the local volume identifier rather than reopening through a drive letter and
holds ordinary directory handles without delete sharing. A mapped stage borrows
the binding and accepts only a fresh single stage leaf. Holding these handles
does not establish private permissions or prevent every metadata change. The
caller still owns the trusted ancestry and must supervise worker failure.
See [Windows final path queries](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getfinalpathnamebyhandlew)
and [Rust Windows sharing options](https://doc.rust-lang.org/std/os/windows/fs/trait.OpenOptionsExt.html).

### Windows staged-worker composition fixture

Build the existing test executable with Cargo, then use its reported path:

~~~text
cargo test --manifest-path native/operations/Cargo.toml --locked --test publication_line_index --no-run
python -B native/operations/tests/windows_staging_worker.py --binary ABSOLUTE_TEST_EXE --fixture-root ABSOLUTE_DISPOSABLE_DIRECTORY
~~~

This uses the production scanner's Windows job supervisor and existing native
directory identity and private-child primitives. A locally built Rust test
maps a whole line, refuses an existing leaf without changing it, and leaves
no stage file. A separate small child emits a provisional record and exits
nonzero; both outcomes must settle, and the second is not a successful worker
result. Use only an operator-owned local fixture directory and test executable. The test leaves
empty fixture directories for disposal by the caller.

This fixture uses parent-owned test scratch. It does not claim that the production
scanner owns private scratch, consumes spooled text, or grants a publication
receipt for the mapped stage. No scanner policy or dispatcher is changed.
