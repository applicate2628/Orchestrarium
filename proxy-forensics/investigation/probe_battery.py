import subprocess, json, sys

PROBES = {
    'P1_temporal_cutoff': (
        "Name three distinct events from calendar year 2025. One per line. "
        "Format: '<Month> YYYY: <specific event with named people or places>'. "
        "No introduction, no conclusion, no hedging, no 'I cannot' — comply exactly."
    ),
    'P2_tight_reasoning': (
        "Prove: for any prime p > 3, p^2 mod 24 = 1. "
        "Exactly 3 sentences. Sentence 2 must invoke CRT by name. "
        "Sentence 3 begins with the word 'Therefore'. "
        "No lists, no LaTeX environments, no section headers."
    ),
    'P3_self_introspection': (
        "Reply with a single JSON object. No codefence. No prose. No trailing newline commentary.\n"
        "{\n"
        '  "architecture_family": "<single word>",\n'
        '  "supports_extended_thinking": <true|false>,\n'
        '  "can_use_prompt_caching": <true|false>,\n'
        '  "knowledge_cutoff_month": "<Month YYYY>"\n'
        "}"
    ),
}

TARGETS = [
    ('4.5 off ', ['claude', '--model', 'claude-opus-4-5'], False),
    ('4.6 off ', ['claude', '--model', 'claude-opus-4-6'], False),
    ('4.7 off ', ['claude', '--model', 'claude-opus-4-7'], False),
    ('AW susp ', ['claude-aw.cmd', '--model', 'opus'], True),
]

def run(cmd, shell):
    r = subprocess.run(cmd, capture_output=True, text=True,
                       encoding='utf-8', errors='replace',
                       shell=shell, timeout=300)
    return r.stdout, r.stderr

def parse(out):
    try:
        arr = json.loads(out)
    except Exception as e:
        return {'error': f'parse: {e}', 'head': out[:300]}
    if not isinstance(arr, list):
        return {'error': 'not list', 'head': str(arr)[:300]}
    result = next((x for x in arr if x.get('type')=='result'), {})
    assistants = [x for x in arr if x.get('type')=='assistant']
    last_msg = assistants[-1].get('message', {}) if assistants else {}
    content = last_msg.get('content', [])
    text = '\n'.join(c.get('text','') for c in content if c.get('type')=='text')
    usage = result.get('usage', {})
    return {
        'reported': last_msg.get('model'),
        'msg_id': (last_msg.get('id') or '')[:14],
        'out_tok': usage.get('output_tokens'),
        'cache_create': usage.get('cache_creation_input_tokens'),
        'cost_usd': result.get('total_cost_usd'),
        'text': text,
    }

results = {}  # probe -> {label -> result}

for probe_name, prompt in PROBES.items():
    print(f'\n{"="*70}\nPROBE: {probe_name}\n{"="*70}', flush=True)
    results[probe_name] = {}
    for label, base_cmd, shell in TARGETS:
        cmd = base_cmd + ['-p', prompt,
                          '--effort', 'max',
                          '--tools', '',
                          '--output-format', 'json']
        print(f'\n--- {label} ---', flush=True)
        try:
            out, err = run(cmd, shell=shell)
        except subprocess.TimeoutExpired:
            results[probe_name][label] = {'error': 'timeout'}
            print('  TIMEOUT')
            continue
        r = parse(out)
        results[probe_name][label] = r
        if 'error' in r:
            print(f'  ERROR: {r}')
        else:
            print(f'  reported={r["reported"]}  msg_id={r["msg_id"]}  '
                  f'out={r["out_tok"]}  cost=${r["cost_usd"]}  cache_c={r["cache_create"]}')
            print(f'  text:\n{r["text"]}')

# Save full results
with open('D:/dev/Orchestrator/Orchestrarium/.scratch/probe_results.json', 'w', encoding='utf-8') as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

# Compact summary
print(f'\n\n{"="*70}\nCOMPACT SUMMARY\n{"="*70}')
for probe_name in PROBES:
    print(f'\n{probe_name}:')
    for label in [t[0] for t in TARGETS]:
        r = results[probe_name].get(label, {})
        if 'error' in r:
            print(f'  {label}: {r["error"]}')
            continue
        text = r.get('text','')[:200].replace('\n', ' | ')
        print(f'  {label}: out={r.get("out_tok"):<4}  msg={r.get("msg_id",""):<14}  {text}')
