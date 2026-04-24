# N51 Scoring Anchors

The post-run scorer awards:

- binary correctness from runner `summary.json`
- patch quality for source ownership, test updates, avoiding protected files, and bounded diff size
- scoreable operator output budget from `worker-output.txt` size
- scoreable turnaround budget from prompt-to-worker-output file timestamps
- diagnostic time proxy from prompt-to-summary file timestamps
- diagnostic cost proxy from `worker-output.txt` size

Scores are comparable within this N51 repeat surface only.
