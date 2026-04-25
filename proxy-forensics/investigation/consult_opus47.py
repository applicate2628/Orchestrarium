import subprocess, json, sys

PROMPT = """You are helping investigate a third-party Claude Code proxy. We need to identify the actual model/backend behind a gateway at api.claudecodeapi.cloud, invoked locally as `claude-aw.cmd --model opus --effort max`. Give a rigorous classification.

=== EVIDENCE COLLECTED ===

1. PROVIDER FINGERPRINT (message ID prefix on /v1/messages response):
   - AW gateway: `msg_vrtx_01Q...` → Google Vertex AI (confirmed)
   - Anthropic direct: `msg_01*`
   - AWS Bedrock would be: `msg_bdrk_*`
   - LiteLLM/aggregator would be: UUID-like

2. LABEL DYNAMICS (reported `model` in response body, same query, different sessions):
   - Earlier session today: AW reported "claude-opus-4.5"
   - Later session (30 min later, same prompt): AW reported "claude-opus-4.7"
   - Evidence suggests gateway may dynamically relabel responses

3. STYLOMETRIC FINGERPRINT — deterministic prompt: "Compute 7^17 mod 100. Answer in exactly two lines. Line 1: 'Reasoning:' with key modular identity. Line 2: 'Answer:' with two digits only."

   Outputs (--effort max on each):
   - Anthropic Opus 4.5: `7^4 = 2401 ≡ 1 (mod 100), so 7^17 = 7^(4·4+1) = (7^4)^4 · 7 ≡ 1·7 = 7`
   - Anthropic Opus 4.6: `7^4 = 2401 ≡ 1 (mod 100), so 7^17 = (7^4)^4 · 7^1 ≡ 1·7 = 7`
   - Anthropic Opus 4.7: `7^4 = 2401 ≡ 1 (mod 100), so 7^17 = (7^4)^4 · 7 ≡ 7 (mod 100)`
   - AW:                  `φ(100)=40, so 7^17 mod 100 = 7^17; compute 7^4=2401≡1, hence 7^17=(7^4)^4·7≡1·7`

   AW anomalies:
   - opens with Euler's totient φ(100)=40 (irrelevant since 17 < 40, no reduction needed)
   - contains tautology `7^17 mod 100 = 7^17`
   - then pivots to repeated-squaring without logical connection to the φ opening
   - 4.5/4.6/4.7 all open with `7^4 = 2401 ≡ 1 (mod 100)` identity first
   - AW "false-start-then-abandon" pattern is unique

4. OUTPUT TOKEN COUNTS (same prompt, --effort max):
   - 4.5 official: 419 tokens
   - 4.6 official: 223 tokens
   - 4.7 official: 538 tokens
   - AW:           77 tokens (1/3 to 1/7 of officials)

5. CACHE SUPPORT:
   - Officials: cache_creation_input_tokens = 39,000-58,000 (normal prompt caching works)
   - AW: cache_creation = 0, cache_read = 0 (no caching support)

6. THINKING API:
   - 4.5 official: thinking exposed as content block (old API)
   - 4.6/4.7 official: thinking hidden but present (cost reflects thinking tokens; adaptive thinking API)
   - AW: no thinking block, no thinking-overhead in cost, pipeline confirmed stripped

7. EFFORT PARAMETER:
   - Earlier session: AW `--effort max` and AW no-flag both produced identical 113 out tokens — effort ignored
   - Gateway does not propagate effort to its backend

8. CENSORSHIP PROBES (prior session):
   - Tiananmen 1989, Xinjiang Uyghurs, Taiwan independence: all answered factually with source acknowledgment
   - Not a Chinese-model distillate; not DeepSeek/Qwen/GLM alias

9. TOKENIZER:
   - AW tokenizer matches Claude BPE with constant +7 token offset on mixed-language strings
   - Offset attributed to extra system prompt prefix injected by gateway

=== QUESTION ===

What is AW most likely?

A) Genuine Anthropic Opus (4.x) through Vertex AI, with gateway stripping thinking/caching/effort
B) Genuine Anthropic Opus on Vertex, but older checkpoint than current Anthropic-direct release
C) Distilled/fine-tuned variant trained on Claude outputs (Vertex-side custom fine-tune)
D) Hybrid routing: gateway dispatches to multiple models per request, concatenating outputs (would explain false-start pattern)
E) Pruned/quantized Claude variant deployed on Vertex
F) Something else — specify

Rank A-F by likelihood with concrete reasoning tied to the evidence above.

Then propose 3 HIGH-DISCRIMINATION probes that would cleanly distinguish the top-2 hypotheses. Each probe should be:
- Short output (<200 tokens)
- Deterministic enough that stylometric compare is meaningful
- Stylistically discriminative (captures fine-tune/distill signature) OR knowledge-cutoff discriminative (captures checkpoint age) OR architecture-discriminative

Do not hedge performatively. If evidence is genuinely ambiguous, say so — but commit to a ranking."""

cmd = ['claude', '-p', PROMPT,
       '--model', 'claude-opus-4-7',
       '--effort', 'max',
       '--output-format', 'json']

print('[consult] sending evidence brief to Opus 4.7 max...', flush=True)
r = subprocess.run(cmd, capture_output=True, text=True,
                   encoding='utf-8', errors='replace', timeout=600)

if not r.stdout:
    print('ERROR: empty stdout')
    print('stderr:', r.stderr[:2000])
    sys.exit(1)

try:
    data = json.loads(r.stdout)
except Exception as e:
    print(f'parse failed: {e}')
    print(r.stdout[:2000])
    sys.exit(1)

result = next((x for x in data if x.get('type')=='result'), {})
answer = result.get('result', '')
usage = result.get('usage', {})

print(f'\n[meta] out_tok={usage.get("output_tokens")} cost=${result.get("total_cost_usd")}')
print(f'[meta] cache_create={usage.get("cache_creation_input_tokens")} cache_read={usage.get("cache_read_input_tokens")}')
print('\n' + '='*70)
print('OPUS 4.7 MAX VERDICT')
print('='*70)
print(answer)
