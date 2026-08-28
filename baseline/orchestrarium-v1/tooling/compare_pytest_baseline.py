#!/usr/bin/env python3
"""Compare Pytest/JUnit and retained test-source evidence against Stage 0."""
from __future__ import annotations
import argparse, hashlib, json, os, re, sys, tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

OBJ=re.compile(r"(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})\Z"); SHA=re.compile(r"[0-9a-f]{64}\Z")
HEX=set("0123456789abcdefABCDEF"); PATHCH=set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")
class Error(RuntimeError): pass

def canon(v): return json.dumps(v,ensure_ascii=False,indent=2,sort_keys=True)+"\n"
def ref(v,n):
    if not OBJ.fullmatch(v): raise Error(f"{n} ref must be an exact 40- or 64-character hexadecimal object ID")
    return v.lower()
def root(v,n):
    v=v.rstrip("/\\")
    if not v: raise Error(f"{n} root must be non-empty")
    return v
def bounded(s,old,new,chars):
    out=[]; i=0
    while True:
        p=s.find(old,i)
        if p<0: out.append(s[i:]); return "".join(out)
        e=p+len(old); a=s[p-1] if p else ""; b=s[e] if e<len(s) else ""
        if (not a or a not in chars) and (not b or b not in chars): out += [s[i:p],new]; i=e
        else: out.append(s[i:e]); i=e
def patterns(values):
    out=[]
    for v in values:
        try: p=re.compile(v)
        except re.error as e: raise Error(f"invalid volatile pattern {v!r}: {e}") from e
        if p.search("") is not None: raise Error(f"volatile pattern must not match empty text: {v!r}")
        out.append(p)
    return out
def norm(v,work,lane,oid,pats):
    if v is None: return None
    s=v.replace("\r\n","\n").replace("\r","\n")
    for rpl,tag in ((lane,"<LANE_ROOT>"),(work,"<WORKTREE_ROOT>")):
        for q in sorted({rpl,rpl.replace('\\','/'),rpl.replace('/','\\')},key=len,reverse=True): s=bounded(s,q,tag,PATHCH)
    s=bounded(s,oid,"<REF>",HEX)
    for p in pats: s=p.sub("<VOLATILE>",s)
    lines=[x.rstrip(" \t") for x in s.split("\n")]
    while lines and not lines[-1]: lines.pop()
    return "\n".join(lines) or None

def junit(path):
    try: tree=ET.parse(path).getroot()
    except (OSError,ET.ParseError) as e: raise Error(f"cannot parse JUnit file {path}: {e}") from e
    out={}
    for x in tree.iter("testcase"):
        c=x.get("classname","").strip(); n=x.get("name","").strip(); f=(x.get("file") or "").replace('\\','/')
        tid=f"{c}::{n}" if c and n else f"{f}::{n}" if f and n else n or f
        if not tid or tid in out: raise Error(f"invalid or duplicate JUnit testcase ID: {tid!r}")
        st="passed"; typ=msg=body=None
        for k in ("failure","error","skipped"):
            y=x.find(k)
            if y is not None: st=k; typ=y.get("type"); msg=y.get("message"); body=y.text; break
        out[tid]={"status":st,"type":typ,"message":msg,"body":body,"file":f or None,"class":c,"name":n}
    if not out: raise Error(f"JUnit file contains no testcases: {path}")
    return out

def inventory(path,expected,label):
    try: p=json.loads(path.read_text(encoding="utf-8"))
    except (OSError,json.JSONDecodeError) as e: raise Error(f"cannot read {label} test inventory {path}: {e}") from e
    if not isinstance(p,dict) or p.get("schemaVersion")!=2: raise Error(f"invalid {label} test inventory schema")
    d=p.get("inventorySha256"); q=dict(p); q.pop("inventorySha256",None)
    if not isinstance(d,str) or not SHA.fullmatch(d) or hashlib.sha256(canon(q).encode()).hexdigest()!=d: raise Error(f"{label} test inventory inventorySha256 mismatch")
    b=p.get("baseline"); es=p.get("entries")
    if not isinstance(b,dict) or b.get("commitSha")!=expected: raise Error(f"{label} test inventory commit mismatch: expected={expected}, actual={None if not isinstance(b,dict) else b.get('commitSha')!r}")
    if not isinstance(es,list): raise Error(f"invalid {label} test inventory entries")
    out={}
    for e in es:
        if not isinstance(e,dict): raise Error(f"invalid {label} test inventory entry")
        name=e.get("path"); dig=e.get("contentSha256"); kind=e.get("kind")
        if not isinstance(name,str) or not name.startswith("tests/") or kind not in {"test-file","test-support"} or not isinstance(dig,str) or not SHA.fullmatch(dig) or name in out: raise Error(f"invalid {label} test inventory entry: {name!r}")
        out[name]=dig
    return out

def diag(x,work,lane,oid,pats): return tuple(norm(x[k],work,lane,oid,pats) for k in ("type","message","body"))
def contradiction(code,n):
    if code not in {0,1}: return [{"exitCode":code,"junitFailureCount":n,"reason":"operational-pytest-exit"}]
    return [{"exitCode":code,"junitFailureCount":n}] if (code==0)!=(n==0) else []
def atomic(path,data):
    path.parent.mkdir(parents=True,exist_ok=True); fd,tmp=tempfile.mkstemp(prefix=f".{path.name}.",dir=path.parent)
    try:
        with os.fdopen(fd,"wb") as h: h.write(data); h.flush(); os.fsync(h.fileno())
        os.replace(tmp,path)
    finally:
        try: os.unlink(tmp)
        except FileNotFoundError: pass

