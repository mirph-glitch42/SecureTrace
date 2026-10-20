# SecureTrace

**Agentic tooling for secure, traceable software development.**

SecureTrace manages the artifacts that make *agent-performed programming*
auditable and compliant with US Department of War (DoW) / DoD software
lifecycle requirements:

- **Deterministic agentic backlogs** — one backlog, machine-indexed, staleness-checked
- **Lessons-learned records** — authoritative, indexed, supersession-safe
- **Algorithm description documents** — registry-governed design records
- **CI/CD gate state** — local hooks ⇄ Makefile ⇄ GitHub Actions, one source of truth
- **Architecture documents** — the structure docs that keep agents honest
- **Software RMF package deliverables** — SSP / SAP / SAR / POA&M / ATO evidence,
  built incrementally as the software is developed (Assess Only / cATO model)

## Quickstart

```sh
make setup        # .venv, pinned deps, git hooks
make gate         # full local gate: format → lint → docs → build → test
make help         # every target
```

Requires Python ≥ 3.12 and (for the secret-scanning gates)
[gitleaks](https://gitleaks.com/).

## The gates

| Gate | Where | What runs |
|---|---|---|
| `pre-commit` | local hook | format-check → lint → docs-check → gitleaks (staged) → tests for changed modules |
| `commit-msg` | local hook | Conventional Commits |
| `pre-push` | local hook | compileall → full test suite → gitleaks (full history) |
| CI `quality` | GitHub Actions | `make setup-ci` + format-check, lint, docs-check, build, test |
| CI `security` | GitHub Actions | gitleaks (full history) + `pip-audit` + CycloneDX SBOM |
| Release | GitHub Actions (tag `v*`) | full gate → sdist+wheel → SBOM → GitHub release |

The gate definitions live in the [`Makefile`](Makefile); hooks and workflows are
thin wrappers. **Adding a gate means adding it to all three in the same change.**

## Repository layout

```
├── BACKLOG.md            # work queue — machine-indexed (scripts/backlog_index.py)
├── LESSONS_LEARNED.md    # lessons record — machine-indexed (scripts/manage_lessons.py)
├── algorithms/           # ALGORITHM DOCUMENTS (registry INDEX.md + <slug>.md docs)
├── src/securetrace/      # CODE (backlog/ lessons/ algorithms/ rmf/ pipeline/)
├── scripts/              # gate + index scripts used by hooks/Makefile/CI
├── hooks/                # git hooks (wired via core.hooksPath)
├── tests/                # 1:1 mirror of src/securetrace + tests/scripts
├── docs/                 # requirements & design documents (dow-requirements.md, …)
├── skills/securetrace/   # agent-facing usage guide for this toolset (SKILL.md)
├── .github/workflows/    # ci.yml, release.yml (SHA-pinned actions)
└── Makefile              # the single gate entrypoint
```

Note the deliberate split: `algorithms/` holds algorithm *documents*;
`src/securetrace/algorithms/` holds the code that manages them.

## Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) — module map, gate architecture, DoW RMF mapping
- [docs/dow-requirements.md](docs/dow-requirements.md) — DoW/DoD RMF + Software
  Acquisition Pathway requirements (the "why" of this project)
- [BACKLOG.md](BACKLOG.md) — what is being built, in what order, with evidence
- [LESSONS_LEARNED.md](LESSONS_LEARNED.md) — what went wrong and the correct fix
- [skills/securetrace/SKILL.md](skills/securetrace/SKILL.md) — the agent-facing
  usage guide: CLI, `scripts/` wrappers, gates, document contracts, RMF
  bundles (kept current by `tests/test_skill_doc.py`)

## License

[MIT](LICENSE) — see [LICENSE](LICENSE).
