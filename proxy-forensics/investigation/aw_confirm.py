import subprocess, json, sys

PROBE_3 = (
    "Reply with a single JSON object. No codefence. No prose. No trailing newline commentary.\n"
    "{\n"
    '  "architecture_family": "<single word>",\n'
    '  "supports_extended_thinking": <true|false>,\n'
    '  "can_use_prompt_caching": <true|false>,\n'
    '  "knowledge_cutoff_month": "<Month YYYY>"\n'
    "}"
)

PRIOR = (
    "Compute 7^17 mod 100. Answer in exactly two lines. "
    "Line 1: 'Reasoning:' followed by the key modular identity. "
    "Line 2: 'Answer:' followed by the two digits only."
)

TESTS = [
    ('P3_json    run1', PROBE_3),
    ('P3_json    run2', PROBE_3),
    ('Prior_717  run1', PRIOR),
    ('Prior_717  run2', PRIOR),
]

def run_aw(prompt):
    cmd = ['claude-aw.cmd', '-p', prompt,
           '--model', 'opus',
           '--effort', 'max',
           '--tools', '',
           '--output-format', 'json']
    r = subprocess.run(cmd, capture_output=True, text=True,
                       encoding='utf-8', errors='replace',
                       shell=True, timeout=300)
    return r.stdout, r.stderr

for label, prompt in TESTS:
    print(f'\n{"="*70}\n{label}\n{"="*70}')
    try:
        out, err = run_aw(prompt)
    except subprocess.TimeoutExpired:
        print('TIMEOUT')
        continue

    print(f'[raw stdout len={len(out)}]')
    # Always show raw head so we see the actual bytes
    print(f'[raw head]: {out[:500]!r}')
    if err:
        print(f'[stderr head]: {err[:300]!r}')

    # Try to parse
    try:
        arr = json.loads(out)
        if isinstance(arr, list):
            result = next((x for x in arr if x.get('type')=='result'), {})
            assistants = [x for x in arr if x.get('type')=='assistant']
            last = assistants[-1].get('message', {}) if assistants else {}
            content = last.get('content', [])
            text = '\n'.join(c.get('text','') for c in content if c.get('type')=='text')
            usage = result.get('usage', {})
            print(f'[parsed] reported={last.get("model")} '
                  f'msg_id={(last.get("id") or "")[:14]} '
                  f'out_tok={usage.get("output_tokens")} '
                  f'cost=${result.get("total_cost_usd")}')
            print(f'[text]:\n{text}')
        else:
            print(f'[parsed non-list]: {arr!r}')
    except Exception as e:
        print(f'[parse fail]: {e}')
