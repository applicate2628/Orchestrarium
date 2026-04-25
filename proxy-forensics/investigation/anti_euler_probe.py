import subprocess, json

PROMPT = (
    "Compute 7^17 mod 100. Do NOT use the words Euler, totient, Fermat, "
    "phi, or any Greek letter. Begin reasoning by computing 7^2 and 7^4 directly. "
    "Two lines: 'Reasoning:' and 'Answer:'."
)

TARGETS = [
    ('4.5 off      ', ['claude', '--model', 'claude-opus-4-5'], False),
    ('4.6 off      ', ['claude', '--model', 'claude-opus-4-6'], False),
    ('4.7 off      ', ['claude', '--model', 'claude-opus-4-7'], False),
    ('AW  run1     ', ['claude-aw.cmd', '--model', 'opus'], True),
    ('AW  run2     ', ['claude-aw.cmd', '--model', 'opus'], True),
]

BANNED = ['euler', 'totient', 'fermat', 'phi', 'φ', 'π', 'Φ']

def run(base_cmd, shell):
    cmd = base_cmd + ['-p', PROMPT,
                      '--effort', 'max',
                      '--tools', '',
                      '--output-format', 'json']
    r = subprocess.run(cmd, capture_output=True, text=True,
                       encoding='utf-8', errors='replace',
                       shell=shell, timeout=300)
    return r.stdout

def parse(out):
    try:
        arr = json.loads(out)
    except Exception as e:
        return {'error': f'parse: {e}', 'head': out[:200]}
    if not isinstance(arr, list):
        return {'error': 'not list', 'head': str(arr)[:200]}
    result = next((x for x in arr if x.get('type')=='result'), {})
    assistants = [x for x in arr if x.get('type')=='assistant']
    last = assistants[-1].get('message', {}) if assistants else {}
    content = last.get('content', [])
    text = '\n'.join(c.get('text','') for c in content if c.get('type')=='text')
    return {
        'reported': last.get('model'),
        'msg_id': (last.get('id') or '')[:14],
        'out_tok': result.get('usage',{}).get('output_tokens'),
        'text': text,
    }

def check_violations(text):
    lower = text.lower()
    found = []
    for word in BANNED:
        if word.lower() in lower:
            found.append(word)
    return found

print(f'PROMPT:\n{PROMPT}\n')
print(f'BANNED words: {BANNED}\n')
print('='*75)

for label, base_cmd, shell in TARGETS:
    print(f'\n--- {label} ---')
    try:
        out = run(base_cmd, shell)
    except subprocess.TimeoutExpired:
        print('  TIMEOUT')
        continue
    r = parse(out)
    if 'error' in r:
        print(f'  ERROR: {r}')
        continue
    print(f'  reported={r["reported"]}  msg_id={r["msg_id"]}  out_tok={r["out_tok"]}')
    print(f'  text:\n{r["text"]}')
    violations = check_violations(r["text"])
    verdict = 'VIOLATION: ' + ', '.join(violations) if violations else 'COMPLIANT (no banned words)'
    print(f'  >>> {verdict}')
