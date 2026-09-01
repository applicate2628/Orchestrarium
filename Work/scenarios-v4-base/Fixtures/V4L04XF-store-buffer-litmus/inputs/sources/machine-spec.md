# Store-buffer machine specification (SB-A and SB-B)

This document is the complete and only definition of the two machines. Both
machines are defined here from scratch. Do not assume the behavior of any
textbook, hardware, or language memory model: where this text differs from a
model you know, THIS TEXT WINS. Everything needed to decide every question in
`programs.md` is in this file.

## 1. Common execution model

- Shared memory holds named variables (`x`, `y`, `z`, `f`, ...). Every
  variable holds an integer and is initialised to `0`.
- Each thread `T1`, `T2`, ... has its own private registers (`r1`, `r2`,
  ...). Every register holds an integer and is initialised to `0`. A thread
  can never read or write another thread's registers.
- Each thread also has its own private FIFO store buffer: an ordered queue of
  `(variable, value)` entries, oldest entry first. Buffers start empty.
- Each thread executes its instruction list strictly in program order. There
  is no speculation and no local reordering of any kind.
- An execution is an arbitrary interleaving of ATOMIC ACTIONS. One action is
  exactly one of:
  1. one thread executing its next instruction (all effects of that
     instruction, as defined below, happen inside the single action), or
  2. a spontaneous write-back: the OLDEST entry of any one thread's
     non-empty store buffer is removed and written to shared memory.
- The scheduler is adversarial and unfair: between any two actions, any
  number of other actions (including zero) may occur, in any order. A
  spontaneous write-back of a thread's buffer may occur at any point,
  including while that thread is between instructions and after that thread
  has finished its program.
- A run is COMPLETE when every thread has executed all of its instructions
  AND every store buffer is empty (remaining entries leave via spontaneous
  write-backs). All questions are about complete runs.
- An OBSERVATION is a conjunction of equality claims over the final state of
  a complete run: `Tn.rk = c` claims thread `n`'s register `rk` ends with
  value `c`; a bare `v = c` claims shared variable `v` ends with value `c`.
  An observation is REACHABLE on a machine if at least one complete run of
  the program on that machine satisfies all of its claims simultaneously.

## 2. Instructions

| Instruction | Meaning |
|---|---|
| `ST v c` | Store constant `c` to variable `v`: append the entry `(v, c)` to the executing thread's own store buffer. Nothing is written to shared memory by this instruction itself (but see the SB-B capacity rule). |
| `STR v r` | Same as `ST`, except the stored value is the current value of the executing thread's register `r`. |
| `LD r v` | Load variable `v` into the executing thread's register `r`. The value source differs per machine; see sections 3 and 4. |
| `FENCE` | Write back ALL entries of the executing thread's own store buffer to shared memory, oldest first, and leave the buffer empty. The whole drain is one atomic action. A fence never affects any other thread's buffer. |
| `CAS r v c_old c_new` | Compare-and-swap. In one atomic action: first write back ALL entries of the executing thread's own store buffer to shared memory (oldest first, buffer left empty); then, if shared memory now holds `v = c_old`, write `v = c_new` to shared memory and set register `r` to `1`; otherwise leave `v` unchanged and set `r` to `0`. The drain happens on success AND on failure. |

Write-backs (spontaneous, forced, fence-driven, CAS-driven) always remove
the OLDEST entry first and write entries to shared memory in FIFO order. A
thread's stores therefore reach shared memory exactly in program order.

## 3. Machine SB-A

- Buffer capacity: UNBOUNDED. `ST`/`STR` never write to memory themselves.
- `LD r v` (store-to-load forwarding): if the executing thread's OWN buffer
  currently contains one or more entries for `v`, the load returns the value
  of the NEWEST such entry and memory is not consulted. Otherwise the load
  returns the current shared-memory value of `v`. A load never sees another
  thread's buffer and never removes buffer entries.

Micro-example (SB-A). One thread runs `ST x 1; LD r1 x`. The store enters
the buffer. The load finds the buffer entry `(x, 1)` and forwards it, so
`r1 = 1` in every complete run, even though `x` in memory may still be `0`
at the moment the load executes.

## 4. Machine SB-B

- Buffer capacity: TWO entries. If a `ST`/`STR` executes while the executing
  thread's buffer already holds two entries, the OLDEST entry is first
  removed and written to shared memory (forced write-back), and then the new
  entry is appended. Both happen inside the same single atomic action as the
  store instruction. The buffer can therefore never hold more than two
  entries.
- `LD r v` (no forwarding): the load ALWAYS returns the current
  shared-memory value of `v`. The executing thread's own buffered stores are
  invisible to its own loads.

Micro-example (SB-B). One thread runs `ST x 1; LD r1 x`. The store enters
the buffer. The load reads shared memory: if the entry `(x, 1)` has not yet
been written back, the load returns `0`. Both `r1 = 0` and `r1 = 1` are
reachable — unlike SB-A, where only `r1 = 1` is.

## 5. Everything else is identical

The two machines differ ONLY in the two respects above (capacity with its
forced write-back, and load forwarding). Instruction set, FIFO write-back
order, `FENCE` and `CAS` semantics, spontaneous write-backs, scheduling,
initial values, termination, and observations are identical.

## Terms and Abbreviations

- `FIFO`: first in, first out — the oldest buffer entry leaves first.
- `CAS`: compare-and-swap, the atomic test-and-set instruction defined above.
- `forwarding`: a load taking its value from the executing thread's own
  store buffer instead of shared memory.
- `write-back`: moving one buffer entry into shared memory.
