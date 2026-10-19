# SecureTrace Architecture

> Structure document (pragmatic-programmer guard: keep this in sync with the
> code). Module map, gate architecture, and the mapping from DoW/DoD RMF
> requirements to this repository's artifacts.

## 1. Module map

```
src/securetrace/
├── __init__.py            # __version__, package docstring
├── __main__.py            # console entry: `securetrace …` argparse dispatch into cli
├── cli.py                 # B3 — subcommands, I/O, messages, exit codes (0/1/2)
├── errors.py              # B3 — typed errors (FormatError et al.) shared by subpackages
├── py.typed               # PEP 561 marker
├── backlog/               # B3 — deterministic backlog parsing/indexing (pure core)
│   ├── __init__.py
│   └── index.py           # marker scan, delta, idempotent TSV rewrite (format: frozen)
├── lessons/               # B3 — lessons-learned record management (pure core)
│   ├── __init__.py
│   └── record.py          # entry lifecycle (add/supersede/sync/check)
├── algorithms/            # B3 — algorithm document registry management (pure core)
│   ├── __init__.py
│   └── registry.py        # INDEX.md row ↔ document consistency
├── rmf/                   # B4 — RMF deliverable (package) generation
│   ├── __init__.py
│   └── deliverables.py    # SSP/SAP/SAR/POA&M scaffolds + evidence bundles
└── pipeline/              # CI/CD gate orchestration helpers
    ├── __init__.py
    └── gates.py           # gate definitions shared by hooks/Makefile/CI consumers
```

Tests mirror 1:1: `tests/<subpkg>/test_<module>.py` for the pure core, `tests/test_cli.py`
for the CLI surface (messages + exit codes), and `tests/test_package.py` for the
package itself. `tests/scripts/test_skill_scripts.py` pins the frozen CLI surface of
the thin `scripts/` wrappers against the skill's reference behavior.

**Naming distinction (important):** `algorithms/` (repo root) holds
*algorithm documents* per the `@algorithm-records-keeper` skill;
`src/securetrace/algorithms/` holds the *code* that manages those documents.
They are related but different artifacts — never merge them.

## 2. Gate architecture

One definition of every gate, three enforcement points:

```
            ┌────────────┐  thin wrappers   ┌─────────────────────┐
 hooks/ ───▶│  Makefile  │◀─────────────────│ .github/workflows/  │
 (git)      └─────┬──────┘                  │ ci.yml / release.yml│
                  │                         └─────────────────────┘
                  ▼
   scripts/  (index checks, changed-test mapping)
   .venv     (pinned, hashed deps: ruff, pytest, pip-audit, cyclonedx-py, build)
```

| Gate stage | pre-commit | pre-push | CI quality | CI security |
|---|---|---|---|---|
| format-check (ruff) | ✔ | — | ✔ | — |
| lint (ruff) | ✔ | — | ✔ | — |
| docs-check (backlog/lessons/algorithms indexes) | ✔ | — | ✔ | — |
| gitleaks | staged | full history | — | full history (action) |
| tests | changed-modules | full suite | full suite | — |
| compileall | — | ✔ | ✔ | — |
| pip-audit | — | — | — | ✔ |
| SBOM (CycloneDX) | — | — | — | ✔ |

Invariants:

1. **No bypass** — hooks are committed (`hooks/`, wired via `core.hooksPath`);
   a gate failure blocks commit/push/CI, full stop.
2. **Frozen index formats** — the TSV index blocks in `BACKLOG.md`,
   `LESSONS_LEARNED.md`, `algorithms/*.md` are the contract between the
   `scripts/` wrappers, the `securetrace` package API (B3), and CI.
   Roundtrip tests in `tests/scripts/` plus the package tests pin the behavior.
3. **Vendored skill scripts** — `scripts/{backlog_index,manage_lessons,algorithm_index}.py`
   were vendored from `~/.lmstudio/skills/…` (provenance in docstrings) so that
   hooks and CI never depend on machine-local paths; B3 turned them into thin
   wrappers over `securetrace.cli`, preserving the exact CLI surface, messages,
   and exit codes. See LESSONS_LEARNED.md LLT-0002.
4. **Pinned, hashed dependencies** — `requirements*.in` → `pip-compile
   --generate-hashes` → `requirements*.txt`; CI installs with `--require-hashes`.
5. **Conventional Commits** enforced locally (commit-msg) — release workflow
   triggers on `v*` tags only.

## 3. DoW/DoD RMF mapping

Full requirements + sources: [`docs/dow-requirements.md`](docs/dow-requirements.md).

| Requirement (source) | Implemented by | Status |
|---|---|---|
| RMF 7 steps, NIST SP 800-37 (DoDI 8510.01) | `securetrace.rmf` deliverable scaffolds (B4) | planned |
| **Assess Only** evidence for software below system level (DoDI 8510.01) | dated, deterministic evidence bundles from CI state (B4) | planned |
| SSP / SAP / SAR / POA&M | `securetrace.rmf` renderers with control→evidence mapping asserted in tests (B4) | planned |
| SWP ≤ 6-month increments, cATO / speed-of-relevance (DoDI 5000.87 + integration guidance) | tag-triggered release pipeline regenerating evidence per release (B1/B4/B5) | B1 done, B4/B5 planned |
| DevSecOps discipline (SSDF SP 800-218) | this repo's own gates as reference implementation (B1) | done |
| Deterministic process records (SWP QC expectation) | BACKLOG.md, LESSONS_LEARNED.md, algorithms/ (B1) | done |
| Supply-chain evidence | pinned hashed lockfiles + per-run and per-release SBOM (B1) | done |

