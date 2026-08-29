#!/usr/bin/env python3
"""Compare complete candidate capability inventory with the immutable baseline."""
from __future__ import annotations
import argparse, hashlib, json, os, re, sys, tempfile
from pathlib import Path
from typing import Mapping, Sequence
SCHEMA_VERSION=1; INVENTORY_SCHEMA_VERSION=2
OBJECT_ID=re.compile(r"[0-9a-fA-F]{40}(?:[0-9a-fA-F]{24})?"); SHA256=re.compile(r"[0-9a-f]{64}"); ALLOWED_CHANGES={"added","modified","removed"}; ALLOWED_MODES={"100644","100755","120000","160000"}
class CapabilityComparisonError(RuntimeError): pass
def _canonical_json(v): return json.dumps(v,ensure_ascii=False,indent=2,sort_keys=True)+"\n"
def _exact_ref(v,*,label):
    if not OBJECT_ID.fullmatch(v): raise CapabilityComparisonError(f"{label} ref must be an exact 40- or 64-character object ID")
    return v.lower()
def _load_inventory(path,*,expected_ref,label):
    try: payload=json.loads(path.read_text(encoding="utf-8"))
    except (OSError,json.JSONDecodeError) as exc: raise CapabilityComparisonError(f"cannot read {label} inventory {path}: {exc}") from exc
    if not isinstance(payload,dict): raise CapabilityComparisonError(f"{label} inventory top level must be an object")
    if payload.get("schemaVersion")!=INVENTORY_SCHEMA_VERSION: raise CapabilityComparisonError(f"unsupported {label} inventory schemaVersion: {payload.get('schemaVersion')!r}")
    declared=payload.get("inventorySha256"); semantic=dict(payload); semantic.pop("inventorySha256",None); computed=hashlib.sha256(_canonical_json(semantic).encode()).hexdigest()
    if not isinstance(declared,str) or not SHA256.fullmatch(declared) or computed!=declared: raise CapabilityComparisonError(f"{label} inventory inventorySha256 mismatch")
    baseline=payload.get("baseline"); entries=payload.get("entries")
    if not isinstance(baseline,dict) or not isinstance(entries,list): raise CapabilityComparisonError(f"{label} inventory lacks baseline or entries")
    if baseline.get("commitSha")!=expected_ref: raise CapabilityComparisonError(f"{label} inventory commit mismatch: expected={expected_ref}, actual={baseline.get('commitSha')!r}")
    result={}
    for raw in entries:
        if not isinstance(raw,dict): raise CapabilityComparisonError(f"{label} inventory contains non-object entry")
        path_value=raw.get("path"); digest=raw.get("contentSha256"); mode=raw.get("mode"); object_type=raw.get("objectType")
        if not isinstance(path_value,str) or not path_value or path_value.startswith('/'): raise CapabilityComparisonError(f"invalid {label} inventory path: {path_value!r}")
        if not isinstance(digest,str) or not SHA256.fullmatch(digest): raise CapabilityComparisonError(f"invalid {label} digest for {path_value!r}")
        if mode not in ALLOWED_MODES: raise CapabilityComparisonError(f"invalid {label} Git mode for {path_value!r}: {mode!r}")
        expected_type='commit' if mode=='160000' else 'blob'
        if object_type!=expected_type: raise CapabilityComparisonError(f"invalid {label} objectType for {path_value!r}: mode={mode!r}, objectType={object_type!r}")
        if path_value in result: raise CapabilityComparisonError(f"duplicate {label} inventory path: {path_value}")
        result[path_value]=(digest,mode,object_type)
    return result
