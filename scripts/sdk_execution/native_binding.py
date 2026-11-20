"""Explicit Root native-child associations, not native execution or permission receipts.

Run from the installed scripts directory: python -m sdk_execution.native_binding.
Only existing work-item artifacts and the canonical ledger store durable state.
"""
from __future__ import annotations
import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    __package__ = "sdk_execution"
from .contracts import json_text, strict_json
from .receiving import review_artifact_target
from .runtime import _owner, _ledger, _events, _child_artifact_document, _sha256


@dataclass(frozen=True)
class NativeBindingContext:
    work_item: str
    ledger_max_events: int | None = None
    ledger_max_bytes: int | None = None

    def __post_init__(self):
        if not Path(self.work_item).is_absolute():
            raise ValueError("native_binding_work_item_absolute_required")


def _text(value):
    if type(value) is not str or not value.strip():
        raise ValueError("native_binding_nonempty_text_required")
    return value


def _key(assignment_id, kind):
    return "native-child-" + kind + "-" + hashlib.sha256(_text(assignment_id).encode()).hexdigest()


def _assignment(value):
    fields={"schema_version","kind","assignment_id","provider","parent_conversation_id","role","scope","task","expected_artifact","acceptance"}
    if (type(value) is not dict or set(value)!=fields or type(value['schema_version']) is not int
            or value['schema_version']!=1 or value['kind']!='native-child-assignment'
            or value['provider']!='antigravity'):
        raise ValueError("native_assignment_invalid")
    for key in fields-{'schema_version','scope'}: _text(value[key])
    if type(value['scope']) is not list or not value['scope']:
        raise ValueError("native_assignment_scope_required")
    for part in value['scope']: _text(part)
    return value


def _rows(context, previous=None):
    if previous is None: return _events(context)[2]
    writer,validator,budget=_ledger(context)
    errors=[]
    rows=validator.load_jsonl(Path(context.work_item)/'agent-runs.jsonl',errors,
        source_bytes=previous.encode(),ledger_resource_budget=budget) if previous else []
    if errors: raise ValueError("native_binding_ledger_invalid")
    return rows


def _load(context, rows, assignment_id, kind):
    key=_key(assignment_id,kind)
    matches=[row for row in rows if row.get('runId')==key]
    if not matches: return None
    if len(matches)!=1: raise ValueError("native_binding_duplicate_record")
    row=matches[0]
    if any(row.get(k)!=v for k,v in {'role':'lead','executionRole':'main','eventKind':'standalone',
            'status':'completed','gate':'none',
            'workItem':Path(context.work_item).name,'scope':['native-child-association:'+assignment_id],
            'artifact':key+'.json'}.items()) or any(k in row for k in ('provider','sdkExecution','launchRunId','terminalClass','authorizing','closesRunIds')):
        raise ValueError("native_binding_record_changed")
    doc=_child_artifact_document(context,row)
    if kind=='assignment': _assignment(doc)
    elif (type(doc) is not dict or set(doc)!={'schema_version','kind','assignment_id','assignment_sha256','child_conversation_id','evidence_reference'}
            or type(doc['schema_version']) is not int or doc['schema_version']!=1 or doc['kind']!='native-child-binding'):
        raise ValueError("native_binding_document_invalid")
    if kind=='binding':
        if not _sha256(doc['assignment_sha256']): raise ValueError('native_binding_digest_invalid')
        _text(doc['child_conversation_id']); _text(doc['evidence_reference'])
    if doc['assignment_id']!=assignment_id: raise ValueError("native_binding_identity_changed")
    return row,doc


def readback(context, assignment_id):
    rows=_rows(context)
    found=_load(context,rows,assignment_id,'assignment')
    if found is None: raise ValueError("native_assignment_unavailable")
    row,assignment=found
    binding=_load(context,rows,assignment_id,'binding')
    if binding is not None and (binding[1]['assignment_sha256']!=row['artifactRevision']
            or binding[1]['child_conversation_id']==assignment['parent_conversation_id']):
        raise ValueError("native_binding_assignment_changed")
    return {'status':'prepared-unbound' if binding is None else 'root-bound',
        'assignment':assignment,'assignment_sha256':row['artifactRevision'],
        'binding':None if binding is None else binding[1],
        'authorizing':False,'native_execution_verified':False,'completion_verified':False}


