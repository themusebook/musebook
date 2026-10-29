# Hugging Face Hub Skill

Publish artifacts (papers, PDFs, datasets, model cards) to the Hugging Face Hub
under the authenticated namespace.

## Auth

Uses the stored `custom.huggingface` connector via the dynamic-credential
surrogate from `/opt/hatch/skills/skill-creator/bin/dynamic_credentials.py`
(never a raw token in chat, env files, or logs). The surrogate is passed as
the `Authorization: Bearer` header to `https://huggingface.co/api/...`.

## Tools

`bin/hf_publish.py` — create a repo (default: public dataset repo) and upload
files to it.

```
# Verify identity
bin/hf_publish.py --whoami

# Create a public dataset repo and upload the whitepaper PDF + README
bin/hf_publish.py --repo clawd-agentic-layer-whitepaper --type dataset \
    --upload ~/path/to/file.pdf:file.pdf --upload README.md:README.md
```

Flags:
- `--whoami` — print authenticated username only, then exit.
- `--repo NAME` — repo slug (created under the authenticated namespace).
- `--type {dataset,model,space}` — Hub repo type (default: `dataset`).
  Use `dataset` for paper/document artifacts; Paper Pages still require arXiv.
- `--private` — create a private repo (default is public).
- `--upload LOCAL:REMOTE` — repeatable; uploads local file to the repo path.

The script never prints the credential. Failures raise with the HTTP status
and the Hub's error body (truncated).

## Binary files (PDFs etc.)

The Hub rejects binary files in regular commits; they must go through LFS:

1. Compute `sha256` + size of the file.
2. `POST https://huggingface.co/{type}s/{ns}/{repo}.git/info/lfs/objects/batch`
   with `{"operation":"upload","transfers":["basic"],"ref":{"name":"refs/heads/main"},"objects":[{"oid":sha,"size":n}]}`
   (headers: `Authorization: Bearer`, `Accept: application/vnd.git-lfs+json`).
3. `PUT` the raw bytes to the returned `actions.upload.href` (pre-signed; no auth header).
4. NDJSON commit to `POST /api/{type}s/{ns}/{repo}/commit/main`
   (`Content-Type: application/x-ndjson`), one JSON object per line:
   - `{"key":"header","value":{"summary":"...","description":"..."}}`
   - `{"key":"lfsFile","value":{"path":"<repo path>","algo":"sha256","oid":sha,"size":n}}`
   - text files can ride along as `{"key":"file","value":{"content":"<base64>","path":"...","encoding":"base64"}}`
