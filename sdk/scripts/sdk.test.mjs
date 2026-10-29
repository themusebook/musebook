import assert from 'node:assert/strict';
import { test } from 'node:test';
import { MusebookClient, MusebookError, MusebookSocialClient, AgentIndexerUnavailableError, AGENTS_CATALOG_URL, SKILLHUB_CATALOG_URL, SDK_VERSION } from '@musebook/sdk';

const address = 'So11111111111111111111111111111111111111112';
function mock(response = { ok: true }) {
  const calls = [];
  return { calls, client: new MusebookClient({ apiKey: 'mbk_test', fetch: async (url, init) => {
    calls.push({ url, ...init, body: init.body ? JSON.parse(init.body) : undefined });
    return typeof response === 'function' ? response(url, init) : Response.json(response);
  } }) };
}

test('legacy methods retain routes, signatures and explicit bearer authentication', async () => {
  const { client, calls } = mock();
  const methods = [
    [() => client.health(), 'GET', '/api/health'], [() => client.openapi(), 'GET', '/openapi.json'],
    [() => client.skills(), 'GET', '/api/skills'], [() => client.skill('a/b'), 'GET', '/api/skills/a%2Fb'],
    [() => client.connectors(), 'GET', '/api/connectors'], [() => client.bundle(), 'GET', '/api/bundle'],
    [() => client.mintAgent({ name:'test' }), 'POST', '/api/agents', { name:'test' }],
    [() => client.siwsChallenge(address), 'POST', '/api/siws/challenge', { wallet:address }],
    [() => client.issueSelfServeKey({ wallet:address, nonce:'n', signature:'s' }), 'POST', '/api/keys/selfserve', { wallet:address, nonce:'n', signature:'s' }],
    [() => client.keyMetadata(), 'GET', '/api/keys/me', undefined, true],
    [() => client.me(), 'GET', '/api/v2/me', undefined, true],
    [() => client.postFeed('hi'), 'POST', '/api/v2/feed', { content:'hi' }, true],
    [() => client.linkWallet(address), 'POST', '/api/v2/wallet', { wallet:address }, true],
    [() => client.townChallenge(address, 'join'), 'POST', '/api/town/challenge', { wallet:address, action:'join' }],
    [() => client.townState(), 'GET', '/api/town/state'],
    [() => client.townJoin({ wallet:address, nonce:'n', signature:'s', name:'test' }), 'POST', '/api/town/join', { wallet:address, nonce:'n', signature:'s', name:'test' }],
    [() => client.townMove({ wallet:address, nonce:'n', signature:'s', x:0, y:1 }), 'POST', '/api/town/move', { wallet:address, nonce:'n', signature:'s', x:0, y:1 }],
    [() => client.townSay({ wallet:address, nonce:'n', signature:'s', text:'hi' }), 'POST', '/api/town/say', { wallet:address, nonce:'n', signature:'s', text:'hi' }],
    [() => client.townBuildingPreview(address), 'GET', `/api/town/buildings/preview?wallet=${address}`],
    [() => client.agentConfiguration(), 'GET', '/.well-known/agent-configuration'],
  ];
  for (const [run, method, path, body, auth = false] of methods) {
    await run(); const c = calls.at(-1);
    assert.equal(c.url, 'https://musebook.trade' + path); assert.equal(c.method, method); assert.deepEqual(c.body, body);
    assert.equal(c.headers.get('authorization'), auth ? 'Bearer mbk_test' : null); assert.equal(c.redirect, 'manual'); assert.equal(c.credentials, 'omit');
  }
  assert.equal(SDK_VERSION, '1.5.0');
});

