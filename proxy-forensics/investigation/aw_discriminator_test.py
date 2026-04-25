import json, subprocess, sys

PROMPT = (
    "Compute 7^17 mod 100. Answer in exactly two lines. "
    "Line 1: 'Reasoning:' followed by the key modular identity. "
    "Line 2: 'Answer:' followed by the two digits only."
)

def run(cmd, shell=False, timeout=240):
    r = subprocess.run(cmd, capture_output=True, text=True,
                       encoding='utf-8', errors='replace',
                       shell=shell, timeout=timeout)
    return r.stdout, r.stderr

def parse(out):
    try:
        arr = json.loads(out)
    except Exception as e:
        return {'error': f'parse fail: {e}', 'head': out[:400]}
    if not isinstance(arr, list):
        return {'error': 'not list', 'head': str(arr)[:400]}
    result = next((x for x in arr if x.get('type')=='result'), {})
    assistants = [x for x in arr if x.get('type')=='assistant']
    last_msg = assistants[-1].get('message', {}) if assistants else {}
    content = last_msg.get('content', [])
    text = '\n'.join(c.get('text','') for c in content if c.get('type')=='text')
    think = '\n---\n'.join(c.get('thinking','') for c in content if c.get('type')=='thinking')
    usage = result.get('usage', {})
    return {
        'reported_model': last_msg.get('model'),
        'msg_id_prefix': (last_msg.get('id') or '')[:12],
        'out_tok': usage.get('output_tokens'),
        'cache_read': usage.get('cache_read_input_tokens'),
        'cache_create': usage.get('cache_creation_input_tokens'),
        'cost_usd': result.get('total_cost_usd'),
        'text': text,
        'think_chars': len(think),
        'think_head': think[:300] if think else '',
    }

targets = [
    ('4.5 official', ['claude', '-p', PROMPT, '--model', 'claude-opus-4-5',
                      '--output-format', 'json', '--effort', 'max'], False),
    ('4.6 official', ['claude', '-p', PROMPT, '--model', 'claude-opus-4-6',
                      '--output-format', 'json', '--effort', 'max'], False),
    ('4.7 official', ['claude', '-p', PROMPT, '--model', 'claude-opus-4-7',
                      '--output-format', 'json', '--effort', 'max'], False),
    ('AW  suspected', ['claude-aw.cmd', '-p', PROMPT, '--model', 'opus',
                       '--output-format', 'json', '--effort', 'max'], True),
]

results = []
for label, cmd, shell in targets:
    print(f'\n=== {label} ===', flush=True)
    try:
        out, err = run(cmd, shell=shell, timeout=240)
    except subprocess.TimeoutExpired:
        print('  TIMEOUT', flush=True)
        results.append((label, {'error': 'timeout'}))
        continue
    res = parse(out)
    results.append((label, res))
    for k, v in res.items():
        if k in ('text','think_head'):
            print(f'  {k}: {v!r}')
        else:
            print(f'  {k}: {v}')

print('\n=== SUMMARY ===')
print(f'{"Variant":<16} {"reported":<28} {"id_prefix":<12} {"out":>5} {"cost":>9} {"think_c":>7}')
for label, r in results:
    print(f'{label:<16} {str(r.get("reported_model","")):<28} {str(r.get("msg_id_prefix","")):<12} '
          f'{str(r.get("out_tok","")):>5} {str(r.get("cost_usd","")):>9} {str(r.get("think_chars","")):>7}')

print('\n=== TEXT COMPARISON ===')
for label, r in results:
    print(f'\n--- {label} ---')
    print(r.get('text','<no text>'))
