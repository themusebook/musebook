#!/usr/bin/env python3
"""GET/HEAD-only live release, archive, route and authentication verification.

Use --origin repeatedly for canonical, immutable Vercel, Vercel alias,
terminal Pages, and immutable Pages URLs. --stage-only omits canonical API and
dedicated skill-host contracts when reviewing a candidate before promotion.
Optional Vercel bypass is read only from MUSEBOOK_VERIFY_VERCEL_BYPASS in the
environment and sent exclusively to validated *.vercel.app origins.

This script never POSTs, signs, submits OAuth callbacks, or invokes any action.
It verifies unauthenticated GET boundaries. Existing local edge-boundary tests
and an explicitly authorized negative POST smoke test cover unsigned writes.
"""
import argparse
import concurrent.futures
import hashlib
import json
import os
import re
import socket
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from reviewed_html_transforms import normalize_reviewed_html

DEFAULT_CANONICAL_SKILL_APPENDIX = Path('/tmp/musebook-routing-audit-2026-10-10/canonical-skill-runtime-appendix.bin')
REVIEWED_CANONICAL_SKILL_APPENDIX_BYTES = 1864
REVIEWED_CANONICAL_SKILL_APPENDIX_SHA256 = 'a9fef5edb5905e198f7ab0f12aba156648f4c149fdeadcd7b2b41dff5d3fcb80'

def reviewed_canonical_skill_appendix(path):
    data=Path(path).read_bytes()
    if len(data)!=REVIEWED_CANONICAL_SKILL_APPENDIX_BYTES or hashlib.sha256(data).hexdigest()!=REVIEWED_CANONICAL_SKILL_APPENDIX_SHA256:
        raise ValueError('Canonical skill appendix differs from the exact reviewed runtime sections')
    return data

class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, newurl):
        redirected=super().redirect_request(request,response,code,message,headers,newurl)
        if redirected and urllib.parse.urlsplit(request.full_url).netloc!=urllib.parse.urlsplit(newurl).netloc:
            redirected.remove_header('X-vercel-protection-bypass')
        return redirected

def origin(value):
    parsed=urllib.parse.urlsplit(value)
    if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError('Expected public HTTPS origin without credentials or query')
    return f'https://{parsed.netloc}'