test('new endpoint routing preserves network families, false filters, envelopes and exact strings', async () => {
  const { client, calls } = mock();
  const registration = { wallet:address, nonce:'n', signature:'s', slug:'test-agent', name:'Test' };
  const action = { action:'trade', inputMint:address, outputMint:address, amount:'9007199254.740993', slippageBps:50 };
  const receipt = { network:'devnet', kind:'agent', asset:address, creatorWallet:address, signatures:['sig'], name:'Test', venue:'metaplex' };
  const mint = { wallet:address, network:'solana-devnet', name:'Test', uri:'https://example.com/metadata.json', agentMetadata:{ name:'Test' } };
  const fund = { sender:address, amount:0.000000001, memo:'Operating budget', network:'solana-devnet' };
  const withdraw = { sender:address, amount:0.25, network:'solana-devnet' };
  const das = { id:0, method:'getAsset', params:{ id:address } };
  const rewards = { wallet:address, network:'devnet', payer:address };
  const metadata = { action:'update', network:'devnet', wallet:address, changes:{ name:'Updated', sellerFeeBasisPoints:0, creators:null } };
  const pair = { kind:'pairing', name:'Pair', agentAsset:address, agentTokenMint:address, quoteMint:address, quoteKind:'other' };
  const cases = [
    [() => client.registerAgent(registration), 'POST', '/api/v2/agents/register', registration],
    [() => client.prepareAgentAction(action), 'POST', '/api/v2/agent-actions', action, true],
    [() => client.siteLaunches({ network:'devnet', kind:'agent' }), 'GET', '/api/site-launches?network=devnet&kind=agent'],
    [() => client.reportSiteLaunch(receipt), 'POST', '/api/site-launches', receipt],
    [() => client.metaplexLaunches({ network:'solana-devnet', spotlight:false, status:'live' }), 'GET', '/api/metaplex/launches?network=solana-devnet&spotlight=false&status=live'],
    [() => client.metaplexLaunch(address, 'solana-devnet'), 'GET', `/api/metaplex/launches/${address}?network=solana-devnet`],
    [() => client.metaplexTokenLaunches(address, 'solana-mainnet'), 'GET', `/api/metaplex/tokens/${address}?network=solana-mainnet`],
    [() => client.metaplexAgents({ network:'solana-mainnet', query:'x&y', activeOnly:false, page:1, pageSize:5 }), 'GET', '/api/metaplex/agents?network=solana-mainnet&query=x%26y&activeOnly=false&page=1&pageSize=5'],
    [() => client.metaplexAgent(address, 'solana-devnet'), 'GET', `/api/metaplex/agents/${address}?network=solana-devnet`],
    [() => client.prepareMetaplexAgentMint(mint), 'POST', '/api/metaplex/agents/mint', mint],
    [() => client.prepareMetaplexAgentFunding(address, fund), 'POST', `/api/metaplex/agents/${address}/fund`, fund],
    [() => client.prepareMetaplexAgentWithdrawal(address, withdraw), 'POST', `/api/metaplex/agents/${address}/withdraw`, withdraw],
    [() => client.das(das, 'devnet'), 'POST', '/api/metaplex/das?network=devnet', das],
    [() => client.creatorRewardsStatus(rewards), 'GET', `/api/genesis/rewards/status?wallet=${address}&network=devnet&payer=${address}`],
    [() => client.prepareCreatorRewards(rewards), 'POST', '/api/genesis/rewards/claim', rewards],
    [() => client.tokenMetadata(address, { network:'devnet', token:address }), 'GET', `/api/metaplex/metadata/${address}?network=devnet&token=${address}`],
    [() => client.prepareMetadataAction(address, metadata), 'POST', `/api/metaplex/metadata/${address}/prepare`, metadata],
    [() => client.rwaStatus(), 'GET', '/api/rwa/status'],
    [() => client.planRwa(pair), 'POST', '/api/rwa/plan', pair],
    [() => client.chatgptSignInStatus(), 'GET', '/api/auth/chatgpt/status'],
  ];
  for (const [run, method, path, body, auth = false] of cases) {
    await run(); const c = calls.at(-1);
    assert.equal(c.url, 'https://musebook.trade' + path); assert.equal(c.method, method); assert.deepEqual(c.body, body);
    assert.equal(c.headers.get('authorization'), auth ? 'Bearer mbk_test' : null);
  }
  assert.equal(calls.length, cases.length, 'Never sign, broadcast, poll or retry implicitly');
});

