# Clawd Chart Agent

Read chart images and score chart setups. Muse itself reads the chart (vision) and returns a structured read: trend, pattern, key levels, momentum, and risk flags. Built as the local companion to the [Clawd Spark Chart Agent Space](https://huggingface.co/spaces/ordlibrary/clawd-spark-chart-agent).

## When to use

User shares or links a price chart image (token, perp, any market) and wants a chart read: "read this chart", "is this chart a gem", "check this setup".

## Workflow

1. **Get the image.** Attached images are already in context — skip to step 2. For a URL:
   ```
   python3 bin/fetch_chart.py --url <image_url> [--name <label>]
   ```
   Saves to `~/workspace/chart-agent/charts/<label>-<ts>.png` and prints the path.

2. **Read it.** Open the file with `muse.read` so the image lands in model context. Read candlesticks, volume bars, axes, and any overlaid indicators.

3. **Score the setup.** Evaluate each axis below and produce the verdict block. Everything is pattern/structure reading — **research only, never buy/sell advice**.

   - **Trend structure** — higher highs / higher lows vs lower highs / lower lows; where price sits vs obvious moving averages.
   - **Pattern** — flag, triangle, range, breakout, breakdown, rounded top/bottom, V-recovery, chop.
   - **Key levels** — horizontal support/resistance with number of touches; round-number magnets.
   - **Volume** — expansion on up moves vs down moves; climax or drying up; divergence from price.
   - **Momentum** — RSI/MACD if visible; otherwise candle-body strength, wick ratio, consecutive closes.
   - **Risk flags** — parabolic vertical move, thin/gappy volume, no pullback, long upper wicks into resistance, breakdown below support with volume, low timeframe only.

4. **Verdict block.** Reply with this exact structure:

   ```
   📊 Chart read: <label/symbol>
   Trend: <uptrend/downtrend/range/chop> — <one line of evidence>
   Pattern: <pattern> — <one line>
   Key levels: support <…>, resistance <…>
   Volume: <read>
   Momentum: <read>
   Risk flags: <list or "none obvious">
   Setup quality: <0-100>/100 — <one-line rationale>
   Note: research only, not financial advice.
   ```

   Setup quality rubric: 80+ clean trend + breakout/hold with volume; 60–79 constructive but needs confirmation; 40–59 mixed/choppy; below 40 breakdown or high-risk structure. Never phrase as "buy this".

## Guardrails

- One chart per read. If the image is unreadable (blurry, cropped axes, no scale), say so and ask for a better capture instead of guessing.
- Do not invent numbers: if axis labels are illegible, describe structure qualitatively.
- Never give buy/sell recommendations, price targets as advice, or leverage suggestions. "Gem" talk = setup-quality scoring, framed as research.
- For pump.fun / low-liquidity tokens, always flag holder concentration and rug risk alongside any chart read.

## Files

- `bin/fetch_chart.py` — download a chart image URL to the local cache and print the path.
- Charts cache: `~/workspace/chart-agent/charts/` (created on demand).
