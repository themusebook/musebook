import assert from 'node:assert/strict';
import { MusebookClient, SDK_VERSION } from '../dist/index.js';

// Deliberately read-only: no keys, wallet proofs, preparation, signing or broadcasts.
const client = new MusebookClient({ baseUrl: process.env.SDK_TEST_BASE_URL, timeoutMs: 30_000 });
const spec = await client.openapi();
for (const [path, method] of [
  ['/api/v2/agents/register', 'post'], ['/api/v2/agent-actions', 'post'],
  ['/api/site-launches', 'get'], ['/api/site-launches', 'post'],
  ['/api/metaplex/launches', 'get'], ['/api/metaplex/launches/{genesis}', 'get'],
  ['/api/metaplex/tokens/{mint}', 'get'], ['/api/metaplex/agents', 'get'],
  ['/api/metaplex/agents/{address}', 'get'], ['/api/metaplex/agents/{address}/agent-card.json', 'get'],
  ['/api/metaplex/agents/mint', 'post'], ['/api/metaplex/agents/{address}/fund', 'post'],
  ['/api/metaplex/agents/{address}/withdraw', 'post'], ['/api/metaplex/das', 'post'],
  ['/api/genesis/rewards/status', 'get'], ['/api/genesis/rewards/claim', 'post'],
  ['/api/metaplex/metadata/{mint}', 'get'], ['/api/metaplex/metadata/{mint}/prepare', 'post'],
  ['/api/rwa/status', 'get'], ['/api/rwa/plan', 'post'], ['/api/auth/chatgpt/status', 'get'],
]) assert.ok(spec.paths?.[path]?.[method], `Contract is missing ${method.toUpperCase()} ${path}`);
console.log(`SDK ${SDK_VERSION}: 21 added API operations match ${spec.info?.version ?? 'live'} OpenAPI`);
const health = await client.health();
assert.equal(health.ok, true);
console.log('health: ok');
const skills = await client.skills();
assert.ok(Array.isArray(skills));
console.log(`skills: ${skills.length}`);
const connectors = await client.connectors();
assert.ok(Array.isArray(connectors));
console.log(`connectors: ${connectors.length}`);
const bundle = await client.bundle();
assert.equal(typeof bundle.tarball_bytes, 'number');
assert.equal(typeof bundle.generated_at, 'string');
console.log(`bundle bytes: ${bundle.tarball_bytes}`);
const receipts = await client.siteLaunches({ network: 'mainnet' });
assert.equal(receipts.ok, true);
assert.ok(Array.isArray(receipts.items));
console.log(`site launches: ${receipts.items.length}`);
const launches = await client.metaplexLaunches({ network: 'solana-mainnet', spotlight: true });
assert.ok(Array.isArray(launches.data));
console.log(`spotlight launches: ${launches.data.length}`);
const agents = await client.metaplexAgents({ network: 'solana-mainnet', page: 1, pageSize: 2 });
assert.equal(agents.success, true);
assert.ok(Array.isArray(agents.data.agents));
console.log(`Metaplex agents: ${agents.data.agents.length}`);
const rwa = await client.rwaStatus();
assert.equal(rwa.launchEnabled, false);
console.log(`RWA: ${rwa.stage}`);
const auth = await client.chatgptSignInStatus();
assert.equal(auth.identityOnly, true);
console.log(`ChatGPT sign-in: ${auth.status}`);
const events = await client.predictionEvents({ start: 0, end: 5, includeMarkets: true });
assert.ok(Array.isArray(events.data));
const marketId = events.data.flatMap(event => event.markets ?? []).find(market => market.marketId)?.marketId;
assert.ok(marketId, 'No prediction market is available for a live read check');
const market = await client.predictionMarket(marketId);
assert.equal(market.marketId, marketId);
const orderbook = await client.predictionOrderbook(marketId);
assert.ok(orderbook === null || typeof orderbook === 'object');
console.log(`prediction events: ${events.data.length}; market/rules/orderbook: ${marketId}`);
