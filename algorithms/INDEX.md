# Algorithm Registry

> One row per algorithm document in this directory. Keep sorted by slug.
> Update the row in the **same change** that changes the document (G8/G9).
> Status values: `draft` · `implemented` · `backfilled` · `deprecated`.

| Slug | Name | Version | Status | File | One-line summary |
|---|---|---|---|---|---|
| — | — | — | — | — | (no algorithm documents yet; first one lands with B3 or B4) |

## Rules

1. Add a row when a document is created; never delete a row (mark `deprecated` instead).
2. The `File` link is the canonical location — no copies elsewhere in the repo.
3. `Version` must equal the document's `METADATA` version (CI can assert this).
4. Backfilled rows keep `Status: backfilled` permanently as a provenance marker; behavioral changes do not remove it.
5. CI check: every `algorithms/*.md` (except `INDEX.md`) has exactly one row, and every row points at an existing file.
