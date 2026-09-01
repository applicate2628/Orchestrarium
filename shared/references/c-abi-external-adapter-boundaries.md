# C ABI for External Adapter Boundaries

<!-- CABI-SEMANTIC id="CABI.scope" -->
## Purpose and applicability

Use a versioned C Application Binary Interface (ABI) when a binary adapter is
replaceable or when its producer and consumer may be built, upgraded, or
distributed independently. Typical examples are optional shared libraries,
plugin backends, and language-neutral capability adapters. The stable contract
belongs to a neutral boundary; provider-native types, handles, allocators,
caches, and cleanup stay behind the adapter.

A C ABI is not required merely because two modules use different source
languages. A private boundary inside one controlled build graph may use the
build's native interface when independent binary compatibility is not a
requirement. Before publishing such a boundary, record whether independent
replacement or distribution is expected; once external consumers depend on a
native ABI, changing that choice becomes a compatibility migration.

This reference defines a design discipline, not a universal platform or
compiler policy. Each repository must fill the concretization fields below and
verify its own supported matrix.

<!-- CABI-SEMANTIC id="CABI.not-wire" -->
## Not a persistence, file, or IPC contract

This ABI is an in-process call boundary. It is explicitly **not** a persistence
format, file format, network protocol, or inter-process communication (IPC)
contract. Do not write public ABI records directly to disk or transmit their
native bytes between processes. A file or IPC boundary needs its own versioned
wire schema, byte order, framing, validation, size limits, and compatibility
rules. Process adapters exchange that wire data; they do not share pointers,
native layouts, function tables, or internal object graphs.

<!-- CABI-SEMANTIC id="CABI.contract-shape" -->
## Contract shape

Publish one small C-compatible header. It defines linkage, export visibility,
and calling convention once, and every public entry point uses those macros.
The producer and consumer modes must be intentional and testable. For example:

```c
#include <stdint.h>

#if defined(_WIN32)
#  if defined(ADAPTER_BUILD)
#    define ADAPTER_API __declspec(dllexport)
#  else
#    define ADAPTER_API __declspec(dllimport)
#  endif
#  define ADAPTER_CALL __cdecl
#else
#  define ADAPTER_API __attribute__((visibility("default")))
#  define ADAPTER_CALL
#endif

#ifdef __cplusplus
extern "C" {
#endif

typedef uint32_t adapter_status;
typedef struct adapter_api adapter_api;

ADAPTER_API adapter_status ADAPTER_CALL
adapter_get_api(uint32_t requested_major,
                uint32_t requested_minor,
                uint32_t output_size,
                adapter_api *output);

#ifdef __cplusplus
}
#endif
```

Export one version-negotiated entry point or one versioned function table
returned by that entry point. The consumer supplies the ABI major and minor it
supports plus the size of its output table. The producer returns a compatible
minor and initializes only the prefix admitted by both the negotiated version
and the caller's size. A major mismatch returns a stable unsupported-version
status. A newer minor may append optional trailing fields or functions; it must
not reinterpret, reorder, or remove an existing field.

Use C linkage, explicit visibility, and an explicit calling convention. Do not
rely on C++ name mangling or ambient build defaults. Hide symbols that are not
part of the public ABI. The exported-symbol inventory is part of the contract
and needs a machine-checkable oracle.

<!-- CABI-SEMANTIC id="CABI.data" -->
## Data representation and evolution

- Use opaque incomplete handle types for state. The adapter creates and
  destroys its handles; callers do not allocate, copy, inspect, or use them
  after destruction.
- Cross the boundary with fixed-width integers, byte spans, function pointers,
  opaque handles, and plain C records. Represent statuses and enumerations as a
  fixed-width integer type plus named constants, not an enum with
  implementation-selected storage.
- Begin every extensible record with `uint32_t size; uint32_t version;`. A
  receiver reads only fields covered by both values. Callers zero reserved
  fields and unknown trailing bytes; a producer rejects nonzero reserved input
  unless the negotiated version assigns it meaning.
