"""Read-only conservative preflight. Never constitutes receiver authority.

Caller must hold pins for result.origins and preserve exact argv/env/context from
inspection through transfer. No credentials or config values appear in results.
"""
from dataclasses import dataclass
from pathlib import Path
import os,re,subprocess
from urllib.parse import urlsplit

@dataclass(frozen=True)
class Qualification:
    eligible: bool
    reason: str
    origins: tuple[str,...] = ()
    executables: tuple[str,...] = ()


def qualify(git, repository, remote, *, env, config_args=(), timeout=10, approved_gh=None, approved_gcm=None):
    """Inspect exactly the proposed Git environment and repeated '-c key=value'.

    Recognized GCM/GH helpers require caller-approved executable paths, returned
    for mandatory owner pinning. No helper is run or disabled; unknowns fallback.
    """
    def deny(reason): return Qualification(False,reason)
    if not isinstance(remote,str) or not re.fullmatch(r'[A-Za-z0-9_-]+',remote):return deny('remote-name')
    if len(config_args)%2 or any(config_args[i]!='-c' for i in range(0,len(config_args),2)):return deny('config-arguments')
    allowed_env={'GIT_CONFIG_NOSYSTEM','GIT_CONFIG_GLOBAL','GIT_CONFIG_SYSTEM','GIT_TERMINAL_PROMPT'}
    for key,value in env.items():
        name=key.upper()
        if value and (name.startswith('GIT_') and name not in allowed_env or name in {'HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','GIT_PROXY_COMMAND','CURL_CA_BUNDLE','SSL_CERT_FILE','SSL_CERT_DIR'}):return deny('environment-override')
    prefix=[str(git),'-C',str(repository),*config_args]
    def call(*args):
        result=subprocess.run([*prefix,*args],env=dict(env),stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout,check=False)
        if result.returncode:raise ValueError('git-inspection')
        if len(result.stdout)>4*1024*1024:raise ValueError('config-size')
        return result.stdout
    try:
        raw=call('config','--includes','--show-origin','--show-scope','--null','--list')
        parts=raw.split(b'\0')
        if parts[-1]!=b'' or (len(parts)-1)%3: return deny('config-framing')
        origins=set()
        for i in range(0,len(parts)-1,3):
            scope,origin,entry=parts[i:i+3]
            name,sep,value=entry.partition(b'\n')
            key=name.decode('utf-8','strict').lower()
            if not sep:return deny('valueless-config')
            if origin.startswith(b'file:'):
                path=Path(os.fsdecode(origin[5:]))
                if not path.is_absolute():path=Path(repository)/path
                origins.add(str(path.absolute()))
            elif scope!=b'command' or origin!=b'command line:':return deny('config-origin')
            if key.startswith(('include.','includeif.','url.')) or key=='extensions.worktreeconfig':return deny('config-indirection')
            if scope==b'worktree':return deny('worktree-config')
            if key in ('core.askpass','core.sshcommand','core.gitproxy'):return deny('credential-or-custom-executor')
            # Only this single HTTP knob is supported initially. URL-specific
            # variants are rejected, including sensitive extraHeader values.
            if key.startswith('http.') and key not in {'http.followredirects','http.sslbackend'}:return deny('unsupported-http-config')
            if key=='http.sslbackend' and value.lower()!=b'schannel':return deny('unsupported-tls-backend')
            if key.startswith('remote.'):
                bits=key.split('.')
                if len(bits)!=3 or bits[1]!=remote.lower() or bits[2] not in {'url','fetch'}:return deny('unsupported-remote-config')
        urls=call('remote','get-url','--push','--all',remote).decode('utf-8','strict').splitlines()
        if len(urls)!=1:return deny('multiple-push-urls')
        url=urls[0]
        # No userinfo, port, query, fragment, percent encoding or subdomain.
        if not re.fullmatch(r'https://github\.com/[A-Za-z0-9_-]+/[A-Za-z0-9_.-]+',url):return deny('endpoint-shape')
        parsed=urlsplit(url)
        if parsed.path.split('/')[-1] in {'.','..'}:return deny('endpoint-shape')
        effective=call('config','--type=bool','--get-urlmatch','http.followRedirects',url).strip()
        if effective!=b'false':return deny('redirects-not-disabled')
        # URL matching is performed by Git, preserving helper ordering/reset.
        matched=subprocess.run([*prefix,'config','--get-urlmatch','credential',url],env=dict(env),stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout)
        if matched.returncode not in (0,1):return deny('credential-inspection')
        helpers=[]; executables=set()
        for row in matched.stdout.decode('utf-8','strict').splitlines():
            key,sep,value=row.partition(' ')
            if key=='credential.helper':helpers.append(value)
            elif key not in {'credential.username','credential.usehttppath','credential.interactive','credential.protectprotocol','credential.sanitizeprompt'}:return deny('unsupported-credential-config')
        for value in helpers:
            if value=='':continue
            if value in {'manager','manager-core'}:
                if not approved_gcm or not Path(approved_gcm).is_file():return deny('gcm-pin-required')
                executables.add(str(Path(approved_gcm).absolute()));continue
            # Recognized gh shell helper; no arbitrary shell suffix/expansion.
            match=re.fullmatch(r'''!\s*(?:"([^"$`\n]+)"|'([^'\n]+)'|([^ \t'"$`;|&<>]+)) auth git-credential''',value)
            if not match or not approved_gh:return deny('unknown-credential-executor')
            target=next(x for x in match.groups() if x is not None)
            if not Path(approved_gh).is_file() or os.path.normcase(os.path.abspath(target))!=os.path.normcase(os.path.abspath(approved_gh)):return deny('gh-pin-required')
            executables.add(str(Path(approved_gh).absolute()))
        # Config files that could appear after inspection are NOT frozen by this
        # function. Caller must pin namespace/context or remain on full graph.
        return Qualification(True,'eligible-pending-owner-pins',tuple(sorted(origins)),tuple(sorted(executables)))
    except (OSError,ValueError,UnicodeError,subprocess.TimeoutExpired):return deny('inspection-failed')
