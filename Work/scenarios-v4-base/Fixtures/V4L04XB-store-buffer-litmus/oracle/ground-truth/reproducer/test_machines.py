"""Validation matrix for the oracle reproducer.

Layer 1: SB-A must reproduce the DOCUMENTED classic-TSO litmus outcomes
         (SB, MP, LB, SB+fences, n6, n5, 2+2W, IRIW). These truths are from
         the x86-TSO literature (Owens/Sarkar/Sewell, "A Better x86 Memory
         Model: x86-TSO"; Intel SDM litmus examples), not from this codebase.
Layer 2: structural cross-checks between machine configurations
         (SC subset-of A and B; B with unbounded capacity + forwarding == A;
         capacity-0 forwarding irrelevance; SC == naive interleaving).
Layer 3: hand-derivable signature cases for the SB-B deviations
         (no forwarding; capacity-2 forced write-back).
"""

from __future__ import annotations

import itertools
import unittest

from machines import (
    SB_A,
    SB_B,
    SC,
    MachineParams,
    enumerate_finals,
    observation_holds,
    reachable,
)


def sc_interleavings(threads):
    """Independent naive-interleaving oracle for the SC configuration."""
    from machines import _collect_names

    variables, reg_names = _collect_names(threads)
    finals = set()
    order_pool = []
    for i, program in enumerate(threads):
        order_pool.extend([i] * len(program))
    for order in set(itertools.permutations(order_pool)):
        mem: dict[str, int] = {v: 0 for v in variables}
        regs = [{r: 0 for r in names} for names in reg_names]
        pcs = [0] * len(threads)
        for i in order:
            op = threads[i][pcs[i]]
            pcs[i] += 1
            kind = op[0]
            if kind == "ST":
                mem[op[1]] = op[2]
            elif kind == "STR":
                mem[op[1]] = regs[i].get(op[2], 0)
            elif kind == "LD":
                regs[i][op[1]] = mem.get(op[2], 0)
            elif kind == "FENCE":
                pass
            elif kind == "CAS":
                if mem.get(op[2], 0) == op[3]:
                    mem[op[2]] = op[4]
                    regs[i][op[1]] = 1
                else:
                    regs[i][op[1]] = 0
        finals.add((tuple(sorted(mem.items())), tuple(tuple(sorted(r.items())) for r in regs)))
    return finals


def _canon(threads, final):
    """Project a final onto fully-populated (mem, regs) tuples for comparison."""
    return final


SB_TEST = [
    [["ST", "x", 1], ["LD", "r1", "y"]],
    [["ST", "y", 1], ["LD", "r1", "x"]],
]
SB_FENCED = [
    [["ST", "x", 1], ["FENCE"], ["LD", "r1", "y"]],
    [["ST", "y", 1], ["FENCE"], ["LD", "r1", "x"]],
]
MP = [
    [["ST", "x", 1], ["ST", "y", 1]],
    [["LD", "r1", "y"], ["LD", "r2", "x"]],
]
LB = [
    [["LD", "r1", "x"], ["ST", "y", 1]],
    [["LD", "r1", "y"], ["ST", "x", 1]],
]
N6 = [
    [["ST", "x", 1], ["LD", "r1", "x"], ["LD", "r2", "y"]],
    [["ST", "y", 2], ["ST", "x", 2]],
]
N5 = [
    [["ST", "x", 1], ["LD", "r1", "x"]],
    [["ST", "x", 2], ["LD", "r1", "x"]],
]
W2PLUS2 = [
    [["ST", "x", 1], ["ST", "y", 2]],
    [["ST", "y", 1], ["ST", "x", 2]],
]
IRIW = [
    [["ST", "x", 1]],
    [["ST", "y", 1]],
    [["LD", "r1", "x"], ["LD", "r2", "y"]],
    [["LD", "r1", "y"], ["LD", "r2", "x"]],
]


class Layer1ClassicTsoLitmus(unittest.TestCase):
    """SB-A must equal classic TSO on the documented corpus."""

    def test_store_buffering_relaxation_allowed(self) -> None:
        self.assertTrue(reachable(SB_TEST, SB_A, {"T1.r1": 0, "T2.r1": 0}))
        self.assertFalse(reachable(SB_TEST, SC, {"T1.r1": 0, "T2.r1": 0}))

    def test_store_buffering_fenced_forbidden(self) -> None:
        self.assertFalse(reachable(SB_FENCED, SB_A, {"T1.r1": 0, "T2.r1": 0}))

    def test_message_passing_preserved(self) -> None:
        self.assertFalse(reachable(MP, SB_A, {"T2.r1": 1, "T2.r2": 0}))

    def test_load_buffering_forbidden(self) -> None:
        self.assertFalse(reachable(LB, SB_A, {"T1.r1": 1, "T2.r1": 1}))

    def test_n6_forwarding_outcome_allowed(self) -> None:
        # Owens/Sarkar/Sewell n6: r1=1, r2=0, final x=1 is TSO-allowed
        # (only via store-to-load forwarding).
        self.assertTrue(reachable(N6, SB_A, {"T1.r1": 1, "T1.r2": 0, "x": 1}))

    def test_n5_forbidden(self) -> None:
        # n5: r1(T1)=2 and r1(T2)=1 is TSO-forbidden.
        self.assertFalse(reachable(N5, SB_A, {"T1.r1": 2, "T2.r1": 1}))

    def test_2_plus_2w_forbidden(self) -> None:
        # 2+2W: x=1 and y=1 finally is TSO-forbidden (needs write reordering).
        self.assertFalse(reachable(W2PLUS2, SB_A, {"x": 1, "y": 1}))

    def test_iriw_forbidden(self) -> None:
        self.assertFalse(
            reachable(IRIW, SB_A, {"T3.r1": 1, "T3.r2": 0, "T4.r1": 1, "T4.r2": 0})
        )


