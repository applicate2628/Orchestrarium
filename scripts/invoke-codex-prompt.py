#!/usr/bin/env python3
"""File-based prompt transport for Codex CLI."""

from __future__ import annotations

import sys
import os
from pathlib import Path


HELP_TEXT = """usage: invoke-codex-prompt.py --help
       invoke-codex-prompt.py TOPIC --terminal-receipt PATH [OPTIONS] [-- CODEX_FLAGS...]

File-based prompt transport for Codex CLI.

options:
  --help                         show this help message and exit
  --prompt-file PATH             read the prompt from PATH
  -PromptFile PATH               legacy spelling for --prompt-file
  --terminal-receipt PATH        write the required terminal receipt to PATH
  --user-approved-launch         caller asserts genuine agreement for this one managed Astra/Max attempt
  --ledger PATH                  append the optional terminal ledger event
  -Ledger PATH                   legacy spelling for --ledger
  --ledger-role ROLE             record the ledger execution role
  -LedgerRole ROLE               legacy spelling for --ledger-role
  --ledger-lane LANE             record the ledger lane
  -LedgerLane LANE               legacy spelling for --ledger-lane
  --ledger-artifact PATH         record the ledger artifact
  -LedgerArtifact PATH           legacy spelling for --ledger-artifact
  --ledger-closes RUN_ID         declare one run closed; repeatable
  -LedgerCloses RUN_ID           legacy spelling for --ledger-closes
  --timeout-secs SECONDS         set a positive finite timeout
  -TimeoutSecs SECONDS           legacy spelling for --timeout-secs
  --result-max-bytes BYTES       set a positive result limit
  -ResultMaxBytes BYTES          legacy spelling for --result-max-bytes
  --capture-max-bytes BYTES      set a positive capture limit
  -CaptureMaxBytes BYTES         legacy spelling for --capture-max-bytes
  --                             pass remaining arguments to Codex CLI
"""


def main(argv: list[str]) -> int:
    if argv == ["--help"]:
        sys.stdout.write(HELP_TEXT)
        return 0

    # CLI argv0 retains the selected launcher even when its file is a link.
    # A direct main() library call uses its selected module origin instead.
    runtime_namespace = Path(os.path.abspath(sys.argv[0] if __name__ == "__main__" else __file__)).parent
    from provider_prompt import launch

    return launch("codex", argv, runtime_namespace=runtime_namespace)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
