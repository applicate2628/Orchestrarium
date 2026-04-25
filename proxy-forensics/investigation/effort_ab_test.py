import json, subprocess, sys, os, shutil
from pathlib import Path

CFG = Path(os.environ['USERPROFILE']) / '.claude.json'
BAK = CFG.with_suffix('.json.bak_effort_test')

# 1) backup + force pinned
shutil.copy(CFG, BAK)
with CFG.open('r', encoding='utf-8') as f:
    d = json.load(f)
orig_unpin = d.get('unpinOpus47LaunchEffort')
d['unpinOpus47LaunchEffort'] = False
with CFG.open('w', encoding='utf-8') as f:
    json.dump(d, f, indent=2)
print(f'[state] unpin forced False (was {orig_unpin}), backup at {BAK}')

PROMPT = (
    "Compute 7^17 mod 100. Answer in exactly two lines. "
    "Line 1: 'Reasoning:' followed by the key modular identity. "
    "Line 2: 'Answer:' followed by the two digits only."
)

def run(extra):
    cmd = ['claude', '-p', PROMPT,
           '--model', 'claude-opus-4-7',
           '--output-format', 'json'] + extra
    r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    return r.stdout, r.stderr

def parse(out):
    try:
        arr = json.loads(out)
    except Exception as e:
        return {'error': f'parse failed: {e}', 'raw_head': out[:400]}
    result = next((x for x in arr if x.get('type')=='result'), {})
    assistants = [x for x in arr if x.get('type')=='assistant']
    last = assistants[-1]['message'] if assistants else {}
    content = last.get('content', [])
    text = '\n'.join(c['text'] for c in content if c.get('type')=='text')
    think = '\n---\n'.join(c['thinking'] for c in content if c.get('type')=='thinking')
    return {
        'out_tok': result.get('usage',{}).get('output_tokens'),
        'in_tok': result.get('usage',{}).get('input_tokens'),
        'cache_read': result.get('usage',{}).get('cache_read_input_tokens'),
        'cache_create': result.get('usage',{}).get('cache_creation_input_tokens'),
        'cost_usd': result.get('total_cost_usd'),
        'think_chars': len(think),
        'text': text,
        'think_head': think[:400],
    }

def check_pin():
    with CFG.open('r', encoding='utf-8') as f:
        return json.load(f).get('unpinOpus47LaunchEffort')

print('\n=== VARIANT A: env=max, pinned, no --effort flag ===')
out_a, err_a = run([])
print(f'[state after A] unpin = {check_pin()}')
res_a = parse(out_a)
for k, v in res_a.items():
    if k == 'think_head':
        print(f'  {k}: {v!r}')
    else:
        print(f'  {k}: {v}')

print('\n=== VARIANT B: --effort max flag (will unpin mid-call) ===')
out_b, err_b = run(['--effort', 'max'])
print(f'[state after B] unpin = {check_pin()}')
res_b = parse(out_b)
for k, v in res_b.items():
    if k == 'think_head':
        print(f'  {k}: {v!r}')
    else:
        print(f'  {k}: {v}')

print('\n=== SUMMARY ===')
print(f'A (pinned, env max)  : out={res_a.get("out_tok")}  think_chars={res_a.get("think_chars")}  cost=${res_a.get("cost_usd")}')
print(f'B (unpinned, flag max): out={res_b.get("out_tok")}  think_chars={res_b.get("think_chars")}  cost=${res_b.get("cost_usd")}')
print(f'\nA text:\n{res_a.get("text","<no text>")}')
print(f'\nB text:\n{res_b.get("text","<no text>")}')
