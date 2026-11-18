"""Windows default-owner attribution; no process, model, ACL or token mutation."""
import os
from pathlib import Path
import pytest
from _module_loading_support import load_module

ROOT=Path(__file__).resolve().parents[1]

@pytest.fixture
def runner():
    return load_module(ROOT/"scripts/process_supervision/process_runner.py","windows_owner_attribution")

@pytest.mark.skipif(os.name!="nt",reason="actual Windows owner metadata")
def test_current_process_created_directory_has_attributed_owner(runner,tmp_path):
    # Elevated Windows defaults to an owner-capable group, not TokenUser.
    identity=runner.bind_cwd_identity(str(tmp_path))
    assert len(identity.owner)==64
    assert identity==runner.bind_cwd_identity(str(tmp_path))

@pytest.mark.parametrize("owner,user,default,groups,allowed",[
    (b"user",b"user",None,None,True),
    (b"group",b"user",b"group",((b"group",8),),True),
    (b"group",b"user",b"group",((b"group",12),),True),
    (b"other",b"user",b"group",((b"group",8),),False),
    (b"group",b"user",b"other",((b"group",8),),False),
    (b"group",b"user",b"group",((b"group",0),),False),
    (b"group",b"user",b"group",((b"group",24),),False),
    (b"group",b"user",None,((b"group",8),),False),
    (b"group",b"user",b"group",None,False),
    (b"group",b"user",b"group",(),False),
    (b"group",b"user",b"group",((b"other",8),),False),
])
def test_exact_token_owner_not_arbitrary_group(runner,owner,user,default,groups,allowed):
    assert runner._windows_owner_attributed(owner,user,default,groups) is allowed

@pytest.mark.skipif(os.name!="nt",reason="Windows cwd/claim binding")
def test_actual_owner_digest_remains_part_of_cwd_and_claim(runner,tmp_path,monkeypatch):
    first=runner.bind_cwd_identity(str(tmp_path))
    declared=runner.claim_directory_identity_sha256(str(tmp_path))
    nonce=b"x"*32
    capability=runner.capability_binding_sha256(nonce,declared)
    # Simulate changed acquired metadata, never change actual filesystem owner.
    monkeypatch.setattr(runner,"_windows_owner_digest",lambda path:"0"*64 if first.owner!="0"*64 else "1"*64)
    assert runner.bind_cwd_identity(str(tmp_path))!=first
    observed=runner.claim_directory_identity_sha256(str(tmp_path))
    assert not runner.validate_claim_directory_binding(declared,observed,capability,nonce)

@pytest.mark.skipif(os.name!="nt",reason="Windows ctypes ABI")
@pytest.mark.parametrize("case,allowed",[
    ("group",True),("user",True),("deny-only",False),("not-owner",False),
    ("unrelated-default",False),("missing-owner",False),("missing-groups",False),
    ("failed-groups",False),("truncated-groups",False),("inflated-count",False),
    ("null-group-sid",False),
])
def test_native_token_buffer_parsing_and_fail_closed(runner,tmp_path,monkeypatch,case,allowed):
    import ctypes
    from ctypes import wintypes as w
    import types
    class Function:
        def __init__(self,fn): self.fn=fn
        def __call__(self,*a): return self.fn(*a)
    class Row(ctypes.Structure):
        _fields_=[("sid",ctypes.c_void_p),("attributes",w.DWORD)]
    class Groups(ctypes.Structure):
        _fields_=[("count",w.DWORD),("groups",Row*1)]
    held=[ctypes.create_string_buffer(value) for value in (b"user",b"group",b"other")]
    user,group,other=[ctypes.addressof(v) for v in held]
    sizes={user:4,group:5,other:5}
    calls=[];closed=[]
    setptr=lambda p,v:setattr(ctypes.cast(p,ctypes.POINTER(ctypes.c_void_p)).contents,"value",v)
    setsize=lambda p,v:setattr(ctypes.cast(p,ctypes.POINTER(w.DWORD)).contents,"value",v)
    def named(path,kind,info,owner,*rest):
        setptr(owner,user if case=="user" else group)
        setptr(rest[-1],99)
        return 0
    def token_info(token,kind,buffer,capacity,needed):
        calls.append(kind)
        missing=(case=="missing-owner" and kind==4) or (case=="missing-groups" and kind==2)
        length=0 if missing else ctypes.sizeof(Groups) if kind==2 else ctypes.sizeof(ctypes.c_void_p)
        setsize(needed,length)
        if not buffer or not length:return False
        if case=="failed-groups" and kind==2:return False
        if kind==2:
            value=Groups.from_buffer(buffer)
            value.count=100 if case=="inflated-count" else 1
            value.groups[0].sid=None if case=="null-group-sid" else group
            value.groups[0].attributes=24 if case=="deny-only" else 0 if case=="not-owner" else 8
            if case=="truncated-groups":setsize(needed,Groups.groups.offset)
        else:
            setptr(buffer,user if kind==1 else other if case=="unrelated-default" else group)
        return True
    def pointer(v):return v.value if hasattr(v,"value") else v
    adv=types.SimpleNamespace(
        GetNamedSecurityInfoW=Function(named),
        OpenProcessToken=Function(lambda process,access,out:(setptr(out,7),True)[1]),
        GetTokenInformation=Function(token_info),
        IsValidSid=Function(lambda p:pointer(p) in sizes),
        GetLengthSid=Function(lambda p:sizes.get(pointer(p),0)))
    kernel=types.SimpleNamespace(GetCurrentProcess=Function(lambda:1),
        CloseHandle=Function(lambda p:closed.append("token")),
        LocalFree=Function(lambda p:closed.append("descriptor")))
    monkeypatch.setattr(runner.ctypes,"WinDLL",lambda name,**kw:adv if name=="advapi32" else kernel)
    if allowed:
        digest=runner._windows_owner_digest(tmp_path)
        import hashlib
        assert digest==hashlib.sha256(b"user" if case=="user" else b"group").hexdigest()
    else:
        with pytest.raises(runner.ProcessSupervisionError,match="PSV1-REQUEST-INVALID"):
            runner._windows_owner_digest(tmp_path)
    if case=="user":assert set(calls)=={1}
    assert closed==["token","descriptor"]
