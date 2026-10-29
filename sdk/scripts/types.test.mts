import { MusebookClient, MusebookSocialClient, type MetadataActionInput, type RwaPlan, type PreparedCreatorRewards, type AgentIndexerFeed, type DirectorySnapshot, type SocialProfile } from '@musebook/sdk';
import { MusebookWebMCPClient } from '@musebook/sdk/webmcp';

const sdk = new MusebookClient();
const controller = new AbortController();
sdk.skills({ signal: controller.signal });
sdk.agentIndexerFeed(1).then(feed => { const stale: boolean = feed.stale; const slot: number = feed.slot; void stale; void slot; });
const feedShape: AgentIndexerFeed['agents'][number]['assetSigner'] = 'signer';
void feedShape;
sdk.directorySnapshot().then((snapshot: DirectorySnapshot) => snapshot.agents[0]?.update_authority);
sdk.launchesFeed().then(feed => feed.events[0]?.marketCapSol);
sdk.skillHubCatalog().then(skills => skills[0]?.category);
sdk.agentsCatalog().then(catalog => catalog.agents[0]?.identifier);
const social = new MusebookSocialClient();
social.profile('wallet').then((profile: SocialProfile) => profile.agent?.asset_id);
social.followingFeed({ wallet: 'wallet' });
// @ts-expect-error Social writes require a session token argument or a configured client token.
social.createPost('hello', 42);
sdk.postFeed('hello', 'mbk_test', { requestId: 'post_12345', signal: controller.signal });
sdk.metaplexLaunches({ network: 'solana-devnet', spotlight: false });
sdk.siteLaunches({ network: 'devnet' });
sdk.prepareAgentAction({ action: 'trade', inputMint: 'mint', outputMint: 'other', amount: '0.000000001', slippageBps: 50 });
sdk.prepareMetadataAction('mint', { action: 'burn', wallet: 'owner', network: 'devnet', token: 'ata', amount: '1' });
sdk.das({ method: 'searchAssets', params: { ownerAddress: 'owner', interface: 'MplCoreAsset', limit: 5 } }, 'devnet');
sdk.metaplexAgentCard('address', 'solana-devnet', { ifNoneMatch: '"v1"' }).then(result => {
  if (result.status === 304) { const card: null = result.card; void card; }
  else { const name: string = result.card.name; void name; }
});
function planOnly(plan: RwaPlan) { const executionAllowed: false = plan.execution.allowed; return executionAllowed; }
function rewards(result: PreparedCreatorRewards) { return result.claimable ? result.blockhash.blockhash : result.transactions; }
void planOnly; void rewards;
const web = new MusebookWebMCPClient();
web.call('musebook_wallet_context', {}).then(result => { if (result) { const address: string | null = result.address; void address; } });
web.call('musebook_site_launches', { network: 'mainnet', kind: 'agent' });
// @ts-expect-error Different API families deliberately use different network enums.
sdk.metaplexLaunches({ network: 'devnet' });
// @ts-expect-error Chain network is not a Metaplex REST network string.
sdk.siteLaunches({ network: 'solana-mainnet' });
// @ts-expect-error Exact trade amounts are decimal strings.
sdk.prepareAgentAction({ action: 'trade', inputMint: 'a', outputMint: 'b', amount: 0.1, slippageBps: 50 });
// @ts-expect-error Burn requires the exact token account and amount.
const invalid: MetadataActionInput = { action: 'burn', wallet: 'owner', network: 'devnet' };
void invalid;
// @ts-expect-error SDK WebMCP entry point does not expose financial execution.
web.call('musebook_execute_swap', { requestId: 'quote' });
// @ts-expect-error No arbitrary RPC forwarding through DAS.
sdk.das({ method: 'sendTransaction', params: {} }, 'devnet');
