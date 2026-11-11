"""One-use owner-bound transfer binding. No standalone scan authority."""
from dataclasses import dataclass
import hashlib
import json
import re


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode('ascii')


@dataclass(frozen=True)
class ScopeBinding:
    invocation: str
    endpoint_identity: str
    object_format: str
    advertisement_sha256: str
    excluded_roots: tuple[str,...]
    route_contract: str

    def __post_init__(self):
        if (any(type(value) is not str for value in (self.invocation,self.endpoint_identity,self.object_format,self.advertisement_sha256,self.route_contract))
            or type(self.excluded_roots) is not tuple or any(type(oid) is not str for oid in self.excluded_roots)):
            raise ValueError('scope field types')
        width={'sha1':40,'sha256':64}.get(self.object_format)
        if (width is None or not self.invocation or not self.route_contract
            or not re.fullmatch(r'sha256:[0-9a-f]{64}',self.endpoint_identity)
            or not re.fullmatch(r'[0-9a-f]{64}',self.advertisement_sha256)
            or tuple(sorted(set(self.excluded_roots)))!=self.excluded_roots
            or any(not re.fullmatch('[0-9a-f]{'+str(width)+'}',oid) or set(oid)=={'0'} for oid in self.excluded_roots)):
            raise ValueError('scope binding')

    @classmethod
    def from_document(cls, value):
        keys={'kind','version','invocation','endpointIdentity','objectFormat','advertisementSha256','excludedRoots','routeContract'}
        if (type(value) is not dict or set(value)!=keys or value['kind']!='receiver-snapshot-scope'
            or type(value['version']) is not int or value['version']!=1 or type(value['excludedRoots']) is not list):
            raise ValueError('scope document')
        return cls(value['invocation'],value['endpointIdentity'],value['objectFormat'],value['advertisementSha256'],tuple(value['excludedRoots']),value['routeContract'])

    def document(self):
        return {'kind':'receiver-snapshot-scope','version':1,'invocation':self.invocation,
                'endpointIdentity':self.endpoint_identity,'objectFormat':self.object_format,
                'advertisementSha256':self.advertisement_sha256,
                'excludedRoots':list(self.excluded_roots),'routeContract':self.route_contract}

    def digest(self):
        return hashlib.sha256(b'orche-receiver-scope-v1\0'+canonical(self.document())).hexdigest()

    def selection_digest(self,native_request):
        return hashlib.sha256(b'orche-native-selection-v5\0'+canonical({'nativeRequest':native_request,'scope':self.document()})).hexdigest()


class TransferBinding:
    """Owner-side single transition; caller must authenticate every channel.

    Restricted to explicit immutable OID sources. A symbolic source could change
    between the native hook and helper's later object resolution.
    """
    def __init__(self,scope,*,channel):
        self.scope=scope;self.channel=channel;self.pending=None;self.used=False

    def bind_hook(self,wire,*,channel,scope_digest):
        if self.pending is not None or self.used or channel is not self.channel or scope_digest!=self.scope.digest():
            self.used=True;raise ValueError('hook binding')
        width=40 if self.scope.object_format=='sha1' else 64
        expected=[];destinations=set()
        for row in wire.splitlines(keepends=True):
            fields=row.removesuffix(b'\n').split(b' ')
            if (not row.endswith(b'\n') or len(fields)!=4
                or fields[0]!=fields[1]
                or not re.fullmatch(rb'[0-9a-f]{'+str(width).encode()+rb'}',fields[1])
                or set(fields[1])=={48}
                or not re.fullmatch(rb'refs/[!-~]+',fields[2])
                or not re.fullmatch(rb'[0-9a-f]{'+str(width).encode()+rb'}',fields[3])):
                self.used=True;raise ValueError('unsupported hook wire')
            ref=fields[2]
            if (ref in destinations or ref.endswith((b'.',b'/')) or b'..' in ref or b'@{' in ref
                or any(ch in ref for ch in b'~^:?*[\\')
                or any(not part or part.startswith(b'.') or part.endswith(b'.lock') for part in ref.split(b'/'))):
                self.used=True;raise ValueError('invalid or duplicate destination')
            destinations.add(ref)
            expected.append(b'push '+fields[1]+b':'+ref+b'\n')
        if not expected or len(set(expected))!=len(expected):
            self.used=True;raise ValueError('empty or duplicate transfer')
        self.pending=tuple(expected)

    def consume_transfer(self,commands,*,channel,scope_digest,same_helper_live):
        if self.used:raise ValueError('replayed transfer')
        self.used=True
        if (self.pending is None or channel is not self.channel or not same_helper_live
            or scope_digest!=self.scope.digest() or tuple(commands)!=self.pending):
            raise ValueError('transfer binding mismatch')
        return self.scope.digest()