def _publish(context, assignment_id, kind, document, *, started_at, expected_assignment_sha256=None):
    writer,validator,budget=_ledger(context)
    item=Path(context.work_item)
    content=(json_text(document)+'\n').encode()
    digest=hashlib.sha256(content).hexdigest()
    key=_key(assignment_id,kind);artifact=key+'.json'
    target=review_artifact_target(item,artifact)
    event=writer.build_event(writer.build_parser().parse_args([
        '--work-item',str(item),'append','--run-id',key,'--role','lead','--execution-role','main',
        '--status','completed','--gate','none','--event-kind','standalone',
        '--artifact',artifact,'--artifact-revision',digest,'--artifact-size-bytes',str(len(content)),
        '--scope=native-child-association:'+assignment_id,
        '--evidence','command:Root explicit native child association; no execution or completion claim',
        '--started-at',started_at,'--updated-at',started_at]),validator)
    def current(previous):
        rows=_rows(context,previous)
        assignment=_load(context,rows,assignment_id,'assignment')
        if kind=='binding':
            if assignment is None or assignment[0]['artifactRevision']!=expected_assignment_sha256:
                raise ValueError("native_binding_assignment_changed")
            if document['child_conversation_id']==assignment[1]['parent_conversation_id']:
                raise ValueError("native_binding_child_is_parent")
        existing=_load(context,rows,assignment_id,kind)
        if existing is not None:
            if existing[1]!=document: raise ValueError("native_binding_conflict")
            return None
        # A failed ledger publication may leave this exact nonauthorizing artifact.
        # An explicit identical retry can receive it; it never launches a child.
        if not target.exists():
            with _owner().TerminalReceiptV1.reserve(target) as receipt: receipt.commit(content)
        _child_artifact_document(context,event)
        return event
    def recheck():
        _child_artifact_document(context,event)
        if kind=='binding':
            prior=_load(context,_rows(context),assignment_id,'assignment')
            if prior is None or prior[0]['artifactRevision']!=expected_assignment_sha256:
                raise ValueError("native_binding_assignment_changed")
    writer._append_event_transaction(item,validator,current,before_replace=recheck,ledger_resource_budget=budget)
    return readback(context,assignment_id)


def prepare(context, assignment, *, started_at):
    assignment=_assignment(json.loads(json_text(assignment)))
    review_artifact_target(context.work_item,assignment['expected_artifact'])
    return _publish(context,assignment['assignment_id'],'assignment',assignment,started_at=started_at)


def bind(context, assignment_id, *, assignment_sha256, child_conversation_id, evidence_reference, started_at):
    document={'schema_version':1,'kind':'native-child-binding','assignment_id':_text(assignment_id),
        'assignment_sha256':_text(assignment_sha256),'child_conversation_id':_text(child_conversation_id),
        'evidence_reference':_text(evidence_reference)}
    return _publish(context,assignment_id,'binding',document,started_at=started_at,
        expected_assignment_sha256=assignment_sha256)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-item',required=True)
    parser.add_argument('--ledger-max-events',type=int)
    parser.add_argument('--ledger-max-bytes',type=int)
    sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('prepare');p.add_argument('--assignment-file',required=True);p.add_argument('--started-at',required=True)
    p=sub.add_parser('bind');p.add_argument('--assignment-id',required=True);p.add_argument('--assignment-sha256',required=True)
    p.add_argument('--child-conversation-id',required=True);p.add_argument('--evidence-reference',required=True);p.add_argument('--started-at',required=True)
    p=sub.add_parser('readback');p.add_argument('--assignment-id',required=True)
    args=parser.parse_args(argv);context=NativeBindingContext(args.work_item,args.ledger_max_events,args.ledger_max_bytes)
    if args.command=='prepare':
        raw=Path(args.assignment_file).read_bytes()
        result=prepare(context,strict_json(raw.decode(),max_bytes=len(raw)),started_at=args.started_at)
    elif args.command=='bind':
        result=bind(context,args.assignment_id,assignment_sha256=args.assignment_sha256,
            child_conversation_id=args.child_conversation_id,evidence_reference=args.evidence_reference,started_at=args.started_at)
    else: result=readback(context,args.assignment_id)
    print(json_text(result));return 0


if __name__=='__main__':
    raise SystemExit(main())