class Layer2StructuralCrossChecks(unittest.TestCase):
    PROGRAMS = [SB_TEST, SB_FENCED, MP, LB, N6, N5, W2PLUS2, IRIW,
                [[["ST", "x", 1], ["ST", "y", 1], ["ST", "z", 1], ["LD", "r1", "x"]]],
                [[["ST", "x", 1], ["ST", "y", 1], ["LD", "r1", "x"]],
                 [["CAS", "r1", "x", 0, 5], ["LD", "r2", "y"]]],
                [[["ST", "x", 1], ["STR", "y", "r1"]],
                 [["LD", "r1", "x"], ["ST", "x", 3], ["FENCE"], ["LD", "r2", "x"]]]]

    def test_sc_subset_of_both_machines(self) -> None:
        for threads in self.PROGRAMS:
            sc = enumerate_finals(threads, SC)
            a = enumerate_finals(threads, SB_A)
            b = enumerate_finals(threads, SB_B)
            self.assertTrue(sc <= a, "SC must embed into SB-A")
            self.assertTrue(sc <= b, "SC must embed into SB-B")

    def test_sc_equals_naive_interleaving(self) -> None:
        for threads in self.PROGRAMS:
            self.assertEqual(enumerate_finals(threads, SC), sc_interleavings(threads))

    def test_unbounded_forwarding_b_config_equals_a(self) -> None:
        b_as_a = MachineParams(name="B-as-A", capacity=None, forwarding=True)
        for threads in self.PROGRAMS:
            self.assertEqual(enumerate_finals(threads, b_as_a), enumerate_finals(threads, SB_A))

    def test_capacity_zero_forwarding_irrelevant(self) -> None:
        sc_fwd = MachineParams(name="SC-fwd", capacity=0, forwarding=True)
        for threads in self.PROGRAMS:
            self.assertEqual(enumerate_finals(threads, sc_fwd), enumerate_finals(threads, SC))


class Layer3DeviationSignatures(unittest.TestCase):
    def test_own_store_invisible_under_b(self) -> None:
        threads = [[["ST", "x", 1], ["LD", "r1", "x"]]]
        self.assertFalse(reachable(threads, SB_A, {"T1.r1": 0}))
        self.assertTrue(reachable(threads, SB_B, {"T1.r1": 0}))

    def test_forced_writeback_pair(self) -> None:
        two_stores = [[["ST", "x", 1], ["ST", "y", 1], ["LD", "r1", "x"]]]
        three_stores = [[["ST", "x", 1], ["ST", "y", 1], ["ST", "z", 1], ["LD", "r1", "x"]]]
        # two stores: buffer not full, x may still be buffered at the load
        self.assertTrue(reachable(two_stores, SB_B, {"T1.r1": 0}))
        # three stores: the third ST forces x into memory before the load
        self.assertFalse(reachable(three_stores, SB_B, {"T1.r1": 0}))
        # SB-A forwards in both shapes
        self.assertFalse(reachable(two_stores, SB_A, {"T1.r1": 0}))
        self.assertFalse(reachable(three_stores, SB_A, {"T1.r1": 0}))

    def test_fence_restores_own_visibility_under_b(self) -> None:
        threads = [[["ST", "x", 1], ["FENCE"], ["LD", "r1", "x"]]]
        self.assertFalse(reachable(threads, SB_B, {"T1.r1": 0}))

    def test_cas_drains_before_test(self) -> None:
        # T1 buffers x=1 then CASes x expecting 1: drain-first makes it succeed.
        threads = [[["ST", "x", 1], ["CAS", "r1", "x", 1, 2]]]
        self.assertFalse(reachable(threads, SB_B, {"T1.r1": 0}))
        self.assertFalse(reachable(threads, SB_A, {"T1.r1": 0}))
        self.assertTrue(reachable(threads, SB_B, {"T1.r1": 1, "x": 2}))


if __name__ == "__main__":
    unittest.main()
