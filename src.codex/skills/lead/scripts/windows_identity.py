"""Held Windows process and file witnesses for the qualified scope broker.

Not a standalone production authorization boundary. The caller still owns the
launch and protocol lifecycle; arbitrary peer-reported PIDs are never sufficient.
"""
import ctypes, hashlib, os
from pathlib import Path
from ctypes import wintypes as W
K=ctypes.WinDLL('kernel32',use_last_error=True);N=ctypes.WinDLL('ntdll');S=ctypes.WinDLL('shell32')
def signature(dll,name,args,result):
 f=getattr(dll,name);f.argtypes=args;f.restype=result;return f
open_process=signature(K,'OpenProcess',[W.DWORD,W.BOOL,W.DWORD],W.HANDLE)
close_handle=signature(K,'CloseHandle',[W.HANDLE],W.BOOL)
process_id=signature(K,'GetProcessId',[W.HANDLE],W.DWORD)
process_times=signature(K,'GetProcessTimes',[W.HANDLE,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p],W.BOOL)
wait_process=signature(K,'WaitForSingleObject',[W.HANDLE,W.DWORD],W.DWORD)
exit_code=signature(K,'GetExitCodeProcess',[W.HANDLE,ctypes.POINTER(W.DWORD)],W.BOOL)
image_name=signature(K,'QueryFullProcessImageNameW',[W.HANDLE,W.DWORD,W.LPWSTR,ctypes.POINTER(W.DWORD)],W.BOOL)
query=signature(N,'NtQueryInformationProcess',[W.HANDLE,W.ULONG,ctypes.c_void_p,W.ULONG,ctypes.POINTER(W.ULONG)],ctypes.c_long)
argv_parse=signature(S,'CommandLineToArgvW',[W.LPCWSTR,ctypes.POINTER(ctypes.c_int)],ctypes.POINTER(W.LPWSTR))
local_free=signature(K,'LocalFree',[ctypes.c_void_p],ctypes.c_void_p)
peer_pid=signature(K,'GetNamedPipeClientProcessId',[W.HANDLE,ctypes.POINTER(W.ULONG)],W.BOOL)
create_file=signature(K,'CreateFileW',[W.LPCWSTR,W.DWORD,W.DWORD,ctypes.c_void_p,W.DWORD,W.DWORD,W.HANDLE],W.HANDLE)
read_file=signature(K,'ReadFile',[W.HANDLE,ctypes.c_void_p,W.DWORD,ctypes.POINTER(W.DWORD),ctypes.c_void_p],W.BOOL)
class FileInfo(ctypes.Structure):
 _fields_=[('attributes',W.DWORD),('creation',W.FILETIME),('access',W.FILETIME),('write',W.FILETIME),('volume',W.DWORD),('sizeHigh',W.DWORD),('sizeLow',W.DWORD),('links',W.DWORD),('indexHigh',W.DWORD),('indexLow',W.DWORD)]
file_info=signature(K,'GetFileInformationByHandle',[W.HANDLE,ctypes.POINTER(FileInfo)],W.BOOL)
class Basic(ctypes.Structure):
 _fields_=[('Reserved1',ctypes.c_void_p),('Peb',ctypes.c_void_p),('Reserved2',ctypes.c_void_p*2),('Pid',ctypes.c_size_t),('Parent',ctypes.c_size_t)]
class Unicode(ctypes.Structure):
 _fields_=[('Length',W.USHORT),('MaximumLength',W.USHORT),('Buffer',ctypes.c_void_p)]
def checked(ok):
 if not ok:raise ctypes.WinError(ctypes.get_last_error())
def canonical(path):return os.path.normcase(os.path.abspath(path))
class PinnedFile:
 """Open before launch; deny concurrent write/delete until qualification ends."""
 def __init__(self,path):
  self.path=canonical(path);self.handle=None;self.directories=[]
  try:
   for parent in reversed(Path(self.path).parents):
    h=create_file(str(parent),0x80,1,None,3,0x02200000,None)
    if h in (None,ctypes.c_void_p(-1).value):raise ctypes.WinError(ctypes.get_last_error())
    self.directories.append(h);info=FileInfo();checked(file_info(h,ctypes.byref(info)))
    if info.attributes & 0x400:raise ValueError('reparse-parent')
  except BaseException:self.close();raise
  self.handle=create_file(self.path,0x80000000,1,None,3,0x00200080,None)
  if self.handle in (None,ctypes.c_void_p(-1).value):
   error=ctypes.get_last_error();self.handle=None;self.close();raise ctypes.WinError(error)
  try:
   info=FileInfo();checked(file_info(self.handle,ctypes.byref(info)))
   if info.attributes & (0x400|0x10):raise ValueError('reparse-or-directory-leaf')
   self.identity=(info.volume,info.indexHigh,info.indexLow)
   digest=hashlib.sha256();buf=ctypes.create_string_buffer(65536);count=W.DWORD();total=0
   while True:
    checked(read_file(self.handle,buf,len(buf),ctypes.byref(count),None))
    if not count.value:break
    total+=count.value
    if total>256*1024*1024:raise ValueError('pinned-file-size')
    digest.update(buf.raw[:count.value])
   self.sha256=digest.hexdigest()
  except BaseException:self.close();raise
 def pinned(self):
  if not self.handle or not self.directories:return False
  info=FileInfo()
  return bool(file_info(self.handle,ctypes.byref(info)) and (info.volume,info.indexHigh,info.indexLow)==self.identity)
 def close(self):
  if self.handle:close_handle(self.handle);self.handle=None
  for handle in reversed(self.directories):close_handle(handle)
  self.directories=[]
