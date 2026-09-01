"""Exhaustive reachability enumerator for the SB-A / SB-B store-buffer machines.

This module is the ORACLE REPRODUCER for the V4L04X store-buffer litmus roots.
Ground truth is never hand-asserted: every observation class is computed by
exhaustive breadth-first enumeration of the full configuration space of each
machine, for both the reachable (witness exists) and unreachable (no final
configuration satisfies the predicate) directions.

Machine semantics (must match inputs/sources/machine-spec.md verbatim):

Shared by SB-A and SB-B
- Shared memory: named variables, integer values, all initialised to 0.
- Per-thread registers, integer values, all initialised to 0.
- Each thread executes its instruction list in strict program order.
- Instructions:
    ST  v c    append store (v, c) to the executing thread's FIFO buffer
    STR v r    same as ST with the executing thread's current register value
    LD  r v    load into register r (source rule differs per machine)
    FENCE      write back the whole own buffer to memory, oldest first,
               as one atomic step
    CAS r v old new
               write back the whole own buffer (oldest first), then in the
               same atomic step: if mem[v] == old then mem[v] := new, r := 1
               else r := 0
- Spontaneous write-back: at any scheduling step, the OLDEST entry of any
  thread's non-empty buffer may be written to memory (also after the owning
  thread has finished its program).
- Termination: a run is complete when every thread finished its program AND
  every buffer is empty (trailing spontaneous write-backs).

SB-A only
- Buffer capacity: unbounded.
- LD r v: if the executing thread's own buffer holds one or more entries for
  v, r receives the value of the NEWEST such entry (store-to-load
  forwarding); otherwise r receives mem[v].

SB-B only
- Buffer capacity: two entries. If a ST/STR executes while the buffer holds
  two entries, the OLDEST entry is written to memory first (forced
  write-back) and the new entry is appended; both happen inside the single
  ST/STR step.
- LD r v: r always receives mem[v]. The executing thread's own buffered
  stores are NOT visible to its own loads.

SC (validation-only machine): capacity 0 -> every ST/STR writes memory
directly inside its own step; buffers always empty; LD reads memory.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class MachineParams:
    name: str
    capacity: int | None  # None = unbounded, 0 = SC (no buffering)
    forwarding: bool


SB_A = MachineParams(name="SB-A", capacity=None, forwarding=True)
SB_B = MachineParams(name="SB-B", capacity=2, forwarding=False)
SC = MachineParams(name="SC", capacity=0, forwarding=False)

# Config layout (all hashable):
#   pcs:  tuple[int, ...]                      per-thread program counter
#   bufs: tuple[tuple[tuple[str, int], ...]]   per-thread FIFO, oldest first
#   mem:  tuple[tuple[str, int], ...]          sorted (var, value) pairs
#   regs: tuple[tuple[tuple[str, int], ...]]   per-thread sorted (reg, value)


def _collect_names(threads: list[list[list[Any]]]) -> tuple[tuple[str, ...], tuple[tuple[str, ...], ...]]:
    variables: set[str] = set()
    per_thread_regs: list[tuple[str, ...]] = []
    for program in threads:
        regs: set[str] = set()
        for op in program:
            kind = op[0]
            if kind in ("ST",):
                variables.add(op[1])
            elif kind == "STR":
                variables.add(op[1])
                regs.add(op[2])
            elif kind == "LD":
                regs.add(op[1])
                variables.add(op[2])
            elif kind == "CAS":
                regs.add(op[1])
                variables.add(op[2])
            elif kind == "FENCE":
                pass
            else:
                raise ValueError(f"unknown op kind: {kind!r}")
        per_thread_regs.append(tuple(sorted(regs)))
    return tuple(sorted(variables)), tuple(per_thread_regs)


def _mem_get(mem: tuple[tuple[str, int], ...], var: str) -> int:
    for name, value in mem:
        if name == var:
            return value
    raise KeyError(var)


def _mem_set(mem: tuple[tuple[str, int], ...], var: str, value: int) -> tuple[tuple[str, int], ...]:
    return tuple((name, value if name == var else old) for name, old in mem)


def _reg_set(regs: tuple[tuple[str, int], ...], reg: str, value: int) -> tuple[tuple[str, int], ...]:
    return tuple((name, value if name == reg else old) for name, old in regs)


def _reg_get(regs: tuple[tuple[str, int], ...], reg: str) -> int:
    for name, value in regs:
        if name == reg:
            return value
    raise KeyError(reg)


def _drain(buf: tuple[tuple[str, int], ...], mem: tuple[tuple[str, int], ...]) -> tuple[tuple[str, int], ...]:
    for var, value in buf:
        mem = _mem_set(mem, var, value)
    return mem


def enumerate_finals(
    threads: list[list[list[Any]]],
    params: MachineParams,
) -> set[tuple[tuple[tuple[str, int], ...], tuple[tuple[tuple[str, int], ...], ...]]]:
    """Return the set of reachable final (mem, regs-per-thread) pairs."""
    variables, reg_names = _collect_names(threads)
    init_mem = tuple((v, 0) for v in variables)
    init_regs = tuple(tuple((r, 0) for r in names) for names in reg_names)
    n = len(threads)
    init = (tuple(0 for _ in range(n)), tuple(() for _ in range(n)), init_mem, init_regs)

    seen = {init}
    queue: deque = deque([init])
    finals: set = set()

    while queue:
        pcs, bufs, mem, regs = queue.popleft()
        successors = []

        for i in range(n):
            program = threads[i]
            pc = pcs[i]
            buf = bufs[i]

            # spontaneous write-back of the oldest entry (any time, incl. done)
            if buf:
                var, value = buf[0]
                successors.append((
                    pcs,
                    tuple(buf[1:] if j == i else bufs[j] for j in range(n)),
                    _mem_set(mem, var, value),
                    regs,
                ))

            if pc >= len(program):
                continue
            op = program[pc]
            kind = op[0]
            new_pcs = tuple(pc + 1 if j == i else pcs[j] for j in range(n))

            if kind in ("ST", "STR"):
                var = op[1]
                value = _reg_get(regs[i], op[2]) if kind == "STR" else op[2]
                if params.capacity == 0:
                    successors.append((new_pcs, bufs, _mem_set(mem, var, value), regs))
                else:
                    new_buf = buf
                    new_mem = mem
                    if params.capacity is not None and len(new_buf) == params.capacity:
                        oldest_var, oldest_value = new_buf[0]
                        new_mem = _mem_set(new_mem, oldest_var, oldest_value)
                        new_buf = new_buf[1:]
                    new_buf = new_buf + ((var, value),)
                    successors.append((
                        new_pcs,
                        tuple(new_buf if j == i else bufs[j] for j in range(n)),
                        new_mem,
                        regs,
                    ))
            elif kind == "LD":
                reg, var = op[1], op[2]
                value = None
                if params.forwarding:
                    for bvar, bvalue in reversed(buf):
                        if bvar == var:
                            value = bvalue
                            break
                if value is None:
                    value = _mem_get(mem, var)
                successors.append((
                    new_pcs,
                    bufs,
                    mem,
                    tuple(_reg_set(regs[i], reg, value) if j == i else regs[j] for j in range(n)),
                ))
            elif kind == "FENCE":
                successors.append((
                    new_pcs,
                    tuple(() if j == i else bufs[j] for j in range(n)),
                    _drain(buf, mem),
                    regs,
                ))
            elif kind == "CAS":
                reg, var, old, new = op[1], op[2], op[3], op[4]
                drained = _drain(buf, mem)
                if _mem_get(drained, var) == old:
                    drained = _mem_set(drained, var, new)
                    result = 1
                else:
                    result = 0
                successors.append((
                    new_pcs,
                    tuple(() if j == i else bufs[j] for j in range(n)),
                    drained,
                    tuple(_reg_set(regs[i], reg, result) if j == i else regs[j] for j in range(n)),
                ))
            else:  # pragma: no cover - guarded in _collect_names
                raise ValueError(kind)

        if not successors:
            # all threads done and all buffers empty
            finals.add((mem, regs))
            continue

        for successor in successors:
            if successor not in seen:
                seen.add(successor)
                queue.append(successor)

    return finals


def observation_holds(
    final: tuple[tuple[tuple[str, int], ...], tuple[tuple[tuple[str, int], ...], ...]],
    observation: dict[str, int],
) -> bool:
    """observation keys: 'x' (final memory) or 'T1.r1' (thread register, 1-based)."""
    mem, regs = final
    for key, expected in observation.items():
        if "." in key:
            thread_part, reg = key.split(".", 1)
            index = int(thread_part[1:]) - 1
            if _reg_get(regs[index], reg) != expected:
                return False
        else:
            if _mem_get(mem, key) != expected:
                return False
    return True


def reachable(threads: list[list[list[Any]]], params: MachineParams, observation: dict[str, int]) -> bool:
    return any(observation_holds(final, observation) for final in enumerate_finals(threads, params))


def classify(threads: list[list[list[Any]]], observation: dict[str, int]) -> str:
    finals_a = enumerate_finals(threads, SB_A)
    finals_b = enumerate_finals(threads, SB_B)
    in_a = any(observation_holds(f, observation) for f in finals_a)
    in_b = any(observation_holds(f, observation) for f in finals_b)
    if in_a and in_b:
        return "both"
    if in_a:
        return "a-only"
    if in_b:
        return "b-only"
    return "neither"


def parse_program(text: str) -> list[list[list[Any]]]:
    """Parse the exact surface syntax used in inputs/sources/programs.md.

    Threads separated by lines 'thread Tn:'; one instruction per line:
      ST v c | STR v r | LD r v | FENCE | CAS r v old new
    """
    threads: list[list[list[Any]]] = []
    current: list[list[Any]] | None = None
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if line.lower().startswith("thread"):
            current = []
            threads.append(current)
            continue
        if current is None:
            raise ValueError("instruction before first thread header")
        parts = line.replace(",", " ").split()
        kind = parts[0].upper()
        if kind == "ST":
            current.append(["ST", parts[1], int(parts[2])])
        elif kind == "STR":
            current.append(["STR", parts[1], parts[2]])
        elif kind == "LD":
            current.append(["LD", parts[1], parts[2]])
        elif kind == "FENCE":
            current.append(["FENCE"])
        elif kind == "CAS":
            current.append(["CAS", parts[1], parts[2], int(parts[3]), int(parts[4])])
        else:
            raise ValueError(f"unknown instruction: {line!r}")
    return threads
