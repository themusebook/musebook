import { MusebookClient, PREDICTION_USDC, type PredictionOrderInput, type PredictionPage } from '../src/index.js';

const uncountedPage: PredictionPage<unknown> = { data: [], pagination: { start: 0, end: 5, hasNext: true } };
void uncountedPage;

const client = new MusebookClient();
const buy: PredictionOrderInput = { ownerPubkey: 'owner', marketId: 'market', isBuy: true, isYes: true, depositAmount: '5000000', depositMint: PREDICTION_USDC };
const sell: PredictionOrderInput = { ownerPubkey: 'owner', positionPubkey: 'position', isBuy: false, isYes: false, contractsDecimal: '1.234567' };
void client.predictionBuildOrder(buy);
void client.predictionBuildOrder(sell);
// @ts-expect-error A wallet owner is required for account lists.
void client.predictionPositions({ start: 0, end: 5 });
// @ts-expect-error Exact deposits must be strings, never floats.
void client.predictionBuildOrder({ ...buy, depositAmount: 5000000 });
// @ts-expect-error Only one sell quantity is allowed.
void client.predictionBuildOrder({ ...sell, contractsMicro: '1234567' });
// @ts-expect-error Unknown trading-status query fields are not supported.
void client.predictionTradingStatus({ network: 'devnet' });
