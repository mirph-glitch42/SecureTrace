# Security Assessment Report (SAR)

## 1. Summary

- Controls assessed: 11
- Satisfied: 11
- Not satisfied: 0
- Git HEAD: `no-git`

## 2. Control results

| Control | Title | Evidence | Result |
|---|---|---|---|
| ST-01 | Deterministic work records (backlog) | `BACKLOG.md` | SATISFIED |
| ST-02 | Quality-control / lessons history | `LESSONS_LEARNED.md` | SATISFIED |
| ST-03 | Algorithm / design records | `algorithms/INDEX.md`, `algorithms/fixture.md` | SATISFIED |
| ST-04 | Architecture & requirements traceability | `ARCHITECTURE.md`, `docs/dow-requirements.md` | SATISFIED |
| SC-01 | Pinned, hashed dependency manifests | `requirements.in`, `requirements-dev.in`, `requirements.txt`, `requirements-dev.txt` | SATISFIED |
| SC-02 | Secret-scanning policy & hooks | `.gitleaks.toml`, `hooks/pre-commit`, `hooks/pre-push` | SATISFIED |
| CI-01 | Gate definitions (local + CI) | `Makefile`, `.github/workflows/ci.yml` | SATISFIED |
| QA-01 | Code quality configuration | `pyproject.toml`, `sonar-project.properties` | SATISFIED |
| REL-01 | License & packaging metadata | `LICENSE`, `pyproject.toml` | SATISFIED |
| REL-02 | Release pipeline with provenance | `.github/workflows/release.yml` | SATISFIED |
| SB-01 | Software bill of materials | `dist/sbom.json` | SATISFIED |

## 3. SAR invariant

Every control cited above maps to at least one evidence file (spec invariant I2;
asserted by the test suite). Evidence files are byte-identical copies under
`evidence/`; `manifest.json` records their SHA-256.

## 4. Findings

See `POAM.md` for the plan of action and milestones.
