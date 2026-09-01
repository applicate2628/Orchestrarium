"""Frozen litmus-program corpus for V4L04XB (base) / V4L04XF (frontier).

Each program: threads + two named observations (O1, O2). Classes are
COMPUTED by machines.classify — never asserted here. 'family' is authoring
metadata only and never ships in visible inputs.

Observation keys: 'Tn.reg' = final register value of thread n (1-based);
bare name = final memory value of that variable.

Order below is the frozen presentation order (P01.. assigned by position).
"""

from __future__ import annotations

BASE_PROGRAMS = [
    # P01 — warmup: cross-thread visibility + store must land
    ("B-W1", {
        "threads": [[["ST", "x", 1]], [["LD", "r1", "x"]]],
        "obs": {"O1": {"T2.r1": 1}, "O2": {"x": 0}},
        "family": "warmup",
    }),
    # P02 — own-store visibility (SB-B signature)
    ("B-F1a", {
        "threads": [[["ST", "x", 1], ["LD", "r1", "x"]]],
        "obs": {"O1": {"T1.r1": 0}, "O2": {"T1.r1": 1}},
        "family": "own-read",
    }),
    # P03 — fence restores own visibility
    ("B-F1b", {
        "threads": [[["ST", "x", 1], ["FENCE"], ["LD", "r1", "x"]]],
        "obs": {"O1": {"T1.r1": 0}, "O2": {"T1.r1": 1, "x": 1}},
        "family": "own-read+fence",
    }),
    # P04 — two stores: below capacity, own read may still be stale in SB-B
    ("B-F2a", {
        "threads": [[["ST", "x", 1], ["ST", "y", 2], ["LD", "r1", "x"]]],
        "obs": {"O1": {"T1.r1": 0}, "O2": {"T1.r1": 1}},
        "family": "forced-flush-2",
    }),
    # P05 — three stores: forced write-back flips P04's answer
    ("B-F2b", {
        "threads": [[["ST", "x", 1], ["ST", "y", 2], ["ST", "z", 3], ["LD", "r1", "x"], ["LD", "r2", "z"]]],
        "obs": {"O1": {"T1.r1": 0}, "O2": {"T1.r1": 1, "T1.r2": 0}},
        "family": "forced-flush-3",
    }),
    # P06 — own read of stale x, then same-var FIFO pins the final value
    ("B-W2", {
        "threads": [[["ST", "x", 1], ["LD", "r1", "x"], ["ST", "x", 2]]],
        "obs": {"O1": {"T1.r1": 0, "x": 1}, "O2": {"T1.r1": 0, "x": 2}},
        "family": "own-read+same-var-fifo",
    }),
    # P07 — classic store-buffering relaxation (SC intuition trap)
    ("B-F3a", {
        "threads": [
            [["ST", "x", 1], ["LD", "r1", "y"]],
            [["ST", "y", 1], ["LD", "r1", "x"]],
        ],
        "obs": {"O1": {"T1.r1": 0, "T2.r1": 0}, "O2": {"x": 0}},
        "family": "sb-classic",
    }),
    # P08 — fenced store-buffering: relaxation gone
    ("B-F3b", {
        "threads": [
            [["ST", "x", 1], ["FENCE"], ["LD", "r1", "y"]],
            [["ST", "y", 1], ["FENCE"], ["LD", "r1", "x"]],
        ],
        "obs": {"O1": {"T1.r1": 0, "T2.r1": 0}, "O2": {"T1.r1": 0, "T2.r1": 1}},
        "family": "sb-fenced",
    }),
    # P09 — message passing: FIFO write-back preserves order in both machines
    ("B-F4a", {
        "threads": [
            [["ST", "x", 1], ["ST", "y", 1]],
            [["LD", "r1", "y"], ["LD", "r2", "x"]],
        ],
        "obs": {"O1": {"T2.r1": 1, "T2.r2": 0}, "O2": {"T2.r1": 0, "T2.r2": 1}},
        "family": "mp-fifo",
    }),
    # P10 — 2+2W: final-memory write order
    ("B-F4b", {
        "threads": [
            [["ST", "x", 1], ["ST", "y", 2]],
            [["ST", "y", 1], ["ST", "x", 2]],
        ],
        "obs": {"O1": {"x": 1, "y": 1}, "O2": {"x": 2, "y": 2}},
        "family": "2+2w",
    }),
    # P11 — n6: forwarding-only outcome (SB-A signature)
    ("B-F5a", {
        "threads": [
            [["ST", "x", 1], ["LD", "r1", "x"], ["LD", "r2", "y"]],
            [["ST", "y", 2], ["ST", "x", 2]],
        ],
        "obs": {"O1": {"T1.r1": 1, "T1.r2": 0, "x": 1}, "O2": {"T1.r1": 2, "T1.r2": 2}},
        "family": "n6",
    }),
    # P12 — n5: forbidden under SB-A, REACHABLE under SB-B (memory reads)
    ("B-F5b", {
        "threads": [
            [["ST", "x", 1], ["LD", "r1", "x"]],
            [["ST", "x", 2], ["LD", "r1", "x"]],
        ],
        "obs": {"O1": {"T1.r1": 2, "T2.r1": 1}, "O2": {"T1.r1": 1, "T2.r1": 2, "x": 1}},
        "family": "n5",
    }),
    # P13 — mirrored SB with own reads: forwarding-only both sides
    ("B-F5c", {
        "threads": [
            [["ST", "x", 1], ["LD", "r1", "x"], ["LD", "r2", "y"]],
            [["ST", "y", 1], ["LD", "r1", "y"], ["LD", "r2", "x"]],
        ],
        "obs": {
            "O1": {"T1.r1": 1, "T1.r2": 0, "T2.r1": 1, "T2.r2": 0},
            "O2": {"T1.r1": 1, "T1.r2": 0, "T2.r1": 1, "T2.r2": 1},
        },
        "family": "sb-own-reads",
    }),
    # P14 — n6 against a three-store writer (forced write-back interplay)
    ("B-F5d", {
        "threads": [
            [["ST", "x", 1], ["LD", "r1", "x"], ["LD", "r2", "y"]],
            [["ST", "y", 2], ["ST", "y", 3], ["ST", "x", 2]],
        ],
        "obs": {"O1": {"T1.r1": 1, "T1.r2": 0, "x": 1}, "O2": {"T1.r1": 1, "T1.r2": 2, "x": 2}},
        "family": "n6-forced",
    }),
    # P15 — CAS drains own buffer before testing
    ("B-F6a", {
        "threads": [[["ST", "x", 1], ["CAS", "r1", "x", 1, 2]]],
        "obs": {"O1": {"T1.r1": 0}, "O2": {"T1.r1": 1, "x": 2}},
        "family": "cas-drain",
    }),
    # P16 — per-variable coherence for cross-thread readers
    ("B-F8a", {
        "threads": [
            [["ST", "x", 1]],
            [["LD", "r1", "x"], ["LD", "r2", "x"]],
        ],
        "obs": {"O1": {"T2.r1": 1, "T2.r2": 0}, "O2": {"T2.r1": 0, "T2.r2": 1}},
        "family": "monotone-read",
    }),
]

