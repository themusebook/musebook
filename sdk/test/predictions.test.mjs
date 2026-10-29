import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { existsSync, readFileSync } from 'node:fs';
import { MusebookClient, MusebookError, predictionMicro, PREDICTION_USDC } from '../dist/index.js';

const owner = '11111111111111111111111111111111';
const page = { start: 0, end: 5 };
const wallet = { ownerPubkey: owner, ...page };
const reads = [
  ['predictionEvents', [{ ...page, includeMarkets: false }], '/events', 'start=0&end=5&includeMarkets=false'],
  ['predictionSearch', ['a & b', { limit: 2 }], '/events/search', 'limit=2&query=a+%26+b'],
  ['predictionEvent', ['event'], '/events/event', ''],
  ['predictionEventMarkets', ['event', page], '/events/event/markets', 'start=0&end=5'],
  ['predictionEventMarket', ['event', 'market'], '/events/event/markets/market', ''],
  ['predictionScore', ['event'], '/events/event/score', ''],
  ['predictionScores', [['a', 'b']], '/events/scores', 'eventIds=a%2Cb'],
  ['predictionSuggested', [owner, 'kalshi'], `/events/suggested/${owner}`, 'provider=kalshi'],
  ['predictionMarket', ['market'], '/markets/market', ''],
  ['predictionOrderbook', ['market'], '/orderbook/market', ''],
  ['predictionTradingStatus', [], '/trading-status', ''],
  ['predictionPositions', [{ ...wallet, isYes: false }], '/positions', `ownerPubkey=${owner}&start=0&end=5&isYes=false`],
  ['predictionPosition', [owner], `/positions/${owner}`, ''],
  ['predictionOrders', [wallet], '/orders', `ownerPubkey=${owner}&start=0&end=5`],
  ['predictionOrder', [owner], `/orders/${owner}`, ''],
  ['predictionOrderStatus', [owner], `/orders/status/${owner}`, ''],
  ['predictionHistory', [wallet], '/history', `ownerPubkey=${owner}&start=0&end=5`],
  ['predictionProfile', [owner], `/profiles/${owner}`, ''],
  ['predictionPnlHistory', [owner, { interval: '1w' }], `/profiles/${owner}/pnl-history`, 'interval=1w'],
  ['predictionTrades', [], '/trades', ''],
  ['predictionLeaderboards', [{ metric: 'pnl' }], '/leaderboards', 'metric=pnl'],
];
const buy = { ownerPubkey: owner, marketId: 'market', isBuy: true, isYes: false, depositAmount: '5000000', depositMint: PREDICTION_USDC };
const sell = { ownerPubkey: owner, positionPubkey: owner, isBuy: false, isYes: true, contractsMicro: '1234567' };
const execute = { signedTransaction: 'caller-signed-bytes', context: { opaque: ['unchanged', { provider: 1 }] }, requestId: 'correlation-only' };
const writes = [
  ['predictionBuildOrder', [buy], '/orders', 'POST', buy],
  ['predictionBuildOrder', [sell], '/orders', 'POST', sell],
  ['predictionBuildClose', [owner, owner], `/positions/${owner}`, 'DELETE', { ownerPubkey: owner }],
  ['predictionBuildCloseAll', [owner, 50], '/positions', 'DELETE', { ownerPubkey: owner, minSellPriceSlippageBps: 50 }],
  ['predictionBuildClaim', [owner, owner], `/positions/${owner}/claim`, 'POST', { ownerPubkey: owner }],
  ['predictionExecute', [execute], '/execute', 'POST', execute],
];

for (const [name, args, path, query] of reads) test(`${name}: route and credential boundary`, async () => {
  let calls = 0;
  const client = new MusebookClient({ apiKey: 'never-send', headers: { Authorization: 'never-send', 'x-api-key': 'never-send' }, fetch: async (url, init) => {
    calls++;
    assert.equal(url, `https://api.musebook.trade/api/predictions${path}${query ? '?' + query : ''}`);
    assert.equal(init.method, 'GET');
    assert.equal(init.cache, 'no-store');
    assert.equal(init.credentials, 'omit');
    assert.equal(init.redirect, 'error');
    assert.deepEqual(init.headers, { accept: 'application/json' });
    assert.equal(init.body, undefined);
    return Response.json({ data: [] });
  } });
  assert.deepEqual(await client[name](...args), { data: [] });
  assert.equal(calls, 1);
});

