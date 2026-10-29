#!/usr/bin/env python3
"""Build deterministic skills and connector review archives from an existing pack."""
import argparse
import collections
import datetime
import gzip
import hashlib
import json
import pathlib
import re
import shutil
import tarfile
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--source', type=pathlib.Path, required=True)
parser.add_argument('--output', type=pathlib.Path, default=ROOT)
parser.add_argument('--manifest-template', type=pathlib.Path, required=True)
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=True)

def archive(source, output, prefix):
    def normalize(info):
        info.uid = info.gid = 0
        info.uname = info.gname = ''
        info.mtime = 0
        info.pax_headers = {}
        return info
    with output.open('wb') as raw, gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0) as gz, tarfile.open(fileobj=gz, mode='w', format=tarfile.PAX_FORMAT) as tar:
        tar.add(source, arcname=prefix, recursive=False, filter=normalize)
        for path in sorted(source.rglob('*')):
            tar.add(path, arcname=prefix + '/' + path.relative_to(source).as_posix(), recursive=False, filter=normalize)
    with tarfile.open(output, 'r:gz') as tar:
        names = [member.name for member in tar.getmembers()]
        assert len(names) == len(set(names)), 'Duplicate archive entries'
    return {'sha256': hashlib.sha256(output.read_bytes()).hexdigest(), 'bytes': output.stat().st_size, 'archive_entry_count': len(names)}

template = json.loads(args.manifest_template.read_text())
with tempfile.TemporaryDirectory(prefix='muse-pack-') as scratch:
    scratch = pathlib.Path(scratch)
    with tarfile.open(args.source, 'r:gz') as tar:
        tar.extractall(scratch / 'input', filter='data')
    source = scratch / 'input' / 'skills'
    if not source.is_dir():
        raise SystemExit('Expected skills/ in source archive')
    cookbook = source / 'openrouter-cookbooks' / 'SKILL.md'
    if not cookbook.exists():
        cookbook.write_text('''---
name: openrouter-cookbooks
description: Read the included OpenRouter cookbook guides for provider integration examples.
---

# OpenRouter cookbooks

Read README.md and the included skills/ guides for integration examples. These are developer documentation, outside the submitted Muse connector tool scope. Account connection grants no additional authority; do not put provider keys in prompts, logs or files.
''')
    shutil.copytree(ROOT / 'connectors', source / 'connectors', dirs_exist_ok=True, ignore=shutil.ignore_patterns('*.tar.gz', 'manifest.json', '__pycache__', '*.pyc'))
    result = archive(source, args.output / 'clawd-skills.tar.gz', 'skills')
    old = {entry['slug']: entry for entry in template['skills']}
    skills = []
    for path in sorted(source.glob('*/SKILL.md')):
        slug = path.parent.name
        text = path.read_text(errors='replace')
        entry = old.get(slug, {'slug': slug, 'name': slug, 'path': slug + '/SKILL.md', 'category': 'General'})
        if 'description' not in entry:
            match = re.search(r'^description:\s*(.+)$', text, re.MULTILINE)
            entry['description'] = match.group(1).strip().strip('"\'') if match else 'Read ' + slug + ' documentation and integration examples.'
            if entry['description'] in ['>', '|', '>-' , '|-']:
                entry['description'] = 'Read ' + slug + ' documentation and integration examples.'
        skills.append(entry)
    count = sum(1 for _ in source.rglob('SKILL.md'))
    assert len(skills) == 272, 'Expected all 272 installable skills'
    manifest = {**template, **result, 'name': 'clawd-skills', 'version': '3.15.1',
                'tarball': '/clawd-skills.tar.gz', 'tarball_url': 'https://musebook.trade/clawd-skills.tar.gz',
                'tarball_bytes': result['bytes'], 'skill_count': len(skills), 'skill_file_count': count,
                'nested_skill_file_count': count - len(skills), 'connector_count': 17, 'connector_package_count': 2,
                'categories': dict(sorted(collections.Counter(s['category'] for s in skills).items())),
                'skills': skills, 'md5': hashlib.md5((args.output / 'clawd-skills.tar.gz').read_bytes()).hexdigest(),
                'generated_at': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'source': 'muse-connector-release-2026-10-10'}
    (args.output / 'clawd-skills-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    releases = []
    output = args.output / 'connectors'
    output.mkdir(exist_ok=True)
    for name in ['connector-clawd', 'connector-birdeye']:
        package = ROOT / 'connectors' / name
        config = json.loads((package / 'connector.json').read_text())
        assert config['mcp']['url'] == 'https://musebook.trade/mcp-auth'
        assert config['mcp']['scopes'] == ['read']
        catalog = json.loads((package / 'docs/tools.json').read_text())
        assert all(t['classification'] == 'read' and not t['sensitive'] and t['annotations']['readOnlyHint'] for t in catalog['tools'])
        releases.append({'name': name, 'version': config['version'], 'url': 'https://musebook.trade/connectors/' + name + '.tar.gz', **archive(package, output / (name + '.tar.gz'), name)})
    (output / 'manifest.json').write_text(json.dumps({'version': '3.15.1', 'packages': releases}, indent=2) + '\n')
    print(json.dumps({k: manifest[k] for k in ['version', 'sha256', 'bytes', 'skill_count', 'skill_file_count', 'connector_package_count']}))