- Append fields for a compatible minor version. Never insert or reorder fields,
  reuse retired values, or change the interpretation of an existing bit.
- Represent UTF-8 text as pointer plus a contract-selected fixed-width length.
  The length is authoritative. A terminator, locale, wide-character type, and
  compiler-sized length are not implicit parts of the contract.
- Use fixed-width integer flags for booleans and bitmasks. Define valid values;
  unknown input bits are zero unless feature negotiation explicitly admits
  them.
- Do not expose C++ containers or strings, exceptions, run-time type identities,
  ownership-bearing objects, standard-library file handles, allocator-specific
  memory, or locale-dependent types.

Every public record has compile-time size, alignment, and relevant field-offset
assertions in each participating language mode. Prefer natural alignment. If a
record requires packing or stronger alignment, scope that declaration narrowly
and test it; never depend on ambient packing state.

<!-- CABI-SEMANTIC id="CABI.ownership" -->
## Ownership, status, and diagnostics

For every handle, pointer, span, callback, and function-table reference,
document the owner, validity interval, release operation, and whether the callee
may retain it. Borrowed inputs are valid only for the call unless the contract
explicitly states a longer lifetime.

Prefer caller-provided output buffers with a two-call query pattern: one call
reports the required length and the next fills a sufficiently large buffer. If
adapter allocation is necessary, expose the exact matching adapter deallocator.
Memory allocated by one side is never released through the other side's
runtime.

Define one stable status type and the possible status outcomes for every
function. On failure, output handles are null and output counts or lengths take
their documented safe values. Diagnostic text supplements the status; it never
replaces it. Provide either a bounded caller buffer or a bounded error-detail
query. Exceptions and other language-runtime unwinding must be caught and
translated inside the adapter.

<!-- CABI-SEMANTIC id="CABI.bulk" -->
## Bulk and numerical data

A generic bulk view states all information needed to validate access:

- element encoding, `element_size`, and required `element_alignment`;
- data pointer, element `count`, and writable `capacity` where applicable;
- total `byte_capacity` and `stride_bytes`;
- mutability, overlap/aliasing rules, and borrowed-buffer lifetime; and
- domain semantics such as dimension, units, coordinate frame, index base,
  sentinel values, and finite-value policy when relevant.

For a writable view, require `count <= capacity`. When `count > 1`, require
`stride_bytes >= element_size`. The accessible extent is zero when `count == 0`;
otherwise calculate `(count - 1) * stride_bytes + element_size` with checked
arithmetic and require the result not to exceed `byte_capacity`. Reject
overflow, short stride, misalignment, unsupported encodings, non-null
inconsistencies, and a null pointer with positive extent before reading,
allocating, or writing. A specialized packed or structure-of-arrays view may
replace this formula only when its owner and equivalent falsifying
preconditions are explicit.

<!-- CABI-SEMANTIC id="CABI.callbacks" -->
## Callbacks, concurrency, and lifetime

Callbacks take an explicit `void *user_data`. The registering side owns that
storage and keeps it valid until deregistration has completed. The contract
states whether callbacks are synchronous or asynchronous, which threads may
invoke them, whether concurrent invocation is possible, and whether re-entry is
allowed. When a callback may outlive its registering call, a drain or unregister
operation proves that no later callback can occur before `user_data` is freed.

Document context ownership, thread safety, cancellation points, and floating-
point environment behavior. Cancellation returns a distinct stable status only
after owned cleanup finishes. The adapter does not silently change the caller's
floating-point control state: it saves and restores state or declares an
exclusive-context precondition.

Initialization and shutdown are either idempotent or explicitly single-shot.
The binary cannot be unloaded while a handle, operation, callback,
adapter-owned allocation, or function-table reference is live. A drain/shutdown
operation establishes quiescence; failure to reach quiescence remains visible
and does not claim unload is safe. A negotiated function table is immutable for
its documented lifetime, and unavailable optional slots are null.

<!-- CABI-SEMANTIC id="CABI.compatibility" -->
## Compatibility and validation