## 4. Data flow (target, B4)

```
CI state (gate results, pip-audit, SBOM) ─┐
BACKLOG.md (work + evidence)            ─┼─▶ securetrace rmf build ─▶ evidence bundle (dated)
algorithms/ (design records)            ─┤         │
LESSONS_LEARNED.md (QC history)         ─┘         ├─▶ SSP / SAP / SAR / POA&M
                                                    └─▶ artifacts/rmf/<date>/ (release)
```

## 5. Release pipeline (keyless signing + provenance, B5)

Tag-triggered (`v*`) — `.github/workflows/release.yml`. Every published
artifact (wheel, sdist) carries two independent attestation layers, both
verified in-pipeline **before** the release is created (fail-fast: a
tampered or foreign artifact can never be published). The release itself is
an **immutable release** (repo setting enabled via
`PUT /repos/mirph-glitch42/SecureTrace/immutable-releases`): the tag is
locked to the commit, assets cannot be modified or deleted after publication,
and GitHub auto-generates a signed **release attestation** (tag + commit SHA
+ asset digests) at creation time.

```
make package ─▶ dist/*.whl, dist/*.tar.gz ─┬─▶ cosign sign-blob ─▶ <artifact>.sigstore.json
                                          │      (keyless: Fulcio OIDC cert + Rekor entry)
                                          └─▶ actions/attest  ─▶ SLSA v1 provenance attestation
                                               (Sigstore public instance;        (one attestation,
                                                stored in GitHub attestation      both subjects;
                                                registry keyed by digest;         local bundle
                                                local bundle also published)     also published)
                                                    │
                  verify (identity-pinned, both) ──┘
                    cosign verify-blob  --bundle <artifact>.sigstore.json
                                        --certificate-identity=https://github.com/mirph-glitch42/SecureTrace/.github/workflows/release.yml@refs/tags/<tag>
                                        --certificate-oidc-issuer=https://token.actions.githubusercontent.com
                    gh attestation verify <artifact> -R mirph-glitch42/SecureTrace
                                        --signer-workflow mirph-glitch42/SecureTrace/.github/workflows/release.yml
                                                    │
                                                    ▼
                    gh release create (immutable) ─▶ auto release attestation
                    gh release verify <tag>          (consumer-side proof, in-pipeline)
                    gh release verify-asset <tag> <artifact>
```

- **Identity:** keyless — no long-lived key. The signer is the workflow's
  GitHub OIDC identity (ephemeral Fulcio certificate, Rekor transparency
  entry). Verification pins certificate identity (repo + workflow + tag ref)
  **and** OIDC issuer, so a signature produced by any other workflow, repo,
  or CI fails. The SLSA attestation is separately verified against a
  fully-anchored SAN pin on the exact workflow file (gh CLI policy; note
  `--signer-workflow` and `--signer-repo` are mutually exclusive in that
  policy — the workflow pin is the stronger one).
- **Pinned toolchain:** `sigstore/cosign-installer` @ commit
  `6f9f17788090df1f26f669e9d70d6ae9567deba6` (v4.1.2) with
  `cosign-release: v2.6.5` (supported v2 series; the installer input name is
  `cosign-release`, and the installer itself verifies the cosign binary
  against the Sigstore release key before use); `actions/attest` @ commit
  `1e69f48acb82d1966a394da916b4c1698aa569d6` (v4, provenance mode,
  multi-subject). Least privilege:
  `permissions: contents: write, id-token: write, attestations: write`
  (a scope may appear only once in the mapping; `write` covers `read`).
- **Consumer recipe** (stock tools, no SecureTrace dependency):
  1. `gh release verify v0.1.0` — release is immutable + valid release
     attestation present; prints all attested asset digests.
  2. `gh release verify-asset v0.1.0 <artifact>` — downloaded asset exactly
     matches the attested release asset (digest + signature).
  3. `cosign verify-blob <artifact> --bundle <artifact>.sigstore.json \
     --certificate-identity https://github.com/mirph-glitch42/SecureTrace/.github/workflows/release.yml@refs/tags/<tag> \
     --certificate-oidc-issuer https://token.actions.githubusercontent.com`
  4. `gh attestation verify <artifact> -R mirph-glitch42/SecureTrace \
     --signer-workflow mirph-glitch42/SecureTrace/.github/workflows/release.yml`
     (online: fetches the attestation for the artifact's digest from the
     GitHub attestation registry).

## 6. Non-goals

- No network access in library code (stdlib-only runtime; RMF bundles build
  offline from local artifacts).
- No secrets, ever — see `.gitleaks.toml`, hooks, and CI security job.
- Not an ATO authority: SecureTrace assembles *evidence*; authorization is a
  human (AO/DA) decision.
