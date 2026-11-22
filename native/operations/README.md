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
