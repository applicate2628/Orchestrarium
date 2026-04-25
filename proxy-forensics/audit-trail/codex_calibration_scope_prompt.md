# Calibration scope question

User just stated: "toolkit должен быть откалиброван на всех доступных моделях со всеми доступными efforts" ("toolkit should be calibrated on all available models with all available efforts").

Current calibration state (v0.6, you GREEN'd at round 13):
- Baseline outputs cached in `baselines.json` for Opus 4.5/4.6/4.7 (5 probes × 1 run each, single effort)
- Live `fingerprint.py` end-to-end pipeline run on **only** plain `claude --model claude-opus-4-7 --effort max` → A-clean high confidence
- Other models (Sonnet 4.6, Haiku 4.5) and other efforts (low/medium/high/xhigh) NOT live-validated

Available models on the user's system:
- claude-opus-4-5 (or `-20251101` date-stamped)
- claude-opus-4-6
- claude-opus-4-7
- claude-sonnet-4-6
- claude-haiku-4-5-20251001

Available efforts (per Anthropic CLI):
- low / medium / high / xhigh / max
- `max` is Opus-tier only (Opus 4.6+); Sonnet/Haiku silently degrade `max`/`xhigh` to high

Toolkit currently hardcoded `--effort max` per scorer-version=0.6.0 normalization choice. I just added `--probe-effort` flag (default "max") to support calibration runs.

## User's standard

"All models × all efforts" = full matrix, ~20 combinations × 10 calls = ~200 API calls = ~$10-20.

## Question for you

Is the user's standard the right calibration discipline for v0.6 toolkit?

Specifically:

1. **Is full {model × effort} matrix necessary**, or is it overkill for a hypothesis-generator scope?
2. The toolkit's PRIMARY job is to fingerprint suspect endpoints (which we don't control); calibrating against efforts WE choose seems redundant if the toolkit always forces `--effort max` on suspects. Counter-argument or agreement?
3. What MINIMUM calibration discipline would you require for a "v0.6 stable" stamp on a multi-model toolkit?
4. What classes of bugs would only show up under specific {model × effort} combos that single-model-max validation would miss?
5. Practical recommendation: run full matrix (~$15), or a representative subset (~$5), or skip and add to documented gaps?

Output:
```
### Summary (2 sentences)
### Answers to 5 questions
### Recommended scope
### Verdict on user's standard
AGREE / DISAGREE-MINOR (suggest narrower) / DISAGREE-MAJOR (suggest different approach)
```

Be honest. If full matrix is overkill, say so. If it's the right standard, confirm it.