for (const [name, args, path, method, body] of writes) test(`${name}: ${body.isBuy === false ? 'fractional sell' : method} prepares or explicitly submits once`, async () => {
  let calls = 0;
  const client = new MusebookClient({ fetch: async (url, init) => {
    calls++;
    assert.equal(url, `https://api.musebook.trade/api/predictions${path}`);
    assert.equal(init.method, method);
    assert.deepEqual(JSON.parse(init.body), body);
    return Response.json(name === 'predictionExecute' ? { ok: true, status: 'Success', signature: 'expected' } : { transaction: 'unsigned', txMeta: { blockhash: 'original', lastValidBlockHeight: 42 } });
  } });
  const response = await client[name](...args);
  if (name !== 'predictionExecute') assert.equal(response.txMeta.blockhash, 'original');
  assert.equal(calls, 1);
});

test('every new prediction operation in OpenAPI has an SDK method', () => {
  const specPath = ['../../openapi.json', '../../web-react/public/openapi.json'].map(path => new URL(path, import.meta.url)).find(existsSync);
  assert.ok(specPath, 'OpenAPI contract must be present in the checkout');
  const spec = JSON.parse(readFileSync(specPath));
  const covered = [...reads.map(([, , path]) => ['get', path]), ...writes.map(([, , path, method]) => [method.toLowerCase(), path])];
  const operations = Object.entries(spec.paths).flatMap(([path, item]) => Object.entries(item).filter(([, op]) => op.tags?.includes('Predictions')).map(([method]) => [method, path]));
  assert.equal(operations.length, 26);
  for (const [method, path] of operations) {
    const pattern = new RegExp('^' + path.slice('/api/predictions'.length).replace(/\{[^}]+\}/g, '[^/]+') + '$');
    assert.ok(covered.some(([m, p]) => m === method && pattern.test(p)), `${method} ${path}`);
  }
});

test('exact quantities never pass through floating point', () => {
  assert.equal(predictionMicro('1.234567'), '1234567');
  assert.equal(predictionMicro('18446744073709.551615'), '18446744073709551615');
  for (const invalid of ['0', '-1', '0.0000001', '1e6', 'NaN', '18446744073709.551616']) assert.throws(() => predictionMicro(invalid), RangeError);
});

test('null orderbook and score remain unavailable; malformed JSON fails', async () => {
  const client = new MusebookClient({ fetch: async () => Response.json(null) });
  assert.equal(await client.predictionOrderbook('market'), null);
  assert.equal(await client.predictionScore('event'), null);
  await assert.rejects(client.predictionTradingStatus(), MusebookError);
  const broken = new MusebookClient({ fetch: async () => new Response('<html>not JSON</html>') });
  await assert.rejects(broken.predictionOrderbook('market'), MusebookError);
});

test('provider errors preserve status, code and Retry-After without retry', async () => {
  let calls = 0;
  const client = new MusebookClient({ fetch: async () => { calls++; return Response.json({ error: 'Wait', code: 'upstream_error' }, { status: 429, headers: { 'retry-after': '30' } }); } });
  await assert.rejects(client.predictionTradingStatus(), error => error.status === 429 && error.retryAfter === '30' && error.body.code === 'upstream_error');
  assert.equal(calls, 1);
});

test('ambiguous or failed execution is never retried or reported successful', async () => {
  for (const result of [null, { status: 'Failed' }, { ok: true, status: 'Success' }, { ok: false, error: 'uncertain', code: 'execution_uncertain' }]) {
    let calls = 0;
    const client = new MusebookClient({ fetch: async () => { calls++; if (result === null) throw new TypeError('connection lost'); return Response.json(result); } });
    await assert.rejects(client.predictionExecute(execute));
    assert.equal(calls, 1);
  }
});

test('existing authenticated methods retain their bearer and CJS exports work', async () => {
  const client = new MusebookClient({ apiKey: 'account-key', fetch: async (_, init) => {
    assert.equal(init.headers.authorization, 'Bearer account-key');
    return Response.json({ ok: true });
  } });
  await client.me();
  const cjs = createRequire(import.meta.url)('../dist/index.cjs');
  assert.equal(cjs.predictionMicro('5'), '5000000');
  assert.equal(typeof cjs.MusebookClient.prototype.predictionBuildClaim, 'function');
});