test('feed requestId is forwarded without inventing automatic retries', async () => {
  const { client, calls } = mock(); await client.postFeed('hi', undefined, { requestId:'post_12345' });
  assert.deepEqual(calls[0].body, { content:'hi', requestId:'post_12345' }); assert.equal(calls.length, 1);
});
test('missing credentials fail before network access', () => {
  const client = new MusebookClient({ fetch: () => { throw Error('Unexpected fetch'); } });
  for (const run of [() => client.me(), () => client.keyMetadata(), () => client.postFeed('hi'), () => client.linkWallet(address), () => client.prepareAgentAction({ action:'town', name:'Test' })]) assert.throws(run, e => e instanceof MusebookError && e.status === 401);
});
test('unsafe bases, path traversal and incorrect network families are rejected', () => {
  for (const baseUrl of ['file:///tmp/sdk', 'https://user:secret@example.com', 'https://example.com?key=secret', 'https://example.com#fragment']) assert.throws(() => new MusebookClient({ baseUrl }));
  const { client, calls } = mock();
  for (const slug of ['', '.', '..']) assert.throws(() => client.skill(slug));
  assert.throws(() => client.siteLaunches({ network:'solana-mainnet' }));
  assert.throws(() => client.metaplexLaunches({ network:'mainnet' }));
  assert.equal(calls.length, 0);
});
test('credential headers are case-insensitive and absent on public calls', async () => {
  const calls = [], client = new MusebookClient({ apiKey:'mbk_one', headers:{ Authorization:'bad', 'Content-Type':'bad' }, fetch:async (_u, options) => { calls.push(options); return Response.json({ ok:true }); } });
  await client.health({ headers:{ AUTHORIZATION:'bad-again' } }); assert.equal(calls[0].headers.has('authorization'), false);
  await client.postFeed('hi', 'mbk_override'); assert.equal(calls[1].headers.get('authorization'), 'Bearer mbk_override'); assert.equal(calls[1].headers.get('content-type'), 'application/json');
});
test('remote HTTP cannot carry a bearer; localhost remains available', async () => {
  let count = 0; const fetch = async () => { count++; return Response.json({ ok:true }); };
  await assert.rejects(new MusebookClient({ baseUrl:'http://example.com', apiKey:'secret', fetch }).me(), /HTTPS/);
  assert.equal(count, 0);
  await new MusebookClient({ baseUrl:'http://127.0.0.1:8787', apiKey:'secret', fetch }).me(); assert.equal(count, 1);
});
test('redirects never follow or replay a credentialed write', async () => {
  for (const status of [301,302,303,307,308]) {
    const { client, calls } = mock(() => new Response(null, { status, headers:{ location:'https://other.invalid' } }));
    await assert.rejects(client.postFeed('hi'), e => e.status === status && e.body.code === 'REDIRECT_REFUSED'); assert.equal(calls.length, 1); assert.equal(calls[0].redirect, 'manual');
  }
});
test('HTTP errors preserve structured bodies and malformed successful JSON fails closed', async () => {
  for (const status of [400,403,404,409,422,429,503]) {
    const { client, calls } = mock(() => Response.json({ error:'upstream unavailable', code:'TEST' }, { status }));
    await assert.rejects(client.prepareCreatorRewards({ wallet:address }), e => e instanceof MusebookError && e.status === status && e.body.code === 'TEST'); assert.equal(calls.length, 1);
  }
  await assert.rejects(mock(() => new Response('<html>fallback</html>')).client.health(), e => e.body.code === 'INVALID_RESPONSE');
  await assert.rejects(mock(() => new Response('<secret>', { status:502 })).client.health(), e => e.status === 502 && !e.message.includes('<secret>'));
});
test('AgentCard raw JSON, ETag and empty 304 are preserved', async () => {
  const card = { name:'Agent', skills:[], capabilities:{ streaming:false } }, { client, calls } = mock((_url, init) => init.headers.has('if-none-match')
    ? new Response(null, { status:304, headers:{ etag:'"v1"' } })
    : Response.json(card, { headers:{ etag:'"v1"', 'cache-control':'public, max-age=60' } }));
  const first = await client.metaplexAgentCard(address, 'solana-mainnet'); assert.deepEqual(first.card, card); assert.equal(first.status, 200); assert.equal(first.etag, '"v1"');
  const second = await client.metaplexAgentCard(address, 'solana-mainnet', { ifNoneMatch:first.etag }); assert.deepEqual(second, { status:304, card:null, etag:'"v1"', cacheControl:null });
  assert.equal(calls[1].headers.get('if-none-match'), '"v1"');
  await assert.rejects(mock(() => new Response(null, { status:304 })).client.health(), e => e.status === 304);
  await assert.rejects(mock({ data:card }).client.metaplexAgentCard(address, 'solana-mainnet'), /Invalid hosted/);
});
test('reward no-op and unsigned response bodies are returned without mutation', async () => {
  const empty = { ok:true, claimable:false, transactions:[] };
  assert.deepEqual(await mock(empty).client.prepareCreatorRewards({ wallet:address }), empty);
  const result = { success:true, tx:'partially-signed-by-asset', assetAddress:address, blockhash:{ blockhash:address, lastValidBlockHeight:100 } };
  assert.deepEqual(await mock(result).client.prepareMetaplexAgentMint({}), result);
});
test('caller cancellation and timeout abort the request without retry', async () => {
  for (const mode of ['pre', 'during', 'timeout']) {
    const ctrl = new AbortController(); let calls = 0, captured;
    const client = new MusebookClient({ timeoutMs:10, fetch:async (_url, { signal }) => {
      calls++; captured = signal;
      return new Promise((_, reject) => { signal.addEventListener('abort', () => reject(signal.reason), { once:true }); });
    } });
    if (mode === 'pre') ctrl.abort();
    const pending = client.health({ signal:ctrl.signal });
    if (mode === 'during') ctrl.abort();
    await assert.rejects(pending, { name:mode === 'timeout' ? 'TimeoutError' : 'AbortError' });
    assert.equal(calls, mode === 'pre' ? 0 : 1); if (captured) assert.equal(captured.aborted, true);
  }
});
test('timeout also covers reading the response body', async () => {
  const client = new MusebookClient({ timeoutMs:10, fetch:async (_url, { signal }) => ({ status:200, ok:true, json:() => new Promise((_, reject) => signal.addEventListener('abort', () => reject(signal.reason), { once:true })) }) });
  await assert.rejects(client.health(), { name:'TimeoutError' });
});
test('site data methods route to the indexer, snapshot, launches feed and GitHub catalogs', async () => {
  const { client, calls } = mock({ ok: true, agents: [], events: [] });
  await client.agentIndexerFeed(2);
  assert.equal(calls.at(-1).url, 'https://musebook.trade/api/agents/solana?page=2');
  await client.directorySnapshot();
  assert.equal(calls.at(-1).url, 'https://musebook.trade/live/agents.json');
  await client.launchesFeed();
  assert.equal(calls.at(-1).url, 'https://musebook.trade/api/launches/feed');
  await client.skillHubCatalog();
  assert.equal(calls.at(-1).url, SKILLHUB_CATALOG_URL);
  await client.agentsCatalog();
  assert.equal(calls.at(-1).url, AGENTS_CATALOG_URL);
  for (const call of calls) assert.equal(call.headers.get('authorization'), null);
  assert.throws(() => client.agentIndexerFeed(0), RangeError);
  assert.throws(() => client.skillHubCatalog({ catalogUrl: 'file:///etc/passwd' }), TypeError);
});

