# Algorithm Registry

> One row per algorithm document in this directory. Keep sorted by slug.
> Update the row in the **same change** that changes the document (G8/G9).
> Status values: `draft` · `implemented` · `backfilled` · `deprecated`.

| Slug | Name | Version | Status | File | One-line summary |
|---|---|---|---|---|---|
| `deterministic-doc-pipeline` | Deterministic Document Pipeline (canonical store → pure render → integrity verify) | 0.1.3 | `draft` | [deterministic-doc-pipeline.md](deterministic-doc-pipeline.md) | Store-as-truth + pure renderer + sha256 integrity check: the three pipeline docs become a function of canonical-JSON data; out-of-band edits are diagnosed, not just detected (B10) |
| `lessons-record` | Lessons Record (append-only entry log with a derived self-describing TSV index) | 0.1.4 | `backfilled` | [lessons-record.md](lessons-record.md) | Append-only `LLT-NNNN` lesson log with closed vocabularies, bidirectional supersession, derived index, and the 0/1/2 exit model |
| `line-index-sync` | Line-Index Sync (marker scan, delta computation, idempotent TSV rewrite) | 0.1.3 | `backfilled` | [line-index-sync.md](line-index-sync.md) | Self-describing TSV index blocks: one constant delta puts every reported line number in post-rewrite coordinates; `sync` idempotent, `check` detects drift (exit 1) |
| `rmf-evidence-bundle` | RMF Evidence Bundle (deterministic collection, control mapping, rendering, packaging) | 0.2.0 | `implemented` | [rmf-evidence-bundle.md](rmf-evidence-bundle.md) | Fixed 11-control catalog + explicit evidence corpus → deterministic SSP/SAP/SAR/POA&M bundles + canonical manifest from repo state (zero network, byte-identical reruns); pinned CLI/Makefile contract |
| `workflow-yaml-strict-parse` | Workflow-YAML Strict Parse (duplicate mapping-key detection for CI workflows) | 0.2.0 | `implemented` | [workflow-yaml-strict-parse.md](workflow-yaml-strict-parse.md) | One-pass `StrictLoader` hard-fails duplicate mapping keys (block + flow, any depth) with 1-based line of the second occurrence; 0/1/2 exit contract — closes the local-vs-GitHub parser tolerance gap (LLT-0017/LLT-0018) |

## Rules

1. Add a row when a document is created; never delete a row (mark `deprecated` instead).
2. The `File` link is the canonical location — no copies elsewhere in the repo.
3. `Version` must equal the document's `METADATA` version (CI can assert this).
4. Backfilled rows keep `Status: backfilled` permanently as a provenance marker; behavioral changes do not remove it.
5. CI check: every `algorithms/*.md` (except `INDEX.md`) has exactly one row, and every row points at an existing file.
