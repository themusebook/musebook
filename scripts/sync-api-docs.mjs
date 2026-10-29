import { copyFileSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const args = process.argv.slice(2);
const check = args.includes('--check');
const roots = args.filter(arg => arg !== '--check');
if (roots.length !== 1 || roots[0].startsWith('-')) {
  console.error('Usage: node scripts/sync-api-docs.mjs [--check] <site-source-root>');
  process.exit(1);
}
const source = resolve(roots[0], 'web-react/public');
const target = fileURLToPath(new URL('../', import.meta.url));
const researchManifest = JSON.parse(readFileSync(resolve(source, 'research/manifest.json'), 'utf8'));
if (!/^\d+\.\d+(?:\.\d+)?$/.test(researchManifest.paperVersion)) throw Error('Invalid research paper version.');
const paperName = `clawd-agentic-layer-v${researchManifest.paperVersion}`;
const files = [
  ['openapi.json', 'openapi.json'],
  ['llms.txt', 'llms.txt'],
  ['prediction-api.md', 'docs/PREDICTIONS.md'],
  ['decide-api.md', 'docs/DECIDE.md'],
  ['agentic-layer.md', 'docs/AGENTIC-LAYER.md'],
  ['market-feeds.md', 'docs/MARKET-FEEDS.md'],
  [`research/${paperName}.md`, `research/${paperName}.md`],
  [`research/${paperName}.html`, `research/${paperName}.html`],
  [`research/${paperName}.pdf`, `research/${paperName}.pdf`],
  ['research/manifest.json', 'research/manifest.json'],
];
// Read and validate the full allowlist before updating any public artifact.
const entries = files.map(([from, to]) => ({ from: resolve(source, from), to: resolve(target, to), bytes: readFileSync(resolve(source, from)) }));
const spec = JSON.parse(entries[0].bytes.toString());
if (!spec.paths?.['/api/predictions/positions/{positionPubkey}/claim']?.post || !spec.info?.version) {
  throw Error('Source must contain the current prediction OpenAPI contract.');
}
if (!entries[1].bytes.toString().includes(`API ${spec.info.version}`)) throw Error('Regenerate source llms.txt before syncing.');
for (const entry of entries) {
  if (check) {
    if (!readFileSync(entry.to).equals(entry.bytes)) throw Error(`Documentation drift: ${entry.to}`);
  } else copyFileSync(entry.from, entry.to);
}
console.log(`${check ? 'Verified' : 'Synced'} ${entries.length} public artifacts; API ${spec.info.version}, ${Object.keys(spec.paths).length} paths.`);
