import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';

const root = fileURLToPath(new URL('..', import.meta.url));
test('packed package supports isolated ESM, CJS and NodeNext TypeScript consumers', { timeout: 60_000 }, () => {
  const dir = mkdtempSync(join(tmpdir(), 'musebook-sdk-'));
  const run = (command, args, cwd = dir) => execFileSync(command, args, { cwd, encoding: 'utf8', stdio: 'pipe', timeout: 30_000 });
  try {
    const [pack] = JSON.parse(run('npm', ['pack', '--ignore-scripts', '--json', '--pack-destination', dir], root));
    assert.equal(pack.version, '1.5.0');
    const files = pack.files.map(file => file.path);
    for (const required of ['dist/index.js', 'dist/index.cjs', 'dist/index.d.ts', 'dist/webmcp.js', 'dist/webmcp.d.ts', 'dist/ows.js', 'dist/ows.d.ts', 'dist/cjs/ows.js', 'dist/cjs/ows.d.ts', 'dist/cjs/index.js', 'dist/cjs/index.d.ts', 'dist/cjs/webmcp.js', 'dist/cjs/webmcp.d.ts', 'dist/cjs/package.json', 'src/types.ts']) {
      assert.ok(files.includes(required), `Missing ${required}`);
    }
    assert.ok(files.every(path => !/(^|\/)(node_modules|\.env[^/]*|scripts)(\/|$)/.test(path)));
    writeFileSync(join(dir, 'package.json'), JSON.stringify({ private: true, type: 'module' }));
    run('npm', ['install', join(dir, pack.filename), '--offline', '--ignore-scripts', '--no-audit', '--no-fund', '--package-lock=false']);
    const assertions = `
      if (sdk.SDK_VERSION !== '1.5.0') throw new Error('wrong SDK version');
      if (typeof sdk.MusebookClient !== 'function') throw new Error('missing client');
      if (typeof sdk.MusebookSocialClient !== 'function') throw new Error('missing social client');
      if (typeof sdk.AgentIndexerUnavailableError !== 'function') throw new Error('missing indexer error');
      if (sdk.DEFAULT_BASE_URL !== 'https://musebook.trade') throw new Error('wrong default base URL');
      if (new browser.MusebookWebMCPClient().supported !== false) throw new Error('SSR unsafe');
      if (Object.keys(sdk).includes('MusebookWebMCPClient')) throw new Error('browser entry leaked');
    `;
    run(process.execPath, ['--input-type=module', '-e', `import * as sdk from '@musebook/sdk'; import * as browser from '@musebook/sdk/webmcp'; ${assertions}`]);
    run(process.execPath, ['--input-type=commonjs', '-e', `const sdk = require('@musebook/sdk'); const browser = require('@musebook/sdk/webmcp'); ${assertions}`]);
    run(process.execPath, ['--input-type=module', '-e', `import { createOWSClient } from '@musebook/sdk/ows'; try { await createOWSClient(); throw new Error('Expected missing optional peer'); } catch(e) { if (!e.message.includes('Install @open-wallet-standard/core')) throw e; }`]);
    run(process.execPath, ['--input-type=commonjs', '-e', `const { createOWSClient } = require('@musebook/sdk/ows'); createOWSClient().then(() => { process.exitCode = 1; }, e => { if (!e.message.includes('Install @open-wallet-standard/core')) throw e; });`]);
    const types = `
      import { MusebookClient, MusebookSocialClient, type RwaPlan } from '@musebook/sdk';
      import { MusebookWebMCPClient } from '@musebook/sdk/webmcp';
      import { createOWSClient, type OWSSolanaWallet } from '@musebook/sdk/ows';
      const client = new MusebookClient();
      const feed = client.agentIndexerFeed(1);
      const snapshot = client.directorySnapshot();
      const social = new MusebookSocialClient({ sessionToken: 'tok' });
      const post = social.createPost('hello');
      void feed; void snapshot; void post;
      const launches = client.metaplexLaunches({ network: 'solana-devnet' });
      const browser = new MusebookWebMCPClient();
      const wallet = browser.call('musebook_wallet_context', {});
      const allowed: RwaPlan['execution']['allowed'] = false;
      createOWSClient().then(ows => {
        const wallet: OWSSolanaWallet = ows.getWallet('fixture');
        ows.signMessage({ wallet: wallet.id, message: 'reviewed', credential: 'owner-provided' });
        // @ts-expect-error signing always needs an explicit credential
        ows.signMessage({ wallet: wallet.id, message: 'missing credential' });
      });
      // @ts-expect-error financial execution is not in the browser companion
      browser.call('musebook_execute_swap', {});
      // @ts-expect-error wrong network family
      client.metaplexLaunches({ network: 'devnet' });
      void launches; void wallet; void allowed;
    `;
    writeFileSync(join(dir, 'consumer.mts'), types);
    writeFileSync(join(dir, 'consumer.cts'), types);
    run(join(root, 'node_modules', '.bin', 'tsc'), ['--noEmit', '--strict', '--target', 'ES2022', '--module', 'NodeNext', '--moduleResolution', 'NodeNext', '--lib', 'ES2022,DOM', 'consumer.mts', 'consumer.cts']);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});