def file_fingerprint(path):
    data=path.read_bytes()
    return {'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}

def fetch(url,method='GET'):
    if method not in ('GET','HEAD'):
        raise ValueError('Verifier permits GET and HEAD only')
    headers={'Cache-Control':'no-cache','Accept':'*/*','User-Agent':'MusebookAlignedReleaseVerifier/1.0'}
    host=urllib.parse.urlsplit(url).hostname or ''
    bypass=os.environ.get('MUSEBOOK_VERIFY_VERCEL_BYPASS')
    if bypass and host.endswith('.vercel.app'):
        headers['x-vercel-protection-bypass']=bypass
    request=urllib.request.Request(url,headers=headers,method=method)
    opener=urllib.request.build_opener(SafeRedirect())
    try:
        response=opener.open(request,timeout=35)
    except urllib.error.HTTPError as error:
        response=error
    with response:
        body=response.read() if method=='GET' else b''
        return {'status':response.status,'content_type':response.headers.get('content-type',''),
                'challenge':bool(response.headers.get('www-authenticate')),
                'cache_control':response.headers.get('cache-control',''),
                'url':response.geturl().split('?',1)[0],'body':body,
                'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}

def main(args):
    dist=args.dist_dir.resolve()
    expected=json.loads((dist/'release.json').read_text())
    origins=[origin(value) for value in args.origin] or [
        'https://musebook.trade','https://musebook-private.vercel.app','https://terminal.musebook.trade']
    origins=list(dict.fromkeys(origins))
    canonical_appendix=None
    if 'https://musebook.trade' in origins:
        canonical_appendix=reviewed_canonical_skill_appendix(
            getattr(args,'canonical_skill_appendix',DEFAULT_CANONICAL_SKILL_APPENDIX))
    rows=[];lock=threading.Lock();jobs=[]
    def check(base,path,method='GET',expected_status=200,kind='file',expected_file=None,
              expected_json=None,checker=None,expected_appendix=None):
        row={'origin':base,'path':path,'method':method,'kind':kind}
        try:
            response=fetch(base+path,method)
            row.update({key:response[key] for key in ('status','content_type','url','bytes','sha256')})
            if response.get('redirects'):
                row['redirects']=response['redirects']
            if response['status']!=expected_status:
                raise ValueError(f'Expected HTTP {expected_status}')
            if expected_file and method=='GET':
                local=file_fingerprint(expected_file)
                comparison_body=response['body']
                if expected_appendix is not None:
                    if base!='https://musebook.trade' or path not in ('/SKILL.md','/skill.md'):
                        raise ValueError('Runtime augmentation is limited to the two canonical skill routes')
                    row['frozen_prefix']=dict(local)
                    combined=expected_file.read_bytes()+expected_appendix
                    local={'bytes':len(combined),'sha256':hashlib.sha256(combined).hexdigest()}
                    row['runtime_augmentation']={'bytes':len(expected_appendix),
                        'sha256':hashlib.sha256(expected_appendix).hexdigest()}
                    if response['body']!=combined:
                        raise ValueError('Canonical skill differs from the exact frozen prefix and reviewed runtime appendix')
                    row['runtime_augmentation_verified']=True
                row['expected']=local
                if expected_file.suffix=='.html' and comparison_body!=expected_file.read_bytes():
                    if 'text/html' not in response['content_type']:
                        raise ValueError('HTML document route returned a different content type')
                    allowed_urls={base+path}
                    if path.endswith('.html'):
                        allowed_urls.add(base+path[:-5])
                    if response['url'] not in allowed_urls:
                        raise ValueError('Reviewed HTML redirected to an unknown origin or route')
                    comparison_body,review=normalize_reviewed_html(base,path,comparison_body,
                        expected_file.read_bytes(),expected_file.relative_to(dist).as_posix(),fetch)
                    row['html_transform_review']=review
                if len(comparison_body)!=local['bytes'] or hashlib.sha256(comparison_body).hexdigest()!=local['sha256']:
                    raise ValueError('Live bytes differ from frozen artifact')
                if 'text/html' in response['content_type'] and expected_file.suffix!='.html':
                    raise ValueError('Binary/document route returned HTML')
            if expected_json is not None:
                actual=json.loads(response['body'])
                if actual!=expected_json:
                    raise ValueError('Release manifest differs from frozen artifact')
            if checker:
                checker(response)
            row['passed']=True
        except Exception as error:
            row['passed']=False
            # Never print response bodies, authorization headers, or redirects' queries.
            row['error']=str(error) if isinstance(error,ValueError) else type(error).__name__
        with lock:
            rows.append(row)
        print(json.dumps({key:row[key] for key in ('origin','path','method','status','passed','runtime_augmentation_verified','error') if key in row}),flush=True)
    def add(*values,**kwargs):
        jobs.append((values,kwargs))
    def html(response):
        body=response['body'].decode('utf8','replace')
        if 'text/html' not in response['content_type'] or 'id="root"' not in body:
            raise ValueError('Expected compiled application HTML shell')
        if expected['entry'] not in body:
            raise ValueError('Application shell references a different entry bundle')
    files={'/clawd-skills.tar.gz':dist/'clawd-skills.tar.gz',
           '/clawd-skills-manifest.json':dist/'clawd-skills-manifest.json',
           '/SKILL.md':dist/'skill.md','/skill.md':dist/'skill.md'}
    for relative in ['plugins/manifest.json','connectors/manifest.json','downloads/manifest.json',
                     'sdk/README.md','llms.txt','openapi.json','install-cli.sh','install-clawd.sh','install.sh',
                     'agentic-layer.md','clawd-agentic-layer-whitepaper.pdf','research/manifest.json',
                     'research/clawd-agentic-layer-v0.6.html','research/clawd-agentic-layer-v0.6.md',
                     'research/clawd-agentic-layer-v0.6.pdf']:
        file=dist/relative
        if file.is_file():
            files['/'+relative]=file
    # Validate every package that the frozen public manifests advertise.
    for relative in ['plugins/manifest.json','connectors/manifest.json','downloads/manifest.json']:
        file=dist/relative
        if not file.exists():
            continue
        value=json.loads(file.read_text())
        for package in value.get('packages',[]):
            path=package.get('download') or urllib.parse.urlsplit(package.get('url','')).path
            if not path and package.get('file'):
                path='/downloads/'+package['file']
            local=dist/path.lstrip('/')
            if not local.is_file():
                raise ValueError('Frozen manifest advertises a missing package')
            fingerprint=file_fingerprint(local)
            if package.get('sha256')!=fingerprint['sha256'] or package.get('bytes')!=fingerprint['bytes']:
                raise ValueError('Frozen advertised package integrity is inconsistent')
            files[path]=local
    routes=args.route or ['/','/skills/','/connector/','/plugin/','/sdk/','/cli/','/terminal/',
                          '/onboard/','/otc/','/meteora/','/circle/','/x402/','/mcp-auth/connect','/mcp-auth/callback']
    local_index=(dist/'index.html').read_text()
    assets={expected['entry'],*re.findall(r'(?:href|src)="(/assets/[^\"]+\.(?:css|js))"',local_index)}
    if args.all_app_assets:
        assets.update('/'+file.relative_to(dist).as_posix() for file in (dist/'assets').glob('*') if file.suffix in ('.js','.css'))
    for base in origins:
        add(base,'/release.json',kind='release',expected_json=expected)
        for path in routes:
            add(base,path,kind='route',checker=html)
        for path in sorted(assets):
            add(base,path,kind='app-asset',expected_file=dist/path.lstrip('/'))
        for path,file in files.items():
            appendix=canonical_appendix if base=='https://musebook.trade' and path in ('/SKILL.md','/skill.md') else None
            add(base,path,kind='download-or-document',expected_file=file,expected_appendix=appendix)
    if not args.stage_only:
        def markdown(response):
            if 'markdown' not in response['content_type']:
                raise ValueError('Expected Markdown content type')
        for path,relative in [('/','skill/index.html'),('/SKILL.md','skill/trade.md'),
                              ('/skill.md','skill/trade.md'),('/skill/trade.md','skill/trade.md'),
                              ('/skill/pump-ows.md','skill/pump-ows.md')]:
            add('https://skill.musebook.trade',path,kind='skill-host',expected_file=dist/relative,
                checker=markdown if path.endswith('.md') else None)
        for path in ['/SKILL.md','/skill.md']:
            add('https://skill.musebook.trade',path,'HEAD',kind='skill-head',checker=markdown)
        for path in ['/skill/','/skill/trade.md','/skill/pump-ows.md']:
            relative='skill/index.html' if path.endswith('/') else path.lstrip('/')
            add('https://musebook.trade',path,kind='canonical-skill',expected_file=dist/relative)
        def healthy(response):
            if json.loads(response['body']).get('ok') is not True:
                raise ValueError('Health did not report ok')
        add('https://musebook.trade','/api/health',kind='public-api',checker=healthy)
        def bundle(response):
            live=json.loads(response['body']);manifest=json.loads((dist/'clawd-skills-manifest.json').read_text())
            if live.get('sha256')!=manifest['sha256'] or live.get('tarball_bytes')!=manifest['bytes'] or live.get('skill_count')!=manifest['skill_count']:
                raise ValueError('API bundle metadata differs from frozen archive manifest')
        add('https://musebook.trade','/api/bundle',kind='public-api',checker=bundle)
        def unauthenticated(response):
            if json.loads(response['body']) is not None:
                raise ValueError('Anonymous request returned a session')
        add('https://musebook.trade','/api/auth/get-session',kind='auth-boundary',checker=unauthenticated)
        def challenge(response):
            if not response['challenge']:
                raise ValueError('Protected MCP lacks its authentication challenge')
        add('https://musebook.trade','/mcp-auth',expected_status=401,kind='auth-boundary',checker=challenge)
        add('https://musebook.trade','/api/keys/me',expected_status=401,kind='auth-boundary')
        add('https://musebook.trade','/api/town/wallet',expected_status=400,kind='selector-boundary')
    dns=[]
    for host in sorted({urllib.parse.urlsplit(base).hostname for base in origins}|({'skill.musebook.trade'} if not args.stage_only else set())):
        try:
            addresses=sorted({row[4][0] for row in socket.getaddrinfo(host,443)})
            dns.append({'host':host,'addresses':addresses,'passed':True})
        except Exception as error:
            dns.append({'host':host,'error':type(error).__name__,'passed':False})
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        list(executor.map(lambda job:check(*job[0],**job[1]),jobs))
    report={'checked_at':datetime.now(timezone.utc).isoformat(),'expected_release':expected,
            'origins':origins,'checks':sorted(rows,key=lambda row:(row['origin'],row['path'],row['method'])),
            'dns':dns,'requests_are_get_head_only':True,'unsigned_post_denials_not_executed':True}
    augmentation_rows=[row for row in rows if row['origin']=='https://musebook.trade' and row['path'] in ('/SKILL.md','/skill.md') and row['method']=='GET']
    report['runtime_augmentation_verified']=(len(augmentation_rows)==2 and
        all(row.get('runtime_augmentation_verified') and row['passed'] for row in augmentation_rows)) if canonical_appendix is not None else None
    if canonical_appendix is not None:
        report['reviewed_runtime_augmentation']={'bytes':len(canonical_appendix),
            'sha256':hashlib.sha256(canonical_appendix).hexdigest()}
    report['passed']=all(row['passed'] for row in rows+dns)
    report['check_count']=len(rows)
    report['failed_count']=sum(not row['passed'] for row in rows)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'passed':report['passed'],'checks':len(rows),'failures':report['failed_count'],'report':str(args.output)}))
    return 0 if report['passed'] else 1

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--dist-dir',type=Path,required=True)
    parser.add_argument('--origin',action='append',default=[])
    parser.add_argument('--route',action='append')
    parser.add_argument('--stage-only',action='store_true')
    parser.add_argument('--all-app-assets',action='store_true')
    parser.add_argument('--canonical-skill-appendix',type=Path,default=DEFAULT_CANONICAL_SKILL_APPENDIX,
                        help='Exact previously reviewed appendix capture; used only for canonical /SKILL.md and /skill.md')
    parser.add_argument('--workers',type=int,default=4,choices=range(1,9))
    parser.add_argument('--output',type=Path,default=Path('/tmp/musebook-aligned-live-verification.json'))
    try:
        sys.exit(main(parser.parse_args()))
    except Exception as error:
        print('Verifier could not start: '+(str(error) if isinstance(error,ValueError) else type(error).__name__),file=sys.stderr)
        sys.exit(1)