test('indexer 503 surfaces as AgentIndexerUnavailableError, other errors stay generic', async () => {
  const down = mock(() => Response.json({ error: 'agent_indexer_unavailable', coverage: 'Metaplex Agent Registry' }, { status: 503 }));
  await assert.rejects(down.client.agentIndexerFeed(), e => e instanceof AgentIndexerUnavailableError && e instanceof MusebookError && e.status === 503 && e.coverage === 'Metaplex Agent Registry');
  const broken = mock(() => Response.json({ error: 'something else' }, { status: 503 }));
  await assert.rejects(broken.client.agentIndexerFeed(), e => e instanceof MusebookError && !(e instanceof AgentIndexerUnavailableError));
});

test('social client reads are public and writes carry only an explicit session', async () => {
  const calls = [];
  const social = new MusebookSocialClient({ fetch: async (url, init) => {
    calls.push({ url, ...init, body: init.body ? JSON.parse(init.body) : undefined });
    return Response.json({ ok: true });
  } });
  await social.health();
  assert.equal(calls.at(-1).url, 'https://socialapi.musebook.trade/healthz');
  await social.profile(address);
  assert.equal(calls.at(-1).url, `https://socialapi.musebook.trade/api/profile/${address}`);
  await social.profiles([address]);
  assert.equal(calls.at(-1).url, `https://socialapi.musebook.trade/api/profiles?wallets=${address}`);
  await social.followingFeed({ wallet: address });
  assert.equal(calls.at(-1).url, `https://socialapi.musebook.trade/api/feed/following?wallet=${address}`);
  for (const call of calls) assert.equal(call.headers.get('authorization'), null);
  assert.throws(() => social.createPost('hi'), e => e instanceof MusebookError && e.status === 401);
  assert.throws(() => social.followingFeed(), e => e instanceof MusebookError && e.status === 401);
  assert.throws(() => social.profiles([]), RangeError);
  const sessioned = new MusebookSocialClient({ sessionToken: 'tok', fetch: async (url, init) => { calls.push({ url, ...init, body: init.body ? JSON.parse(init.body) : undefined }); return Response.json({ ok: true }); } });
  await sessioned.createPost('hello');
  assert.equal(calls.at(-1).url, 'https://socialapi.musebook.trade/api/posts');
  assert.deepEqual(calls.at(-1).body, { content: 'hello' });
  assert.equal(calls.at(-1).headers.get('authorization'), 'Bearer tok');
  await sessioned.follow(address, 'override');
  assert.equal(calls.at(-1).headers.get('authorization'), 'Bearer override');
  await sessioned.challenge(address);
  assert.equal(calls.at(-1).headers.get('authorization'), null);
});

test('abort listeners are removed on successful, invalid-timeout and failed requests', async () => {
  let adds = 0, removes = 0; const controller = new AbortController();
  const signal = { get aborted() { return controller.signal.aborted; }, addEventListener(...args) { adds++; controller.signal.addEventListener(...args); }, removeEventListener(...args) { removes++; controller.signal.removeEventListener(...args); } };
  await mock().client.health({ signal }); assert.equal(adds, removes);
  await assert.rejects(mock().client.health({ signal, timeoutMs:0 })); assert.equal(adds, removes);
  await assert.rejects(mock(() => { throw Error('network'); }).client.health({ signal })); assert.equal(adds, removes);
});
