// Run only after publication; verifies a clean registry consumer, not a local link.
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, writeFileSync, rmSync, readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { SDK_VERSION } from '../dist/index.js';

const dir = mkdtempSync(join(tmpdir(), 'musebook-npm-consumer-'));
const metadata = await (await fetch(`https://registry.npmjs.org/@musebook%2fsdk/${SDK_VERSION}`)).json();
assert.equal(metadata.version, SDK_VERSION, 'Version must be public on npm before testing');
const tarball = readFileSync(new URL(`../musebook-sdk-${SDK_VERSION}.tgz`, import.meta.url));
assert.equal(metadata.dist.integrity, 'sha512-' + createHash('sha512').update(tarball).digest('base64'));
const run = (args) => execFileSync(process.execPath, args, { cwd: dir, encoding: 'utf8', stdio: 'pipe', timeout: 30_000 });
try {
  writeFileSync(join(dir, 'package.json'), JSON.stringify({ private: true, type: 'module' }));
  execFileSync('npm', ['install', `@musebook/sdk@${SDK_VERSION}`, '@open-wallet-standard/core@1.4.3', '--ignore-scripts', '--no-audit', '--no-fund', '--prefer-online', '--cache', join(dir, 'npm-cache'), '--registry=https://registry.npmjs.org/'], { cwd: dir, stdio: 'pipe', timeout: 60_000 });
  const checks = `
    if (SDK_VERSION !== '${SDK_VERSION}') throw Error('Version mismatch');
    if (typeof MusebookClient !== 'function') throw Error('Missing API client');
    if (new MusebookWebMCPClient().supported !== false) throw Error('Browser entry is not SSR safe');
    const ows = await createOWSClient({ vaultPath: ${JSON.stringify(join(dir, 'vault'))} });
    const wallet = MODE === 'esm' ? ows.createWallet({ name: 'npm-fixture', passphrase: 'temporary-npm-smoke-passphrase' }) : ows.getWallet('npm-fixture');
    const sig = ows.signMessage({ wallet: wallet.id, message: 'npm install verification', credential: 'temporary-npm-smoke-passphrase' });
    if (sig.signature.length !== 128) throw Error('Invalid OWS signature');
    console.log(JSON.stringify({ mode: MODE, version: SDK_VERSION, address: wallet.address, nativeOWS: true }));
  `;
  const esm = run(['--input-type=module', '-e', `import { MusebookClient, SDK_VERSION } from '@musebook/sdk'; import { MusebookWebMCPClient } from '@musebook/sdk/webmcp'; import { createOWSClient } from '@musebook/sdk/ows'; const MODE = 'esm'; ${checks}`]);
  const cjs = run(['--input-type=commonjs', '-e', `const { MusebookClient, SDK_VERSION } = require('@musebook/sdk'); const { MusebookWebMCPClient } = require('@musebook/sdk/webmcp'); const { createOWSClient } = require('@musebook/sdk/ows'); const MODE = 'cjs'; (async()=>{${checks}})().catch(e=>{console.error(e);process.exitCode=1;});`]);
  const evidence = { at: new Date().toISOString(), version: SDK_VERSION, integrity: metadata.dist.integrity, consumers: [JSON.parse(esm), JSON.parse(cjs)], installedFrom: 'https://registry.npmjs.org/', fundsMoved: false };
  writeFileSync(new URL('../../artifacts/musebot/npm-install-verified.json', import.meta.url), JSON.stringify(evidence, null, 2));
  console.log(JSON.stringify(evidence, null, 2));
} finally { rmSync(dir, { recursive: true, force: true }); }
