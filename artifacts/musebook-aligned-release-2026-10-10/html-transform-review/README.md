# Strict HTML transformation review

`transform-review.json` preserves the actual hashes and time of the reviewed HTML captures and the live checks at 2026-10-10T19:20:11.896507+00:00. It does not relabel those checks as a later release verification.

The four permitted origin/path pairs are the dedicated skill homepage, the canonical `/skill/` page, and the canonical and terminal v0.6 research HTML paths. Only the pinned same-origin WebMCP tag, exact navigation shim, restricted Cloudflare challenge-loader template, and terminal paper email-obfuscation/decoder pair are normalized. The remaining bytes must equal the exact frozen document. Public helper JavaScript must have its reviewed size and SHA-256. All 15 mutation checks reject unknown scripts, origins, paths, changed code or content.

The navigation shim is an exact literal in the preserved Musebook Worker. The WebMCP bridge tag and public payload were verified at three public origins; the captured Musebook Worker contains no injector. The injection mechanism is not independently attributed. Restricted Cloudflare data fields are never executed by the verifier. XOR-decoded email content must restore the original bytes.

`verify_aligned_live.py` and `reviewed_html_transforms.py` are unchanged copies of the reviewed GET/HEAD-only implementation. For a portable run, provide the pinned public Markdown appendix explicitly:

```sh
python3 verify_aligned_live.py \
  --dist-dir <frozen-dist-directory> \
  --canonical-skill-appendix canonical-skill-runtime-appendix.md \
  --output <verification-report.json>
```

The appendix is a public document capture, not private runtime source. Its byte count and checksum are pinned in the verifier and companion JSON. No Worker module, service bindings, credentials, environment values or browser authorization state are included here. Uppercase skill routing and the canonical paper PDF are ordinary exact-byte checks; HTML normalization cannot waive their failures.
