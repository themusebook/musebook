# Supermemory skill

Supermemory (supermemory.ai) is the memory layer. Use it to search past
memories and ingest content worth remembering, scoped to one containerTag
at a time. Tags never cross-query.

## Client

`bin/sm.py` — authenticated with the stored `custom.supermemory` connector
(Bearer header on `api.supermemory.ai`). Auth goes through
`dynamic_credentials.add_surrogate_to_request`; urllib only.

(`--tag` and `--compact` go before the subcommand)

```
sm.py --tag T search --q "..." [--limit N] [--mode memories|documents]
sm.py docs --q "..." [--limit N]          # shared superrag docs (musebook:docs)
sm.py --tag T add --content "..." [--custom-id ID] [--metadata '{...}']
echo "..." | sm.py --tag T add --stdin
sm.py --tag T profile
```

## Container tags

| Tag | Use |
| --- | --- |
| `musebook:operator` | Clawd↔operator memory — default for agent-side work |
| `musebook:visitor:<uuid>` | site chat visitors |
| `musebook:agent:<agent_id>` | first-party API agents |
| `musebook:docs` | shared reference docs (superrag) |

Tag format: `^[a-zA-Z0-9_:-]+$`, max 100 chars. Always pass a tag explicitly
when the work is agent- or visitor-scoped; default is `musebook:operator`.

Gotcha (verified 2026-09-18): `POST /v3/documents/documents` only honors the
`containerTags` **plural** array filter. The singular `containerTag` is
silently ignored and the endpoint returns every container's documents — a
cross-tag leak if served publicly. Always use `containerTags: [<tag>]` and
re-check `document.containerTags` / `memory.spaceContainerTag` in code.

## Jev ↔ Supermemory loop

TypeSafe's Jev gives fast typed judgments; Supermemory gives them history.
Combine them in this order:

1. **Recall**: `sm.py search --q "<task>" --tag musebook:operator` for relevant
   memories before asking Jev.
2. **Enrich**: fold the top hits into the Jev `state` so the judgment sees
   past context, not just the current input.
3. **Judge**: ask Jev (`../typesafe-ai/bin/jev.py`) as usual — choice / score /
   noul, confidence-gated routing.
4. **Remember**: `sm.py add` the judgments worth keeping (decisions, routing
   outcomes, corrections) back under `musebook:operator` with
   `--metadata '{"source":"jev-loop"}'` so the next loop recalls them.

Keep judgments narrow and atomic; ingest only what future judgments would
benefit from. Never ingest secrets, raw keys, or credential values.
