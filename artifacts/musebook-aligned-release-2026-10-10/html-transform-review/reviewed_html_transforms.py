"""Strict byte normalization for four independently reviewed HTML responses.

Only fixed templates, checked insertion points, three exact public origins and
two pinned frozen files are accepted. No HTML parser, whitespace cleanup,
generic script removal or guessed application equivalence is used.
"""
import base64
import hashlib
import re
import threading


def fingerprint(data):
    return {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


BRIDGE_TEMPLATE = b'<script type="module" src="{origin}/.webmcp/bridge.js" data-packs="c2pa,mcp-server-client"></script>'
BRIDGE_TEMPLATE_SHA256 = 'ac9dba8ca48c2f65987ba994654da18f74ddd049002a6061ec4ac8d10c08336a'
BRIDGE_HELPER = {'bytes': 72952, 'sha256': '2e3d1e39775cdbea0da8ddcca3876eee3b91119ccefb2295c295a8e562c14d60'}
NAVIGATION = b'<script id="musebook-connector-document-navigation">document.addEventListener("click",function(e){if(e.defaultPrevented||e.button!==0||e.metaKey||e.ctrlKey||e.shiftKey||e.altKey)return;var t=e.target instanceof Element?e.target:e.target&&e.target.parentElement;var a=t&&t.closest("a[href]");if(!a||a.hasAttribute("target")||a.hasAttribute("download"))return;var u=new URL(a.href,location.href);if(u.origin!==location.origin||(u.pathname!=="/connector"&&u.pathname!=="/connector/"))return;e.preventDefault();e.stopPropagation();location.assign(u.href);},true);</script>'
NAVIGATION_SHA256 = '127b9ddc9be9c8fb927afd3faaebaed296bd548faababf605ff87798832726f5'
CHALLENGE_TEMPLATE = b"<script>window.__CF$cv$params={r:'{r}',t:'{t}',u:'{u}',ut:'{ut}',i:60};(function(){if(!document.body)return;var s=document.createElement('script');s.src='/cdn-cgi/challenge-platform/scripts/precursor/main.js';document.head.appendChild(s);})();</script>"
CHALLENGE_TEMPLATE_SHA256 = 'a50e77a1baad13c244ea20e707921f9f24783322e393e1e1f5a82b4f162a0949'
CHALLENGE_PATTERN = re.compile(
    rb"<script>window\.__CF\$cv\$params=\{r:'([0-9a-f]{16})',t:'([A-Za-z0-9+/]{14}==)',u:'([0-9a-f]{32})',ut:'([A-Za-z0-9_.-]{43}-[0-9]{10}-1\.2\.1\.1-[A-Za-z0-9_.-]{107})',i:60\};"
    rb"\(function\(\)\{if\(!document\.body\)return;var s=document\.createElement\('script'\);s\.src='/cdn-cgi/challenge-platform/scripts/precursor/main\.js';document\.head\.appendChild\(s\);\}\)\(\);</script>"
)
EMAIL_SCRIPT = b'<script data-cfasync="false" src="/cdn-cgi/scripts/5c5dd728/cloudflare-static/email-decode.min.js"></script>'
EMAIL_SCRIPT_SHA256 = 'd9bfa4dd31a8c86f6ad537774d2fd2e2b1658e59f4fa204991eab7704bcad99d'
EMAIL_HELPER = {'bytes': 1239, 'sha256': '2595496fe48df6fcf9b1bc57c29a744c121eb4dd11566466bc13d2e52e6bbcc8'}
EMAIL_TEMPLATE = b'<a href="/cdn-cgi/l/email-protection" class="__cf_email__" data-cfemail="{cfemail}">[email&#160;protected]</a>'
EMAIL_TEMPLATE_SHA256 = '9427549a87a86d2f0a3a386e2c792080c543e6ecd9710bd5afc30ee66d48a4f2'
EMAIL_PATTERN = re.compile(rb'<a href="/cdn-cgi/l/email-protection" class="__cf_email__" data-cfemail="([0-9a-f]{18})">\[email&#160;protected\]</a>')
EMAIL_PLAINTEXT = b'~pot@1.0'

SKILL_FILE = {'file': 'skill/index.html', 'bytes': 6979, 'sha256': '26bf453dc3883d9ce961272ce881e72d18dc8897a390ae51a0a49e261b3a1a80'}
PAPER_FILE = {'file': 'research/clawd-agentic-layer-v0.6.html', 'bytes': 2142897, 'sha256': '75374394023f077d0a3fcc01cff5d38c421ff6a249f8f99dc65cb633fad2c8d1'}
POLICIES = {
    ('https://skill.musebook.trade', '/'): {'frozen': SKILL_FILE, 'bridge_anchor': b'<link rel="canonical" href="https://skill.musebook.trade/">', 'challenge': True},
    ('https://musebook.trade', '/skill/'): {'frozen': SKILL_FILE, 'bridge_anchor': b'<link rel="canonical" href="https://skill.musebook.trade/">', 'challenge': True},
    ('https://musebook.trade', '/research/clawd-agentic-layer-v0.6.html'): {'frozen': PAPER_FILE, 'bridge_anchor': b'<head>', 'bridge_after_anchor': True, 'navigation': True},
    ('https://terminal.musebook.trade', '/research/clawd-agentic-layer-v0.6.html'): {'frozen': PAPER_FILE, 'bridge_anchor': b'<style>', 'challenge': True, 'email': True},
}

_helper_cache = {}
_helper_lock = threading.Lock()


def checked_template(data, sha256):
    if hashlib.sha256(data).hexdigest() != sha256:
        raise ValueError('Reviewed HTML template integrity failed')


def checked_helper(base, path, expected, fetch_helper):
    url = base + path
    with _helper_lock:
        if url not in _helper_cache:
            response = fetch_helper(url)
            if response['status'] != 200 or response['url'] != url or 'javascript' not in response['content_type']:
                raise ValueError('Reviewed HTML helper endpoint changed')
            actual = fingerprint(response['body'])
            if actual != expected:
                raise ValueError('Reviewed HTML helper bytes changed')
            _helper_cache[url] = {'url': url, **actual, 'verified': True}
        return dict(_helper_cache[url])


def normalize_reviewed_html(base, path, body, expected, relative_file, fetch_helper):
    policy = POLICIES.get((base, path))
    if policy is None:
        raise ValueError('HTML differences are not approved for this exact origin and route')
    frozen = policy['frozen']
    if relative_file != frozen['file'] or fingerprint(expected) != {k: frozen[k] for k in ('bytes', 'sha256')}:
        raise ValueError('HTML normalization requires the exact reviewed frozen file')
    transforms = []
    helpers = []
    normalized = body

    # The bridge's public payload is independently pinned; its injector is not
    # present in the captured Musebook Worker. Do not invent that attribution.
    checked_template(BRIDGE_TEMPLATE, BRIDGE_TEMPLATE_SHA256)
    bridge = BRIDGE_TEMPLATE.replace(b'{origin}', base.encode('ascii'))
    if normalized.count(bridge) > 1:
        raise ValueError('Duplicate reviewed WebMCP bridge')
    if bridge in normalized:
        anchor = policy['bridge_anchor']
        if expected.count(anchor) != 1:
            raise ValueError('Reviewed WebMCP bridge anchor is ambiguous')
        offset = expected.index(anchor) + (len(anchor) if policy.get('bridge_after_anchor') else 0)
        actual_offset = normalized.index(bridge)
        if actual_offset != offset or normalized[:actual_offset] != expected[:offset]:
            raise ValueError('Reviewed WebMCP bridge insertion point changed')
        helpers.append(checked_helper(base, '/.webmcp/bridge.js', BRIDGE_HELPER, fetch_helper))
        transforms.append({'kind': 'reviewed_same_origin_webmcp_bridge', **fingerprint(bridge), 'template_sha256': BRIDGE_TEMPLATE_SHA256, 'insertion_offset': offset})
        normalized = normalized.replace(bridge, b'', 1)

    checked_template(NAVIGATION, NAVIGATION_SHA256)
    if NAVIGATION in normalized:
        if not policy.get('navigation') or normalized.count(NAVIGATION) != 1:
            raise ValueError('Connector navigation shim is not approved here')
        offset = expected.index(b'<head>') + len(b'<head>')
        if normalized.index(NAVIGATION) != offset or normalized[:offset] != expected[:offset]:
            raise ValueError('Connector navigation shim insertion point changed')
        transforms.append({'kind': 'preserved_worker_connector_navigation', **fingerprint(NAVIGATION), 'template_sha256': NAVIGATION_SHA256, 'insertion_offset': offset})
        normalized = normalized.replace(NAVIGATION, b'', 1)

    checked_template(CHALLENGE_TEMPLATE, CHALLENGE_TEMPLATE_SHA256)
    challenges = list(CHALLENGE_PATTERN.finditer(normalized))
    if challenges:
        if not policy.get('challenge') or len(challenges) != 1:
            raise ValueError('Cloudflare challenge template is not approved here')
        match = challenges[0]
        snippet = match[0]
        template = re.sub(rb"(r|t|u|ut):'[^']*'", lambda m: m[1] + b":'{" + m[1] + b"}'", snippet)
        checked_template(template, CHALLENGE_TEMPLATE_SHA256)
        if len(snippet) != 473 or normalized[match.end():] != b'</body></html>\n':
            raise ValueError('Cloudflare challenge placement or size changed')
        timestamp = base64.b64decode(match[2], validate=True)
        token_timestamp = match[4][44:54]
        if not re.fullmatch(rb'[0-9]{10}', timestamp) or abs(int(timestamp) - int(token_timestamp)) > 60:
            raise ValueError('Cloudflare challenge data fields changed format')
        transforms.append({'kind': 'cloudflare_precursor_loader', **fingerprint(snippet), 'template_sha256': CHALLENGE_TEMPLATE_SHA256, 'dynamic_data_fields': ['r', 't', 'u', 'ut'], 'dynamic_fields_never_executed_by_verifier': True})
        normalized = normalized[:match.start()] + normalized[match.end():]

    checked_template(EMAIL_SCRIPT, EMAIL_SCRIPT_SHA256)
    checked_template(EMAIL_TEMPLATE, EMAIL_TEMPLATE_SHA256)
    emails = list(EMAIL_PATTERN.finditer(normalized))
    email_scripts = normalized.count(EMAIL_SCRIPT)
    if emails or email_scripts:
        if not policy.get('email') or len(emails) != 1 or email_scripts != 1:
            raise ValueError('Cloudflare email transformation is not approved here')
        match = emails[0]
        encoded = bytes.fromhex(match[1].decode('ascii'))
        decoded = bytes(value ^ encoded[0] for value in encoded[1:])
        if decoded != EMAIL_PLAINTEXT or expected.count(decoded) != 1:
            raise ValueError('Cloudflare email decoding differs from reviewed frozen text')
        template = EMAIL_PATTERN.sub(EMAIL_TEMPLATE, match[0])
        checked_template(template, EMAIL_TEMPLATE_SHA256)
        transforms.append({'kind': 'cloudflare_email_obfuscation', **fingerprint(match[0]), 'template_sha256': EMAIL_TEMPLATE_SHA256, 'decoded': fingerprint(decoded)})
        normalized = normalized[:match.start()] + decoded + normalized[match.end():]
        offset = normalized.index(EMAIL_SCRIPT)
        if normalized[offset + len(EMAIL_SCRIPT):] != b'</body></html>\n':
            raise ValueError('Cloudflare email helper insertion point changed')
        helpers.append(checked_helper(base, '/cdn-cgi/scripts/5c5dd728/cloudflare-static/email-decode.min.js', EMAIL_HELPER, fetch_helper))
        transforms.append({'kind': 'cloudflare_email_decoder', **fingerprint(EMAIL_SCRIPT), 'template_sha256': EMAIL_SCRIPT_SHA256})
        normalized = normalized.replace(EMAIL_SCRIPT, b'', 1)

    if normalized != expected:
        raise ValueError('HTML still differs after exact reviewed transformations; unknown changes are rejected')
    return normalized, {'policy': 'strict_reviewed_html_transforms_v1', 'remaining_bytes_match_frozen_exactly': True, 'observed': fingerprint(body), 'normalized': fingerprint(normalized), 'transformations': transforms, 'helpers': helpers}
