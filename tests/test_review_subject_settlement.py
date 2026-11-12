"""Synthetic public W/V receiving for historical review-subject settlement."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load(relative, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def actual_known_loop_delivery(root, item, subject_file, dto, protocol):
    import subprocess
    loop_fixture = load('tests/test_review_loop_state_v2.py', 'subject_actual_loop_fixture')
    state = root / '.scratch/reviews/loop-a/state.json'
    args = loop_fixture._begin_arguments(root, state)
    args[args.index('--artifact-file') + 1] = subject_file
    begun = loop_fixture._run(root, *args)
    (root / '.scratch/loop-begin.stdout').write_text(begun.stdout, encoding='utf8')
    (root / '.scratch/loop-begin.stderr').write_text(begun.stderr, encoding='utf8')
    assert begun.returncode == 0, begun.stderr
    receipt = json.loads(begun.stdout)
    commission = item / 'reviews/commission.txt'
    commission.write_text('OWN synthetic genuine commissioning instruction: return exactly verdict, blockers, rationale, root_proven, scope_unchanged, verification_adequate for formal Version2 verdict. Protocol ' + protocol + '; loop loop-a; surgical attempt ' + receipt['attempts']['surgical'] + '; reviewed revision ' + receipt['artifact_revision'] + '. This is an overall result, never a per-finding promise.\n', encoding='utf8')
    result_file = root / '.scratch/delivered-result.json'
    result_file.write_text(json.dumps(dto, ensure_ascii=False), encoding='utf8')
    recorded = loop_fixture._run(root, 'record-result', '--state', state, '--operation-id', 'known-delivery',
        '--round', 1, '--lane', 'surgical', '--attempt-id', receipt['attempts']['surgical'],
        '--artifact-revision', receipt['artifact_revision'], '--result-file', result_file)
    (root / '.scratch/loop-result.stdout').write_text(recorded.stdout, encoding='utf8')
    (root / '.scratch/loop-result.stderr').write_text(recorded.stderr, encoding='utf8')
    (item / 'reviews/known-state.json').write_bytes(state.read_bytes())
    return receipt, recorded.returncode


@pytest.fixture
def case(tmp_path, request):
    configuration = dict(getattr(request, "param", {}))
    if configuration.get('unit_context') or configuration.get('target_unit') or configuration.get('malformed_context'):
        configuration.update(proof_version=2, semantic_units=True)
    known = configuration.get('known_contract')
    known_role = configuration.get('known_role', 'reviewerPass')
    protocol = configuration.get('known_protocol', 'review-loop-explicit-six-field-result-v2')
    known_receipt = None
    if known:
        import subprocess
        subprocess.run(['git', 'init', '-q', str(tmp_path)], check=True)
        configuration.update(proof_version=2, sha256_revision=True)
    fixtures = load('tests/test_agent_run_ledger.py', 'subject_existing_fixtures')
    writer = fixtures.load_ledger_module()
    validator = writer.load_validator()
    item = fixtures.prepare_valid_work_item(tmp_path)
    (item / 'before.md').write_bytes(b'original admitted design\n')
    (item / 'after.md').write_bytes(b'corrected admitted design\n')
    before = hashlib.sha256((item / 'before.md').read_bytes()).hexdigest()
    after = hashlib.sha256((item / 'after.md').read_bytes()).hexdigest()
    if configuration.get('sha256_revision'):
        before, after = 'sha256:' + before, 'sha256:' + after
    if configuration.get('opaque_revisions'):
        before, after = 'git:' + before[:40], 'git:' + after[:40]
    dto = {'verdict': configuration.get('known_verdict', 'REVISE' if known_role == 'target' else 'PASS'),
           'blockers': [], 'rationale': 'specific actual synthetic overall result',
           'root_proven': 'specific root evidence', 'scope_unchanged': 'actual scope', 'verification_adequate': 'actual checks'}
    if configuration.get('known_missing'): dto.pop(configuration['known_missing'])
    if configuration.get('known_wrong_meta'): dto[configuration['known_wrong_meta']] = True
    target_id, pass_id = 'synthetic-safe2049-target', 'synthetic-safe2058-reviewer'
    findings = [{'id': f'PCC-SURG-{i}', 'detail': f'actual synthetic finding {i}'} for i in (1, 2, 3)]
    target = {'artifact_revision': before, 'blockerDetails': findings,
              'scope': ['admitted synthetic subject'], 'angle': 'surgical'}
    if configuration.get('semantic_units'):
        target['archiveExamples'] = copy.deepcopy(findings)
    if configuration.get('target_unit'):
        target['foreignTarget'] = {'id': 'UNRELATED-FINDING', 'detail': 'not the actual original finding'}
        if configuration['target_unit'] == 'foreign-revision':
            target['blockerDetails'][0]['reviewedRevision'] = after
    malformed = configuration.get('malformed_context')
    if malformed and malformed.startswith('target'):
        target['foreignTarget'] = {'id': findings[0]['id'], 'detail': 'actual selected target unit'}
        if malformed == 'target-id': target['foreignTarget']['id'] = 1
        else: target['foreignTarget']['reviewedRevision'] = 1
    if known and known_role == 'target':
        target['knownResult'] = copy.deepcopy(dto)
        known_receipt, known_record_return = actual_known_loop_delivery(tmp_path, item, item / 'before.md', dto, protocol)
    (item / 'reviews/r1.json').write_text(json.dumps(target))
    target_hash = hashlib.sha256((item / 'reviews/r1.json').read_bytes()).hexdigest()
    passed = {'artifact_revision': after, 'priorFindingDispositions': [
        {'id': finding['id'], 'verdict': 'verified', 'disposition': 'corrected in reviewed design'} for finding in findings],
        'scope': ['unrelated subject'] if configuration.get('wrong_scope') else target['scope'], 'angle': 'surgical',
        'inputPins': {'priorReview': target_hash, 'before': before, 'after': after},
        'commission': {'authorRunId': pass_id if configuration.get('author_reviewer') else 'synthetic-author', 'reviewerRunId': pass_id}}
    if configuration.get('semantic_units'):
        passed['unfamiliar'] = {
            'prefix': 'Пример \"quote\" and escaped newline\n',
            'current': [{'id': finding['id'], 'verdict': configuration.get('unit_verdict', 'verified'),
                         'reviewedRevision': after, 'statement': 'identical statement/status'} for finding in findings],
            'historical': [{'id': finding['id'], 'verdict': 'failed' if configuration.get('unit_verdict', 'verified') == 'verified' else 'verified',
                            'reviewedRevision': before, 'statement': 'identical statement/status'} for finding in findings]}
        passed.pop('priorFindingDispositions')
    context_case = configuration.get('unit_context')
    if context_case:
        original = passed['unfamiliar']['current'][0]
        inner = copy.deepcopy(original)
        if context_case != 'older-negative':
            inner.pop('reviewedRevision')
        outer = copy.deepcopy(original)
        outer['nestedClaim'] = inner
        if context_case in {'failed', 'unresolved', 'deep-failed'}:
            outer['verdict'] = 'unresolved' if context_case == 'unresolved' else 'failed'
        elif context_case == 'foreign-before':
            outer.update(id='FOREIGN-FINDING', reviewedRevision=before)
        elif context_case == 'older-negative':
            outer.update(verdict='failed', reviewedRevision=before)
        elif context_case == 'revision-only':
            outer.pop('verdict')
            outer['reviewedRevision'] = before
        else:
            raise AssertionError('unknown OWN source context case')
        if context_case == 'deep-failed':
            middle = copy.deepcopy(inner)
            middle['nestedClaim'] = inner
            outer['nestedClaim'] = middle
        passed['unfamiliar']['current'][0] = outer
    if configuration.get('manual_json'):
        passed['verdict'] = 'PASS'
        passed['actualReviewerClaims'] = {finding['id']: 'Explicitly verified corrected design at ' + after for finding in findings}
        passed.pop('priorFindingDispositions')
    if configuration.get('scalar_claims'):
        passed.pop('verdict', None)
    if configuration.get('unpromised_overall_dto'):
        passed['historicalUncommissionedExample'] = {**dto, 'verdict': 'REVISE', 'root_proven': False}
    passed.update(configuration.get('report_metadata', {}))
    if malformed and malformed.startswith('reviewer'):
        record = passed['unfamiliar']['current'][0]
        if malformed == 'reviewer-id': record['id'] = 1
        elif malformed == 'reviewer-revision': record['reviewedRevision'] = 1
        else: record['revision'] = before
    if configuration.get('nested_envelope'):
        passed = {'id': 'outer document identity', 'revision': 1, 'body': passed}
    if configuration.get('claim_verdict'):
        passed['priorFindingDispositions'][0].update(verdict=configuration['claim_verdict'], disposition='Required finding remains unresolved in reviewed revision')
    if configuration.get('alternate_collection'):
        passed['actualReviewerClaims'] = passed.pop('priorFindingDispositions')
    if configuration.get('wrong_lineage'):
        passed['inputPins'] = {'after': after}
    if known and known_role == 'reviewerPass':
        passed['knownResult'] = copy.deepcopy(dto)
        known_receipt, known_record_return = actual_known_loop_delivery(tmp_path, item, item / 'after.md', dto, protocol)
    if configuration.get('manual'):
        passed_text = 'Corrected subject ' + after + '\nPrior subject ' + before + '\nScope: admitted synthetic subject\nAngle: surgical\n'
        for finding in findings:
            passed_text += finding['id'] + ': explicitly verified corrected design at ' + after + '\n'
        (item / 'reviews/r2.json').write_bytes(passed_text.encode('utf8'))
    else:
        (item / 'reviews/r2.json').write_text(json.dumps(passed, ensure_ascii=False), encoding='utf-8')
    pass_hash = hashlib.sha256((item / 'reviews/r2.json').read_bytes()).hexdigest()
    (item / 'reviews/received.md').write_text('Root received actual independent assignment, report and finding claims.\n')
    def append(run_id, role, status, gate, artifact, scope, *extra):
        return writer.main(['--work-item', str(item), 'append', '--run-id', run_id,
            '--role', role, '--execution-role', 'main' if role == 'lead' else 'internal',
            '--event-kind', 'standalone', '--status', status, '--gate', gate,
            '--scope', scope, '--artifact', artifact, '--evidence', 'manual-check:synthetic actual own reviewer return',
            '--started-at', '2026-10-25T10:00:00Z', '--updated-at', '2026-10-25T10:00:01Z', *extra])
    assert append(target_id, 'security-reviewer', 'revise', 'REVISE', 'reviews/r1.json',
                  'round-one-label', '--finding-class', 'publication-safety', '--artifact-revision', target_hash) == 0
    assert append(pass_id, configuration.get('reviewer_role', 'security-reviewer'), 'completed', 'PASS', 'reviews/r2.json',
                  'round-two-label', '--artifact-revision', '0' * 64 if configuration.get('stale_report_revision') else pass_hash,
                  *(['--assigned-role', configuration['reviewer_assigned_role']] if configuration.get('reviewer_assigned_role') else [])) == 0
    context = validator.load_effective_ledger_view(tmp_path, item,
        item.relative_to(tmp_path).as_posix() + '/agent-runs.jsonl')
    raw_pins = {row.event['runId']: row.raw_line_sha256 for row in context.rows}
    def anchor(ref, path):
        return {'source': {'kind': 'review', 'ref': ref},
                'sourceSha256': hashlib.sha256((item / ref).read_bytes()).hexdigest(),
                'selector': {'kind': 'json-value', 'path': path}}
    fact = {'kind': 'manual-check', 'ref': 'actual separate native nonauthoring assignment and original return',
            'result': 'received by actual Root owner'}
    proof = {'version': 1, 'target': {'runId': target_id, 'rawLineSha256': raw_pins[target_id]},
        'reviewerPass': {'runId': pass_id, 'rawLineSha256': raw_pins[pass_id]},
        'reports': {'targetSha256': target_hash, 'passSha256': pass_hash},
        'subject': {'before': {'artifactKey': 'before.md', 'revision': before},
                    'after': {'artifactKey': 'after.md', 'revision': after}},
        'bindingEvidence': {
            'scope': {'relation': 'same', 'sources': [anchor('reviews/r1.json', ['scope']), anchor('reviews/r2.json', ['scope'])]},
            'angle': {'value': 'surgical', 'sources': [anchor('reviews/r1.json', ['angle']), anchor('reviews/r2.json', ['angle'])]},
            'lineage': {'sources': [anchor('reviews/r2.json', ['inputPins'])]},
            'nativeReceiving': {'facts': [fact], 'sources': [anchor('reviews/r2.json', ['commission'])]}},
        'findingEvidence': {'completeTargetFindings': anchor('reviews/r1.json', ['blockerDetails']),
            'dispositions': [{'findingId': finding['id'],
                'targetFinding': anchor('reviews/r1.json', ['blockerDetails', i]),
                'reviewerDisposition': anchor('reviews/r2.json', ['priorFindingDispositions', i])}
                for i, finding in enumerate(findings)]}, 'receivingMode': 'structured'}
    if configuration.get('manual'):
        def text_anchor(text):
            raw = (item / 'reviews/r2.json').read_bytes()
            selected = text.encode('utf8')
            start = raw.index(selected)
            return {'source': {'kind': 'review', 'ref': 'reviews/r2.json'},
                    'sourceSha256': hashlib.sha256(raw).hexdigest(),
                    'selector': {'kind': 'utf8-range', 'start': start, 'end': start + len(selected)}}
        proof['receivingMode'] = 'owner-equivalent'
        proof['bindingEvidence']['scope']['sources'] = [anchor('reviews/r1.json', ['scope']), text_anchor('Scope: admitted synthetic subject')]
        proof['bindingEvidence']['angle']['sources'] = [anchor('reviews/r1.json', ['angle']), text_anchor('Angle: surgical')]
        proof['bindingEvidence']['lineage']['sources'] = [text_anchor('Corrected subject ' + after + '\nPrior subject ' + before)]
        proof['bindingEvidence']['nativeReceiving']['sources'] = []
        for row in proof['findingEvidence']['dispositions']:
            row['reviewerDisposition'] = text_anchor(row['findingId'] + ': explicitly verified corrected design at ' + after)
    if configuration.get('owner_equivalent'):
        proof['receivingMode'] = 'owner-equivalent'
    if configuration.get('alternate_collection'):
        for index, row in enumerate(proof['findingEvidence']['dispositions']):
            row['reviewerDisposition'] = anchor('reviews/r2.json', ['actualReviewerClaims', index])
    if configuration.get('manual_json'):
        for row in proof['findingEvidence']['dispositions']:
            row['reviewerDisposition'] = anchor('reviews/r2.json', [])
    if configuration.get('claim_text_selector'):
        raw = (item / 'reviews/r2.json').read_bytes()
        text = b'Required finding remains unresolved in reviewed revision'
        start = raw.index(text)
        proof['findingEvidence']['dispositions'][0]['reviewerDisposition'] = {
            'source': {'kind': 'review', 'ref': 'reviews/r2.json'},
            'sourceSha256': hashlib.sha256(raw).hexdigest(),
            'selector': {'kind': 'utf8-range', 'start': start, 'end': start + len(text)}}
    if configuration.get('proof_version') == 2:
        def v2unit(value):
            value = copy.deepcopy(value)
            if value['selector']['kind'] == 'utf8-range':
                raw = (item / value['source']['ref']).read_bytes()
                value['selector'] = {'kind': 'utf8-range', 'start': 0, 'end': len(raw)}
            return value
        results = []
        for index, old in enumerate(proof['findingEvidence']['dispositions']):
            claim = old['reviewerDisposition']
            if configuration.get('semantic_units'):
                path = ['unfamiliar', 'current', index]
                if index == 0 and context_case:
                    path += ['nestedClaim'] * (2 if context_case == 'deep-failed' else 1)
                    path += ['statement']
                claim = anchor('reviews/r2.json', path)
            results.append({'findingId': old['findingId'], 'targetFinding': v2unit(old['targetFinding']),
                'reviewerClaimUnit': v2unit(claim), 'reviewedRevision': after,
                'meaning': 'reviewer-explicitly-reverified-corrected-finding'})
        proof['version'] = 2
        proof.pop('receivingMode')
        proof['findingEvidence'] = {'completeTargetFindings': v2unit(proof['findingEvidence']['completeTargetFindings'])}
        proof['rootSemanticReceiving'] = {'version': 1, 'action': 'receive-independent-review-claims', 'findings': results}
        for part in proof['bindingEvidence'].values():
            part['sources'] = [v2unit(value) for value in part['sources']]
    if configuration.get('target_unit'):
        proof['findingEvidence']['completeTargetFindings']['selector']['path'] = []
        kind = configuration['target_unit']
        if kind in {'foreign', 'foreign-leaf'}:
            proof['rootSemanticReceiving']['findings'][0]['targetFinding']['selector']['path'] = (
                ['foreignTarget', 'detail'] if kind == 'foreign-leaf' else ['foreignTarget'])
        elif kind == 'foreign-revision':
            proof['rootSemanticReceiving']['findings'][0]['targetFinding']['selector']['path'] += ['detail']
    if configuration.get('scalar_claims'):
        for result in proof['rootSemanticReceiving']['findings']:
            result['reviewerClaimUnit']['selector']['path'] = ['actualReviewerClaims', result['findingId']]
    if malformed and malformed.startswith('target'):
        proof['findingEvidence']['completeTargetFindings']['selector']['path'] = []
        proof['rootSemanticReceiving']['findings'][0]['targetFinding']['selector']['path'] = ['foreignTarget', 'detail']
    if configuration.get('nested_envelope'):
        def move_report_anchors(value):
            if type(value) is dict:
                if value.get('source', {}).get('ref') == 'reviews/r2.json':
                    assert value['selector']['kind'] == 'json-value'
                    value['selector']['path'].insert(0, 'body')
                for part in value.values(): move_report_anchors(part)
            elif type(value) is list:
                for part in value: move_report_anchors(part)
        move_report_anchors(proof)
    contract_evidence = []
    if known:
        producer_id = target_id if known_role == 'target' else pass_id
        report_ref = 'reviews/r1.json' if known_role == 'target' else 'reviews/r2.json'
        binding = {'schemaVersion': 1, 'kind': 'review-source-contract-binding', 'protocol': protocol,
            'producer': {'runId': producer_id, 'rawLineSha256': raw_pins[producer_id]},
            'commission': {'source': {'kind': 'review', 'ref': 'reviews/commission.txt'},
                'sourceSha256': hashlib.sha256((item / 'reviews/commission.txt').read_bytes()).hexdigest(),
                'selector': {'kind': 'utf8-range', 'start': 0, 'end': len((item / 'reviews/commission.txt').read_bytes())}},
            'delivery': anchor(report_ref, ['knownResult']),
            'loop': {'state': anchor('reviews/known-state.json', []), 'round': 1, 'lane': 'surgical',
                     'attemptId': known_receipt['attempts']['surgical'], 'artifactRevision': known_receipt['artifact_revision']}}
        defect = configuration.get('known_reference_defect')
        if defect == 'attempt': binding['loop']['attemptId'] = 'different-admitted-attempt'
        elif defect == 'revision': binding['loop']['artifactRevision'] = before if known_role != 'target' else after
        elif defect == 'producer': binding['producer']['rawLineSha256'] = '0' * 64
        elif defect == 'lane': binding['loop']['lane'] = 'scout'
        elif defect == 'delivery': binding['delivery']['source']['ref'] = 'reviews/r1.json' if known_role != 'target' else 'reviews/r2.json'
        contract_evidence.append({'kind': 'review', 'ref': 'reviews/commission.txt',
            'result': validator._canonical_projection_bytes(binding).decode('utf8')})
        proof['rootSemanticReceiving']['version'] = 2
    def settle(selected=None, run_id='synthetic-root-receiving'):
        selected = proof if selected is None else selected
        return append(run_id, 'lead', 'completed', 'PASS', 'reviews/received.md', 'actual semantic receiving',
            '--closes', target_id, '--evidence-json', json.dumps(fact),
            *[argument for entry in contract_evidence for argument in ('--evidence-json', json.dumps(entry))],
            '--review-closure-proof-json', json.dumps(selected))
    settle.contract_evidence = tuple(copy.deepcopy(contract_evidence))
    return writer, validator, item, proof, settle, tmp_path, anchor


def test_public_append_and_effective_reader_distinct_reports(case):
    writer, validator, item, proof, settle, root, _anchor = case
    prefix = (item / 'agent-runs.jsonl').read_bytes()
    assert settle() == 0
    ledger = (item / 'agent-runs.jsonl').read_bytes()
    assert ledger.startswith(prefix)
    events = [json.loads(line) for line in ledger.splitlines()]
    assert events[-1]['role'] == 'lead' and events[-1]['executionRole'] == 'main'
    assert events[-1]['reviewClosureProofs'][0]['reviewerPass']['runId'] == events[1]['runId']
    states = []
    errors = validator.validate_work_item(item, strict_revise=False, obligation_state_out=states)
    assert not errors, errors
    assert states and not states[-1].open_revise
    assert not (item / 'agent-runs.jsonl.lock').exists()
    assert not (item / 'agent-runs.jsonl.tmp').exists()


def test_anchor_native_capture_and_literal_utf8_selection(case):
    _writer, validator, item, _proof, _settle, _root, anchor = case
    inputs = validator._CurrentEvidenceV1()
    admitted = {'reviews/r1.json': inputs.artifact(item, 'reviews/r1.json', 'source', 'synthetic', [])}
    value = validator.resolve_review_source_anchor_v1(anchor('reviews/r1.json', ['blockerDetails', 0, 'id']),
        admitted_sources=admitted, inputs=inputs)
    assert value.value == 'PCC-SURG-1'
    inputs.receive()
    assert all(p.qualify() for p in inputs.predicates.values())
    path = item / 'reviews/r1.json'
    replacement = path.with_suffix('.replacement')
    replacement.write_bytes(path.read_bytes())
    os.replace(replacement, path)
    assert any(not p.qualify() for p in inputs.predicates.values())


def test_anchor_invalid_shapes_and_unadmitted_source(case):
    _writer, validator, item, _proof, _settle, _root, anchor = case
    source = anchor('reviews/r1.json', ['blockerDetails'])
    for path in [[True], [-1], [0.5]]:
        candidate = copy.deepcopy(source)
        candidate['selector']['path'] = path
        with pytest.raises(ValueError): validator.parse_review_source_anchor_v1(candidate)
    with pytest.raises(ValueError):
        validator.resolve_review_source_anchor_v1(source, admitted_sources={}, inputs=validator._CurrentEvidenceV1())


@pytest.mark.parametrize('mutation', ['partial', 'owner-equivalent-partial', 'raw', 'report', 'subject', 'angle', 'root-claim'])
def test_public_negative_preserves_raw_ledger(case, mutation):
    _writer, _validator, item, proof, settle, _root, anchor = case
    selected = copy.deepcopy(proof)
    if mutation in {'partial', 'owner-equivalent-partial'}:
        selected['findingEvidence']['dispositions'].pop()
        if mutation == 'owner-equivalent-partial': selected['receivingMode'] = 'owner-equivalent'
    elif mutation == 'raw': selected['reviewerPass']['rawLineSha256'] = '0' * 64
    elif mutation == 'report': selected['reports']['passSha256'] = '0' * 64
    elif mutation == 'subject': selected['subject']['after']['revision'] = '0' * 64
    elif mutation == 'angle': selected['bindingEvidence']['angle']['value'] = 'another angle'
    elif mutation == 'root-claim':
        selected['findingEvidence']['dispositions'][0]['reviewerDisposition'] = anchor('reviews/received.md', [])
    before = (item / 'agent-runs.jsonl').read_bytes()
    assert settle(selected) != 0
    assert (item / 'agent-runs.jsonl').read_bytes() == before


@pytest.mark.parametrize('case', [
    {'reviewer_role': 'architect'}, {'author_reviewer': True},
    {'wrong_scope': True}, {'wrong_lineage': True}, {'stale_report_revision': True}], indirect=True)
def test_actual_authority_scope_lineage_fail_closed(case):
    _writer, _validator, item, _proof, settle, _root, _anchor = case
    before = (item / 'agent-runs.jsonl').read_bytes()
    assert settle() != 0
    assert (item / 'agent-runs.jsonl').read_bytes() == before


@pytest.mark.parametrize('case', [{'proof_version': 2, 'semantic_units': True}], indirect=True)
def test_exact_replay_and_authorized_witness_disposition(case):
    writer, validator, item, proof, settle, _root, _anchor = case
    assert settle() == 0
    ledger = (item / 'agent-runs.jsonl').read_bytes()
    # Normal preserving move of precisely this test's two disposable draft
    # witnesses; record/read back exact source identities, never infer authority
    # from later absence. This is fixture artifact disposition, not item close.
    (item / 'after.md').write_bytes(b'later unreviewed revision is not approved by historical settlement\n')
    retained = item / 'retained-subjects'
    retained.mkdir()
    effects = []
    for name in ('before.md', 'after.md'):
        source = item / name
        identity = (source.stat().st_dev, source.stat().st_ino)
        data = source.read_bytes()
        destination = retained / name
        assert not destination.exists()
        source.rename(destination)
        assert not source.exists() and destination.read_bytes() == data
        assert (destination.stat().st_dev, destination.stat().st_ino) == identity
        effects.append({'source': name, 'destination': str(destination.relative_to(item)),
                        'fileId': identity[1], 'sha256': hashlib.sha256(data).hexdigest()})
    (item / 'witness-disposition.json').write_text(json.dumps(effects))
    assert settle() == 0  # Existing exact replay, no first-placement witnesses.
    assert (item / 'agent-runs.jsonl').read_bytes() == ledger
    states = []
    assert validator.validate_work_item(item, strict_revise=False, obligation_state_out=states) == []
    assert not states[-1].open_revise
    changed = copy.deepcopy(proof)
    changed['bindingEvidence']['angle']['value'] = 'different replay'
    assert settle(changed) != 0
    assert (item / 'agent-runs.jsonl').read_bytes() == ledger
    assert settle(run_id='second-distinct-receiving') != 0
    assert (item / 'agent-runs.jsonl').read_bytes() == ledger


@pytest.mark.parametrize('case', [{'proof_version': 2, 'semantic_units': True}], indirect=True)
@pytest.mark.parametrize('selected', ['after.md', 'reviews/r2.json'])
def test_same_byte_first_placement_input_replacement_refuses(case, selected):
    writer, validator, item, proof, _settle, _root, _anchor = case
    fact = proof['bindingEvidence']['nativeReceiving']['facts'][0]
    args = writer.build_parser().parse_args(['--work-item', str(item), 'append',
        '--run-id', 'synthetic-native-placement', '--role', 'lead', '--execution-role', 'main',
        '--event-kind', 'standalone', '--status', 'completed', '--gate', 'PASS',
        '--scope', 'actual semantic receiving', '--artifact', 'reviews/received.md',
        '--closes', proof['target']['runId'], '--evidence-json', json.dumps(fact),
        '--review-closure-proof-json', json.dumps(proof),
        '--started-at', '2026-10-25T10:00:00Z', '--updated-at', '2026-10-25T10:00:01Z'])
    event = writer.build_event(args, validator)
    previous = (item / 'agent-runs.jsonl').read_bytes()
    def swap():
        source = item / selected
        old_id = source.stat().st_ino
        replacement = source.with_name(source.name + '.replacement')
        replacement.write_bytes(source.read_bytes())
        os.replace(replacement, source)
        assert source.stat().st_ino != old_id
    with pytest.raises(ValueError, match='DRIFT|current|STALE'):
        writer._append_event_transaction(item, validator, lambda previous: event, before_replace=swap)
    assert (item / 'agent-runs.jsonl').read_bytes() == previous
    assert not (item / 'agent-runs.jsonl.lock').exists()
    assert not (item / 'agent-runs.jsonl.tmp').exists()


def test_corrupt_durable_report_reopens_dependent_closure(case):
    _writer, validator, item, _proof, settle, _root, _anchor = case
    assert settle() == 0
    (item / 'reviews/r2.json').write_text('{"different":"actual retained claim lost"}')
    states = []
    errors = validator.validate_work_item(item, strict_revise=False, obligation_state_out=states)
    assert errors
    assert states and any(row.run_id == 'synthetic-safe2049-target' for row in states[-1].open_revise)


def test_anchor_strict_json_utf8_and_literal_domains(tmp_path):
    validator = load('scripts/validate-work-item-state.py', 'anchor_strict_validator')
    item = tmp_path / 'work-items/active/anchors'
    item.mkdir(parents=True)
    path = item / 'source.json'
    def receive(raw, selector):
        path.write_bytes(raw)
        inputs = validator._CurrentEvidenceV1()
        locator = inputs.artifact(item, 'source.json', 'source', 'anchor-test', [])
        anchor = {'source': {'kind': 'review', 'ref': 'source.json'},
                  'sourceSha256': hashlib.sha256(raw).hexdigest(), 'selector': selector}
        return validator.resolve_review_source_anchor_v1(anchor,
            admitted_sources={'source.json': locator}, inputs=inputs).value
    assert receive(b'{"*":{"": [1]}}', {'kind': 'json-value', 'path': ['*', '', 0]}) == 1
    for raw in [b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":Infinity}', b'{"x":1e9999}', b'\xff']:
        with pytest.raises((ValueError, UnicodeError)):
            receive(raw, {'kind': 'json-value', 'path': []})
    # Build actual multibyte bytes without depending on escaped-source locale.
    raw = bytes([65, 206, 187, 66])
    assert receive(raw, {'kind': 'utf8-range', 'start': 1, 'end': 3}) == chr(955)
    for start, end in [(1, 2), (2, 3), (0, 9), (1, 1)]:
        with pytest.raises((ValueError, UnicodeError)):
            receive(raw, {'kind': 'utf8-range', 'start': start, 'end': end})


def test_captured_current_history_retains_relation_after_real_custody_copy(case):
    from dataclasses import replace
    import shutil
    _writer, validator, item, _proof, settle, root, _anchor = case
    assert settle() == 0
    # Dispose exact test-created draft witnesses by a normal preserving move.
    witness_effects = []
    for name in ('before.md', 'after.md'):
        source = item / name
        before = source.read_bytes()
        identity = source.stat().st_ino
        source.unlink()  # Explicit normal removal of this exact test-created ordinary draft.
        assert not source.exists()
        witness_effects.append({'source': name, 'fileId': identity,
                               'sha256': hashlib.sha256(before).hexdigest(), 'removed': True})
    (item / 'witness-disposition.json').write_text(json.dumps(witness_effects))
    helpers = load('tests/test_ledger_h1_effective_view.py', 'review_existing_history_fixture')
    observed = helpers._capture_current_history(validator, root, item)
    assert observed.acquisition_complete and not observed.operation_diagnostics()
    binding = observed._current_item.binding
    owner = validator.load_lifecycle_owner()
    custody = root / 'retained-review-custody'
    custody.mkdir()
    records = []
    for index, record in enumerate(binding.files):
        path = custody / str(index) / Path(record.original_path).name
        path.parent.mkdir()
        path.write_bytes(record.snapshot.data)
        snapshot = owner._capture_file_snapshot(path, failure_id='TEST-RETAINED')
        assert snapshot.data == record.snapshot.data
        records.append(replace(record, snapshot=snapshot))
    current_directory = owner._capture_directory_snapshot(custody, failure_id='TEST-CUSTODY')
    acquired = owner.AcquiredWorkItemInputV1(root,
        tuple(owner.CapturedInputAssociationV1(
            binding.acquired_input.files[root / record.original_path].original,
            record.snapshot) for record in records),
        tuple(owner.CapturedInputAssociationV1(row.original, current_directory)
              for row in binding.acquired_input.directories.values()))
    retained = replace(binding, files=tuple(records), acquired_input=acquired)
    # Existing typed capture/association owner, same fixture pattern as
    # test_legacy_flat_history_binding.py:113-140; no new transfer store.
    assert item.is_relative_to(root)
    shutil.rmtree(item)
    assert not item.exists()
    after = validator.observe_captured_work_item_history(retained)
    assert after.acquisition_complete and not after.operation_diagnostics()
    assert not after.obligations.open_revise
    assert after.ledger_sha256 == observed.ledger_sha256
    # Corruption of ACTUAL retained reviewer claims stays a refusal.
    claim = next(record for record in records if record.original_path.endswith('/reviews/r2.json'))
    claim.snapshot.path.write_bytes(b'changed durable claim')
    damaged = validator.observe_captured_work_item_history(retained)
    assert damaged.operation_diagnostics()


@pytest.mark.parametrize('case', [{'manual': True, 'proof_version': 2}], indirect=True)
def test_owner_equivalent_actual_text_claims_without_format_or_loop_gate(case):
    _writer, validator, item, proof, settle, _root, _anchor = case
    assert proof['version'] == 2
    assert settle() == 0
    states = []
    assert validator.validate_work_item(item, strict_revise=False, obligation_state_out=states) == []
    assert not states[-1].open_revise


def test_later_captured_read_rejects_replacement_but_new_capture_is_not_old_inode_promise(case):
    _writer, validator, item, _proof, settle, root, _anchor = case
    assert settle() == 0
    context = validator.load_effective_ledger_view(root, item,
        item.relative_to(root).as_posix() + '/agent-runs.jsonl')
    report = item / 'reviews/r2.json'
    original_id = report.stat().st_ino
    alternate = report.with_suffix('.replacement')
    alternate.write_bytes(report.read_bytes())
    os.replace(alternate, report)
    assert report.stat().st_ino != original_id
    errors = []
    open_revise, _launches = validator.validate_closure(context.rows, errors, context=context)
    assert errors or open_revise
    # This is a genuinely new capture after the test-authorized copy operation,
    # not reuse/clearing of the earlier transaction's native snapshot.
    states = []
    assert validator.validate_work_item(item, strict_revise=False, obligation_state_out=states) == []
    assert not states[-1].open_revise


@pytest.mark.parametrize('case', [{'reviewer_role': 'architect', 'reviewer_assigned_role': 'security-reviewer'}], indirect=True)
def test_assigned_role_label_cannot_launder_another_native_profession(case):
    _writer, _validator, item, _proof, settle, _root, _anchor = case
    before = (item / 'agent-runs.jsonl').read_bytes()
    assert settle() != 0
    assert (item / 'agent-runs.jsonl').read_bytes() == before




@pytest.mark.parametrize('case', [{'sha256_revision': True}], indirect=True)
@pytest.mark.parametrize('replace_witness', [False, True])
def test_prefixed_sha256_revision_keeps_first_placement_witness_binding(case, replace_witness):
    _writer, validator, item, proof, settle, _root, _anchor = case
    assert proof['subject']['after']['revision'].startswith('sha256:')
    before = (item / 'agent-runs.jsonl').read_bytes()
    if replace_witness:
        (item / 'after.md').write_bytes(b'unreviewed substituted first-placement witness\n')
    result = settle()
    after = (item / 'agent-runs.jsonl').read_bytes()
    states = []
    errors = validator.validate_work_item(item, strict_revise=False, obligation_state_out=states)
    open_ids = [row.run_id for row in states[-1].open_revise]
    print(json.dumps({'probe': 'prefixed-sha256-first-witness', 'replaced': replace_witness,
                      'writerReturn': result, 'ledgerUnchanged': before == after,
                      'openReviseIDs': open_ids, 'validatorErrors': errors}))
    if replace_witness:
        assert result != 0 and after == before
        assert open_ids == [proof['target']['runId']]
    else:
        assert result == 0 and not errors and not open_ids


@pytest.mark.parametrize('case', [{'opaque_revisions': True}], indirect=True)
def test_opaque_git_revision_identifiers_are_not_universal_content_hashes(case):
    _writer, validator, item, _proof, settle, _root, _anchor = case
    assert settle() == 0
    states = []
    assert validator.validate_work_item(item, strict_revise=False, obligation_state_out=states) == []
    assert not states[-1].open_revise


@pytest.mark.parametrize('case', [{'proof_version': 2, 'semantic_units': True}, {'known_contract': True}], indirect=True)
def test_current_only_cross_repository_clone_retains_c3_without_source_witnesses(case, monkeypatch):
    """Real normal Git clone and destination public receiving; no push/alias map."""
    import subprocess
    import shutil
    _writer, validator, item, proof, settle, root, _anchor = case
    assert settle() == 0
    original_ledger = (item / 'agent-runs.jsonl').read_bytes()
    witness_disposition = []
    for name in ('before.md', 'after.md'):
        path = item / name
        native = path.stat()
        data = path.read_bytes()
        path.unlink()  # Exact ordinary witnesses created by this case only.
        assert not path.exists()
        witness_disposition.append({'path': name, 'nativeID': [native.st_dev, native.st_ino],
                                    'sha256': hashlib.sha256(data).hexdigest(), 'sourceAbsent': True})
    (item / 'witness-disposition.json').write_text(json.dumps(witness_disposition))
    transfer_kind = 'known' if proof['rootSemanticReceiving']['version'] == 2 else 'unpromised'
    current = {path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
               for path in item.rglob('*') if path.is_file()}
    git = str(Path(shutil.which('git')).resolve(strict=True))
    commands = []
    def run(*args):
        argv = [git, *map(str, args)]
        result = subprocess.run(argv, capture_output=True, timeout=30)
        # Preserve complete acquired bytes in the test's owned evidence before
        # assertions. This is a hermetic fixture transfer, not Source/real W.
        evidence = root.parent / (root.name + '-' + transfer_kind + '-transfer-evidence')
        evidence.mkdir(exist_ok=True)
        index = len(commands)
        (evidence / (str(index) + '.stdout')).write_bytes(result.stdout)
        (evidence / (str(index) + '.stderr')).write_bytes(result.stderr)
        commands.append({'argv': argv, 'exit': result.returncode})
        (evidence / 'commands.json').write_text(json.dumps(commands))
        assert result.returncode == 0, result.stderr
        return result.stdout
    run('init', '--initial-branch=main', '--object-format=sha1', root)
    run('-C', root, 'add', '--', item.relative_to(root))
    run('-C', root, '-c', 'user.name=Synthetic C3 transfer', '-c', 'user.email=synthetic@example.invalid',
        'commit', '-m', 'synthetic current durable review evidence')
    source_oid = run('-C', root, 'rev-parse', 'HEAD').strip()
    # Only the current durable item is ever committed. No draft bytes, old
    # Source, real journal, ignored state or user configuration is copied.
    destination = root.parent / (root.name + '-' + transfer_kind + '-received')
    assert not destination.exists()
    run('clone', '--no-hardlinks', '--', root, destination)
    assert not (destination / '.git/objects/info/alternates').exists()
    assert not (destination / '.git/commondir').exists()
    assert run('-C', destination, 'rev-parse', 'HEAD').strip() == source_oid
    assert len(run('-C', destination, 'rev-list', '--all').splitlines()) == 1
    received_item = destination / item.relative_to(root)
    assert root.stat().st_ino != destination.stat().st_ino
    assert {path.relative_to(destination).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in received_item.rglob('*') if path.is_file()} == current
    assert not (received_item / 'before.md').exists() and not (received_item / 'after.md').exists()
    for relative in current:
        assert (root / relative).stat().st_ino != (destination / relative).stat().st_ino
    retained_source = root.parent / (root.name + '-' + transfer_kind + '-source-retained')
    assert not retained_source.exists()
    old_root_id = root.stat().st_ino
    root.rename(retained_source)  # Normal preserving source disposition.
    assert not root.exists() and retained_source.stat().st_ino == old_root_id
    trap = destination / 'unselected-private.bin'
    trap.write_bytes(b'\xffunselected synthetic trap')
    actual_open = Path.open
    def confined_open(path, *args, **kwargs):
        absolute = path.absolute()
        if absolute == trap or absolute.is_relative_to(root) or absolute.is_relative_to(retained_source):
            raise AssertionError('destination current-only read attempted unselected/old source body')
        return actual_open(path, *args, **kwargs)
    owner = validator.load_lifecycle_owner()
    actual_capture = owner._capture_file_snapshot
    native_captures = []
    def confined_capture(path, *args, **kwargs):
        absolute = Path(path).absolute()
        if absolute == trap or not (absolute.is_relative_to(destination) or absolute.is_relative_to(ROOT)):
            raise AssertionError('destination native capture escaped selected current/code roots')
        native_captures.append(str(absolute))
        return actual_capture(path, *args, **kwargs)
    with monkeypatch.context() as guard:
        guard.setattr(Path, 'open', confined_open)
        guard.setattr(owner, '_capture_file_snapshot', confined_capture)
        states = []
        errors = validator.validate_work_item(received_item, strict_revise=False, obligation_state_out=states)
        assert not errors and states and not states[-1].open_revise, errors
        context = validator.load_effective_ledger_view(destination, received_item,
            received_item.relative_to(destination).as_posix() + '/agent-runs.jsonl')
        closure_errors = []
        validity = validator.derive_event_validity(context.rows, received_item, closure_errors, context=context)
        opened, launches = validator.validate_closure(context.rows, closure_errors, context=context, validity=validity)
        assert not closure_errors and not opened and not launches
        import contextlib, io
        public_output = io.StringIO()
        with contextlib.redirect_stdout(public_output):
            public_return = validator.main(['--work-item', str(received_item), '--obligations-json'])
        public_result = json.loads(public_output.getvalue())
        assert public_return == 0 and public_result['result'] == 'PASS'
        assert not public_result['obligations']['openRevises']
    assert native_captures and any(name.endswith('reviews' + os.sep + 'r2.json') for name in native_captures)
    assert (received_item / 'agent-runs.jsonl').read_bytes() == original_ledger
    # These are actual destination current/effective public acquisitions. No
    # hand-built original-root capture or transferred authority object exists.
    (received_item / 'reviews/r2.json').write_bytes(b'corrupt actual retained reviewer claim')
    damaged_states = []
    damaged = validator.validate_work_item(received_item, strict_revise=False, obligation_state_out=damaged_states)
    damaged_ids = [row.run_id for row in damaged_states[-1].open_revise] if damaged_states else []
    print(json.dumps({'probe': 'real-current-only-cross-repository', 'sourceNativeID': old_root_id,
                      'destinationNativeID': destination.stat().st_ino, 'currentFileCount': len(current),
                      'gitCommits': 1, 'sourcePathAbsent': not root.exists(), 'draftWitnessesAbsent': True,
                      'publicEffectiveCleanBeforeCorruption': True, 'publicCliClean': True,
                      'selectedNativeCaptures': native_captures,
                      'corruptionDiagnostics': damaged, 'corruptionOpenReviseIDs': damaged_ids,
                      'ledgerUnchanged': (received_item / 'agent-runs.jsonl').read_bytes() == original_ledger}))
    assert damaged and proof['target']['runId'] in damaged_ids
    assert (received_item / 'agent-runs.jsonl').read_bytes() == original_ledger


@pytest.mark.parametrize('case', [{'manual_json': True, 'owner_equivalent': True, 'proof_version': 2}], indirect=True)
def test_owner_equivalent_overall_report_verdict_is_not_a_finding_schema(case):
    _writer, validator, item, _proof, settle, _root, _anchor = case
    result = settle()
    states = []
    errors = validator.validate_work_item(item, strict_revise=False, obligation_state_out=states)
    print(json.dumps({'probe': 'manual-json-overall-verdict', 'writerReturn': result, 'errors': errors,
                      'openReviseIDs': [row.run_id for row in states[-1].open_revise]}))
    assert result == 0 and not errors and not states[-1].open_revise


@pytest.mark.parametrize('case', [{'proof_version': 2, 'semantic_units': True}], indirect=True)
def test_v2_actual_unit_positive_and_typed_source_ancestry(case):
    _writer, validator, item, proof, settle, _root, _anchor = case
    assert settle() == 0
    states = []
    assert validator.validate_work_item(item, strict_revise=False, obligation_state_out=states) == []
    assert not states[-1].open_revise
    rows = [json.loads(line) for line in (item / 'agent-runs.jsonl').read_bytes().splitlines()]
    def actual_depth(value):
        if type(value) is dict: return max((1 + actual_depth(part) for part in value.values()), default=0)
        if type(value) is list: return max((1 + actual_depth(part) for part in value), default=0)
        return 0
    assert actual_depth(rows[-1]) == validator.MAX_JSON_NESTING_DEPTH == 9
    # Historical negative/equal text outside selected current units is no veto.
    import subprocess
    result = subprocess.run([sys.executable, '-X', 'utf8', '-B', str(ROOT / 'scripts/validate-work-item-state.py'),
        '--work-item', str(item), '--obligations-json'], capture_output=True, timeout=60)
    (item.parent / 'cold-reader.stdout').write_bytes(result.stdout)
    (item.parent / 'cold-reader.stderr').write_bytes(result.stderr)
    assert result.returncode == 0, result.stdout + result.stderr
    assert not json.loads(result.stdout)['obligations']['openRevises']
    before = (item / 'agent-runs.jsonl').read_bytes()
    assert settle() == 0
    assert (item / 'agent-runs.jsonl').read_bytes() == before




@pytest.mark.parametrize('case', [{'proof_version': 2, 'semantic_units': True}], indirect=True)
def test_v2_authority_coordinate_and_actual_result_negatives(case):
    _writer, _validator, item, proof, settle, _root, _anchor = case
    before = (item / 'agent-runs.jsonl').read_bytes()
    for defect in ('JSON-range', 'highlight', 'missing-meaning', 'wrong-revision', 'duplicate'):
        selected = copy.deepcopy(proof)
        result = selected['rootSemanticReceiving']['findings'][0]
        if defect == 'JSON-range':
            raw = (item / 'reviews/r2.json').read_bytes()
            result['reviewerClaimUnit']['selector'] = {'kind': 'utf8-range', 'start': 0, 'end': len(raw)}
        elif defect == 'highlight': result['highlight'] = result['reviewerClaimUnit']
        elif defect == 'missing-meaning': result.pop('meaning')
        elif defect == 'wrong-revision': result['reviewedRevision'] = 'other-revision'
        elif defect == 'duplicate': selected['rootSemanticReceiving']['findings'].append(copy.deepcopy(result))
        assert settle(selected) != 0
        assert (item / 'agent-runs.jsonl').read_bytes() == before


@pytest.mark.parametrize('case', [{'proof_version': 2, 'manual': True},
                                {'proof_version': 2, 'manual_json': True}], indirect=True)
def test_v2_prose_and_manual_overall_json_actual_positive(case):
    _writer, validator, item, proof, settle, _root, _anchor = case
    assert settle() == 0
    states = []
    assert validator.validate_work_item(item, strict_revise=False, obligation_state_out=states) == []
    assert not states[-1].open_revise


@pytest.mark.parametrize('case', [{'proof_version': 2, 'manual': True}], indirect=True)
def test_v2_prose_subrange_and_missing_root_meaning_refuse(case):
    _writer, _validator, item, proof, settle, _root, _anchor = case
    before = (item / 'agent-runs.jsonl').read_bytes()
    selected = copy.deepcopy(proof)
    selected['rootSemanticReceiving']['findings'][0]['reviewerClaimUnit']['selector']['start'] = 1
    assert settle(selected) != 0
    selected = copy.deepcopy(proof)
    selected['rootSemanticReceiving']['findings'][0]['meaning'] = 'PASS'
    assert settle(selected) != 0
    assert (item / 'agent-runs.jsonl').read_bytes() == before




def test_v2_source_unit_integrity_errors_never_become_prose(tmp_path):
    fixtures = load('tests/test_agent_run_ledger.py', 'v2_unit_integrity_fixtures')
    validator = fixtures.load_ledger_module().load_validator()
    item = fixtures.prepare_valid_work_item(tmp_path)
    source = item / 'reviews/unit.json'
    def receive(raw, selector):
        source.write_bytes(raw)
        inputs = validator._CurrentEvidenceV1()
        locator = inputs.artifact(item, 'reviews/unit.json', 'unit integrity', 'synthetic', [])
        anchor = {'source': {'kind': 'review', 'ref': 'reviews/unit.json'},
                  'sourceSha256': hashlib.sha256(raw).hexdigest(), 'selector': selector}
        return validator.resolve_review_source_unit_v2(anchor, admitted_sources={'reviews/unit.json': locator}, inputs=inputs)
    for raw in (b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":1e999}', b'\xffbroken UTF8'):
        with pytest.raises((ValueError, UnicodeError)):
            receive(raw, {'kind': 'utf8-range', 'start': 0, 'end': len(raw)})
    raw = b'"actual JSON string prose"'
    value = receive(raw, {'kind': 'json-value', 'path': []})
    assert value.value == 'actual JSON string prose' and value.coordinate == ()
    with pytest.raises(ValueError, match='actual JSON'):
        receive(raw, {'kind': 'utf8-range', 'start': 0, 'end': len(raw)})
    raw = 'whole actual prose \u041f\u0440\u0438\u043c\u0435\u0440'.encode('utf-8')
    value = receive(raw, {'kind': 'utf8-range', 'start': 0, 'end': len(raw)})
    assert value.selector_kind == 'utf8-range' and value.coordinate == (0, len(raw))
    with pytest.raises(ValueError): receive(raw, {'kind': 'json-value', 'path': []})


@pytest.mark.parametrize('case', [{'manual': True}], indirect=True)
def test_unproved_opaque_v1_is_not_upgraded_by_nonempty_source(case):
    _writer, validator, item, proof, settle, _root, _anchor = case
    before = (item / 'agent-runs.jsonl').read_bytes()
    assert proof['version'] == 1 and settle() != 0
    states = []
    assert validator.validate_work_item(item, strict_revise=False, obligation_state_out=states) == []
    assert [row.run_id for row in states[-1].open_revise] == [proof['target']['runId']]
    assert (item / 'agent-runs.jsonl').read_bytes() == before


@pytest.mark.parametrize('case', [{'proof_version': 2, 'semantic_units': True}], indirect=True)
def test_v2_wrong_binding_and_source_cannot_receive(case):
    _writer, validator, item, proof, settle, _root, _anchor = case
    before = (item / 'agent-runs.jsonl').read_bytes()
    for defect in ('subject', 'report-hash', 'reviewer-row', 'source'):
        selected = copy.deepcopy(proof)
        if defect == 'subject': selected['subject']['after']['revision'] = 'unproved'
        elif defect == 'report-hash': selected['reports']['passSha256'] = '0' * 64
        elif defect == 'reviewer-row': selected['reviewerPass']['rawLineSha256'] = '0' * 64
        else: selected['rootSemanticReceiving']['findings'][0]['reviewerClaimUnit']['source']['ref'] = 'reviews/unselected-trap.json'
        assert settle(selected) != 0
        assert (item / 'agent-runs.jsonl').read_bytes() == before
    states = []
    assert validator.validate_work_item(item, strict_revise=False, obligation_state_out=states) == []
    assert [row.run_id for row in states[-1].open_revise] == [proof['target']['runId']]


@pytest.mark.parametrize('case', [{'proof_version': 2, 'reviewer_role': 'architect'}], indirect=True)
def test_v2_actual_wrong_profession_refuses(case):
    _writer, _validator, item, _proof, settle, _root, _anchor = case
    before = (item / 'agent-runs.jsonl').read_bytes()
    assert settle() != 0 and (item / 'agent-runs.jsonl').read_bytes() == before




@pytest.mark.parametrize('case', [
    {'proof_version': 2, 'manual_json': True, 'scalar_claims': True},
    {'proof_version': 2, 'manual_json': True, 'scalar_claims': True, 'report_metadata': {'id': 'synthetic-report-identity-not-a-finding'}},
    {'proof_version': 2, 'semantic_units': True, 'report_metadata': {'revision': 1}},
    {'proof_version': 2, 'semantic_units': True, 'report_metadata': {'formatVersion': 1}},
    {'proof_version': 2, 'manual_json': True, 'scalar_claims': True, 'nested_envelope': True, 'report_metadata': {'id': 'nested report metadata', 'revision': 1}},
    {'proof_version': 2, 'manual_json': True, 'scalar_claims': True, 'nested_envelope': True, 'report_metadata': {'documentLabel': 'nested report metadata', 'formatVersion': 1}},
    {'proof_version': 2, 'manual_json': True, 'report_metadata': {'id': 'overall report', 'revision': 1, 'observations': [{'id': 'document observation', 'revision': 1}]}},
    {'proof_version': 2},
], indirect=True)
def test_v2_document_metadata_roles_preserve_actual_claims(case):
    _writer, validator, item, _proof, settle, _root, _anchor = case
    assert settle() == 0
    states = []
    assert validator.validate_work_item(item, strict_revise=False, obligation_state_out=states) == []
    assert not states[-1].open_revise
    import subprocess
    cold = subprocess.run([sys.executable, '-X', 'utf8', '-B', str(ROOT / 'scripts/validate-work-item-state.py'),
        '--work-item', str(item), '--obligations-json'], capture_output=True, timeout=60)
    (item.parent / 'metadata-pair-cold.stdout').write_bytes(cold.stdout)
    (item.parent / 'metadata-pair-cold.stderr').write_bytes(cold.stderr)
    assert cold.returncode == 0, cold.stdout + cold.stderr
    assert not json.loads(cold.stdout)['obligations']['openRevises']


def assert_model_receiving(case, expected, *, selected=None, cold_candidate=True):
    """Public/effective/new-process receiving; no real Root act is simulated."""
    import subprocess
    writer, validator, item, proof, settle, _root, _anchor = case
    ledger = item / 'agent-runs.jsonl'
    before = ledger.read_bytes()
    from unittest import mock
    candidates = []
    actual_build = writer.build_event
    def observed(*args, **kwargs):
        event = actual_build(*args, **kwargs)
        candidates.append(copy.deepcopy(event))
        return event
    with mock.patch.object(writer, 'build_event', side_effect=observed):
        code = settle(selected)
    after = ledger.read_bytes()
    if candidates:
        (item.parent / 'model-actual-public-candidate.json').write_text(json.dumps(candidates[-1], indent=2), encoding='utf8')
    states = []
    errors = validator.validate_work_item(item, strict_revise=False, obligation_state_out=states)
    opened = [row.run_id for row in states[-1].open_revise]
    tested = after
    if not expected and code != 0 and cold_candidate and candidates:
        # Deliberate own fixture corruption carries the ACTUAL refused public
        # candidate; it proves cold machine receiving, not a genuine Root act.
        assert after == before
        tested = before + json.dumps(candidates[-1], separators=(',', ':')).encode('utf8') + b'\n'
        ledger.write_bytes(tested)
        durable_states = []
        durable_errors = validator.validate_work_item(item, strict_revise=False, obligation_state_out=durable_states)
        assert durable_errors
        assert [row.run_id for row in durable_states[-1].open_revise] == [proof['target']['runId']]
    cold = subprocess.run([sys.executable, '-X', 'utf8', '-B', str(ROOT / 'scripts/validate-work-item-state.py'),
        '--work-item', str(item), '--obligations-json'], capture_output=True, timeout=60)
    (item.parent / 'model-cold.stdout').write_bytes(cold.stdout)
    (item.parent / 'model-cold.stderr').write_bytes(cold.stderr)
    view = json.loads(cold.stdout)
    print(json.dumps({'probe': 'model-known-or-truthful-synthetic-receiving', 'expected': expected,
        'writerReturn': code, 'publicRawUnchanged': before == after, 'errors': errors,
        'open': opened, 'coldExit': cold.returncode, 'coldOpen': view['obligations']['openRevises'],
        'actualRefusedCandidateCold': tested != after}))
    assert (code == 0) == expected
    assert opened == ([] if expected else [proof['target']['runId']])
    assert (cold.returncode == 0) == expected
    assert bool(view['obligations']['openRevises']) != expected
    if expected:
        assert not errors
    else:
        assert after == before
    assert ledger.read_bytes() == tested
    return after


@pytest.mark.parametrize('case', [{'known_contract': True}, {'known_contract': True, 'known_role': 'target'}], indirect=True)
def test_explicit_six_field_known_public_cold_and_replay(case):
    _writer, validator, item, _proof, settle, _root, _anchor = case
    after = assert_model_receiving(case, True)
    event = json.loads(after.splitlines()[-1])
    proof = event['reviewClosureProofs'][0]
    assert proof['rootSemanticReceiving']['version'] == 2
    known = [entry for entry, _binding in validator._review_contract_references(event)]
    assert len(known) == 1
    assert type(known[0]['result']) is str
    assert known[0] in proof['bindingEvidence']['nativeReceiving']['facts']
    assert any(entry['ref'] == 'reviews/known-state.json' for entry in event['evidence'])
    # Exact first-placement-only drafts may be disposed without rebaselining
    # the actual commissioning/delivery/state sources retained by this result.
    for name in ('before.md', 'after.md'):
        (item / name).unlink()
    assert settle() == 0
    assert (item / 'agent-runs.jsonl').read_bytes() == after


@pytest.mark.parametrize('case', [
    {'known_contract': True, 'known_verdict': 'REVISE'},
    {'known_contract': True, 'known_verdict': 'pass'},
    {'known_contract': True, 'known_missing': 'blockers'},
    {'known_contract': True, 'known_wrong_meta': 'root_proven'},
    {'known_contract': True, 'known_protocol': 'review-loop-default-minimum-result-v2'},
    *[{'known_contract': True, 'known_reference_defect': defect}
      for defect in ('attempt', 'revision', 'producer', 'lane', 'delivery')],
], indirect=True)
def test_known_actual_promise_value_and_association_fail_closed(case):
    assert_model_receiving(case, False)


@pytest.mark.parametrize('case', [{'known_contract': True}], indirect=True)
@pytest.mark.parametrize('defect', ['downgrade', 'drop-forwarded-fact', 'result-not-string', 'missing-support', 'noncanonical'])
def test_known_input_cannot_be_erased_by_interpretation_or_transport(case, defect, monkeypatch):
    writer, validator, item, proof, _settle, _root, _anchor = case
    selected = copy.deepcopy(proof)
    if defect == 'downgrade':
        selected['rootSemanticReceiving']['version'] = 1
    elif defect == 'missing-support':
        (item / 'reviews/known-state.json').unlink()
    else:
        build = writer.build_event
        def corrupt_forwarding(*args, **kwargs):
            event = build(*args, **kwargs)
            if defect == 'drop-forwarded-fact':
                facts = event['reviewClosureProofs'][0]['bindingEvidence']['nativeReceiving']['facts']
                facts[:] = [entry for entry in facts if not (type(entry.get('result')) is str
                    and entry['result'].startswith('{'))]
            else:
                for entry in event['evidence']:
                    if type(entry.get('result')) is str and entry['result'].startswith('{'):
                        value = json.loads(entry['result'])
                        entry['result'] = json.dumps(value, indent=2) if defect == 'noncanonical' else value
            return event
        monkeypatch.setattr(writer, 'build_event', corrupt_forwarding)
    assert_model_receiving(case, False, selected=selected)


@pytest.mark.parametrize('case', [{'known_contract': True}], indirect=True)
def test_known_support_same_byte_replacement_remains_currentness_refusal(case, monkeypatch):
    _writer, validator, item, _proof, _settle, _root, _anchor = case
    owner = validator.load_review_loop_owner()
    actual = owner.qualify_completed_verdict_result_v2
    replaced = []
    def qualify(*args, **kwargs):
        result = actual(*args, **kwargs)
        if not replaced:
            path = item / 'reviews/known-state.json'
            before = path.stat().st_ino
            alternate = path.with_suffix('.replacement')
            alternate.write_bytes(path.read_bytes())
            os.replace(alternate, path)
            replaced.append((before, path.stat().st_ino))
        return result
    monkeypatch.setattr(owner, 'qualify_completed_verdict_result_v2', qualify)
    assert_model_receiving(case, False, cold_candidate=False)
    assert replaced and replaced[0][0] != replaced[0][1]


def test_real_L_default_minimum_and_fixed_profile_presence_are_distinct():
    owner = load('scripts/review_loop_state.py', 'model_L_value_owner')
    minimum = {'verdict': 'PASS', 'rationale': 'actual rationale', 'root_proven': 'actual root',
               'scope_unchanged': 'actual scope', 'verification_adequate': 'actual verification'}
    assert owner.verdict_result_errors_v2(minimum) == []
    assert owner.verdict_result_errors_v2(minimum, require_all_fields=True)
    six = {**minimum, 'blockers': []}
    assert owner.verdict_result_errors_v2(six, require_all_fields=True) == []
    for wrong in (True, 1, 'pass', 'VERIFIED', {}, []):
        assert owner.verdict_result_errors_v2({**six, 'verdict': wrong}, require_all_fields=True)


@pytest.mark.parametrize('case', [{'proof_version': 2, 'semantic_units': True, 'unit_verdict': 'failed'}], indirect=True)
def test_unknown_negative_has_no_genuine_positive_Root_receiving_input(case):
    # These controlled assertions are ACTUAL NEGATIVE source. A positive Root
    # frame over them would be fabricated, not a machine decoder countermodel.
    # Do not issue one and call that genuine semantic receiving. The public
    # port must refuse when the genuine normalized Root act is absent.
    _writer, _validator, _item, proof, _settle, _root, _anchor = case
    missing_act = copy.deepcopy(proof)
    missing_act.pop('rootSemanticReceiving')
    assert_model_receiving(case, False, selected=missing_act)


@pytest.mark.parametrize('case', [{'proof_version': 2, 'semantic_units': True, 'unpromised_overall_dto': True}], indirect=True)
def test_uncommissioned_DTO_shape_supplies_no_machine_promise(case):
    assert_model_receiving(case, True)


@pytest.mark.parametrize('case', [{'known_contract': True}], indirect=True)
def test_prior_actual_Root_adoption_cannot_be_dropped_from_next_candidate(case, monkeypatch):
    writer, _validator, item, _proof, settle, _root, _anchor = case
    assert len(settle.contract_evidence) == 1
    arguments = ['--work-item', str(item), 'append', '--run-id', 'synthetic-known-commission-adoption',
        '--role', 'lead', '--execution-role', 'main', '--event-kind', 'standalone', '--status', 'completed', '--gate', 'PASS',
        '--scope', 'actual synthetic known commission acquisition', '--artifact', 'reviews/commission.txt',
        '--started-at', '2026-10-25T10:00:02Z', '--updated-at', '2026-10-25T10:00:03Z',
        '--evidence-json', json.dumps(settle.contract_evidence[0])]
    assert writer.main(arguments) == 0
    actual_build = writer.build_event
    def omitted(*args, **kwargs):
        event = actual_build(*args, **kwargs)
        event['evidence'][:] = [entry for entry in event['evidence']
            if not (type(entry.get('result')) is str and entry['result'].startswith('{'))]
        receiving = event['reviewClosureProofs'][0]
        receiving['rootSemanticReceiving']['version'] = 1
        facts = receiving['bindingEvidence']['nativeReceiving']['facts']
        facts[:] = [entry for entry in facts if not (type(entry.get('result')) is str and entry['result'].startswith('{'))]
        return event
    monkeypatch.setattr(writer, 'build_event', omitted)
    assert_model_receiving(case, False)


@pytest.mark.parametrize('case', [{'known_contract': True}], indirect=True)
def test_current_typed_promise_cannot_be_relabelled_as_unrelated_then_downgraded(case, monkeypatch):
    writer, validator, _item, _proof, _settle, _root, _anchor = case
    actual_build = writer.build_event
    def wrong_producer_transport(*args, **kwargs):
        event = actual_build(*args, **kwargs)
        proof = event['reviewClosureProofs'][0]
        proof['rootSemanticReceiving']['version'] = 1
        for entry in [*event['evidence'], *proof['bindingEvidence']['nativeReceiving']['facts']]:
            if type(entry.get('result')) is str and entry['result'].startswith('{'):
                value = json.loads(entry['result'])
                value['producer']['runId'] = 'unselected-producer'
                entry['result'] = validator._canonical_projection_bytes(value).decode('utf8')
        return event
    monkeypatch.setattr(writer, 'build_event', wrong_producer_transport)
    assert_model_receiving(case, False)


