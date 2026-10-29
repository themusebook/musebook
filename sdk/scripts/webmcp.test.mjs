import assert from 'node:assert/strict';
import test from 'node:test';
import { MusebookWebMCPClient, WebMCPUnavailableError } from '../dist/webmcp.js';

const origin = 'https://musebook.trade';
const names = ['musebook_wallet_context', 'musebook_site_launches', 'musebook_metaplex_launches', 'musebook_agent_card'];
const tool = (name = names[0], overrides = {}) => ({ name, origin, annotations: { readOnlyHint: true }, ...overrides });
function fixture(tools = [tool()], result = { connected: false }) {
  const calls = [];
  const context = {
    async getTools() { assert.equal(this, context); return tools; },
    async executeTool(registered, input, options) {
      assert.equal(this, context);
      calls.push({ registered, input, options });
      return result;
    },
  };
  const client = new MusebookWebMCPClient({ context, expectedOrigin: origin });
  return { client, context, calls };
}

test('browser subpath is safe to import without a document and reports unavailable', async () => {
  const client = new MusebookWebMCPClient();
  assert.equal(client.supported, false);
  await assert.rejects(client.tools(), WebMCPUnavailableError);
  await assert.rejects(client.call(names[0], {}), WebMCPUnavailableError);
});

test('discovery filters origins, write tools and misleading annotations', async () => {
  const allowed = names.map(name => tool(name));
  const { client } = fixture([
    ...allowed,
    tool('musebook_execute_swap'),
    tool(names[0], { origin: 'https://untrusted.example' }),
    tool(names[0], { annotations: {} }),
    tool(names[0], { annotations: { readOnlyHint: true, consequentialHint: true } }),
  ]);
  assert.equal(client.supported, true);
  assert.deepEqual(await client.tools(), allowed);
});

test('execution preserves the native receiver, tool object, object input and signal', async () => {
  const registered = tool(names[1]);
  const expected = { network: 'devnet', items: [] };
  const { client, calls } = fixture([registered], expected);
  const input = { network: 'devnet', limit: 5 };
  const options = { signal: new AbortController().signal };
  assert.equal(await client.call(names[1], input, options), expected);
  assert.equal(calls[0].registered, registered);
  assert.equal(calls[0].input, input);
  assert.equal(calls[0].options, options);
});

test('legacy string encoding is explicit and string results are parsed once', async () => {
  const { context, calls } = fixture([tool()], '{"connected":false}');
  const client = new MusebookWebMCPClient({ context, expectedOrigin: origin, inputEncoding: 'json-string' });
  assert.deepEqual(await client.call(names[0], {}), { connected: false });
  assert.equal(calls[0].input, '{}');
  assert.equal(calls.length, 1);
  assert.equal(await fixture([tool()], null).client.call(names[0], {}), null);
  await assert.rejects(fixture([tool()], 'not JSON').client.call(names[0], {}), SyntaxError);
});

test('missing and duplicate trusted tools fail closed without execution', async () => {
  for (const tools of [[], [tool(), tool()], [tool(names[0], { origin: 'https://other.example' })]]) {
    const { client, calls } = fixture(tools);
    await assert.rejects(client.call(names[0], {}), WebMCPUnavailableError);
    assert.equal(calls.length, 0);
  }
});

test('abort before and during discovery prevents tool execution', async () => {
  const first = new AbortController();
  first.abort();
  const { client, context, calls } = fixture();
  await assert.rejects(client.call(names[0], {}, { signal: first.signal }), { name: 'AbortError' });
  const second = new AbortController();
  context.getTools = async () => { second.abort(); return [tool()]; };
  await assert.rejects(client.call(names[0], {}, { signal: second.signal }), { name: 'AbortError' });
  assert.equal(calls.length, 0);
});

test('a type error never triggers an execution retry or encoding fallback', async () => {
  const { client, context } = fixture();
  let executions = 0;
  context.executeTool = async () => { executions++; throw new TypeError('invalid native argument'); };
  await assert.rejects(client.call(names[0], {}), TypeError);
  assert.equal(executions, 1);
});

test('JavaScript callers cannot bypass the discovery-only method allowlist', async () => {
  const { client, calls } = fixture([tool('musebook_execute_swap')]);
  await assert.rejects(client.call('musebook_execute_swap', {}), /only invokes/);
  assert.equal(calls.length, 0);
});
