# Post-Trade Reporting

> Pull execution reports from the Get Order endpoint to build post-trade dashboards, reconcile fee revenue, and measure execution quality.

After an order executes, `GET /orders/{orderId}` returns the full execution report: fill prices, fees earned, gas costs, venue routing, and onchain confirmation status.

## Order-level summary (`order.filled`)

| Field                         | Description                                                     |
| ----------------------------- | --------------------------------------------------------------- |
| `filled.averagePrice`         | Average execution price across all fills, in contra asset units |
| `filled.averageNotionalPrice` | Average execution price in USD                                  |
| `filled.targetAmount`         | Total target asset filled                                       |
| `filled.contraAmount`         | Total contra asset filled                                       |

## Per-fill detail (`fills` array)

Each entry = one execution event. For TWAP, each time slice produces its own fill; otherwise typically one fill per order.

**Pricing and amounts:** `fillPrice`, `targetAmount`, `contraAmount`, `notional` (USD).

**Fee breakdown** (in the fee token unless noted):

| Field                   | Description                                    |
| ----------------------- | ---------------------------------------------- |
| `feeAmount`             | Total fee (platform + network + integrator fee) |
| `feeTicker`             | Token the fee is denominated in                |
| `tradeFeeAmount`        | Definitive's platform fee (excludes your fee)  |
| `networkFeeAmount`      | Gas/network portion                            |
| `integratorFeeAmount`   | Your integrator fee (`"0"` if none)            |
| `feeNotional`           | Total fee in USD                               |
| `tradeFeeNotional`      | Definitive's platform fee in USD                |
| `networkFeeNotional`    | Gas cost in USD                                |
| `integratorFeeNotional` | Your integrator fee in USD                     |

**Execution metadata:** `venues` (DEXs/liquidity sources), `transactionId` (onchain tx hash), `filledAt`, `status` (onchain confirmation status).

## Common use cases

- **Revenue tracking:** sum `integratorFeeNotional` across fills for total earnings in USD. That fee routes to your Definitive vault.
- **Execution quality:** compare `filled.averageNotionalPrice` vs quote price for realized slippage; inspect `venues` per fill.
- **Gas cost accounting:** `networkFeeNotional` per fill.
- **TWAP analysis:** each slice has its own `fillPrice`, `filledAt`, `venues` — chart execution across the TWAP window.

References: [Get Order endpoint](/docs/api-reference/flash/get-order), [Monetize Your Integration](/docs/monetizing-your-integration).
