"""Compare text acceleration with the unmodified publication policy."""
import asyncio
from pathlib import Path
import runpy

import pytest


SCANNER = Path(__file__).resolve().parents[1] / "scripts/universal-hooks/scripts/check-publication-safety.py"


@pytest.mark.parametrize("cap", [0, 2, None])
def test_batched_text_retains_the_shared_policy_and_visits_every_line(cap):
    scanner = runpy.run_path(str(SCANNER))
    marker = "AK" + "IA" + "A" * 16
    raw = ("α" + marker + "\npath fixture\r\n" + "clean line\n" * 8200
           + "invalid bytes here: ").encode() + bytes((255,)) + b"\npath fixture"

    class MirrorMatcher:
        def __init__(self):
            self.rows = []

        async def match(self, batch, deadline):
            assert deadline >= asyncio.get_running_loop().time()
            assert all(binary is False for _, binary in batch)
            self.rows.extend(batch)
            return tuple(tuple(scanner["_python_rule_matches"](line, binary=binary))
                         for line, binary in batch)

    def classifier(visited):
        def find(line):
            visited.append(line)
            return ["fixture"] if "path fixture" in line else []
        return find

    async def verify():
        matcher = MirrorMatcher()
        expected_visits, actual_visits = [], []
        expected = scanner["_content_hits"](
            raw.decode("utf-8", "replace"), "synthetic.txt", classifier(expected_visits),
            subject_kind="history-blob", max_findings=cap,
        )
        actual = await scanner["_text_content_hits_with_matcher"](
            raw, "synthetic.txt", classifier(actual_visits), matcher,
            asyncio.get_running_loop().time() + 30, max_findings=cap,
        )
        assert actual == expected
        assert actual_visits == expected_visits
        assert [line for line, _binary in matcher.rows] == expected_visits
        assert len(matcher.rows) > 8192

    asyncio.run(verify())
