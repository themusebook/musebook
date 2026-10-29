import { MusebookClient, type PreparedCreatorRewards, type Network } from '@musebook/sdk';
import { MusebookWebMCPClient, type WebMCPReadResults } from '@musebook/sdk/webmcp';

const sdk = new MusebookClient();
const network: Network = 'devnet';
sdk.siteLaunches({ network });
const client = new MusebookWebMCPClient({ inputEncoding: 'json-string' });
const result: Promise<WebMCPReadResults['musebook_wallet_context'] | null> = client.call('musebook_wallet_context', {});
const empty: PreparedCreatorRewards = { ok: true, claimable: false, transactions: [] };
void result; void empty;
// @ts-expect-error CJS declarations retain the read-only tool allowlist.
client.call('musebook_prediction_execute', {});
