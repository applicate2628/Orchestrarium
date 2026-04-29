# Verifier

`check_visual_localization.py` supports:

- `--bundle-shape-only`: validate scenario files and oracle structure
- `--answer-file <path>`: parse provider output or a JSON answer file
- `--metrics-out <path>`: write machine-readable metrics

The parser accepts raw JSON or text containing one JSON object. Runtime, quota,
or unsupported image-route failures must be classified by the runner before the
verifier is interpreted as model evidence.
