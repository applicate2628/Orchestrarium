#!/usr/bin/env python3
"""Development/CI entry point for review-loop-state validation.

The canonical V1/V2 schema and transition owner is ``review_loop_state.py``.
This wrapper intentionally stays out of installed target runtimes.
"""
from __future__ import annotations

import sys

from review_loop_state import REVIEW_LOOP_ROUND_CAP, load_ledger, validate_record, validate_v1, validate_v2, validator_main


# Compatibility names for repository callers that imported the old module.
def validate(data, cap=REVIEW_LOOP_ROUND_CAP):
    return validate_record(data, cap=cap)[0]


def main(argv):
    return validator_main(argv)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