def _load_dispositions(path,*,baseline_ref):
    try: payload=json.loads(path.read_text(encoding="utf-8"))
    except (OSError,json.JSONDecodeError) as exc: raise CapabilityComparisonError(f"cannot read dispositions {path}: {exc}") from exc
    if not isinstance(payload,dict) or payload.get("schemaVersion")!=SCHEMA_VERSION: raise CapabilityComparisonError("dispositions top level/schemaVersion is invalid")
    if payload.get("baselineRef")!=baseline_ref: raise CapabilityComparisonError("dispositions baselineRef mismatch")
    if payload.get("scope")!="ORCHE-IMPL-000": raise CapabilityComparisonError("dispositions scope must be ORCHE-IMPL-000")
    entries=payload.get("entries")
    if not isinstance(entries,list): raise CapabilityComparisonError("dispositions entries must be an array")
    result={}
    for raw in entries:
        if not isinstance(raw,dict): raise CapabilityComparisonError("dispositions contain a non-object entry")
        p=raw.get("path"); ch=raw.get("change"); reason=raw.get("reason"); contracts=raw.get("contractIds")
        if not isinstance(p,str) or not p or p.startswith('/'): raise CapabilityComparisonError(f"invalid disposition path: {p!r}")
        if ch not in ALLOWED_CHANGES: raise CapabilityComparisonError(f"invalid disposition change for {p!r}: {ch!r}")
        if not isinstance(reason,str) or not reason.strip(): raise CapabilityComparisonError(f"disposition reason is required for {p!r}")
        if not isinstance(contracts,list) or not contracts or not all(isinstance(x,str) and x for x in contracts): raise CapabilityComparisonError(f"one or more contractIds are required for {p!r}")
        if p in result: raise CapabilityComparisonError(f"duplicate disposition path: {p}")
        result[p]=ch
    return result
def compare(baseline,candidate,dispositions,*,baseline_ref,candidate_ref):
    added=sorted(set(candidate)-set(baseline)); removed=sorted(set(baseline)-set(candidate)); modified=sorted(p for p in set(baseline)&set(candidate) if baseline[p]!=candidate[p])
    actual={**{p:'added' for p in added},**{p:'modified' for p in modified},**{p:'removed' for p in removed}}
    blockers={"missingDispositions":sorted(set(actual)-set(dispositions)),"staleDispositions":sorted(set(dispositions)-set(actual)),"mismatchedDispositions":sorted(p for p in set(actual)&set(dispositions) if actual[p]!=dispositions[p])}
    verdict='PASS' if all(not v for v in blockers.values()) else 'BLOCKED'
    return {"schemaVersion":1,"baselineRef":baseline_ref,"candidateRef":candidate_ref,"changes":{"added":added,"modified":modified,"removed":removed},"reviewedDispositions":[{"path":p,"change":dispositions[p]} for p in sorted(dispositions)],"blockers":blockers,"verdict":verdict}
def _atomic_write(path,content):
    path.parent.mkdir(parents=True,exist_ok=True); fd,tmp=tempfile.mkstemp(prefix=f'.{path.name}.',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as h: h.write(content); h.flush(); os.fsync(h.fileno())
        os.replace(tmp,path)
    finally:
        if Path(tmp).exists(): Path(tmp).unlink()
def parse_args(argv):
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--baseline-inventory',type=Path,required=True); p.add_argument('--candidate-inventory',type=Path,required=True); p.add_argument('--baseline-ref',required=True); p.add_argument('--candidate-ref',required=True); p.add_argument('--dispositions',type=Path,required=True); p.add_argument('--output',type=Path,required=True); return p.parse_args(argv)
def main(argv=None):
    a=parse_args(sys.argv[1:] if argv is None else argv)
    try:
        br=_exact_ref(a.baseline_ref,label='baseline'); cr=_exact_ref(a.candidate_ref,label='candidate')
        if br==cr: raise CapabilityComparisonError('candidate ref must differ from baseline ref')
        r=compare(_load_inventory(a.baseline_inventory,expected_ref=br,label='baseline'),_load_inventory(a.candidate_inventory,expected_ref=cr,label='candidate'),_load_dispositions(a.dispositions,baseline_ref=br),baseline_ref=br,candidate_ref=cr); _atomic_write(a.output,_canonical_json(r).encode()); print(f"RESULT: {r['verdict']} capability-baseline added={len(r['changes']['added'])} modified={len(r['changes']['modified'])} removed={len(r['changes']['removed'])}"); return 0 if r['verdict']=='PASS' else 1
    except (CapabilityComparisonError,OSError,ValueError) as e: print(f"RESULT: FAIL capability-baseline: {e}",file=sys.stderr); return 2
if __name__=='__main__': raise SystemExit(main())