FRONTIER_PROGRAMS = [
    # P01 — own-read staleness exported through memory
    ("F-N1", {
        "threads": [
            [["ST", "x", 1], ["ST", "y", 2], ["LD", "r1", "x"], ["STR", "p", "r1"]],
            [["LD", "r2", "p"], ["LD", "r3", "x"]],
        ],
        "obs": {"O1": {"T1.r1": 0, "T2.r2": 0, "p": 0}, "O2": {"T2.r2": 1, "T2.r3": 0}},
        "family": "own-read-export",
    }),
    # P02 — near-miss of P01: third store forces the answer to flip
    ("F-N2", {
        "threads": [
            [["ST", "x", 1], ["ST", "y", 2], ["ST", "z", 3], ["LD", "r1", "x"], ["STR", "p", "r1"]],
            [["LD", "r2", "p"], ["LD", "r3", "x"]],
        ],
        "obs": {"O1": {"T1.r1": 0}, "O2": {"T2.r2": 1, "T2.r3": 1}},
        "family": "own-read-export-forced",
    }),
    # P03 — n6 with the writer's own-read exported via STR (both directions split)
    ("F-N3", {
        "threads": [
            [["ST", "x", 1], ["LD", "r1", "x"], ["STR", "e", "r1"], ["LD", "r2", "y"]],
            [["ST", "y", 2], ["ST", "x", 2]],
        ],
        "obs": {"O1": {"e": 1, "T1.r2": 0, "x": 1}, "O2": {"e": 0}},
        "family": "n6-str-export",
    }),
    # P04 — forwarding versus CAS drain (composed SB-A signature)
    ("F-N4", {
        "threads": [
            [["ST", "x", 1], ["LD", "r1", "x"], ["LD", "r2", "y"]],
            [["ST", "y", 2], ["CAS", "r3", "x", 0, 2]],
        ],
        "obs": {
            "O1": {"T1.r1": 1, "T1.r2": 0, "T2.r3": 1, "x": 2},
            "O2": {"T1.r1": 1, "T1.r2": 0, "T2.r3": 1, "x": 1},
        },
        "family": "n6-cas",
    }),
    # P05 — write-to-read causality chain across three threads
    ("F-C1", {
        "threads": [
            [["ST", "x", 1], ["ST", "f", 1]],
            [["LD", "r1", "f"], ["ST", "g", 1]],
            [["LD", "r2", "g"], ["LD", "r3", "x"]],
        ],
        "obs": {"O1": {"T2.r1": 1, "T3.r2": 1, "T3.r3": 0}, "O2": {"T2.r1": 0, "T3.r2": 1, "T3.r3": 1}},
        "family": "wrc",
    }),
    # P06 — CAS contention: exactly one winner
    ("F-C2", {
        "threads": [
            [["CAS", "r1", "x", 0, 1]],
            [["CAS", "r1", "x", 0, 2]],
        ],
        "obs": {"O1": {"T1.r1": 1, "T2.r1": 1}, "O2": {"T1.r1": 1, "T2.r1": 0, "x": 1}},
        "family": "cas-contention",
    }),
    # P07 — CAS steals the slot while the writer's store is still buffered
    ("F-C3", {
        "threads": [
            [["ST", "x", 1], ["ST", "y", 1], ["LD", "r1", "x"]],
            [["CAS", "r2", "x", 0, 5], ["LD", "r3", "y"]],
        ],
        "obs": {"O1": {"T1.r1": 5}, "O2": {"T1.r1": 5, "T2.r3": 1, "x": 5}},
        "family": "cas-interleave",
    }),
    # P08 — store-buffering with one fence only
    ("F-C4", {
        "threads": [
            [["ST", "x", 1], ["FENCE"], ["LD", "r1", "y"]],
            [["ST", "y", 1], ["LD", "r1", "x"]],
        ],
        "obs": {"O1": {"T1.r1": 0, "T2.r1": 0}, "O2": {"T1.r1": 1, "T2.r1": 0}},
        "family": "sb-half-fence",
    }),
    # P09 — CAS-synchronized observer of a forced write-back
    ("F-C5", {
        "threads": [
            [["ST", "x", 1], ["ST", "y", 2], ["ST", "z", 3], ["CAS", "r1", "w", 0, 1]],
            [["CAS", "r2", "w", 0, 1], ["LD", "r3", "x"]],
        ],
        "obs": {"O1": {"T1.r1": 1, "T2.r2": 0, "T2.r3": 0}, "O2": {"T1.r1": 0, "T2.r2": 1, "T2.r3": 0}},
        "family": "cas-sync-flush",
    }),
    # P10 — own read appears to travel back in time; observers stay coherent
    ("F-C6", {
        "threads": [
            [["ST", "x", 1], ["ST", "x", 2], ["LD", "r1", "x"]],
            [["LD", "r2", "x"], ["LD", "r3", "x"]],
        ],
        "obs": {"O1": {"T1.r1": 1}, "O2": {"T2.r2": 2, "T2.r3": 1}},
        "family": "same-var-own",
    }),
    # P11 — three-store window: own reads across the forced boundary
    ("F-C7", {
        "threads": [
            [["ST", "x", 1], ["ST", "y", 1], ["ST", "z", 1], ["LD", "r1", "z"], ["LD", "r2", "x"]],
            [["LD", "r3", "z"], ["LD", "r4", "x"]],
        ],
        "obs": {"O1": {"T1.r1": 0, "T1.r2": 1}, "O2": {"T2.r3": 0, "T2.r4": 1}},
        "family": "forced-flush-window",
    }),
    # P12 — n6 writer split by a fence
    ("F-C8", {
        "threads": [
            [["ST", "x", 1], ["LD", "r1", "x"], ["LD", "r2", "y"]],
            [["ST", "y", 2], ["FENCE"], ["ST", "x", 2]],
        ],
        "obs": {"O1": {"T1.r1": 1, "T1.r2": 0, "x": 1}, "O2": {"T1.r1": 2, "T1.r2": 0}},
        "family": "n6-fenced",
    }),
    # P13 — message passing through a CAS'd flag
    ("F-C9", {
        "threads": [
            [["ST", "x", 7], ["CAS", "r1", "f", 0, 1]],
            [["CAS", "r2", "f", 1, 2], ["LD", "r3", "x"]],
        ],
        "obs": {"O1": {"T2.r2": 1, "T2.r3": 0}, "O2": {"T2.r2": 1, "T2.r3": 7, "f": 2}},
        "family": "mp-cas-flag",
    }),
    # P14 — same variable three times: eviction pins the oldest value
    ("F-CA", {
        "threads": [
            [["ST", "x", 1], ["ST", "x", 2], ["ST", "x", 3], ["LD", "r1", "x"]],
        ],
        "obs": {"O1": {"T1.r1": 1}, "O2": {"T1.r1": 3}},
        "family": "same-var-forced",
    }),
    # P15 — independent-writer IRIW shape on three threads
    ("F-CB", {
        "threads": [
            [["ST", "x", 1], ["ST", "a", 1]],
            [["ST", "y", 1], ["ST", "b", 1]],
            [["LD", "r1", "a"], ["LD", "r2", "y"], ["LD", "r3", "b"], ["LD", "r4", "x"]],
        ],
        "obs": {
            "O1": {"T3.r1": 1, "T3.r2": 0, "T3.r3": 1, "T3.r4": 0},
            "O2": {"T3.r1": 1, "T3.r2": 0, "T3.r3": 1, "T3.r4": 1},
        },
        "family": "iriw-ish-3t",
    }),
    # P16 — own-read staleness chained through a second variable
    ("F-CC", {
        "threads": [
            [["ST", "x", 1], ["ST", "y", 1], ["LD", "r1", "x"], ["STR", "z", "r1"]],
            [["LD", "r2", "z"], ["LD", "r3", "y"]],
        ],
        "obs": {"O1": {"T2.r2": 0, "T2.r3": 1, "z": 0}, "O2": {"T2.r2": 1, "T2.r3": 0}},
        "family": "own-read-chain",
    }),
    # P17 — racing writer: fence separates two own reads
    ("F-CD", {
        "threads": [
            [["ST", "x", 1], ["LD", "r1", "x"], ["FENCE"], ["LD", "r2", "x"]],
            [["ST", "x", 2]],
        ],
        "obs": {"O1": {"T1.r1": 0, "T1.r2": 1, "x": 2}, "O2": {"T1.r1": 2, "T1.r2": 2, "x": 1}},
        "family": "own-read-race",
    }),
    # P18 — eviction order with same-variable overwrite in the buffer
    ("F-CE", {
        "threads": [
            [["ST", "x", 1], ["ST", "y", 1], ["ST", "x", 2], ["LD", "r1", "y"]],
            [["LD", "r2", "x"], ["LD", "r3", "y"]],
        ],
        "obs": {"O1": {"T1.r1": 0}, "O2": {"T2.r2": 0, "T2.r3": 1}},
        "family": "eviction-order",
    }),
    # P19 — a fence in the reader cannot flush the writer's buffer
    ("F-CG", {
        "threads": [
            [["ST", "x", 1], ["ST", "y", 1]],
            [["LD", "r1", "y"], ["FENCE"], ["LD", "r2", "x"]],
        ],
        "obs": {"O1": {"T2.r1": 1, "T2.r2": 0}, "O2": {"T2.r1": 0, "T2.r2": 1}},
        "family": "observer-fence-decoy",
    }),
    # P20 — two writers on one variable, register + final memory joint claim
    ("F-CJ", {
        "threads": [
            [["ST", "x", 1], ["ST", "x", 2]],
            [["ST", "x", 3], ["LD", "r1", "x"]],
        ],
        "obs": {"O1": {"T2.r1": 3, "x": 1}, "O2": {"T2.r1": 1, "x": 3}},
        "family": "same-var-race",
    }),
]
