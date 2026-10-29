# Clawd Research relay verification — October 3, 2026

Production endpoint: https://musebook.trade/mcp-research
Server version: 1.2.0
Worker deployment: af87bd1f-8b2b-46bc-b5fb-f9030026e043

- Local and production initialization succeeded.
- Fourteen tools advertise output schemas.
- stream_launches opened wss://clawd-ws.fly.dev/ws and received 55 observations during each five-second verification sample.
- render_clawd_launches preserved the returned structured sample.
- resources/read returned ui://clawd-research/launches-v1.html with the visible https://clawd-ws.fly.dev/ link.
- Sampling duration 26 seconds was rejected.
- Four existing relay tests passed; Worker dry-run build passed.
- A browser host harness rendered all 55 observations, the exact source link, retrieval time and refresh button. The button completed a bridge roundtrip using the captured sample; this is not an actual ChatGPT session.
- Version 1.2.0 ZIP rebuilt at plugins/releases/clawd-research-plugin.zip with metadata, skill, cases and output schemas.

The copied server_instructions warning is a generic review finding. The original live instructions were valid and did not contain the warning text. Updated instructions now specify sampling then rendering and distinguish observations from verified receipts. Only a fresh portal review can establish whether the finding clears. No submission or approval was performed.

Official references:
https://developers.openai.com/plugins/deploy/app-review
https://developers.openai.com/plugins/deploy/submission
