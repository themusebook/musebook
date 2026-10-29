import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { Client } from '../musebook-tui/node_modules/@modelcontextprotocol/sdk/dist/esm/client/index.js';
import { StreamableHTTPClientTransport } from '../musebook-tui/node_modules/@modelcontextprotocol/sdk/dist/esm/client/streamableHttp.js';

const origin = process.argv[2] || 'https://musebook.trade';
const read = path => JSON.parse(readFileSync(new URL('../' + path, import.meta.url)));
const report = { origin, checkedAt: new Date().toISOString(), checks: [] };
for (const plugin of ['musebook', 'clawd-research']) {
  const standard = read(`plugins/${plugin}/plugin.json`);
  const codex = read(`plugins/${plugin}/.codex-plugin/plugin.json`);
  for (const field of ['name', 'version', 'description']) assert.equal(standard[field], codex[field]);
  const standardMcp = read(`plugins/${plugin}/mcp.json`).mcpServers;
  const codexMcp = read(`plugins/${plugin}/.mcp.json`).mcpServers;
  for (const name of Object.keys(standardMcp)) assert.equal(standardMcp[name].url, codexMcp[name].url);
  for (const [scope, group] of Object.entries(read(`plugins/${plugin}/MCP_OUTPUT_SCHEMAS.json`).groups)) {
    if (scope === 'account') continue; // Authenticated calls require an owner's grant.
    const endpoint = new URL(new URL(group.endpoint).pathname, origin);
    const client = new Client({ name: 'musebook-integration-check', version: '1.0.0' });
    try {
      await client.connect(new StreamableHTTPClientTransport(endpoint));
      const { tools } = await client.listTools();
      for (const expected of group.tools) {
        const actual = tools.find(tool => tool.name === expected.name);
        assert(actual, `Missing ${expected.name}`);
        assert(actual.outputSchema, `Missing output schema: ${expected.name}`);
        assert.equal(actual.annotations.readOnlyHint, expected.annotations.readOnlyHint);
        assert.equal(actual.annotations.destructiveHint, false);
      }
      const result = await client.callTool({ name: plugin === 'musebook' ? 'open_musebook' : 'rwa_readiness', arguments: {} });
      assert(!result.isError, JSON.stringify(result));
      assert(result.structuredContent);
      report.checks.push({ plugin, tools: group.tools.length, representativeCall: 'passed' });
    } finally { await client.close(); }
  }
}
for (const pkg of read('plugins/releases/manifest.json').packages) {
  const bytes = readFileSync(new URL('../plugins/releases/' + pkg.download.split('/').pop(), import.meta.url));
  assert.equal(bytes.length, pkg.bytes);
  assert.equal(createHash('sha256').update(bytes).digest('hex'), pkg.sha256);
  report.checks.push({ archive: pkg.name, version: pkg.version, checksum: 'passed' });
}
const protectedResponse = await fetch(new URL('/mcp-auth', origin), {
  method: 'POST', headers: { 'content-type': 'application/json', accept: 'application/json, text/event-stream' },
  body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'tools/list', params: {} }), signal: AbortSignal.timeout(30000),
});
assert.equal(protectedResponse.status, 401);
assert(protectedResponse.headers.get('www-authenticate'));
report.checks.push({ accountEndpoint: 'requires authorization' });
console.log(JSON.stringify(report, null, 2));