class ProcessWitness:
 def __init__(self,pid):
  self.handle=open_process(0x1000|0x100000,False,pid)
  if not self.handle:raise ctypes.WinError(ctypes.get_last_error())
  try:
   self.pid=process_id(self.handle)
   if self.pid!=pid:raise ValueError('pid-mismatch')
   self.creation=self._creation();self.parent,self.argv=self._information();buf=ctypes.create_unicode_buffer(32768);length=W.DWORD(len(buf));checked(image_name(self.handle,0,buf,ctypes.byref(length)));self.image=canonical(buf.value)
   if not self.live():raise ValueError('process-not-live')
  except BaseException:self.close();raise
 def _creation(self):
  created=ctypes.c_ulonglong();exited=ctypes.c_ulonglong();kernel=ctypes.c_ulonglong();user=ctypes.c_ulonglong();checked(process_times(self.handle,ctypes.byref(created),ctypes.byref(exited),ctypes.byref(kernel),ctypes.byref(user)));return created.value
 def _information(self):
  info=Basic();size=W.ULONG()
  if query(self.handle,0,ctypes.byref(info),ctypes.sizeof(info),ctypes.byref(size))<0:raise ValueError('process-basic-info')
  buf=ctypes.create_string_buffer(65536)
  if query(self.handle,60,buf,len(buf),ctypes.byref(size))<0:raise ValueError('process-command-line')
  value=Unicode.from_buffer(buf)
  start=ctypes.addressof(buf);end=start+size.value
  if (size.value>len(buf) or size.value<ctypes.sizeof(Unicode) or value.Length%2 or value.Length>value.MaximumLength or value.Buffer is None or value.Buffer<start+ctypes.sizeof(Unicode) or value.Buffer+value.Length>end):raise ValueError('invalid-process-command-buffer')
  text=ctypes.wstring_at(value.Buffer,value.Length//2);count=ctypes.c_int();argv=argv_parse(text,ctypes.byref(count));checked(bool(argv))
  try:return info.Parent,tuple(argv[i] for i in range(count.value))
  finally:local_free(argv)
 def live(self):
  return bool(self.handle and wait_process(self.handle,0)==258 and self._creation()==self.creation)
 def child_of(self,parent):return self.live() and parent.live() and self.parent==parent.pid and self.creation>=parent.creation
 def uses(self,file):return self.live() and file.pinned() and self.image==file.path
 def close(self):
  if self.handle:close_handle(self.handle);self.handle=None

def pipe_process(connection):
 pid=W.ULONG();checked(peer_pid(connection.fileno(),ctypes.byref(pid)));w=ProcessWitness(pid.value)
 try:
  again=W.ULONG();checked(peer_pid(connection.fileno(),ctypes.byref(again)))
  if again.value!=w.pid:raise ValueError('pipe-peer-changed')
  return w
 except BaseException:w.close();raise

class SameHelperLifecycle:
 """Holds process identities from capture to the eventual transfer boundary.

The producer must already be authenticated as the exact pinned relay script.
No object identity may be replaced by reopening a peer-supplied PID later.
 """
 def __init__(self, *, root, dispatcher, relay, upstream, git_file, relay_interpreter, upstream_file, upstream_args, launcher, shell_file):
  self.root=root;self.dispatcher=dispatcher;self.relay=relay;self.upstream=upstream;self.launcher=launcher;self.shell_file=shell_file
  self.git_file=git_file;self.relay_interpreter=relay_interpreter;self.upstream_file=upstream_file;self.upstream_args=tuple(upstream_args)
  self._captured=False;self._invalid=False;self._consumed=False
  if not self.current():raise ValueError('unqualified-helper-chain')
 def current(self):
  return (not self._invalid and self.root.uses(self.git_file)
          and self.dispatcher.uses(self.git_file) and self.dispatcher.child_of(self.root)
          and self.launcher.uses(self.shell_file) and self.launcher.child_of(self.dispatcher)
          and self.relay.uses(self.relay_interpreter) and self.relay.child_of(self.launcher)
          and self.upstream.uses(self.upstream_file) and self.upstream.child_of(self.relay)
          and self.upstream.argv[1:]==self.upstream_args)
 def capture_once(self):
  if self._captured or not self.current():self._invalid=True;return False
  self._captured=True;return True
 def consume(self):
  if not self._captured or self._consumed or not self.current():return False
  self._consumed=True;return True
