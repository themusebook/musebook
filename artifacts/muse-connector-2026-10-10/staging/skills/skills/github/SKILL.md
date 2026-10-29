---
name: github
description: Call the GitHub REST API with the user's stored credential (surrogate-authenticated, token never read). Create repos, push files via the Git Data API, manage issues/PRs.
version: 1.0.0
---

# GitHub skill

`bin/gh_api.py METHOD /path [payload.json|-]` — surrogate-authenticated GitHub REST API caller.
Auth goes through the `custom.github` credential via authd; the token is never read or printed.

## Examples

Who am I: `bin/gh_api.py GET /user | python3 -c "import json,sys; u=json.load(sys.stdin); print(u['login'])"`

Create an org repo: `echo '{"name":"my-repo","public":true,"description":"..."}' | bin/gh_api.py POST /orgs/MYORG/repos -`
(Falls back to `POST /user/repos` when org creation is not permitted.)

Push a whole directory as the initial commit (Git Data API, preserves exec bits):
1. `bin/gh_api.py POST /repos/{o}/{r}/git/blobs` per file: `{"content":"<base64>","encoding":"base64"}` -> sha
2. `bin/gh_api.py POST /repos/{o}/{r}/git/trees`: `{"tree":[{"path":"...","mode":"100644","type":"blob","sha":"..."}]}` (use `100755` for executables)
3. `bin/gh_api.py POST /repos/{o}/{r}/git/commits`: `{"message":"...","tree":"<tree_sha>"}`
4. `bin/gh_api.py POST /repos/{o}/{r}/git/refs`: `{"ref":"refs/heads/main","sha":"<commit_sha>"}`

Verify: `bin/gh_api.py GET /repos/{o}/{r}` and `bin/gh_api.py GET /repos/{o}/{r}/git/trees/main?recursive=1`.

## Rules
- Never print or log the credential. The surrogate exchange handles auth.
- Public repos only unless the user explicitly asks for private.
- Destructive actions (delete repo, force-push) need explicit user approval.
