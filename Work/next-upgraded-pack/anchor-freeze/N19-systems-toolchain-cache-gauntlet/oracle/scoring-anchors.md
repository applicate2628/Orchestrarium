# N19 Scoring Anchors

The post-run scorer awards:

- binary correctness from runner `summary.json`
- patch quality for source ownership, test updates, avoiding protected files, and bounded diff size
- time proxy from prompt-to-summary file timestamps
- cost proxy from `worker-output.txt` size