The public header must compile in the repository's declared C and C++ language
modes, in producer and consumer configurations, with the repository's warning
policy. Validate the built binary's calling convention, record layout,
visibility, and export inventory rather than inferring them from source alone.

For every supported ABI release, exercise both compatibility directions: old
consumer with new producer, and new consumer with old producer. Include negative
tests for at least:

- unsupported major versions and unavailable optional functions;
- undersized tables/records and nonzero reserved inputs;
- null, invalid, stale, and double-destroyed handles;
- undersized buffers, checked-arithmetic overflow, misalignment, and short
  stride;
- allocation/free pairing and failure-path cleanup;
- callback after unregister, cancellation during cleanup, and unsafe unload;
- stable status/diagnostic behavior; and
- unintended exports or language-mangled public symbols.

Deprecation retains defined behavior throughout the supported ABI major.
Introduce a replacement in a later minor, document the overlap, and remove the
old surface only in a new major with a migration plan. Never reuse a retired
status value, field, function-table slot, or exported symbol for another
meaning.

<!-- CABI-SEMANTIC id="CABI.concretization" -->
## Repository-local concretization

Before implementation, the owning repository records these fields in the
accepted design and passes them to toolchain implementation and review. A field
may say `not applicable` only with a reason and a falsifying probe.

- **Boundary owner and consumers:** the contract owner, producer(s), consumer(s),
  and the evidence that they can vary independently.
- **Supported platforms and architectures:** each supported operating-system,
  architecture, data-model, and binary-format cell.
- **Language baselines:** the C mode, C++ mode, warning policy, and header
  compatibility expectations.
- **Toolchain matrix:** repository-selected producer/consumer toolchain cells;
  no generic reference chooses these on the repository's behalf.
- **Calling convention and export mechanism:** public macros, producer/consumer
  modes, symbol visibility mechanism, and symbol inventory owner.
- **ABI version and support window:** current major/minor, compatibility window,
  feature-negotiation rules, and deprecation/removal policy.
- **Layout and symbol oracles:** compile-time layout assertions plus the binary
  inspection command or test that proves calling convention and public exports.
- **Compatibility matrix:** old/new producer-consumer cells, negative cases,
  target environment, evidence location, and gate owner.
- **Lifecycle and unload policy:** initialization, handle/allocation/callback
  quiescence, shutdown, unload proof, and failure behavior.

Also name repository-specific scalar/index encodings, units/frames, thread and
re-entry model, diagnostic/status registry, performance constraints, packaging
surface, and rollback path wherever those concerns apply.

<!-- CABI-SEMANTIC id="CABI.acceptance" -->
## Acceptance checklist

- [ ] Independent binary replacement/distribution is required, or the decision
  for a controlled native boundary is recorded.
- [ ] The public header has C linkage, export, and calling-convention macros and
  exports only the intended version-negotiation surface.
- [ ] Major/minor negotiation, table/record size checks, reserved-zero rules,
  and append-only evolution are tested.
- [ ] State is opaque; values are fixed-width and ownership/lifetime rules are
  explicit.
- [ ] Status, diagnostics, allocation/free, callbacks, cancellation,
  concurrency, shutdown, and unload have observable failure behavior.
- [ ] Bulk views validate encoding, size, alignment, extent, overflow,
  mutability, aliasing, and lifetime before access.
- [ ] The declared C/C++ producer-consumer matrix, layout assertions, export
  oracle, negative tests, and both compatibility directions pass.
- [ ] The ABI is not reused as persistence, file, network, or IPC encoding.
- [ ] Every Repository-local concretization field is present and evidence-bound.

## Terms and Abbreviations

- **ABI:** Application Binary Interface, the binary-level calling and data
  contract between separately built components.
- **C ABI:** an ABI exposed with C linkage and C-compatible data and layout
  rules.
- **IPC:** inter-process communication between separate processes.
- **Plain C record:** a C-compatible structure with no language-runtime
  ownership or behavior crossing the boundary.