def compare(a):
    br=ref(a.baseline_ref,"baseline"); cr=ref(a.candidate_ref,"candidate")
    roots=[root(a.baseline_root,"baseline worktree"),root(a.candidate_root,"candidate worktree"),root(a.baseline_lane_root,"baseline lane"),root(a.candidate_lane_root,"candidate lane")]
    if len({x.replace('\\','/') for x in roots})!=4: raise Error("worktree and isolated lane roots must all be distinct")
    pats=patterns(a.volatile_pattern); b=junit(a.baseline_junit); c=junit(a.candidate_junit)
    bi=inventory(a.baseline_test_inventory,br,"baseline"); ci=inventory(a.candidate_test_inventory,cr,"candidate")
    bids=set(b); cids=set(c); bf={i for i in b if b[i]["status"] in {"failure","error"}}; cf={i for i in c if c[i]["status"] in {"failure","error"}}
    bs={i for i in b if b[i]["status"]=="skipped"}; cs={i for i in c if c[i]["status"]=="skipped"}
    bd={i:diag(b[i],roots[0],roots[2],br,pats) for i in bf}; cd={i:diag(c[i],roots[1],roots[3],cr,pats) for i in cf}
    sd1={i:diag(b[i],roots[0],roots[2],br,pats) for i in bs&cs}; sd2={i:diag(c[i],roots[1],roots[3],cr,pats) for i in bs&cs}
    missbd=sorted(i for i,v in bd.items() if not any(x is not None for x in v)); misscd=sorted(i for i,v in cd.items() if not any(x is not None for x in v))
    missbs=sorted(i for i,v in sd1.items() if not any(x is not None for x in v)); misscs=sorted(i for i,v in sd2.items() if not any(x is not None for x in v))
    blockers={
      "newFailures":sorted(cf-bf),"missingBaselineTests":sorted(bids-cids),
      "maskedBaselineFailures":sorted(i for i in bf if i in c and c[i]["status"]=="skipped"),
      "passingTestRegressions":sorted(i for i in bids&cids if b[i]["status"]=="passed" and c[i]["status"]!="passed"),
      "changedKnownFailureKind":sorted(i for i in bf&cf if b[i]["status"]!=c[i]["status"]),
      "missingBaselineFailureDiagnostics":missbd,"missingCandidateFailureDiagnostics":misscd,
      "changedKnownFailureDiagnostics":sorted(i for i in bf&cf if b[i]["status"]==c[i]["status"] and i not in set(missbd+misscd) and bd[i]!=cd[i]),
      "missingBaselineSkipDiagnostics":missbs,"missingCandidateSkipDiagnostics":misscs,
      "changedRetainedSkipDiagnostics":sorted(i for i in bs&cs if i not in set(missbs+misscs) and sd1[i]!=sd2[i]),
      "baselineSkipsNoLongerSkipped":sorted(i for i in bs if i in c and c[i]["status"]!="skipped"),
      "missingBaselineTestFiles":sorted(set(bi)-set(ci)),
      "changedBaselineTestFiles":sorted(i for i in set(bi)&set(ci) if bi[i]!=ci[i]),
      "baselineExitContradiction":contradiction(a.baseline_exit,len(bf)),
      "candidateExitContradiction":contradiction(a.candidate_exit,len(cf)),
    }
    resolved=a.baseline_exit==1 and a.candidate_exit==0 and not cf and not blockers["baselineExitContradiction"]
    blockers["pytestExitCodeRegression"]=[] if a.candidate_exit==a.baseline_exit or resolved else [{"baselineExitCode":a.baseline_exit,"candidateExitCode":a.candidate_exit}]
    verdict="PASS" if all(not v for v in blockers.values()) else "BLOCKED"
    return {"schemaVersion":3,"baseline":{"exitCode":a.baseline_exit,"ref":br,"failures":len(bf),"total":len(b)},"candidate":{"exitCode":a.candidate_exit,"ref":cr,"failures":len(cf),"total":len(c)},"blockers":blockers,"observations":{"additionalCandidateTests":sorted(cids-bids),"additionalCandidateTestFiles":sorted(set(ci)-set(bi)),"resolvedBaselineFailures":sorted(i for i in bf if i in c and c[i]["status"]=="passed")},"verdict":verdict}

def args(v):
    p=argparse.ArgumentParser(description=__doc__)
    for n in ("baseline-junit","candidate-junit","baseline-test-inventory","candidate-test-inventory","output"): p.add_argument("--"+n,type=Path,required=True)
    for n in ("baseline-exit","candidate-exit"): p.add_argument("--"+n,type=int,required=True)
    for n in ("baseline-ref","candidate-ref","baseline-root","candidate-root","baseline-lane-root","candidate-lane-root"): p.add_argument("--"+n,required=True)
    p.add_argument("--volatile-pattern",action="append",default=[]); return p.parse_args(v)
def main(v=None):
    a=args(sys.argv[1:] if v is None else v)
    try: r=compare(a); atomic(a.output,canon(r).encode()); print(f"RESULT: {r['verdict']} pytest-baseline baseline_failures={r['baseline']['failures']} candidate_failures={r['candidate']['failures']}"); return 0 if r["verdict"]=="PASS" else 1
    except (Error,OSError,ValueError) as e: print(f"RESULT: FAIL pytest-baseline: {e}",file=sys.stderr); return 2
if __name__=="__main__": raise SystemExit(main())
